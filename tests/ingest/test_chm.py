"""Offline tests for CHM corridor extraction (synthetic data only)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

from hatkalkani.ingest import chm

METRIC = "EPSG:32635"


def params() -> chm.ChmParams:
    return chm.ChmParams(
        half_width_m=30.0,
        min_encroach_canopy_m=4.0,
        strike_margin_m=1.0,
        strike_max_distance_m=30.0,
        strike_min_cluster_px=4,
        clearance_band_m={"lv": 1.0, "mv": 3.0, "hv": 5.0},
    )


def test_quadkey_bounds_known_tile() -> None:
    minx, miny, maxx, maxy = chm.quadkey_bounds_3857("1221003102")
    assert minx == pytest.approx(2974317.6446, abs=1e-3)
    assert maxy == pytest.approx(4657155.259, abs=1e-2)
    assert maxx - minx == pytest.approx(chm.WORLD_3857 / 1024)


def test_candidate_quadkeys_roundtrip() -> None:
    qk = "1221003102"
    b = chm.quadkey_bounds_3857(qk)
    inner = box(b[0] + 100, b[1] + 100, b[2] - 100, b[3] - 100)
    assert chm.candidate_quadkeys(inner, 10) == [qk]


def test_segment_corridors_requires_metric_crs() -> None:
    gdf = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 0)])], crs="EPSG:4326")
    with pytest.raises(ValueError):
        chm.segment_corridors(gdf, 30)


def test_segment_corridors_flat_cap_area() -> None:
    gdf = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (100, 0)])], crs=METRIC)
    area = chm.segment_corridors(gdf, 30).iloc[0].area
    assert area == pytest.approx(100 * 60)


def test_segment_stats_basic_and_clusters() -> None:
    h = np.zeros((60, 60), dtype=np.uint8)
    mask = np.ones_like(h, dtype=bool)
    yy, xx = np.indices(h.shape)
    dist = np.abs(yy - 30) + 0.5  # distance to a horizontal line at row 30
    h[28:31, 10:13] = 12  # 9 px tree, close to line -> strike cluster and encroachment
    h[5, 5] = 40  # single far pixel: tall but isolated -> no cluster
    s = chm.segment_chm_stats(h, mask, dist, params(), clearance_m=3.0)
    assert s["chm_n_px"] == 3600
    assert s["chm_max"] == 40
    assert s["chm_p50"] == 0
    assert s["chm_strike_clusters"] == 1
    assert s["chm_encroach_frac"] > 0
    assert s["chm_nan_reason"] == ""


def test_segment_stats_no_coverage_is_nan_with_reason() -> None:
    h = np.full((10, 10), chm.NODATA, dtype=np.uint8)
    s = chm.segment_chm_stats(h, np.ones_like(h, bool), np.zeros((10, 10)), params(), 3.0)
    assert np.isnan(s["chm_p90"])
    assert s["chm_nan_reason"] == "no_chm_coverage"


def test_merge_into_fills_only_empty() -> None:
    dst = np.array([[chm.NODATA, 5]], dtype=np.uint8)
    chm.merge_into(dst, np.array([[9, 9]], dtype=np.uint8), np.array([[True, True]]))
    assert dst.tolist() == [[9, 5]]


def test_extract_and_stats_end_to_end(tmp_path: Path) -> None:
    # Synthetic "tile" in EPSG:3857 around a point in Menderes, UTM 35N segment on top.
    to_utm = Transformer.from_crs("EPSG:4326", METRIC, always_xy=True)
    to_merc = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    ux, uy = to_utm.transform(27.1, 38.25)
    mx, my = to_merc.transform(27.1, 38.25)
    res = 1.2
    n = 400
    tile = tmp_path / "tile.tif"
    arr = np.full((n, n), 12, dtype=np.uint8)
    tr = from_origin(mx - n * res / 2, my + n * res / 2, res, res)
    with rasterio.open(
        tile,
        "w",
        driver="GTiff",
        dtype="uint8",
        count=1,
        width=n,
        height=n,
        crs="EPSG:3857",
        transform=tr,
    ) as d:
        d.write(arr, 1)
    line = LineString([(ux - 100, uy), (ux + 100, uy)])
    segs = gpd.GeoDataFrame(
        {"segment_id": ["a_0001", "b_0001"], "voltage_level": ["mv", "hv"]},
        geometry=[LineString(line.coords[:1] + [(ux, uy)]), LineString([(ux, uy), (ux + 100, uy)])],
        crs=METRIC,
    )
    cors = chm.segment_corridors(segs, 30)
    t, w, h = chm.grid_for(cors.union_all().bounds)
    out = tmp_path / "chm_corridor.tif"
    chm.extract_corridor({"t": str(tile)}, cors, out, t, w, h, METRIC, log=lambda *_: None)
    stats = chm.compute_segment_stats(segs, out, params())
    assert list(stats["segment_id"]) == ["a_0001", "b_0001"]
    assert (stats["chm_p50"] == 12).all()
    assert (stats["chm_valid_frac"] > 0.95).all()
    with rasterio.open(out) as r:
        assert r.crs.to_epsg() == 32635
        assert r.nodata == chm.NODATA


def test_cache_decision_param_change_recomputes_stats_only() -> None:
    p = params()
    key = {"segments_sha256": "a", "half_width_m": 30.0}
    skey = chm.stats_cache_key(p)
    meta = {"cache_key": key, "stats_key": skey}
    assert chm.cache_decision(meta, key, skey, True, True) == "hit"
    # changed clearance band / strike parameter -> stats recomputed, raster kept
    for changed in (
        chm.ChmParams(**{**vars(p), "clearance_band_m": {"lv": 1.0, "mv": 4.0, "hv": 5.0}}),
        chm.ChmParams(**{**vars(p), "strike_margin_m": 2.0}),
        chm.ChmParams(**{**vars(p), "strike_max_distance_m": 40.0}),
        chm.ChmParams(**{**vars(p), "strike_min_cluster_px": 9}),
        chm.ChmParams(**{**vars(p), "min_encroach_canopy_m": 5.0}),
    ):
        assert chm.cache_decision(meta, key, chm.stats_cache_key(changed), True, True) == "stats"
    # legacy meta without stats_key -> recompute stats once
    assert chm.cache_decision({"cache_key": key}, key, skey, True, True) == "stats"
    # raster key mismatch or missing raster -> full re-extraction
    assert chm.cache_decision(meta, {**key, "half_width_m": 40.0}, skey, True, True) == "full"
    assert chm.cache_decision(meta, key, skey, False, True) == "full"
