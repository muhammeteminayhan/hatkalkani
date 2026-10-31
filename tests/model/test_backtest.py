"""Retrospective test (risk-model-spec section 5, ADR-013) on synthetic data.

Pure parts with hand-checked numbers, then the whole backtest on the synthetic AOI:
event selection (season, VIIRS, FIRMS type, district), the contract shape, and the time
leakage guarantee: season detections create events but never move the as_of ranking.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from synth import AOI, AS_OF, BASE_FIRMS, firms_frame, midpoint

from hatkalkani.features.asof import AsOf
from hatkalkani.ingest.common import MANIFEST_COLUMNS
from hatkalkani.model import backtest as bt
from hatkalkani.model.run import read_risk

EVENT_PROPS = {"event_id", "start_date", "end_date", "n_detections", "dist_to_line_m",
               "near_line", "nearest_segment_id", "risk_pct_nearest"}
WUI_PROV = {"file": "buildings.parquet", "source": "overture",
            "overture_release": "2026-10-21.0",
            "temporal_status": "static_release_after_backtest_as_of"}
TIME_VARYING_PROV = {
    "fire_history": {"max_time_used_utc": "2025-05-28T11:54:00+00:00"},
    "fuel_dryness": {"max_time_used_utc": "2025-05-31T09:10:06+00:00"},
    "wind_exposure": {"max_time_used_utc": "2024-09-30T20:00:00+00:00"},
}
BASE_LAYERS = [
    {"layer": "lines", "source": "osm_power_lines", "release": "2026-10-30",
     "used_by": ["segments", "all_factors", "near_line_events"]},
    {"layer": "boundary", "source": "osm_boundary", "release": "2026-10-30",
     "used_by": ["segments", "event_universe"]},
]


def _cfg(**kw) -> bt.BacktestConfig:
    base = dict(as_of=date(2025, 5, 31), season=(date(2025, 6, 1), date(2025, 9, 30)),
                metric_crs="EPSG:32635", event_line_distance_m=500, cluster_distance_m=1000,
                cluster_gap_days=2, top_shares=(0.1, 0.2), bootstrap_n=10, bootstrap_seed=1,
                sensitivity_distances_m=(1000,))
    return bt.BacktestConfig(**{**base, **kw})


def _limitations(static=(), chm=None, type_filter=None, n=2, total=10):
    return bt.limitations(
        n, total, _cfg(), chm_dates=chm or {"acq_min": "2016-07-22", "acq_max": "2020-02-18"},
        static_layers=list(static),
        type_filter=type_filter or {"type_column": True, "n_excluded_by_type": {}})


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
    cfg = _cfg()
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
                            _cfg(season=(date(2025, 5, 15), date(2025, 9, 30))))


def test_static_layers_after_as_of_are_declared_not_silently_passed():
    """REV-F3F4 Y1: static layers carry no max_time_used_utc. A layer whose
    temporal_status says "after_" or whose release/access date is on or after as_of is
    listed (not raised: there is no as_of snapshot to use instead)."""
    fmeta = {"as_of": "2025-05-31", "provenance": {
        **TIME_VARYING_PROV,
        "wui_exposure": WUI_PROV,
        "fuel_continuity": {"file": "worldcover.tif", "temporal_status": "static_2021"},
        "slope": {"file": "dem_slope.tif"},
        "old_layer": {"file": "old.parquet", "release": "2025-05-30"},
        "same_day": {"file": "same.parquet", "release": "2025-05-31"},  # >= as_of
        "asset_condition": {"status": "unavailable"},
    }}
    base = [*BASE_LAYERS, {"layer": "older", "source": "x", "release": "2020-01-01",
                           "used_by": ["segments"]},
            {"layer": "undated", "source": None, "release": None, "used_by": ["segments"]}]
    chk = bt.check_no_leakage({"as_of": "2025-05-31"}, fmeta, _cfg(), base)
    assert chk.as_of == AsOf(date(2025, 5, 31))
    got = {e["layer"]: e for e in chk.static_after_as_of}
    assert set(got) == {"buildings", "lines", "boundary", "same", "undated"}
    b = got["buildings"]
    assert (b["release"], b["release_date"]) == ("2026-10-21.0", "2026-10-21")
    assert b["used_by"] == ["wui_exposure", "baselines.buildings"]
    assert "temporal_status" in b["basis"] and "2026-10-21" in b["basis"]
    assert got["lines"]["release_date"] == "2026-10-30"
    assert "near_line_events" in got["lines"]["used_by"]
    assert got["undated"]["release"] is None and "unknown" in got["undated"]["basis"]
    for e in chk.static_after_as_of:
        assert {"layer", "release", "used_by", "label_tr", "label_en", "basis"} <= set(e)
    # nothing static is flagged when every static input predates as_of
    clean = {"as_of": "2025-05-31", "provenance": {
        **TIME_VARYING_PROV, "slope": {"file": "dem_slope.tif"},
        "fuel_continuity": {"file": "worldcover.tif", "temporal_status": "static_2021"}}}
    rmeta = {"as_of": "2025-05-31",
             "chm_dates": {"acq_min": "2016-07-22", "acq_max": "2020-02-18"}}
    assert bt.check_no_leakage(rmeta, clean, _cfg(), base[2:3]).static_after_as_of == ()
    # a multi-year backtest with an early as_of must declare later CHM and WorldCover
    early = _cfg(as_of=date(2019, 5, 31), season=(date(2019, 6, 1), date(2019, 9, 30)))
    late = bt.check_no_leakage({**rmeta, "as_of": "2019-05-31"},
                               {**clean, "as_of": "2019-05-31", "provenance": {
                                   "fuel_continuity": clean["provenance"]["fuel_continuity"]}},
                               early, base[2:3])
    got = {e["layer"]: e for e in late.static_after_as_of}
    assert set(got) == {"chm", "worldcover", "older"}
    assert got["chm"]["release_date"] == "2020-02-18"
    assert "baselines.vegetation_chm" in got["chm"]["used_by"]
    assert got["worldcover"]["used_by"] == ["fuel_continuity", "baselines.tree_shrub_cover"]


def test_leakage_block_note_and_buildings_baseline_limitation():
    fmeta = {"provenance": {**TIME_VARYING_PROV, "wui_exposure": WUI_PROV}}
    chk = bt.check_no_leakage({"as_of": "2025-05-31"}, {"as_of": "2025-05-31", **fmeta},
                              _cfg(), BASE_LAYERS)
    block = bt.leakage_block(chk, fmeta)
    assert block["static_after_as_of"] == list(chk.static_after_as_of)
    assert [e["layer"] for e in block["time_varying_before_cutoff"]] == [
        "fire_history", "fuel_dryness", "wind_exposure"]
    assert block["cutoff_utc"] == "2025-05-31T21:00:00+00:00"
    for key, words in (("note_tr", ("FIRMS, Sentinel-2, rüzgâr", "Overture 2026-10-21.0",
                                    "OSM 2026-10-30", "iyimser")),
                       ("note_en", ("FIRMS, Sentinel-2, wind", "Overture 2026-10-21.0",
                                    "OSM 2026-10-30", "optimistic"))):
        for w in words:
            assert w in block[key], (key, w)
    tr, en = _limitations(chk.static_after_as_of)
    assert len(tr) == len(en)
    hit_tr = [s for s in tr if "Bina yakınlığı taban çizgisi" in s]
    hit_en = [s for s in en if "building-proximity baseline" in s]
    assert len(hit_tr) == len(hit_en) == 1
    assert "iyimser" in hit_tr[0] and "Overture 2026-10-21.0" in hit_tr[0]
    assert "optimistic" in hit_en[0] and "OSM 2026-10-30" in hit_en[0]
    # without a late building layer the baseline sentence is not written
    tr0, en0 = _limitations([e for e in chk.static_after_as_of if e["layer"] != "buildings"])
    assert not any("Bina yakınlığı" in s for s in tr0)
    assert not any("building-proximity" in s for s in en0)
    empty = bt.leakage_block(bt.LeakageCheck(AsOf(date(2025, 5, 31)), ()), fmeta)
    assert empty["static_after_as_of"] == [] and "bulunmadı" in empty["note_tr"]


def test_degenerate_bootstrap_interval_is_null_with_note():
    """REV-F3F4 O2: with k in {0, n} every bootstrap resample has the same share, so the
    percentile interval [x, x] is not a confidence interval."""
    boot = np.random.default_rng(0).integers(0, 2, size=(500, 2))
    for in_top in (np.array([False, False]), np.array([True, True])):
        b = bt.lift_block(in_top, 0.2, boot)
        assert b["ci95"] is None and b["ci95_note"] == bt.CI_NOTE_DEGENERATE
        assert b["lift"] == pytest.approx(in_top.mean() / 0.2)
        assert b["ci95_binomial"] is not None and b["ci95_binomial"][1] > b["ci95_binomial"][0]
    mixed = bt.lift_block(np.array([True, False]), 0.2, boot)
    assert mixed["ci95"] is not None and mixed["ci95_note"] is None
    empty = bt.lift_block(np.zeros(0, dtype=bool), 0.2, np.zeros((0, 0), dtype=int))
    assert empty["ci95"] is None and empty["ci95_note"] == bt.CI_NOTE_NO_EVENTS
    no_top = bt.lift_block(np.array([False, False]), 0.0, boot)
    assert no_top["lift"] is None and no_top["ci95_note"] == bt.CI_NOTE_EMPTY_TOP
    assert bt.null_block(2, 0.1, 0.1, np.random.default_rng(1), 100)["ci95_note"] is None
    assert bt.null_block(0, 0.1, 0.1, np.random.default_rng(1), 100)["ci95_note"] == \
        bt.CI_NOTE_NO_EVENTS


def _exact_power(n: int, p0: float, p1: float, alpha: float) -> float:
    k = next(k for k in range(n + 2) if stats.binom.sf(k - 1, n, p0) <= alpha)
    return float(stats.binom.sf(k - 1, n, p1))


def test_verdict_threshold_matches_its_power_rationale():
    """MIN_EVENTS_INFORMATIVE is the smallest n from which a one-sided exact binomial
    test (alpha 0.05) keeps >= 80 % power for lift 2 in the top 20 % (0.40 vs 0.20)."""
    power = {n: _exact_power(n, 0.20, 0.40, 0.05) for n in range(2, 201)}
    stable = min(n for n in power if all(power[m] >= 0.80 for m in power if m >= n))
    assert bt.MIN_EVENTS_INFORMATIVE == stable
    v = bt.verdict(2)
    assert v == {**v, "informative": False, "n_events": 2,
                 "min_events": bt.MIN_EVENTS_INFORMATIVE}
    assert {"informative", "reason_tr", "reason_en"} <= set(v)
    assert str(bt.MIN_EVENTS_INFORMATIVE) in v["reason_tr"]
    assert str(bt.MIN_EVENTS_INFORMATIVE) in v["reason_en"]
    assert bt.verdict(stable)["informative"] is True
    assert bt.verdict(stable - 1)["informative"] is False


def test_chm_limitation_is_generated_from_the_risk_meta_dates():
    """REV-F3F4 O1: the CHM range is read from rmeta["chm_dates"], not typed by hand."""
    tr, en = bt.chm_limitation({"acq_min": "2016-07-22", "acq_max": "2020-02-18"},
                               date(2025, 5, 31))
    assert "2016-07-22…2020-02-18" in tr and "5,3–8,9 yıl" in tr
    assert "2016-07-22…2020-02-18" in en and "5.3–8.9 years" in en
    tr, en = bt.chm_limitation({"file": None, "note": "missing"}, date(2025, 5, 31))
    assert "bilinmiyor" in tr and "unknown" in en
    lim_tr, lim_en = _limitations(chm={"acq_min": "2017-01-01", "acq_max": "2019-12-31"})
    assert any("2017-01-01…2019-12-31" in s for s in lim_tr)
    assert any("2017-01-01…2019-12-31" in s for s in lim_en)
    assert not any("2020-02-19" in s for s in [*lim_tr, *lim_en])


def test_limitations_state_selection_bias_and_soft_registration_wording():
    """REV-F3F4 O4 and D2: the registration claim names what can be verified."""
    tr, en = _limitations()
    joined_tr, joined_en = " ".join(tr), " ".join(en)
    assert "Seçim yanlılığı" in joined_tr and "Selection bias" in joined_en
    for w in ("c423a81", "aynı commit", "0 tespit"):
        assert w in joined_tr, w
    for w in ("c423a81", "same commit", "0 season detections"):
        assert w in joined_en, w
    assert not re.search(r"önceden kayıtlı|sonuç görülmeden", joined_tr, re.I)
    assert not re.search(r"pre-registered", joined_en, re.I)
    tr2, en2 = _limitations(type_filter={"type_column": True,
                                         "n_excluded_by_type": {"2": 3, "3": 1}})
    assert "4 tespit" in " ".join(tr2) and "4 season detections" in " ".join(en2)
    tr3, _ = _limitations(type_filter={"type_column": False})
    assert "type sütunu yok" in " ".join(tr3)


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


def sens_results(s):
    return list(s["sensitivity_line_distance"]["results"].values())


def _lift_blocks(s):
    """(block, n events) of every lift_block: model, single-factor baselines and the
    distance sensitivities (baseline views carry no n_events of their own)."""
    for res in (s, *sens_results(s)):
        n = res["n_events"]
        yield from ((res[k], n) for k in ("top10", "top20"))
        for key, b in res["baselines"].items():
            if key not in ("expected", "length"):
                yield from ((b[k], n) for k in ("top10", "top20"))


def test_summary_contract_and_sensitivity_labels(run):
    _, res = run
    s = res.summary
    assert {"as_of", "season", "n_events", "top10", "top20", "baselines", "limitations_tr",
            "limitations_en", "event_line_distance_m", "n_events_total", "verdict",
            "leakage"} <= set(s)
    assert s["as_of"] == "2025-05-31" and s["season"] == "2025-06-01..2025-09-30"
    for k in ("top10", "top20"):
        assert {"share", "expected", "lift", "ci95", "ci95_note"} <= set(s[k])
        assert s[k]["lift"] == pytest.approx(s[k]["share"] / s[k]["expected"], abs=1e-3)
    for key in ("expected", "length", "vegetation_chm", "fire_history", "linear",
                "tree_shrub_cover", "buildings"):
        b = s["baselines"][key]
        assert b["label_tr"] and b["label_en"]
        for k in ("top10", "top20"):
            assert {"share", "lift", "ci95", "ci95_note"} <= set(b[k])
    for b, n in _lift_blocks(s):  # O2: no degenerate interval is reported as an interval
        assert (b["ci95"] is None) == (b["ci95_note"] is not None)  # null iff explained
        if b["share"] is None:  # the ranking's top set is empty (synthetic ties)
            assert b["ci95_note"] == bt.CI_NOTE_EMPTY_TOP
        elif b["n_in_top"] in (0, n):
            assert b["ci95_note"] == bt.CI_NOTE_DEGENERATE
    for res in (s, *sens_results(s)):
        for key in ("expected", "length"):
            for k in ("top10", "top20"):
                b = res["baselines"][key][k]
                assert (b["ci95"] is None) == (b["ci95_note"] is not None)
    sens = s["sensitivity_line_distance"]
    assert "DUYARLILIK" in sens["label_tr"] and "SENSITIVITY" in sens["label_en"]
    assert "Önceden kayıtlı" not in sens["label_tr"]
    assert "pre-registered" not in sens["label_en"]
    assert set(sens["results"]) == {"1000", "2000"}
    assert sens["results"]["2000"]["n_events"] == 4  # the 1.4 km event joins
    assert s["limitations_tr"] and len(s["limitations_tr"]) == len(s["limitations_en"])
    v = s["verdict"]
    assert v["informative"] is False and v["n_events"] == s["n_events"] == 3
    assert v["reason_tr"] and v["reason_en"]
    lk = s["leakage"]
    assert {"static_after_as_of", "note_tr", "note_en"} <= set(lk)
    # synthetic AOI: the wui provenance flags the building layer; without a MANIFEST and
    # without chm_acq_segment.parquet the dates of lines, boundary and CHM are unknown and
    # therefore declared as well
    layers = {e["layer"]: e for e in lk["static_after_as_of"]}
    assert set(layers) == {"buildings", "lines", "boundary", "chm"}
    assert layers["lines"]["release"] is None and layers["chm"]["release"] is None
    assert any("Bina yakınlığı taban çizgisi" in t for t in s["limitations_tr"])
    json.dumps(s, allow_nan=False)


def test_base_layer_dates_come_from_the_manifest(run):
    syn, _ = run
    man = syn.root / "data" / "raw" / "MANIFEST.csv"
    rows = [
        {"kaynak": "osm_power_lines", "yerel_yol": f"data/raw/{AOI}/lines_overpass.json",
         "tarih": "2026-10-30"},
        {"kaynak": "osm_power_lines", "yerel_yol": "data/raw/other_aoi/lines_overpass.json",
         "tarih": "2027-01-01"},  # another AOI: ignored
        {"kaynak": "osm_boundary", "yerel_yol": f"data/raw/{AOI}/boundary_overpass.json",
         "tarih": "2024-01-01"},  # before as_of: not declared
    ]
    with man.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        w.writerows([{c: r.get(c, "") for c in MANIFEST_COLUMNS} for r in rows])
    base = {b["layer"]: b for b in bt.base_layer_dates(syn.root, AOI)}
    assert base["lines"]["release"] == "2026-10-30"
    assert base["boundary"]["release"] == "2024-01-01"
    s = bt.run_backtest(AOI, syn.root).summary
    layers = {e["layer"]: e for e in s["leakage"]["static_after_as_of"]}
    assert set(layers) == {"buildings", "lines", "chm"}
    assert layers["lines"]["release"] == "2026-10-30"
    assert "OSM 2026-10-30" in s["leakage"]["note_tr"]


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
