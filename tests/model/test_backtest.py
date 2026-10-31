"""Retrospective test (risk-model-spec section 5, ADR-013) on synthetic data.

Pure parts with hand-checked numbers, then the whole backtest on the synthetic AOI:
event selection (season, VIIRS, FIRMS type, district), the contract shape, and the time
leakage guarantee: season detections create events but never move the as_of ranking.
"""

from __future__ import annotations

import json
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
from synth import AOI, AS_OF, BASE_FIRMS, firms_frame, midpoint

from hatkalkani.model import backtest as bt
from hatkalkani.model.run import read_risk

EVENT_PROPS = {"event_id", "start_date", "end_date", "n_detections", "dist_to_line_m",
               "near_line", "nearest_segment_id", "risk_pct_nearest"}


# ------------------------------------------------------------------ pure parts
def test_cluster_events_chain_distance_and_day_gap():
    xy = np.array([[0, 0], [900, 0], [1800, 0], [0, 1100], [0, 0], [3000, 0], [3000, 0]])
    day = np.array([0, 0, 2, 0, 3, 10, 12])
    # A-B 900 m same day, B-C 900 m two days apart -> chain; D 1100 m away; E three days
    # after A; F-G same place two days apart
    assert bt.cluster_events(xy, day, 1000, 2).tolist() == [0, 0, 0, 1, 2, 3, 3]
    assert bt.cluster_events(np.zeros((0, 2)), np.zeros(0), 1000, 2).tolist() == []


def test_ignition_proxy_is_centroid_of_first_overpass():
    t0 = pd.Timestamp("2025-07-01 10:30", tz="UTC")
    det = pd.DataFrame({
        "x": [0.0, 200.0, 800.0], "y": [0.0, 0.0, 0.0],
        "t": [t0, t0, t0 + pd.Timedelta(hours=13)],
        "day": [date(2025, 7, 1), date(2025, 7, 1), date(2025, 7, 2)],
    })
    p = bt.ignition_proxies(det, np.array([0, 0, 0]))
    assert (p.loc[0, "x"], p.loc[0, "y"]) == (100.0, 0.0)
    assert p.loc[0, "start_date"] == date(2025, 7, 1)
    assert p.loc[0, "end_date"] == date(2025, 7, 2)
    assert p.loc[0, "n_detections"] == 3


def test_lift_block_numbers_and_empty_case():
    rng = np.random.default_rng(0)
    in_top = np.array([True, False, False, False])
    boot = rng.integers(0, 4, size=(2000, 4))
    b = bt.lift_block(in_top, 0.1, boot)
    assert (b["share"], b["expected"], b["lift"], b["n_in_top"]) == (0.25, 0.1, 2.5, 1)
    assert b["ci95"][0] <= 2.5 <= b["ci95"][1]
    assert b["p_value_binomial"] == pytest.approx(1 - 0.9**4, abs=1e-4)
    lo, hi = b["ci95_binomial"]
    assert lo < 2.5 < hi
    empty = bt.lift_block(np.zeros(0, dtype=bool), 0.1, np.zeros((0, 0), dtype=int))
    assert empty["share"] is None and empty["lift"] is None and empty["n_events"] == 0


def test_top_mask_and_null_block():
    pct = np.array([0.05, 0.15, 0.85, 0.9, 0.95])
    assert bt.top_mask(pct, 0.10).tolist() == [False, False, False, True, True]
    nb = bt.null_block(10, 0.1, 0.1, np.random.default_rng(1), 5000)
    assert nb["lift"] == 1.0 and nb["ci95"][0] == 0.0 and nb["ci95"][1] >= 2.0


