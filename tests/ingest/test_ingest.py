"""Offline unit tests for the ingest stage (synthetic geometry only)."""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, box

from hatkalkani.ingest import common
from hatkalkani.ingest.boundary import relation_to_geom
from hatkalkani.ingest.lines import (
    LINE_COLUMNS,
    clip_to_boundary,
    parse_edas,
    parse_osm_lines,
    parse_voltage_v,
    voltage_class,
    voltage_level,
)
from hatkalkani.ingest.segments import build_segments, cut_points

METRIC = "EPSG:32635"


def test_cut_points_exact_multiple() -> None:
    assert cut_points(300.0, 100.0, 50.0) == [0.0, 100.0, 200.0, 300.0]


def test_cut_points_short_tail_merged() -> None:
    assert cut_points(240.0, 100.0, 50.0) == [0.0, 100.0, 240.0]


def test_cut_points_long_tail_kept() -> None:
    assert cut_points(260.0, 100.0, 50.0) == [0.0, 100.0, 200.0, 260.0]


def test_cut_points_shorter_than_one_segment() -> None:
    assert cut_points(30.0, 100.0, 50.0) == [0.0, 30.0]


def test_voltage_parsing_and_classes() -> None:
    assert parse_voltage_v("154000;34500") == 154000
    assert parse_voltage_v("") is None
    assert parse_voltage_v(None) is None
    assert voltage_class(380000) == "ge154kv"
    assert voltage_class(34500) == "kv33_36"
    assert voltage_class(11000) == "diger"
    assert voltage_class(None) == "etiketsiz"
    assert voltage_level(None, "minor_line") == ("mv", "assumed")
    assert voltage_level(None, "line") == ("hv", "assumed")
    assert voltage_level(34500, "line") == ("mv", "tag")


def _osm_payload() -> dict:
    way = {
        "type": "way",
        "id": 42,
        "tags": {"power": "line", "voltage": "154000"},
        "geometry": [{"lat": 38.0, "lon": 27.0}, {"lat": 38.0, "lon": 27.02}],
    }
    cable = {**way, "id": 43, "tags": {"power": "cable"}}
    return {"elements": [way, cable]}


def test_parse_osm_lines_schema_and_cable_excluded() -> None:
    g = parse_osm_lines(_osm_payload())
    assert len(g) == 1
    row = g.iloc[0]
    assert row.source == "osm" and row.line_id == "42" and row.voltage_kv == 154.0
    assert row.voltage_class == "ge154kv"


def test_clip_and_segment_lengths_match() -> None:
    lines = parse_osm_lines(_osm_payload())
    # boundary clips off the eastern part of the line
    boundary = box(26.99, 37.99, 27.012, 38.01)
    clipped = clip_to_boundary(lines, boundary, METRIC)
    assert 0 < clipped.length_m.iloc[0] < 1800
    segs = build_segments(clipped, METRIC, 100.0, 50.0)
    assert abs(segs.length_m.sum() - clipped.length_m.sum()) <= 1.0
    assert segs.segment_id.is_unique
    assert segs.segment_id.iloc[0] == "42_0001"
    assert (segs.length_m >= 50 - 1e-6).all() and (segs.length_m < 150).all()
    assert list(segs.seq) == list(range(1, len(segs) + 1))
    assert set(LINE_COLUMNS) <= set(clipped.columns)


def test_edas_mapping_kv_and_crs_required() -> None:
    raw = gpd.GeoDataFrame(
        {"HAT_ID": [7, 8], "GERILIM": [34.5, 154.0]},
        geometry=[LineString([(27.0, 38.0), (27.01, 38.0)])] * 2,
        crs="EPSG:4326",
    )
    g = parse_edas(raw)
    assert list(g.source) == ["edas", "edas"]
    assert list(g.power) == ["minor_line", "line"]
    assert list(g.voltage_class) == ["kv33_36", "ge154kv"]
    assert g.line_id.iloc[0] == "edas_7"
    with pytest.raises(ValueError):
        parse_edas(raw.set_crs(None, allow_override=True))


def test_relation_to_geom_square() -> None:
    def way(pts: list[tuple[float, float]]) -> dict:
        return {
            "type": "way",
            "role": "outer",
            "geometry": [{"lon": x, "lat": y} for x, y in pts],
        }

    rel = {"members": [way([(0, 0), (1, 0), (1, 1)]), way([(1, 1), (0, 1), (0, 0)])]}
    geom = relation_to_geom(rel)
    assert geom is not None and abs(geom.area - 1.0) < 1e-9


def test_manifest_cache_roundtrip(tmp_path) -> None:
    f = tmp_path / "data" / "raw" / "x" / "a.json"
    f.parent.mkdir(parents=True)
    f.write_text("{}", encoding="utf-8")
    assert not common.is_cached(f, tmp_path)
    common.register(f, "t", "http://example", "lic", tmp_path)
    assert common.is_cached(f, tmp_path)
    f.write_text("{ }", encoding="utf-8")
    assert not common.is_cached(f, tmp_path)


@pytest.mark.network
def test_overpass_boundary_menderes(tmp_path) -> None:
    from hatkalkani.ingest.boundary import boundary_query

    p = common.fetch_overpass(
        boundary_query("İzmir", "Menderes"),
        tmp_path / "data" / "raw" / "b.json",
        "t",
        root=tmp_path,
    )
    assert p.exists()
