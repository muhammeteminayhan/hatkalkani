"""Time leakage (risk-model-spec: "as_of sonrasındaki hiçbir veri özelliklere giremez").

Each test injects data stamped at/after the as_of cutoff and requires byte-identical
features; every negative test has a positive control showing the same injection *before*
the cutoff does change the features (so the test can actually detect leakage).
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
from synth import AOI, AS_OF, BASE_FIRMS, CURRENT, SEGMENTS, midpoint

from hatkalkani.features import FACTORS, FactorResult, TemporalLeakageError, factor
from hatkalkani.features.asof import AsOf
from hatkalkani.features.build import FeatureBuildError, build_features
from hatkalkani.features.context import FeatureContext


def _build(syn, as_of) -> tuple[pd.DataFrame, dict]:
    df, meta, _ = build_features(FeatureContext(AOI, syn.root), as_of=as_of)
    return df, meta


def _future_firms() -> list[tuple]:
    rows = []
    for sid in SEGMENTS:
        x, y = midpoint(sid)
        rows += [
            ("VIIRS_SNPP_SP", datetime(2025, 5, 31, 21, 0), x, y),  # == cutoff (00:00 local)
            ("VIIRS_NOAA20_NRT", datetime(2025, 6, 1, 10, 0), x + 400, y),
            ("VIIRS_SNPP_NRT", datetime(2025, 6, 29, 11, 0), x, y + 400),
            ("VIIRS_SNPP_SP", datetime(2026, 8, 1, 11, 0), x - 400, y),
        ]
    return rows


def _overwrite_wind(syn, start_utc: pd.Timestamp, end_utc: pd.Timestamp, gust: float) -> int:
    p = syn.interim / "wind_hourly.parquet"
    w = pd.read_parquet(p)
    m = (w["time_utc"] >= start_utc) & (w["time_utc"] < end_utc)
    w.loc[m, "wind_gust_10m_ms"] = gust
    w.to_parquet(p, index=False)
    return int(m.sum())


def test_future_firms_wind_and_s2_leave_backtest_features_unchanged(syn):
    before, meta0 = _build(syn, AS_OF)
    future = _future_firms()
    syn.write_firms(BASE_FIRMS + future)
    cutoff = AsOf(AS_OF).cutoff_utc
    n_wind = _overwrite_wind(syn, cutoff, pd.Timestamp("2030-01-01", tz="UTC"), 99.0)
    assert n_wind > 0  # scenario days 2025-06-27..30 are after the cutoff
    syn.write_s2("late", np.full((240, 240), -0.9, dtype="float32"))
    syn.write_s2("sneaky", np.full((240, 240), -0.9, dtype="float32"))
    syn.write_s2_meta({
        "late": {"window": ["2025-06-01", "2025-06-30"],
                 "scenes": [{"id": "z", "datetime": "2025-06-20T09:00:00+00:00"}]},
        # window "ends" on as_of but one scene is after the cutoff -> must not be eligible
        "sneaky": {"window": ["2025-05-01", "2025-05-31"],
                   "scenes": [{"id": "y", "datetime": "2025-05-20T09:00:00+00:00"},
                              {"id": "x", "datetime": "2025-06-02T09:00:00+00:00"}]},
    })
    after, meta1 = _build(syn, AS_OF)
    pd.testing.assert_frame_equal(before, after)
    f0, f1 = meta0["provenance"]["fire_history"], meta1["provenance"]["fire_history"]
    assert f1["n_viirs_excluded_at_or_after_cutoff"] == (
        f0["n_viirs_excluded_at_or_after_cutoff"] + len(future))
    s2 = meta1["provenance"]["fuel_dryness"]
    assert s2["selected"] == "backtest"
    assert {c["name"]: c["eligible"] for c in s2["candidates"]} == {
        "backtest": True, "current": False, "late": False, "sneaky": False}


def test_firms_positive_control_one_minute_before_cutoff(syn):
    before, _ = _build(syn, AS_OF)
    x, y = midpoint("1001_0002")
    syn.write_firms(BASE_FIRMS + [("VIIRS_SNPP_SP", datetime(2025, 5, 31, 20, 59), x, y)])
    after, _ = _build(syn, AS_OF)
    gained = after["fire_history"] - before["fire_history"]
    assert (gained > 0).all()  # 2 km kernel reaches every synthetic segment
    static = [n for n, s in FACTORS.items() if s.temporal != "time_filtered"]
    pd.testing.assert_frame_equal(before[static], after[static])


def test_wind_cutoff_inside_a_climatology_summer(syn):
    as_of = date(2023, 7, 15)
    cutoff = AsOf(as_of).cutoff_utc  # 2023-07-15 21:00 UTC
    before, meta = _build(syn, as_of)
    assert meta["provenance"]["wind_exposure"]["max_time_used_utc"] == (
        "2023-07-15T20:00:00+00:00")  # last hour of the local day
    assert meta["provenance"]["wind_exposure"]["years_used"] == [2022, 2023]
    _overwrite_wind(syn, cutoff, pd.Timestamp("2030-01-01", tz="UTC"), 99.0)
    after, _ = _build(syn, as_of)
    pd.testing.assert_frame_equal(before, after)
    # positive control: the same storm two weeks *before* as_of moves the 95th percentile
    _overwrite_wind(syn, pd.Timestamp("2023-06-30T21:00:00Z"), cutoff, 99.0)
    changed, _ = _build(syn, as_of)
    assert (changed["wind_exposure"] > after["wind_exposure"]).all()


def test_s2_positive_control_later_as_of_selects_later_composite(syn):
    syn.write_s2("late", np.full((240, 240), -0.9, dtype="float32"))
    syn.write_s2_meta({"late": {"window": ["2025-06-01", "2025-06-30"],
                                "scenes": [{"id": "z", "datetime": "2025-06-20T09:00:00+00:00"}]}})
    df, meta = _build(syn, date(2025, 6, 30))
    assert meta["provenance"]["fuel_dryness"]["selected"] == "late"
    assert np.allclose(df["fuel_dryness"], -0.9)


def test_no_composite_before_as_of_gives_documented_nan(syn):
    df, meta = _build(syn, date(2025, 4, 1))
    assert df["fuel_dryness"].isna().all()
    assert (df["nan_reasons"].str.contains("fuel_dryness:no_s2_composite_before_as_of")).all()
    assert meta["provenance"]["fuel_dryness"]["selected"] is None


def test_static_factors_identical_across_as_of(syn):
    a, _ = _build(syn, AS_OF)
    b, _ = _build(syn, CURRENT)
    static = [n for n, s in FACTORS.items() if s.temporal != "time_filtered"]
    pd.testing.assert_frame_equal(a[static], b[static])
    assert not np.allclose(a["fire_history"], b["fire_history"])


def _one_factor_registry(provenance: dict) -> dict:
    reg: dict = {}

    @factor(name="probe", component="ignition", unit="-", source="test", as_of_rule="test",
            temporal="time_filtered", direction="higher", label_tr="t", label_en="t",
            definition="d", registry=reg)
    def probe(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
        n = len(ctx.ids)
        return FactorResult(values=ctx.series(np.zeros(n)),
                            nan_reason=ctx.series([""] * n, dtype="object"),
                            provenance=provenance)

    return reg


def test_runtime_guard_rejects_data_after_cutoff(syn):
    ctx = FeatureContext(AOI, syn.root)
    reg = _one_factor_registry({"max_time_used_utc": "2025-05-31T21:00:00+00:00"})
    with pytest.raises(TemporalLeakageError):
        build_features(ctx, as_of=AS_OF, registry=reg, strict_config=False)
    ok = _one_factor_registry({"max_time_used_utc": "2025-05-31T20:59:59+00:00"})
    df, _, _ = build_features(ctx, as_of=AS_OF, registry=ok, strict_config=False)
    assert "probe" in df


def test_time_filtered_factor_must_report_its_latest_timestamp(syn):
    ctx = FeatureContext(AOI, syn.root)
    with pytest.raises(FeatureBuildError, match="max_time_used_utc"):
        build_features(ctx, as_of=AS_OF, registry=_one_factor_registry({}),
                       strict_config=False)
