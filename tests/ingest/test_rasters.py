"""Offline tests for F2-2 raster helpers plus checks on produced interim rasters."""

from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio

from hatkalkani.ingest import common
from hatkalkani.ingest.rasters import (
    normalized_difference,
    slope_degrees,
    tpi,
    valid_mask_from_scl,
    write_cog,
)
from hatkalkani.ingest.worldcover import tile_names

INTERIM = common.ROOT / "data" / "interim" / "izmir_menderes"


def test_normalized_difference_range_and_nan() -> None:
    a = np.array([[0.5, 0.0, np.nan]], dtype="float32")
    b = np.array([[0.1, 0.0, 0.2]], dtype="float32")
    out = normalized_difference(a, b)
    assert out[0, 0] == pytest.approx(0.4 / 0.6, rel=1e-5)
    assert np.isnan(out[0, 1]) and np.isnan(out[0, 2])


def test_scl_mask() -> None:
    scl = np.array([0, 3, 4, 5, 8, 9, 10, 11])
    expected = [False, False, True, True, False, False, False, True]
    assert valid_mask_from_scl(scl).tolist() == expected


def test_slope_of_plane() -> None:
    x = np.arange(20) * 30.0
    dem = np.tile(x, (20, 1)) * 0.5  # 0.5 rise per metre east
    s = slope_degrees(dem, 30.0)
    assert s == pytest.approx(np.degrees(np.arctan(0.5)), abs=1e-4)


def test_tpi_peak_and_flat() -> None:
    dem = np.zeros((41, 41))
    dem[20, 20] = 50.0
    t = tpi(dem, 30.0, radius_m=90.0)
    assert t[20, 20] == pytest.approx(50.0)
    assert tpi(np.full((21, 21), 7.0), 30.0)[10, 10] == pytest.approx(0.0)


def test_worldcover_tile_names() -> None:
    names = tile_names([26.9, 37.9, 27.3, 38.4])
    assert names == [
        "ESA_WorldCover_10m_2021_v200_N36E024_Map.tif",
        "ESA_WorldCover_10m_2021_v200_N36E027_Map.tif",
    ]


def test_write_cog_roundtrip(tmp_path) -> None:
    from rasterio.transform import from_origin

    arr = np.random.default_rng(0).random((300, 300)).astype("float32")
    tr = from_origin(500000, 4200000, 20, 20)
    p = write_cog(tmp_path / "t.tif", arr, tr, "EPSG:32635", np.nan)
    with rasterio.open(p) as r:
        assert r.crs.to_epsg() == 32635 and r.profile["tiled"]
        assert np.allclose(r.read(1), arr)


@pytest.mark.skipif(not (INTERIM / "s2_meta.json").exists(), reason="ingest not run")
def test_produced_rasters() -> None:
    for name in ["s2_ndvi_backtest", "s2_ndmi_backtest", "s2_ndvi_current", "s2_ndmi_current"]:
        with rasterio.open(INTERIM / f"{name}.tif") as r:
            assert r.crs.to_epsg() == 32635
            a = r.read(1)
            assert np.nanmin(a) >= -1 and np.nanmax(a) <= 1
    for name in ["dem", "dem_slope", "dem_tpi", "worldcover"]:
        with rasterio.open(INTERIM / f"{name}.tif") as r:
            assert r.crs.to_epsg() == 32635
    meta = json.loads((INTERIM / "s2_meta.json").read_text(encoding="utf-8"))
    assert all(p["n_scenes"] > 0 for p in meta["periods"].values())


@pytest.mark.network
def test_stac_search_live() -> None:
    from hatkalkani.ingest.sentinel2 import search_items

    assert search_items([27.0, 38.0, 27.1, 38.1], ("2025-05-01", "2025-05-10"))
