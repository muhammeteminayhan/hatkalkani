"""Factor contributions (exact Shapley values against the reference segment) and top_factors.

The reference implementation below averages marginal gains over *all permutations*, an
independent route from the subset-weight formula used in ``hatkalkani.model.explain``.
"""

from __future__ import annotations

import itertools
import json
import math

import numpy as np
import pytest
from model_synth import factor_metas, feature_frame, make_config

from hatkalkani.model.explain import shapley_values, top_factor_lists
from hatkalkani.model.score import combine_risk, score_features


def permutation_shapley(x: np.ndarray, ref: np.ndarray, value) -> np.ndarray:
    k = len(x)
    phi = np.zeros(k)
    perms = list(itertools.permutations(range(k)))
    for perm in perms:
        cur = ref.copy()
        prev = value(cur)
        for i in perm:
            cur[i] = x[i]
            now = value(cur)
            phi[i] += now - prev
            prev = now
    return phi / len(perms)


def _value_fn(w_ign: np.ndarray, w_con: np.ndarray, mode: str):
    def value(m: np.ndarray) -> np.ndarray:
        m2 = np.atleast_2d(m)
        p = (m2 * w_ign).sum(axis=1)
        c = (m2 * w_con).sum(axis=1)
        return combine_risk(p, c, mode)

    return value


@pytest.mark.parametrize("mode", ["geometric", "linear"])
def test_fast_shapley_matches_permutation_definition(mode):
    rng = np.random.default_rng(11)
    w_ign = np.array([0.5, 0.3, 0.2, 0.0, 0.0])
    w_con = np.array([0.0, 0.0, 0.0, 0.6, 0.4])
    X = rng.random((6, 5))
    ref = np.full(5, 0.5)
    value = _value_fn(w_ign, w_con, mode)
    fast = shapley_values(X, ref, value)
    for r in range(len(X)):
        slow = permutation_shapley(X[r], ref.copy(), lambda m: float(value(m)[0]))
        np.testing.assert_allclose(fast[r], slow, atol=1e-10)
    # efficiency: contributions add up to risk minus the reference segment's risk
    np.testing.assert_allclose(fast.sum(axis=1), value(X) - value(ref)[0], atol=1e-10)


def test_linear_contributions_have_closed_form():
    w_ign = np.array([0.7, 0.3, 0.0])
    w_con = np.array([0.0, 0.0, 1.0])
    X = np.random.default_rng(5).random((8, 3))
    phi = shapley_values(X, np.full(3, 0.5), _value_fn(w_ign, w_con, "linear"))
    want = 100 * (0.6 * w_ign + 0.4 * w_con) * (X - 0.5)
    np.testing.assert_allclose(phi, want, atol=1e-12)


def test_null_and_symmetric_players():
    w_ign = np.array([0.5, 0.5, 0.0])  # players 0 and 1 symmetric
    w_con = np.array([0.0, 0.0, 1.0])
    X = np.array([[0.9, 0.9, 0.7], [0.2, 0.2, 0.1]])
    phi = shapley_values(X, np.full(3, 0.5), _value_fn(w_ign, w_con, "geometric"))
    np.testing.assert_allclose(phi[:, 0], phi[:, 1], atol=1e-12)
    X2 = X.copy()
    X2[:, 1] = 0.5  # a factor sitting exactly at the reference contributes nothing
    phi2 = shapley_values(X2, np.full(3, 0.5), _value_fn(w_ign, w_con, "geometric"))
    np.testing.assert_allclose(phi2[:, 1], 0.0, atol=1e-12)


def test_score_contributions_sum_to_risk_minus_reference():
    res = score_features(feature_frame(60), factor_metas(), make_config())
    fr = res.frame
    contrib = fr[[c for c in fr.columns if c.startswith("contrib_")]].sum(axis=1)
    np.testing.assert_allclose(contrib, fr["risk"] - res.meta["reference"]["risk"], atol=1e-9)
    assert res.meta["reference"]["risk"] == pytest.approx(50.0)  # all factors at 0.5


def test_top_factor_lists_order_sign_labels_and_ties():
    names = ["a", "b", "c", "d"]
    labels = {n: {"tr": n.upper() + "-tr", "en": n.upper() + "-en"} for n in names}
    contrib = np.array([
        [1.0, 5.0, 3.0, 4.0],  # -> b, d, c
        [-1.0, 2.0, -3.0, -0.5],  # only one factor raises the score
        [2.0, 2.0, 1.0, 0.0],  # tie -> config order (a before b)
        [-1.0, -2.0, -3.0, -4.0],  # nothing raises the score -> empty list
    ])
    lists = top_factor_lists(contrib, names, labels, n=3)
    assert [t["key"] for t in lists[0]] == ["b", "d", "c"]
    assert [t["key"] for t in lists[1]] == ["b"]
    assert [t["key"] for t in lists[2]] == ["a", "b", "c"]
    assert lists[3] == []
    assert lists[0][0] == {"key": "b", "label_tr": "B-tr", "label_en": "B-en", "contribution": 5.0}


def test_score_top_factors_are_json_with_api_keys():
    res = score_features(feature_frame(40), factor_metas(), make_config())
    for raw, row in zip(res.frame["top_factors"], res.frame.itertuples(), strict=True):
        items = json.loads(raw)
        assert len(items) <= 3
        vals = [t["contribution"] for t in items]
        assert vals == sorted(vals, reverse=True) and all(v > 0 for v in vals)
        for t in items:
            assert set(t) == {"key", "label_tr", "label_en", "contribution"}
            assert math.isclose(t["contribution"], getattr(row, f"contrib_{t['key']}"),
                                abs_tol=0.005)
