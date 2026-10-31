"""Preventive de-energisation scenario (risk-model-spec section 6, ADR-012).

Pure core on hand-made arrays (expected values written out below), then the cached
``compute_scenario`` end to end on the synthetic AOI with an independent brute-force
check of every number, the API contract shape, error types, timing and the CLI.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
import yaml
from shapely.geometry import box
from synth import AOI, METRIC, SEGMENTS, WIND_CELLS

from hatkalkani.model import scenario as scn
from hatkalkani.model.config import TIERS

API_PROPS = {"segment_id", "line_id", "voltage_class", "risk", "tier", "p_ignition",
             "consequence", "top_factors"}
SCEN_DAY = "2025-06-28"


# ------------------------------------------------------------------ pure core
def _core(gust, tiers, thr=50.0, min_tier="yuksek"):
    #            line A: 3 x 100 m      line B: 2 x 50 m
    line_idx = np.array([0, 0, 0, 1, 1])
    length = np.array([100.0, 100.0, 100.0, 50.0, 50.0])
    risk = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    rank = np.array([TIERS.index(t) for t in tiers])
    # building b0 near seg 0, b1 near segs 2 and 3, b2 near seg 4
    pairs_seg = np.array([0, 2, 3, 4])
    pairs_bld = np.array([0, 1, 1, 2])
    return scn.evaluate_scenario(np.asarray(gust, dtype=float), rank, risk, length, line_idx,
                                 pairs_seg, pairs_bld, n_lines=2, gust_kmh=thr,
                                 min_tier=min_tier)


def test_core_cuts_whole_way_of_a_candidate_segment():
    r = _core([60, 40, 40, 40, 40], ["yuksek", "kritik", "dusuk", "kritik", "orta"])
    # only seg 0 is windy AND >= yuksek -> line A (3 segments) is cut, line B is not
    assert r.candidate.tolist() == [True, False, False, False, False]
    assert r.cut_line.tolist() == [True, False]
    assert r.targeted.tolist() == [True, True, True, False, False]
    assert r.district_km == pytest.approx(0.4)
    assert r.targeted_km == pytest.approx(0.3)
    assert (r.district_buildings, r.targeted_buildings) == (3, 2)  # b0, b1
    # length-weighted risk: A = 10+20+30 = 60 (x100 m), B = (40+50) x 50 m = 45 (x100 m)
    assert r.risk_covered_ratio == pytest.approx(6000 / 10500)
    # sensitivity: only the candidate segment itself is switched off
    assert r.segment_unit_km == pytest.approx(0.1)
    assert r.segment_unit_buildings == 1
    assert r.segment_unit_risk_ratio == pytest.approx(1000 / 10500)


def test_core_gust_must_exceed_threshold_strictly_and_tier_is_inclusive():
    tiers = ["yuksek", "yuksek", "orta", "kritik", "dusuk"]
    r = _core([50.0, 50.01, 80, 80, 80], tiers)
    assert r.candidate.tolist() == [False, True, False, True, False]
    assert r.cut_line.tolist() == [True, True]
    r = _core([80] * 5, tiers, min_tier="dusuk")
    assert r.candidate.all() and r.risk_covered_ratio == pytest.approx(1.0)
    r = _core([80] * 5, tiers, min_tier="kritik")
    assert r.candidate.tolist() == [False, False, False, True, False]


def test_core_nan_gust_is_never_a_candidate_and_empty_cut_is_zero():
    r = _core([np.nan] * 5, ["kritik"] * 5)
    assert not r.candidate.any() and not r.targeted.any()
    assert (r.targeted_km, r.targeted_buildings, r.risk_covered_ratio) == (0.0, 0, 0.0)


def test_as_of_before_is_strict():
    as_ofs = ["2025-05-31", "2026-10-30"]
    assert scn.as_of_before(date(2025, 6, 29), as_ofs) == "2025-05-31"
    assert scn.as_of_before(date(2026, 10, 30), as_ofs) == "2025-05-31"  # same day: no
    assert scn.as_of_before(date(2026, 10, 31), as_ofs) == "2026-10-30"
    with pytest.raises(ValueError, match="before"):
        scn.as_of_before(date(2025, 5, 31), as_ofs)


def test_daily_max_uses_local_calendar_day_and_converts_to_kmh():
    rows = []
    for pid, (lat, lon) in {"a": (38.1, 27.1), "a2": (38.1, 27.1), "b": (38.2, 27.2)}.items():
        for h in range(-2, 26):  # 22:00 local the day before .. 01:00 the day after
            t = pd.Timestamp("2025-06-28") + pd.Timedelta(hours=h)
            g = 10.0 if pid.startswith("a") else 20.0
            if pid == "a" and h == 23:
                g = 15.0  # 23:00 local on the 28th: same local day
            if pid == "a" and h == 24:
                g = 99.0  # 00:00 local on the 29th = 21:00 UTC on the 28th
            rows.append((pid, lat, lon, t, g))
    w = pd.DataFrame(rows, columns=["point_id", "lat", "lon", "time_local", "wind_gust_10m_ms"])
    w["time_utc"] = w["time_local"].dt.tz_localize("Europe/Istanbul").dt.tz_convert("UTC")
    cells, days, kmh, hours = scn.daily_max_gust_kmh(w)
    assert len(cells) == 2  # a and a2 are one Open-Meteo cell (ADR-009 D5)
    row = days.index(date(2025, 6, 28))
    a = cells.index[cells["label"] == "a"][0]
    b = cells.index[cells["label"] == "b"][0]
    assert kmh[row, a] == pytest.approx(15.0 * 3.6)
    assert kmh[row, b] == pytest.approx(20.0 * 3.6)
    assert hours[row, a] == 24 and hours[row, b] == 24
    assert kmh[days.index(date(2025, 6, 29)), a] == pytest.approx(99.0 * 3.6)


# ------------------------------------------------------------- end to end (syn)
BUILDINGS = {  # centre -> (near line 1001, near line 2002); no case close to 300 m
    (510150, 4219900): (True, False),
    (510100, 4220600): (False, True),
    (510250, 4220200): (True, True),
    (511000, 4222000): (False, False),
    (509500, 4219800): (False, False),
}
GUST_MS = {"g00": 10.0, "g01": 20.0, "g02": 10.0}  # 36 / 72 km/h on SCEN_DAY


def _write_inputs(syn) -> None:
    gpd.GeoDataFrame(
        {"source": "overture", "source_id": [f"b{i}" for i in range(len(BUILDINGS))]},
        geometry=[box(x - 5, y - 5, x + 5, y + 5) for x, y in BUILDINGS], crs=METRIC,
    ).to_crs("EPSG:4326").to_parquet(syn.interim / "buildings.parquet")
    w = pd.read_parquet(syn.interim / "wind_hourly.parquet")
    day = w["time_local"].dt.date == date.fromisoformat(SCEN_DAY)
    w.loc[day, "wind_gust_10m_ms"] = w.loc[day, "point_id"].map(GUST_MS)
    w.to_parquet(syn.interim / "wind_hourly.parquet", index=False)


def _build_risk(syn) -> None:
    from hatkalkani.features.build import main as features_main
    from hatkalkani.model.run import main as model_main

    dates = ["2025-05-31", "2026-10-30"]
    assert features_main(["--aoi", AOI, "--as-of", *dates, "--root", str(syn.root)]) == 0
    assert model_main(["--aoi", AOI, "--as-of", *dates, "--root", str(syn.root)]) == 0


@pytest.fixture
def scen(syn):
    _write_inputs(syn)
    _build_risk(syn)
    scn.clear_cache()
    yield syn
    scn.clear_cache()


def _nearest_cell(sid: str) -> str:
    _, _, x0, x1, y = SEGMENTS[sid]
    mx = (x0 + x1) / 2
    d = {pid: np.hypot(mx - cx, y - cy) for pid, (cx, cy) in WIND_CELLS.items()}
    return min(sorted(d), key=d.get)


def _brute_force(syn, thr: float, min_tier: str) -> dict:
    """Independent re-computation from the risk file, shapely distances and SEGMENTS."""
    from hatkalkani.model.run import read_risk

    risk, _ = read_risk(syn.processed / "risk_2025-05-31.parquet")
    risk = risk.set_index("segment_id")
    gust = {sid: GUST_MS[_nearest_cell(sid)] * 3.6 for sid in SEGMENTS}
    ok = TIERS[: TIERS.index(min_tier) + 1]
    cand = [s for s in SEGMENTS if gust[s] > thr and risk.loc[s, "tier"] in ok]
    lines = sorted({SEGMENTS[s][0] for s in cand})
    tsegs = [s for s in SEGMENTS if SEGMENTS[s][0] in lines]
    bpts = gpd.read_parquet(syn.interim / "buildings.parquet").to_crs(METRIC)
    bpts = bpts.geometry.representative_point()

    def near(segs: list[str]) -> int:
        geoms = [shapely.LineString([(SEGMENTS[s][2], SEGMENTS[s][4]),
                                     (SEGMENTS[s][3], SEGMENTS[s][4])]) for s in segs]
        if not geoms:
            return 0
        u = shapely.union_all(geoms)
        return int(sum(p.distance(u) <= 300.0 for p in bpts))

    lw = {s: risk.loc[s, "risk"] * risk.loc[s, "length_m"] for s in SEGMENTS}
    return {
        "lines": lines, "segs": tsegs, "cand": cand, "gust": gust,
        "km_all": sum(risk.loc[s, "length_m"] for s in SEGMENTS) / 1000,
        "km_t": sum(risk.loc[s, "length_m"] for s in tsegs) / 1000,
        "b_all": near(list(SEGMENTS)), "b_t": near(tsegs),
        "ratio": sum(lw[s] for s in tsegs) / sum(lw.values()),
    }


@pytest.mark.parametrize("thr,min_tier", [(50.0, "orta"), (50.0, "dusuk"), (30.0, "dusuk"),
                                          (71.9, "dusuk"), (72.0, "dusuk"), (50.0, "kritik")])
def test_compute_scenario_matches_brute_force(scen, thr, min_tier):
    out = scn.compute_scenario(AOI, SCEN_DAY, thr, min_tier, root=scen.root)
    exp = _brute_force(scen, thr, min_tier)
    assert out["inputs"] == {"gust_kmh": thr, "min_tier": min_tier, "as_of_used": "2025-05-31"}
    assert out["district_wide"]["line_km"] == pytest.approx(exp["km_all"], abs=1e-3)
    assert out["district_wide"]["buildings"] == exp["b_all"] == 3
    t = out["targeted"]
    assert t["line_ids"] == exp["lines"]
    assert t["line_km"] == pytest.approx(exp["km_t"], abs=1e-3)
    assert t["buildings"] == exp["b_t"]
    assert t["risk_covered_ratio"] == pytest.approx(exp["ratio"], abs=1e-4)
    props = [f["properties"] for f in out["segments"]["features"]]
    assert [p["segment_id"] for p in props] == exp["segs"]
    for p in props:
        assert p["gust_kmh"] == pytest.approx(exp["gust"][p["segment_id"]], abs=0.05)
        assert p["candidate"] == (p["segment_id"] in exp["cand"])


def test_contract_shape_wgs84_and_notes(scen):
    out = scn.compute_scenario(AOI, SCEN_DAY, 50, "dusuk", root=scen.root)
    assert {"date", "inputs", "district_wide", "targeted", "segments", "note_tr",
            "note_en"} <= set(out)
    assert out["date"] == SCEN_DAY
    assert {"line_km", "buildings"} <= set(out["district_wide"])
    assert {"line_km", "buildings", "line_ids", "risk_covered_ratio"} <= set(out["targeted"])
    fc = out["segments"]
    assert fc["type"] == "FeatureCollection" and fc["features"]
    for f in fc["features"]:
        assert set(f["properties"]) == API_PROPS | {"gust_kmh", "candidate"}
        assert isinstance(f["properties"]["top_factors"], list)
        lon, lat = f["geometry"]["coordinates"][0]
        assert 26 < lon < 28 and 37 < lat < 39
    for word in ("OSM", "EDAŞ", "vekil"):
        assert word in out["note_tr"]
    for word in ("OSM", "feeder", "proxy"):
        assert word in out["note_en"]
    # REV-F3F4 D6: the suffix of "%66'sı" depends on how the number is read aloud; the
    # sentence is built so that no percentage takes a suffix
    assert re.search(r"%\d", out["note_tr"])
    assert not re.search(r"%\d+(?:,\d+)?'", out["note_tr"])
    json.dumps(out, allow_nan=False)  # strict JSON (no NaN)


@pytest.mark.parametrize("line,hv", [(0.995, 0.66), (1.0, 0.6), (0.5, 0.0), (0.123, 0.1)])
def test_notes_never_attach_a_suffix_to_a_percentage(line, hv):
    # three segments: tagged >= 154 kV line, other line, minor_line
    length = np.array([hv, line - hv, 1 - line]) * 1000
    power = np.array(["line", "line", "minor_line"])
    vclass = np.array(["ge154kv", "etiketsiz", "etiketsiz"])
    tr, en = scn._notes(vclass, power, length, 300.0)
    assert not re.search(r"%\d+(?:,\d+)?'", tr)
    pct = f"%{100 * line:.1f}".replace(".", ",")
    assert pct in tr and f"%{100 * hv:.0f}" in tr
    assert f"{100 * line:.1f}%" in en


def test_errors_map_to_api_status_codes(scen, tmp_path):
    with pytest.raises(FileNotFoundError):  # API: 503
        scn.compute_scenario("nope", SCEN_DAY, 50, "yuksek", root=scen.root)
    with pytest.raises(FileNotFoundError):
        scn.compute_scenario(AOI, SCEN_DAY, 50, "yuksek", root=tmp_path)
    for bad in [("2025-13-01", 50, "yuksek"), (SCEN_DAY, -1, "yuksek"),
                (SCEN_DAY, float("nan"), "yuksek"), (SCEN_DAY, 50, "high"),
                ("2025-07-15", 50, "yuksek"),  # no wind data that day
                ("2025-05-20", 50, "yuksek")]:  # no risk map before the day
        with pytest.raises(ValueError):  # API: 422
            scn.compute_scenario(AOI, *bad, root=scen.root)


def test_defaults_come_from_config(scen):
    a = scn.compute_scenario(AOI, SCEN_DAY, root=scen.root)
    assert a["inputs"]["gust_kmh"] == 50.0 and a["inputs"]["min_tier"] == "yuksek"
    path = scen.root / "config" / "risk_weights.yaml"
    rw = yaml.safe_load(path.read_text(encoding="utf-8"))
    rw["scenario"] = {"gust_threshold_kmh": 45, "risk_threshold_tier": "orta"}
    path.write_text(yaml.safe_dump(rw), encoding="utf-8")
    b = scn.compute_scenario(AOI, SCEN_DAY, root=scen.root)  # config edit: cache rebuilt
    assert b["inputs"]["gust_kmh"] == 45.0 and b["inputs"]["min_tier"] == "orta"
    del rw["scenario"]
    path.write_text(yaml.safe_dump(rw), encoding="utf-8")
    with pytest.raises(scn.ScenarioDataError, match="scenario"):
        scn.compute_scenario(AOI, SCEN_DAY, root=scen.root)


def test_later_data_does_not_change_the_scenario(scen):
    """Only the scenario day's wind and the latest risk map dated before it are used."""
    before = scn.compute_scenario(AOI, SCEN_DAY, 50, "dusuk", root=scen.root)
    w = pd.read_parquet(scen.interim / "wind_hourly.parquet")
    nxt = w["time_local"].dt.date == date(2025, 6, 29)
    w.loc[nxt, "wind_gust_10m_ms"] = 0.5
    w.to_parquet(scen.interim / "wind_hourly.parquet", index=False)
    later = scen.processed / "risk_2026-10-30.parquet"
    later.write_bytes(later.read_bytes())  # touch: a newer map must not be used
    after = scn.compute_scenario(AOI, SCEN_DAY, 50, "dusuk", root=scen.root)
    assert after == before