def test_leakage_guard_refuses_later_data():
    cfg = bt.BacktestConfig(as_of=date(2025, 5, 31), season=(date(2025, 6, 1),
                            date(2025, 9, 30)), metric_crs="EPSG:32635",
                            event_line_distance_m=500, cluster_distance_m=1000,
                            cluster_gap_days=2, top_shares=(0.1, 0.2), bootstrap_n=10,
                            bootstrap_seed=1, sensitivity_distances_m=(1000,))
    ok = {"as_of": "2025-05-31",
          "provenance": {"fire_history": {"max_time_used_utc": "2025-05-31T20:59:00+00:00"}}}
    bt.check_no_leakage({"as_of": "2025-05-31"}, ok, cfg)
    late = {"as_of": "2025-05-31",
            "provenance": {"fire_history": {"max_time_used_utc": "2025-05-31T21:00:00+00:00"}}}
    with pytest.raises(bt.BacktestLeakageError, match="fire_history"):
        bt.check_no_leakage({"as_of": "2025-05-31"}, late, cfg)
    with pytest.raises(bt.BacktestLeakageError, match="backtest_asof"):
        bt.check_no_leakage({"as_of": "2026-10-30"}, ok, cfg)
    with pytest.raises(bt.BacktestLeakageError, match="season"):
        bt.check_no_leakage({"as_of": "2025-05-31"}, ok,
                            bt.BacktestConfig(**{**cfg.__dict__, "season": (
                                date(2025, 5, 15), date(2025, 9, 30))}))


# ------------------------------------------------------------ synthetic AOI run
SEASON_EXTRA = [  # (product, utc time, x, y, type)
    ("VIIRS_SNPP_SP", datetime(2025, 8, 2, 10, 0), *midpoint("2002_0001"), 0),  # near 2002
    ("VIIRS_NOAA20_SP", datetime(2025, 8, 3, 23, 0), 510050, 4220900, 0),  # same fire, chain
    ("VIIRS_SNPP_SP", datetime(2025, 8, 20, 10, 0), 510100, 4221800, 0),  # 1.4 km: far
    ("VIIRS_SNPP_SP", datetime(2025, 7, 1, 10, 0), *midpoint("1001_0001"), 2),  # static src
    ("MODIS_SP", datetime(2025, 7, 2, 10, 0), *midpoint("1001_0002"), 0),  # MODIS: ignored
    ("VIIRS_SNPP_SP", datetime(2025, 9, 30, 21, 30), *midpoint("1001_0002"), 0),  # Oct 1 loc
    ("VIIRS_SNPP_SP", datetime(2025, 7, 9, 10, 0), 513000, 4220000, 0),  # outside district
]


def _write_firms(syn, extra=SEASON_EXTRA) -> None:
    rows = [r[:4] for r in [*BASE_FIRMS, *extra]]
    df = firms_frame(rows)
    df["type"] = pd.array([0] * len(BASE_FIRMS) + [r[4] for r in extra], dtype="Int64")
    df.to_parquet(syn.interim / "firms.parquet", index=False)


def _build(syn) -> None:
    from hatkalkani.features.build import main as features_main
    from hatkalkani.model.run import main as model_main

    assert features_main(["--aoi", AOI, "--as-of", AS_OF.isoformat(),
                          "--root", str(syn.root)]) == 0
    assert model_main(["--aoi", AOI, "--as-of", AS_OF.isoformat(),
                       "--root", str(syn.root)]) == 0


@pytest.fixture
def run(syn):
    _write_firms(syn)
    _build(syn)
    return syn, bt.run_backtest(AOI, syn.root)


def test_events_selection_and_properties(run):
    syn, res = run
    ev = res.events.set_index("event_id")
    # universe: in season, VIIRS, type 0, inside the district. BASE_FIRMS adds two
    # season detections at 1001_0003 (2025-06-01 00:30 local and 2025-07-15)
    assert len(ev) == 4
    assert res.summary["n_events_total"] == 4
    assert sorted(ev["start_date"]) == ["2025-06-01", "2025-07-15", "2025-08-02",
                                       "2025-08-20"]
    chain = ev[ev["start_date"] == "2025-08-02"].iloc[0]
    assert chain["n_detections"] == 2 and chain["end_date"] == "2025-08-04"
    assert chain["nearest_segment_id"] == "2002_0001" and chain["near_line"]
    far = ev[ev["start_date"] == "2025-08-20"].iloc[0]
    assert far["dist_to_line_m"] == pytest.approx(1400, abs=1) and not far["near_line"]
    assert res.summary["n_events"] == 3
    risk, _ = read_risk(syn.processed / f"risk_{AS_OF.isoformat()}.parquet")
    pct = risk.set_index("segment_id")["risk_pct"]
    for _, e in ev.iterrows():
        assert e["risk_pct_nearest"] == pytest.approx(pct[e["nearest_segment_id"]], abs=1e-4)
    gj = json.loads(res.events.to_json())
    for f in gj["features"]:
        assert EVENT_PROPS <= set(f["properties"])
    det = res.summary["events_summary"]["detections"]
    assert det["type_filter"]["n_excluded_by_type"] == {"2": 1}
    assert res.summary["events_summary"]["n_clusters_outside_aoi"] == 1


