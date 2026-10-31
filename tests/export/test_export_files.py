"""Export writers: CSV (UTF-8 BOM), RFC 7946 GeoJSON and GeoPackage, always EPSG:4326."""

from __future__ import annotations

import csv
import io
import json

import geopandas as gpd
import pandas as pd
import pyogrio
import pytest
from shapely.geometry import LineString

from hatkalkani.export import ensure_wgs84, write_csv, write_geojson, write_gpkg

METRIC = "EPSG:32635"


def _frame() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "span_id": ["A_0001-0002", "B_0003-0003"],
            "main_reason_tr": ["Hatta yakın yüksek ağaç", "Yerleşime yakınlık (çğıöşü)"],
            "risk_max": [81.25, 60.0],
            "map_url": ["https://www.google.com/maps?q=38.1,27.1",
                        "https://www.google.com/maps?q=38.2,27.2"],
            "top_factors": [[{"key": "a", "contribution": 1.5}], []],
        },
        geometry=[LineString([(500000, 4220000), (500200, 4220000)]),
                  LineString([(500000, 4221000), (500100, 4221050)])],
        crs=METRIC,
    )


def test_ensure_wgs84_converts_and_rejects_missing_crs():
    g = ensure_wgs84(_frame())
    assert g.crs.to_epsg() == 4326
    x, y = g.geometry.iloc[0].coords[0]
    assert 26 < x < 28 and 37 < y < 39  # lon/lat order
    with pytest.raises(ValueError, match="CRS"):
        ensure_wgs84(gpd.GeoDataFrame({"a": [1]}, geometry=[LineString([(0, 0), (1, 1)])]))


def test_csv_has_bom_turkish_text_and_quoted_urls(tmp_path):
    p = write_csv(_frame().drop(columns="top_factors"), tmp_path / "w.csv")
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["span_id"] for r in rows] == ["A_0001-0002", "B_0003-0003"]
    assert rows[1]["main_reason_tr"] == "Yerleşime yakınlık (çğıöşü)"
    assert rows[0]["map_url"].endswith("q=38.1,27.1")  # comma inside a quoted field
    assert "geometry" not in rows[0]
    assert b"\r\n" in raw  # fixed line ending on every platform


def test_geojson_is_rfc7946_with_nested_properties(tmp_path):
    p = write_geojson(_frame(), tmp_path / "w.geojson", precision=6)
    gj = json.loads(p.read_text(encoding="utf-8"))
    assert gj["type"] == "FeatureCollection" and "crs" not in gj
    f0 = gj["features"][0]
    assert f0["type"] == "Feature" and f0["geometry"]["type"] == "LineString"
    assert f0["properties"]["top_factors"] == [{"key": "a", "contribution": 1.5}]
    assert f0["properties"]["main_reason_tr"] == "Hatta yakın yüksek ağaç"
    for lon, lat in f0["geometry"]["coordinates"]:
        assert 26 < lon < 28 and 37 < lat < 39
        assert round(lon, 6) == lon and round(lat, 6) == lat
    back = gpd.read_file(p)
    assert back.crs.to_epsg() == 4326 and len(back) == 2


def test_gpkg_roundtrip_in_wgs84(tmp_path):
    p = write_gpkg(_frame().drop(columns="top_factors"), tmp_path / "w.gpkg", layer="workorders")
    info = pyogrio.read_info(p, layer="workorders")
    assert "4326" in str(info["crs"]) and info["features"] == 2
    back = gpd.read_file(p, layer="workorders")
    assert back["main_reason_tr"].tolist() == _frame()["main_reason_tr"].tolist()
    pd.testing.assert_series_equal(back["risk_max"], _frame()["risk_max"], check_names=False)
    # rewriting replaces the file instead of appending a second layer copy
    write_gpkg(_frame().drop(columns="top_factors"), p, layer="workorders")
    assert pyogrio.read_info(p, layer="workorders")["features"] == 2