def test_cache_is_fast_and_follows_input_changes(scen):
    scn.compute_scenario(AOI, SCEN_DAY, 50, "dusuk", root=scen.root)  # cold
    t0 = time.perf_counter()
    for _ in range(20):
        out = scn.compute_scenario(AOI, SCEN_DAY, 50, "dusuk", root=scen.root)
    assert (time.perf_counter() - t0) / 20 < 0.5
    assert out["district_wide"]["buildings"] == 3
    b = gpd.read_parquet(scen.interim / "buildings.parquet")
    b = pd.concat([b, b.iloc[[0]]], ignore_index=True)  # one more building near 1001
    b.to_parquet(scen.interim / "buildings.parquet")
    assert scn.compute_scenario(AOI, SCEN_DAY, 50, "dusuk",
                                root=scen.root)["district_wide"]["buildings"] == 4


def test_cli_writes_dates_and_selected_day_reproducibly(scen):
    # candidates (syn aoi.yaml): 2025-06-27, 2025-06-30; make the 30th the windiest
    w = pd.read_parquet(scen.interim / "wind_hourly.parquet")
    d = w["time_local"].dt.date
    w.loc[d == date(2025, 6, 27), "wind_gust_10m_ms"] = 12.0
    w.loc[d == date(2025, 6, 30), "wind_gust_10m_ms"] = 18.0
    w.loc[(d == date(2025, 6, 30)) & (w["point_id"] == "g01"), "wind_gust_10m_ms"] = 21.0
    w.to_parquet(scen.interim / "wind_hourly.parquet", index=False)
    assert scn.main(["--aoi", AOI, "--root", str(scen.root)]) == 0
    dates = json.loads((scen.processed / "scenario_dates.json").read_text(encoding="utf-8"))
    assert [e["date"] for e in dates] == ["2025-06-27", "2025-06-30"]
    assert dates[1]["max_gust_kmh"] == pytest.approx(21.0 * 3.6, abs=0.05)
    assert [e["selected"] for e in dates] == [False, True]
    out = scen.processed / "scenario_2025-06-30.json"
    first = out.read_bytes()
    assert json.loads(first)["inputs"]["gust_kmh"] == 50.0
    scn.clear_cache()
    assert scn.main(["--aoi", AOI, "--root", str(scen.root)]) == 0
    assert out.read_bytes() == first
    assert (scen.processed / "scenario_dates.json").read_bytes() == json.dumps(
        dates, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def test_selection_rule_prefers_highest_max_then_median_then_earliest():
    rows = [{"date": "2025-06-27", "max_gust_kmh": 80.0, "median_gust_kmh": 60.0},
            {"date": "2025-06-28", "max_gust_kmh": 80.0, "median_gust_kmh": 70.0},
            {"date": "2025-06-29", "max_gust_kmh": 80.0, "median_gust_kmh": 70.0},
            {"date": "2025-06-30", "max_gust_kmh": 79.9, "median_gust_kmh": 90.0}]
    assert scn.select_scenario_day(rows) == "2025-06-28"
    with pytest.raises(ValueError):
        scn.select_scenario_day([])


def test_wind_unit_is_metres_per_second_times_3_6():
    assert scn.KMH_PER_MS == pytest.approx(3.6)
    with pytest.raises(ValueError, match="calendar date"):
        scn._parse_day(pd.Timestamp("2025-06-28 10:00").to_pydatetime())