def test_summary_contract_and_sensitivity_labels(run):
    _, res = run
    s = res.summary
    assert {"as_of", "season", "n_events", "top10", "top20", "baselines", "limitations_tr",
            "limitations_en", "event_line_distance_m", "n_events_total"} <= set(s)
    assert s["as_of"] == "2025-05-31" and s["season"] == "2025-06-01..2025-09-30"
    for k in ("top10", "top20"):
        assert {"share", "expected", "lift", "ci95"} <= set(s[k])
        assert s[k]["lift"] == pytest.approx(s[k]["share"] / s[k]["expected"], abs=1e-3)
    for key in ("expected", "length", "vegetation_chm", "fire_history", "linear",
                "tree_shrub_cover", "buildings"):
        b = s["baselines"][key]
        assert b["label_tr"] and b["label_en"]
        for k in ("top10", "top20"):
            assert {"share", "lift", "ci95"} <= set(b[k])
    sens = s["sensitivity_line_distance"]
    assert "DUYARLILIK" in sens["label_tr"] and "SENSITIVITY" in sens["label_en"]
    assert set(sens["results"]) == {"1000", "2000"}
    assert sens["results"]["2000"]["n_events"] == 4  # the 1.4 km event joins
    assert s["limitations_tr"] and len(s["limitations_tr"]) == len(s["limitations_en"])
    json.dumps(s, allow_nan=False)


def test_season_detections_never_move_the_as_of_ranking(run):
    """Leakage: the backtest only reads the as_of risk map. Adding season and later data
    and rebuilding everything changes the events, not one segment's percentile."""
    syn, before = run
    risk0, _ = read_risk(syn.processed / f"risk_{AS_OF.isoformat()}.parquet")
    more = [*SEASON_EXTRA,
            ("VIIRS_SNPP_SP", datetime(2025, 6, 10, 10, 0), *midpoint("1001_0002"), 0),
            ("VIIRS_NOAA20_SP", datetime(2025, 9, 1, 10, 0), *midpoint("2002_0002"), 0),
            ("VIIRS_SNPP_NRT", datetime(2026, 8, 1, 10, 0), *midpoint("1001_0001"), None)]
    _write_firms(syn, more)
    w = pd.read_parquet(syn.interim / "wind_hourly.parquet")
    w.loc[w["time_local"] >= pd.Timestamp("2025-06-01"), "wind_gust_10m_ms"] = 99.0
    w.to_parquet(syn.interim / "wind_hourly.parquet", index=False)
    _build(syn)
    risk1, _ = read_risk(syn.processed / f"risk_{AS_OF.isoformat()}.parquet")
    pd.testing.assert_series_equal(risk0["risk_pct"], risk1["risk_pct"])
    after = bt.run_backtest(AOI, syn.root)
    assert after.summary["n_events_total"] == before.summary["n_events_total"] + 2
    old = before.events.set_index("event_id")
    new = after.events.set_index(["start_date", "nearest_segment_id"])
    for _, e in old.iterrows():
        assert new.loc[(e["start_date"], e["nearest_segment_id"]),
                       "risk_pct_nearest"] == e["risk_pct_nearest"]


def test_cli_outputs_are_reproducible(run):
    syn, _ = run
    assert bt.main(["--aoi", AOI, "--root", str(syn.root)]) == 0
    a = (syn.processed / "backtest.json").read_bytes()
    e = (syn.processed / "events_2025.geojson").read_bytes()
    assert bt.main(["--aoi", AOI, "--root", str(syn.root)]) == 0
    assert (syn.processed / "backtest.json").read_bytes() == a
    assert (syn.processed / "events_2025.geojson").read_bytes() == e
    gj = json.loads(e)
    assert gj["type"] == "FeatureCollection" and "crs" not in gj
    lon, lat = gj["features"][0]["geometry"]["coordinates"]
    assert 26 < lon < 28 and 37 < lat < 39
