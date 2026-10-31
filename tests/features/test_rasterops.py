"""Windowed raster helpers and the runtime CHM validation (REV-F2 O1)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

from hatkalkani.features.rasterops import (
    RasterValidationError,
    bounds_window,
    check_chm_values,
    check_crs,
    pixel_distance,
    read_zone,
    validate_chm_profile,
    values_in_polygon,
    water_fraction,
)

METRIC = "EPSG:32635"


def _tif(path: Path, arr: np.ndarray, res: float = 1.0, nodata=255, crs=METRIC,
         x0: float = 0.0, y1: float = 100.0, **extra) -> Path:
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0],
                       count=1, dtype=str(arr.dtype), crs=crs,
                       transform=from_origin(x0, y1, res, res), nodata=nodata, **extra) as d:
        d.write(arr, 1)
    return path


def test_validate_chm_profile_accepts_ingest_format(tmp_path):
    p = _tif(tmp_path / "c.tif", np.zeros((100, 100), dtype="uint8"))
    with rasterio.open(p) as src:
        prof = validate_chm_profile(src, METRIC)
    assert prof["dtype"] == "uint8" and prof["nodata"] == 255 and prof["res_m"] == 1.0


@pytest.mark.parametrize(
    "arr, kwargs, msg",
    [
        (np.zeros((10, 10), dtype="uint16"), {}, "dtype"),
        (np.zeros((10, 10), dtype="uint8"), {"nodata": 0}, "nodata"),
        (np.zeros((10, 10), dtype="uint8"), {"crs": "EPSG:4326"}, "CRS"),
    ],
)
def test_validate_chm_profile_rejects(tmp_path, arr, kwargs, msg):
    p = _tif(tmp_path / "c.tif", arr, **kwargs)
    with rasterio.open(p) as src, pytest.raises(RasterValidationError, match=msg):
        validate_chm_profile(src, METRIC)


def test_validate_chm_profile_rejects_scaled_band(tmp_path):
    p = _tif(tmp_path / "c.tif", np.zeros((10, 10), dtype="uint8"))
    with rasterio.open(p, "r+") as dst:
        dst.scales = (0.1,)
    with rasterio.open(p) as src, pytest.raises(RasterValidationError, match="scale"):
        validate_chm_profile(src, METRIC)


def test_check_chm_values_range():
    check_chm_values(np.array([0, 12, 37], dtype="uint8"), "ok")
    check_chm_values(np.array([], dtype="uint8"), "empty")
    with pytest.raises(RasterValidationError, match="plausible"):
        check_chm_values(np.array([5, 150], dtype="uint8"), "decimetres?")


def test_check_crs(tmp_path):
    p = _tif(tmp_path / "c.tif", np.zeros((5, 5), dtype="uint8"), crs="EPSG:32636")
    with rasterio.open(p) as src, pytest.raises(RasterValidationError):
        check_crs(src, METRIC, "c.tif")


def test_read_zone_and_distance(tmp_path):
    arr = np.arange(100 * 100, dtype="float32").reshape(100, 100)
    arr[0, 0] = np.nan
    p = _tif(tmp_path / "f.tif", arr, nodata=float("nan"))
    poly = box(10, 10, 20, 30)  # 10 x 20 pixels whose centres are inside
    with rasterio.open(p) as src:
        z = read_zone(src, poly)
        assert int(z.inside.sum()) == 200 and int(z.valid.sum()) == 200
        assert bounds_window(src, (500, 500, 600, 600)) is None
        line = LineString([(10, 50), (60, 50)])
        zl = read_zone(src, line, all_touched=True)
        d = pixel_distance(line, zl.data.shape, zl.transform)
    assert d.min() == pytest.approx(0.5)


def test_water_fraction_average_on_aligned_grid(tmp_path):
    wc = np.full((20, 20), 30, dtype="uint8")
    wc[0:2, 0:2] = 80  # one full 2x2 block -> coarse pixel (0, 0) is all water
    wc[2, 2] = 80  # one of four fine pixels of coarse pixel (1, 1)
    p = _tif(tmp_path / "wc.tif", wc, res=10.0, nodata=0, x0=0, y1=200)
    with rasterio.open(p) as src:
        frac = water_fraction(src, (10, 10), from_origin(0, 200, 20, 20), src.crs, 80)
    assert frac[0, 0] == pytest.approx(1.0)
    assert frac[1, 1] == pytest.approx(0.25)
    assert frac[0, 1] == 0.0 and frac[1, 0] == 0.0 and frac[5, 5] == 0.0


def test_values_in_polygon_matches_full_read(tmp_path):
    arr = np.random.default_rng(0).normal(size=(300, 300)).astype("float32")
    p = _tif(tmp_path / "t.tif", arr, res=10.0, nodata=-9999.0, x0=0, y1=3000,
             tiled=True, blockxsize=64, blockysize=64)
    poly = box(500, 700, 2100, 2400).buffer(150)
    with rasterio.open(p) as src:
        got = np.sort(values_in_polygon(src, poly))
        z = read_zone(src, poly, pad=0)
    assert np.array_equal(got, np.sort(z.values().astype("float64")))
