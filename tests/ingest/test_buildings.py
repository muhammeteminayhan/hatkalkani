"""Offline unit tests for the buildings ingest (synthetic geometry only)."""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, box

from hatkalkani.ingest.buildings import (
    OUT_COLUMNS,
    clip_buildings,
    corridor_buffer,
    count_near_lines,
    parse_osm_buildings,
    summarize,
)

METRIC = "EPSG:32635"


def _gdf(geoms: list, datasets: list[str] | None = None) -> gpd.GeoDataFrame:
    n = len(geoms)
    return gpd.GeoDataFrame(
        {
            "source": ["overture"] * n,
            "source_id": [f"b{i}" for i in range(n)],
            "dataset": datasets or ["OpenStreetMap"] * n,
        },
        geometry=geoms,
        crs="EPSG:4326",
    )


def test_corridor_buffer_grows_by_about_500m() -> None:
    b = box(27.0, 38.0, 27.1, 38.1)
    buf = corridor_buffer(b, METRIC, 500.0)
    assert buf.contains(b)
    # 500 m is ~0.0057 deg of latitude
    assert buf.bounds[3] - 38.1 == pytest.approx(0.0045, abs=0.0015)


def test_clip_keeps_only_buildings_within_area() -> None:
    area = box(27.0, 38.0, 27.1, 38.1)
    inside = box(27.01, 38.01, 27.0101, 38.0101)
    crossing = box(27.099, 38.05, 27.101, 38.051)
    outside = box(27.5, 38.5, 27.5001, 38.5001)
    out = clip_buildings(_gdf([inside, crossing, outside]), area, METRIC)
    assert list(out["source_id"]) == ["b0"]


def test_clip_requires_crs_and_drops_duplicates() -> None:
    area = box(27.0, 38.0, 27.1, 38.1)
    g = box(27.01, 38.01, 27.0101, 38.0101)
    df = _gdf([g, g])
    df["source_id"] = "dup"
    assert len(clip_buildings(df, area, METRIC)) == 1
    with pytest.raises(ValueError):
        clip_buildings(df.set_crs(None, allow_override=True), area, METRIC)


def test_parse_osm_buildings() -> None:
    ring = [
        {"lon": 27.0, "lat": 38.0},
        {"lon": 27.001, "lat": 38.0},
        {"lon": 27.001, "lat": 38.001},
        {"lon": 27.0, "lat": 38.001},
        {"lon": 27.0, "lat": 38.0},
    ]
    data = {
        "elements": [
            {
                "type": "way",
                "id": 7,
                "geometry": ring,
                "tags": {"building": "house", "height": "6"},
            },
            {"type": "way", "id": 8, "geometry": ring[:3], "tags": {"building": "yes"}},
            {"type": "way", "id": 9, "geometry": ring, "tags": {"highway": "road"}},
        ]
    }
    gdf = parse_osm_buildings(data)
    assert len(gdf) == 1
    assert gdf.iloc[0]["source_id"] == "w7"
    assert gdf.iloc[0]["height_m"] == 6.0
    assert set(OUT_COLUMNS) <= set(gdf.columns)


def test_summarize_shares() -> None:
    g = box(27.0, 38.0, 27.001, 38.001)
    s = summarize(_gdf([g, g, g, g], ["A", "A", "A", "B"]))
    assert s["count"] == 4
    assert s["dataset_share"] == {"A": 0.75, "B": 0.25}
    assert summarize(_gdf([]))["count"] == 0


def test_count_near_lines() -> None:
    line = gpd.GeoDataFrame(geometry=[LineString([(27.0, 38.0), (27.1, 38.0)])], crs="EPSG:4326")
    near = box(27.05, 38.001, 27.0501, 38.0011)  # ~110 m north
    far = box(27.05, 38.02, 27.0501, 38.0201)  # ~2.2 km north
    b = _gdf([near, far])
    assert count_near_lines(b, line, METRIC, 300.0) == 1
    assert count_near_lines(b, line, METRIC, 10.0) == 0
    assert count_near_lines(b.iloc[0:0], line, METRIC, 300.0) == 0


def test_license_read_per_record_not_hardcoded() -> None:
    import pandas as pd

    from hatkalkani.ingest.buildings import summarize_licenses

    assert summarize_licenses(pd.Series(["ODbL-1.0", "ODbL-1.0"])) == "ODbL-1.0"
    mixed = summarize_licenses(pd.Series(["ODbL-1.0", "CDLA-Permissive-2.0", None]))
    assert mixed == "CDLA-Permissive-2.0; ODbL-1.0; unknown"
    assert summarize_licenses(pd.Series([], dtype=object)) == "unknown"
    import hatkalkani.ingest.buildings as b

    assert not hasattr(b, "OVERTURE_LICENSE")
