"""Windowed raster access for per-segment statistics, plus runtime raster validation.

Rasters are never read whole: every statistic reads only the window around one geometry
(or block windows for AOI-wide references), so memory stays bounded for any AOI size.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import rasterio
import shapely
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import Affine, array_bounds
from rasterio.warp import reproject
from rasterio.windows import Window, from_bounds
from shapely.geometry.base import BaseGeometry

from hatkalkani.ingest import chm as chm_ingest

CHM_DTYPE = "uint8"
CHM_NODATA = chm_ingest.NODATA  # 255 = outside corridor / no data (ingest convention)
# Plausibility ceiling for canopy heights in metres. The tallest trees on Earth are ~115 m
# and Mediterranean canopies stay far below; larger values mean a unit or scaling error
# (e.g. decimetres stored in uint8 would put a 15 m pine at 150).
CHM_MAX_PLAUSIBLE_M = 100.0


class RasterValidationError(ValueError):
    """Raster does not match the expected CRS, dtype, nodata, scaling or value range."""


def check_crs(src: rasterio.DatasetReader, expected: str, name: str) -> None:
    if src.crs is None:
        raise RasterValidationError(f"{name}: raster has no CRS; refusing to guess")
    if CRS.from_user_input(src.crs) != CRS.from_user_input(expected):
        raise RasterValidationError(f"{name}: CRS {src.crs} differs from {expected}")


def bounds_window(
    src: rasterio.DatasetReader, bounds: tuple[float, float, float, float], pad: int = 1
) -> Window | None:
    """Integer window covering `bounds` (+pad pixels), clipped to the raster; None if outside."""
    win = from_bounds(*bounds, transform=src.transform)
    c0 = max(math.floor(win.col_off) - pad, 0)
    r0 = max(math.floor(win.row_off) - pad, 0)
    c1 = min(math.ceil(win.col_off + win.width) + pad, src.width)
    r1 = min(math.ceil(win.row_off + win.height) + pad, src.height)
    if c1 <= c0 or r1 <= r0:
        return None
    return Window(c0, r0, c1 - c0, r1 - r0)


def valid_mask(data: np.ndarray, nodata: float | int | None) -> np.ndarray:
    ok = np.ones(data.shape, dtype=bool)
    if data.dtype.kind == "f":
        ok &= np.isfinite(data)
    if nodata is not None and not (isinstance(nodata, float) and math.isnan(nodata)):
        ok &= data != nodata
    return ok


@dataclass(frozen=True)
class Zone:
    """Window of one raster around one geometry."""

    data: np.ndarray
    inside: np.ndarray  # pixel centre inside the geometry (all touched pixels for lines)
    valid: np.ndarray  # inside and not nodata / NaN
    transform: Affine

    def values(self) -> np.ndarray:
        return self.data[self.valid]


def read_zone(
    src: rasterio.DatasetReader, geom: BaseGeometry, *, pad: int = 1, all_touched: bool = False
) -> Zone | None:
    win = bounds_window(src, geom.bounds, pad)
    if win is None:
        return None
    data = src.read(1, window=win)
    tr = src.window_transform(win)
    inside = rasterize(
        [(geom, 1)], out_shape=data.shape, transform=tr, fill=0, dtype="uint8",
        all_touched=all_touched,
    ).astype(bool)
    return Zone(data, inside, inside & valid_mask(data, src.nodata), tr)


def pixel_distance(geom: BaseGeometry, shape: tuple[int, int], transform: Affine) -> np.ndarray:
    """Horizontal distance (CRS units) from each pixel centre to `geom`."""
    rows, cols = np.indices(shape)
    xs, ys = transform @ (cols.ravel() + 0.5, rows.ravel() + 0.5)
    return shapely.distance(geom, shapely.points(xs, ys)).reshape(shape)


def water_fraction(
    wc_src: rasterio.DatasetReader,
    shape: tuple[int, int],
    transform: Affine,
    crs: Any,
    water_class: int,
) -> np.ndarray:
    """Share of each destination pixel covered by `water_class` (average resampling)."""
    out = np.zeros(shape, dtype="float32")
    win = bounds_window(wc_src, array_bounds(shape[0], shape[1], transform), pad=2)
    if win is None:
        return out
    indicator = (wc_src.read(1, window=win) == water_class).astype("float32")
    reproject(
        source=indicator,
        destination=out,
        src_transform=wc_src.window_transform(win),
        src_crs=wc_src.crs,
        dst_transform=transform,
        dst_crs=crs,
        resampling=Resampling.average,
    )
    return out


def _intersect(a: Window, b: Window) -> Window | None:
    c0, r0 = max(a.col_off, b.col_off), max(a.row_off, b.row_off)
    c1 = min(a.col_off + a.width, b.col_off + b.width)
    r1 = min(a.row_off + a.height, b.row_off + b.height)
    if c1 <= c0 or r1 <= r0:
        return None
    return Window(c0, r0, c1 - c0, r1 - r0)


def values_in_polygon(src: rasterio.DatasetReader, polygon: BaseGeometry) -> np.ndarray:
    """Valid values of all pixels whose centre lies in `polygon`, read block by block."""
    outer = bounds_window(src, polygon.bounds, pad=0)
    if outer is None:
        return np.empty(0)
    parts = []
    for _, block in src.block_windows(1):
        w = _intersect(block, outer)
        if w is None:
            continue
        data = src.read(1, window=w)
        inside = rasterize(
            [(polygon, 1)], out_shape=data.shape, transform=src.window_transform(w),
            fill=0, dtype="uint8",
        ).astype(bool)
        m = inside & valid_mask(data, src.nodata)
        if m.any():
            parts.append(data[m].astype("float64"))
    return np.concatenate(parts) if parts else np.empty(0)


# ------------------------------------------------------------- CHM checks
def validate_chm_profile(src: rasterio.DatasetReader, metric_crs: str) -> dict[str, Any]:
    """Fail fast unless the corridor CHM is single-band uint8 metres with nodata 255,
    unit scale, zero offset, square pixels and the metric CRS (REV-F2 O1)."""
    problems = []
    if src.count != 1:
        problems.append(f"band count {src.count} != 1")
    if src.dtypes[0] != CHM_DTYPE:
        problems.append(f"dtype {src.dtypes[0]} != {CHM_DTYPE}")
    if src.nodata is None or float(src.nodata) != float(CHM_NODATA):
        problems.append(f"nodata {src.nodata} != {CHM_NODATA}")
    if tuple(float(s) for s in src.scales) != (1.0,):
        problems.append(f"scale {src.scales} != (1.0,)")
    if tuple(float(o) for o in src.offsets) != (0.0,):
        problems.append(f"offset {src.offsets} != (0.0,)")
    rx, ry = (abs(float(r)) for r in src.res)
    if not math.isclose(rx, ry, rel_tol=1e-9):
        problems.append(f"non-square pixels {src.res}")
    if src.crs is None or CRS.from_user_input(src.crs) != CRS.from_user_input(metric_crs):
        problems.append(f"CRS {src.crs} != {metric_crs}")
    if problems:
        raise RasterValidationError("chm_corridor.tif: " + "; ".join(problems))
    return {
        "dtype": src.dtypes[0],
        "nodata": int(src.nodata),
        "scale": 1.0,
        "offset": 0.0,
        "res_m": rx,
        "crs": src.crs.to_string(),
        "units": [u or "" for u in src.units],
        "max_plausible_m": CHM_MAX_PLAUSIBLE_M,
    }


def check_chm_values(values: np.ndarray, where: str) -> None:
    """Valid canopy heights must lie in [0, CHM_MAX_PLAUSIBLE_M]."""
    if values.size == 0:
        return
    vmin, vmax = float(values.min()), float(values.max())
    if vmin < 0 or vmax > CHM_MAX_PLAUSIBLE_M:
        raise RasterValidationError(
            f"{where}: canopy height range [{vmin}, {vmax}] m is outside the plausible "
            f"[0, {CHM_MAX_PLAUSIBLE_M}] m; check units/scaling of chm_corridor.tif"
        )
