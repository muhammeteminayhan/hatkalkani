"""Work packages: merging consecutive kritik/yuksek segments into spans (spec section 4)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from pyproj import Transformer
from shapely.geometry import LineString

from hatkalkani.model.workorders import WORKORDER_COLUMNS, build_workorders

METRIC = "EPSG:32635"
TO_LL = Transformer.from_crs(METRIC, "EPSG:4326", always_xy=True)
LABELS = {"enc": {"tr": "Ağaç", "en": "Trees"}, "wui": {"tr": "Yerleşim", "en": "Buildings"}}


def _segments() -> gpd.GeoDataFrame:
    """Line A: 6 x 100 m along x; line B: 4 x 100 m with a 40 m gap after seq 2."""
    rows = []
    a_tiers = ["kritik", "yuksek", "orta", "kritik", "kritik", "dusuk"]
    a_risk = [80.0, 70.0, 40.0, 75.0, 90.0, 10.0]
    a_strike = [2, 1, 0, 0, 3, 9]
    for i in range(6):
        x0 = 500000 + 100 * i
        rows.append(("A", i + 1, a_tiers[i], a_risk[i], a_strike[i], 100.0,
                     LineString([(x0, 4200000), (x0 + 100, 4200000)])))
    b_x = [500000, 500100, 500240, 500340]  # gap of 40 m between seq 2 and 3
    for i, x0 in enumerate(b_x):
        rows.append(("B", i + 1, "yuksek", 90.0 if i < 2 else 60.0, 1, 100.0,
                     LineString([(x0, 4201000), (x0 + 100, 4201000)])))
    gdf = gpd.GeoDataFrame(
        rows, columns=["line_id", "seq", "tier", "risk", "strike_trees", "length_m", "geometry"],
        crs=METRIC)
    gdf["segment_id"] = [f"{r.line_id}_{r.seq:04d}" for r in gdf.itertuples()]
    gdf["voltage_class"] = "ge154kv"
    gdf["voltage_level"] = "hv"
    gdf["voltage_kv"] = 154.0
    gdf["aux_strike_tall_clusters"] = gdf["strike_trees"] // 2
    # contributions: line A seq 4-5 driven by buildings, everything else by trees
    gdf["contrib_enc"] = np.where((gdf.line_id == "A") & gdf.seq.isin([4, 5]), 1.0, 8.0)
    gdf["contrib_wui"] = np.where((gdf.line_id == "A") & gdf.seq.isin([4, 5]), 6.0, -2.0)
    gdf["as_of"] = "2025-05-31"
    return gdf.to_crs("EPSG:4326")


def test_spans_merge_only_consecutive_contiguous_segments_of_one_line():
    wo = build_workorders(_segments(), labels=LABELS, metric_crs=METRIC)
    spans = {r.span_id: r for r in wo.itertuples()}
    assert set(spans) == {"A_0001-0002", "A_0004-0005", "B_0001-0002", "B_0003-0004"}
    assert spans["A_0001-0002"].segment_ids == "A_0001;A_0002"
    assert spans["A_0004-0005"].n_segments == 2
    assert spans["A_0004-0005"].tier_max == "kritik"
    assert spans["B_0003-0004"].tier_max == "yuksek"


def test_span_fields_and_values():
    wo = build_workorders(_segments(), labels=LABELS, metric_crs=METRIC)
    assert list(wo.columns) == [*WORKORDER_COLUMNS, "geometry"]
    assert wo.crs.to_epsg() == 4326
    s = wo.set_index("span_id").loc["A_0004-0005"]
    assert s.length_m == pytest.approx(200.0)
    assert s.risk_max == pytest.approx(90.0)
    assert s.risk_mean == pytest.approx(82.5)  # length-weighted (equal lengths here)
    assert s.strike_tree_count == 3 and s.strike_tall_count == 1
    assert s.main_reason_key == "wui" and s.main_reason_tr == "Yerleşim"
    assert s.main_reason_en == "Buildings"
    lon0, lat0 = TO_LL.transform(500300, 4200000)
    lon1, lat1 = TO_LL.transform(500500, 4200000)
    assert (s.start_lon, s.start_lat) == pytest.approx((lon0, lat0), abs=1e-6)
    assert (s.end_lon, s.end_lat) == pytest.approx((lon1, lat1), abs=1e-6)
    mlon, mlat = TO_LL.transform(500400, 4200000)  # midpoint along the span
    assert s.map_url == f"https://www.google.com/maps?q={mlat:.6f},{mlon:.6f}"
    assert s.geometry.length > 0 and s.geometry.geom_type == "LineString"


def test_sorting_by_max_risk_then_strike_count():
    wo = build_workorders(_segments(), labels=LABELS, metric_crs=METRIC)
    # B_0001-0002 and A_0004-0005 both have risk_max 90; B has 2 strike, A has 3
    assert wo["span_id"].tolist()[:2] == ["A_0004-0005", "B_0001-0002"]
    assert wo["priority"].tolist() == list(range(1, len(wo) + 1))
    assert wo["risk_max"].is_monotonic_decreasing


def test_no_work_tiers_gives_empty_table_with_schema():
    segs = _segments()
    segs["tier"] = "orta"
    wo = build_workorders(segs, labels=LABELS, metric_crs=METRIC)
    assert len(wo) == 0 and list(wo.columns) == [*WORKORDER_COLUMNS, "geometry"]


def test_missing_crs_is_rejected():
    s = _segments()
    segs = gpd.GeoDataFrame(s.drop(columns="geometry"), geometry=list(s.geometry))  # no CRS
    with pytest.raises(ValueError, match="CRS"):
        build_workorders(segs, labels=LABELS, metric_crs=METRIC)
