"""Shared raster helpers for the F2-2 ingest modules (grid, COG writing, terrain, masking)."""

from __future__ import annotations

import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine, from_origin
from scipy import ndimage

from hatkalkani.ingest.common import ROOT, load_aoi, processed_dir

AOI_BUFFER_M = 1000.0  # AOI + 1 km, per task F2-2
SCL_BAD = (0, 3, 8, 9, 10)  # no-data, cloud shadow, cloud medium/high prob., thin cirrus
TPI_RADIUS_M = 300.0  # neighbourhood radius for the topographic position index
EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"


def interim_dir(aoi_id: str, root: Path = ROOT) -> Path:
    return root / "data" / "interim" / aoi_id


def target_bounds(aoi_id: str, res: float, margin_m: float = 0.0, root: Path = ROOT):
    """AOI bounds + buffer in the metric CRS, snapped outward to multiples of `res`."""
    aoi = load_aoi(aoi_id)
    gdf = gpd.read_parquet(processed_dir(aoi_id, root) / "boundary.parquet")
    if gdf.crs is None:
        raise ValueError("boundary.parquet has no CRS")
    gdf = gdf.to_crs(aoi.metric_crs)
    minx, miny, maxx, maxy = gdf.total_bounds
    b = AOI_BUFFER_M + margin_m
    return (
        math.floor((minx - b) / res) * res,
        math.floor((miny - b) / res) * res,
        math.ceil((maxx + b) / res) * res,
        math.ceil((maxy + b) / res) * res,
    ), aoi.metric_crs


def make_geobox(bounds, crs: str, res: float):
    from odc.geo.geobox import GeoBox
    from odc.geo.xr import xr_coords  # noqa: F401  (ensures odc.geo xarray support is loaded)

    return GeoBox.from_bbox(bounds, crs=crs, resolution=res)


def grid_transform(bounds, res: float) -> Affine:
    return from_origin(bounds[0], bounds[3], res, res)


def write_cog(
    path: Path,
    arr: np.ndarray,
    transform: Affine,
    crs: str,
    nodata: float | int | None,
    resampling: str = "nearest",
) -> Path:
    """Write a single-band array as a tiled, deflate-compressed COG (via a temporary GTiff)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.tif")
    prof = {
        "driver": "GTiff",
        "height": arr.shape[0],
        "width": arr.shape[1],
        "count": 1,
        "dtype": str(arr.dtype),
        "crs": CRS.from_string(crs),
        "transform": transform,
        "nodata": nodata,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
    }
    with rasterio.open(tmp, "w", **prof) as dst:
        dst.write(arr, 1)
    from rasterio.shutil import copy as rio_copy

    rio_copy(
        tmp,
        path,
        driver="COG",
        compress="deflate",
        blocksize=256,
        overview_resampling=resampling,
        predictor="3" if arr.dtype.kind == "f" else "2",
    )
    tmp.unlink()
    return path


# ---------------------------------------------------------------- pure compute
def normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(a - b) / (a + b) as float32; NaN where the denominator is not positive or inputs are NaN."""
    a = a.astype("float32")
    b = b.astype("float32")
    den = a + b
    out = np.full(a.shape, np.nan, dtype="float32")
    ok = np.isfinite(den) & (den > 0)
    out[ok] = (a[ok] - b[ok]) / den[ok]
    return np.clip(out, -1.0, 1.0)


def valid_mask_from_scl(scl: np.ndarray) -> np.ndarray:
    """True where the SCL class is usable (not nodata, shadow, cloud or cirrus)."""
    return ~np.isin(scl, SCL_BAD)


def slope_degrees(dem: np.ndarray, res: float) -> np.ndarray:
    """Slope in degrees from a DEM on a square-pixel metric grid (central differences)."""
    z = dem.astype("float64")
    dzdy, dzdx = np.gradient(z, res)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy))).astype("float32")


def disk_kernel(radius_px: int) -> np.ndarray:
    """Normalised disk kernel with the centre cell removed."""
    r = radius_px
    yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
    k = ((xx**2 + yy**2) <= r * r).astype("float64")
    k[r, r] = 0.0
    return k / k.sum()


def tpi(dem: np.ndarray, res: float, radius_m: float = TPI_RADIUS_M) -> np.ndarray:
    """Topographic Position Index: elevation minus mean elevation within `radius_m` (metres)."""
    r = max(1, int(round(radius_m / res)))
    z = dem.astype("float64")
    mean = ndimage.convolve(z, disk_kernel(r), mode="nearest")
    return (z - mean).astype("float32")
