"""Normalisation, P/C combination, tiers and config handling (risk-model-spec section 3).

Expected values come from independent brute-force code (explicit loops over segments),
not from the functions under test.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest
from model_synth import config_dict, factor_metas, feature_frame, make_config

from hatkalkani.model.config import ConfigError, model_config_from_dict
from hatkalkani.model.normalize import percentile_rank
from hatkalkani.model.score import ScoreError, assign_tiers, score_features


def brute_percentile(values: list[float], lower: bool = False) -> list[float]:
    """(#less + 0.5 * #equal) / n over finite values, by explicit counting."""
    vals = [(-v if lower else v) for v in values]
    finite = [v for v in vals if not math.isnan(v)]
    n = len(finite)
    out = []
    for v in vals:
        if math.isnan(v):
            out.append(math.nan)
            continue
        less = sum(1 for u in finite if u < v)
        equal = sum(1 for u in finite if u == v)
        out.append((less + 0.5 * equal) / n)
    return out


def test_percentile_rank_matches_brute_force_with_ties_nan_and_direction():
    vals = [0.0, 0.0, 0.0, 0.3, 0.1, math.nan, 0.3, 2.0]
    for lower in (False, True):
        got = percentile_rank(np.array(vals), direction="lower" if lower else "higher")
        np.testing.assert_allclose(got, brute_percentile(vals, lower), equal_nan=True)
    const = percentile_rank(np.array([4.0, 4.0, 4.0]), direction="higher")
    np.testing.assert_allclose(const, [0.5, 0.5, 0.5])  # a constant factor is neutral
    with pytest.raises(ValueError, match="direction"):
        percentile_rank(np.array([1.0]), direction="up")


def test_mid_rank_percentiles_average_to_one_half_even_with_ties():
    df = feature_frame(200)
    res = score_features(df, factor_metas(), make_config())
    for f in ("enc", "fuel", "wui"):
        assert res.frame[f"norm_{f}"].mean() == pytest.approx(0.5, abs=1e-12)


def test_geometric_and_linear_scores_match_hand_formula():
    df = feature_frame(30)
    metas = factor_metas()
    for combine in ("geometric", "linear"):
        res = score_features(df, metas, make_config(combine=combine))
        enc = brute_percentile(df["enc"].tolist())
        dry = brute_percentile(df["dry"].tolist(), lower=True)
        fuel = brute_percentile(df["fuel"].tolist())
        wui = brute_percentile(df["wui"].tolist())
        for i in range(len(df)):
            d = dry[i]
            if math.isnan(d):  # documented NaN policy: all_water -> 0, other reasons -> 0.5
                d = 0.0 if "all_water" in df["nan_reasons"].iloc[i] else 0.5
            p = 0.6 * enc[i] + 0.4 * d
            c = 0.7 * fuel[i] + 0.3 * wui[i]
            want = 100 * math.sqrt(p * c) if combine == "geometric" else 100 * (0.6 * p + 0.4 * c)
            assert res.frame["p_ignition"].iloc[i] == pytest.approx(p, abs=1e-12)
            assert res.frame["consequence"].iloc[i] == pytest.approx(c, abs=1e-12)
            assert res.frame["risk"].iloc[i] == pytest.approx(want, abs=1e-9)
    assert res.frame["risk"].between(0, 100).all()


def test_nan_policy_is_explicit_and_recorded():
    df = feature_frame(30)
    res = score_features(df, factor_metas(), make_config())
    fr = res.frame
    assert fr.loc[3, "norm_dry"] == 0.0  # all_water: no vegetation -> lowest dryness risk
    assert fr.loc[11, "norm_dry"] == 0.5  # missing data -> neutral reference value
    assert fr.loc[3, "imputed"] == "dry:all_water"
    assert fr.loc[11, "imputed"] == "dry:no_valid_ndmi_pixels"
    assert (fr.drop(index=[3, 11])["imputed"] == "").all()
    assert res.meta["imputed_counts"] == {"dry": {"all_water": 1, "no_valid_ndmi_pixels": 1}}
    bad = df.copy()
    bad.loc[5, "fuel"] = np.nan  # NaN without a documented reason
    with pytest.raises(ScoreError, match="fuel"):
        score_features(bad, factor_metas(), make_config())


def test_unavailable_factor_is_skipped_but_cannot_carry_weight():
    df = feature_frame(20)
    res = score_features(df, factor_metas(), make_config())
    assert (res.frame["contrib_asset"] == 0).all() and res.frame["norm_asset"].isna().all()
    cfg = config_dict(consequence={"fuel": 0.6, "wui": 0.3, "asset": 0.1})
    with pytest.raises(ScoreError, match="asset"):
        score_features(df, factor_metas(), model_config_from_dict(cfg))


def test_weights_are_renormalised_with_a_warning_and_missing_columns_fail():
    df = feature_frame(25)
    base = score_features(df, factor_metas(), make_config())
    scaled = score_features(df, factor_metas(),
                            make_config(ignition={"enc": 1.2, "dry": 0.8}))  # sum 2
    pd.testing.assert_series_equal(base.frame["risk"], scaled.frame["risk"])
    assert any("ignition" in w for w in scaled.meta["warnings"])
    assert scaled.meta["weights_effective"]["ignition"] == {"enc": 0.6, "dry": 0.4}
    with pytest.raises(ScoreError, match="enc"):
        score_features(df.drop(columns="enc"), factor_metas(), make_config())


def test_changing_a_config_weight_changes_the_score():
    df = feature_frame(40)
    base = score_features(df, factor_metas(), make_config())
    more_enc = score_features(df, factor_metas(),
                              make_config(ignition={"enc": 0.9, "dry": 0.1}))
    diff = more_enc.frame["risk"] - base.frame["risk"]
    assert (diff.abs() > 1e-9).any()
    # P rises exactly where encroachment ranks above dryness (independent check)
    up = base.frame["norm_enc"] > base.frame["norm_dry"]
    assert (more_enc.frame.loc[up, "p_ignition"] > base.frame.loc[up, "p_ignition"]).all()


def test_registering_a_new_factor_needs_only_a_column_meta_and_weight():
    from hatkalkani.model.score import FactorMeta

    df = feature_frame(30)
    df["field_feedback"] = np.arange(len(df), dtype=float)
    metas = factor_metas({"field_feedback": FactorMeta(
        "field_feedback", "ignition", "higher", "static", "Saha", "Field")})
    # dominant weight: only the two consequence factors could out-contribute it
    cfg = make_config(ignition={"enc": 0.1, "dry": 0.1, "field_feedback": 0.8})
    res = score_features(df, metas, cfg)
    assert "contrib_field_feedback" in res.frame
    assert res.frame["contrib_field_feedback"].iloc[-1] > 0  # highest rank -> pushes up
    assert any(t["key"] == "field_feedback" for t in json.loads(res.frame["top_factors"].iloc[-1]))
    with pytest.raises(ScoreError, match="field_feedback"):
        score_features(df.drop(columns="field_feedback"), metas, cfg)


def test_tier_proportions_follow_config_percentiles():
    risk = np.random.default_rng(3).permutation(np.linspace(1, 99, 1000))
    pct, tier = assign_tiers(risk, {"kritik": 0.95, "yuksek": 0.80, "orta": 0.50})
    counts = pd.Series(tier).value_counts().to_dict()
    assert counts == {"kritik": 50, "yuksek": 150, "orta": 300, "dusuk": 500}
    order = np.argsort(risk)
    rank_of_tier = {"dusuk": 0, "orta": 1, "yuksek": 2, "kritik": 3}
    assert np.all(np.diff([rank_of_tier[t] for t in tier[order]]) >= 0)  # monotone in risk
    assert np.all(np.diff(pct[order]) > 0)


def test_tied_scores_never_split_across_tiers():
    risk = np.array([10.0] * 6 + [50.0] * 3 + [90.0])
    _, tier = assign_tiers(risk, {"kritik": 0.95, "yuksek": 0.80, "orta": 0.50})
    for v in np.unique(risk):
        assert len(set(tier[risk == v])) == 1


def test_invalid_config_is_rejected():
    for over, msg in [
        ({"combine": "max"}, "combine"),
        ({"normalization": "zscore"}, "normalization"),
        ({"ignition": {"enc": -0.1, "dry": 1.1}}, "negative"),
        ({"ignition": {"enc": 0.0, "dry": 0.0}}, "ignition"),
        ({"tiers": {"kritik": 0.8, "yuksek": 0.9, "orta": 0.5}}, "tiers"),
        ({"tiers": {"kritik": 0.95, "yuksek": 0.8}}, "orta"),
    ]:
        with pytest.raises(ConfigError, match=msg):
            model_config_from_dict(config_dict(**over))


def test_scoring_is_deterministic():
    df = feature_frame(50)
    a = score_features(df, factor_metas(), make_config())
    b = score_features(df.copy(), factor_metas(), make_config())
    pd.testing.assert_frame_equal(a.frame, b.frame)
    assert a.meta == b.meta
