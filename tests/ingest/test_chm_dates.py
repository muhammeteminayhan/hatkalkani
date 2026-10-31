"""Offline tests for per-segment CHM acquisition dates (synthetic footprints)."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, box

from hatkalkani.ingest import chm_dates

METRIC = "EPSG:32635"


def segs() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"segment_id": ["a_0001", "b_0001", "c_0001"]},
        geometry=[
            LineString([(0, 0), (100, 0)]),  # fully in footprint A
            LineString([(100, 0), (200, 0)]),  # half A, half B
            LineString([(1000, 0), (1100, 0)]),  # no footprint
        ],
        crs=METRIC,
    )


def fps() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"date": pd.to_datetime(["2016-07-22", "2020-02-19"])},
        geometry=[box(-50, -100, 150, 100), box(150, -100, 400, 100)],
        crs=METRIC,
    )


def test_clean_footprints_drops_bad_dates() -> None:
    g = gpd.GeoDataFrame(
        {"acq_date": ["2019-01-02", None, "bogus"]},
        geometry=[box(0, 0, 1, 1)] * 3,
        crs="EPSG:4326",
    )
    out = chm_dates.clean_footprints(g)
    assert len(out) == 1 and out["date"].iloc[0] == pd.Timestamp("2019-01-02")


def test_clean_footprints_without_column() -> None:
    g = gpd.GeoDataFrame({"x": [1]}, geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")
    assert chm_dates.clean_footprints(g).empty


def test_segment_dates() -> None:
    df = chm_dates.compute_segment_dates(segs(), fps(), 30.0)
    assert list(df.columns) == chm_dates.COLUMNS
    a, b, c = (df.iloc[i] for i in range(3))
    first = pd.Timestamp("2016-07-22")
    assert a["chm_acq_min"] == a["chm_acq_max"] == a["chm_acq_dominant"] == first
    assert a["chm_acq_year"] == 2016 and a["chm_acq_coverage"] == pytest.approx(1.0)
    assert b["chm_acq_min"] == pd.Timestamp("2016-07-22")
    assert b["chm_acq_max"] == pd.Timestamp("2020-02-19")
    # corridor x in [100,200]: A covers [100,150], B covers [150,200] -> tie -> newer date
    assert b["chm_acq_dominant"] == pd.Timestamp("2020-02-19")
    assert b["chm_acq_coverage"] == pytest.approx(1.0)
    assert pd.isna(c["chm_acq_dominant"]) and c["chm_acq_coverage"] == 0.0
    assert pd.isna(c["chm_acq_year"])


def test_partial_coverage_and_dominant_by_area() -> None:
    s = gpd.GeoDataFrame(
        {"segment_id": ["x"]}, geometry=[LineString([(0, 0), (100, 0)])], crs=METRIC
    )
    f = gpd.GeoDataFrame(
        {"date": pd.to_datetime(["2018-01-01", "2019-01-01"])},
        geometry=[box(0, -30, 25, 30), box(25, -30, 75, 30)],  # 25% / 50%, 25% uncovered
        crs=METRIC,
    )
    r = chm_dates.compute_segment_dates(s, f, 30.0).iloc[0]
    assert r["chm_acq_dominant"] == pd.Timestamp("2019-01-01")
    assert r["chm_acq_coverage"] == pytest.approx(0.75)


def test_crs_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        chm_dates.compute_segment_dates(segs(), fps().to_crs("EPSG:4326"), 30.0)
