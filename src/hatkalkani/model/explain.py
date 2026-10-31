"""Factor contributions and the top reasons per segment (risk-model-spec section 3, ADR-010).

A contribution is the exact Shapley value of a factor in "risk of this segment minus risk
of the reference segment" (every factor at the AOI mid-percentile 0.5, risk 50 with the
config weights). Contributions therefore add up to ``risk - 50`` and a factor is positive
exactly when it pushes this segment above a typical one. With the geometric combination
P and C interact, so a share-of-score split (w * f) would credit the heaviest weight in
almost every segment; Shapley values split the interaction fairly.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence

import numpy as np

MAX_PLAYERS = 14  # 2^14 coalitions x segments stays well below a second for the pilot
CONTRIBUTION_DECIMALS = 2  # top_factors values (risk points)


def shapley_values(
    X: np.ndarray, reference: np.ndarray, value: Callable[[np.ndarray], np.ndarray]
) -> np.ndarray:
    """Exact Shapley values per row of ``X`` (n, k) for ``value`` (rows -> scores).

    Coalition S means "factors in S at the segment's own value, the rest at reference".
    """
    X = np.asarray(X, dtype="float64")
    n, k = X.shape
    if k > MAX_PLAYERS:
        raise ValueError(f"{k} weighted factors exceed the exact Shapley limit {MAX_PLAYERS}")
    ref = np.asarray(reference, dtype="float64").reshape(1, k)
    masks = np.arange(1 << k)
    bits = ((masks[:, None] >> np.arange(k)) & 1).astype(bool)  # (2^k, k)
    v = np.empty((len(masks), n))
    for m in masks:
        v[m] = value(np.where(bits[m][None, :], X, ref))
    size = bits.sum(axis=1)
    weight = np.array([math.factorial(s) * math.factorial(k - s - 1) / math.factorial(k)
                       if s < k else 0.0 for s in range(k + 1)])
    phi = np.zeros((n, k))
    for i in range(k):
        without = masks[~bits[:, i]]
        gains = v[without | (1 << i)] - v[without]  # (2^(k-1), n)
        phi[:, i] = (weight[size[without]][:, None] * gains).sum(axis=0)
    return phi


def top_factor_lists(
    contrib: np.ndarray,
    names: Sequence[str],
    labels: Mapping[str, Mapping[str, str]],
    *,
    n: int = 3,
) -> list[list[dict]]:
    """Per row: up to ``n`` factors that raise the score most (rounded contribution > 0).

    Ties keep the config order of ``names``. Rows where nothing raises the score above the
    reference segment get an empty list.
    """
    contrib = np.asarray(contrib, dtype="float64")
    out: list[list[dict]] = []
    order_idx = np.arange(len(names))
    for row in contrib:
        rounded = np.round(row, CONTRIBUTION_DECIMALS)
        order = np.lexsort((order_idx, -rounded))  # descending value, then config order
        items = []
        for j in order:
            if rounded[j] <= 0 or len(items) == n:
                break
            name = names[j]
            lab = labels.get(name, {})
            items.append({
                "key": name,
                "label_tr": str(lab.get("tr", name)),
                "label_en": str(lab.get("en", name)),
                "contribution": float(rounded[j]),
            })
        out.append(items)
    return out
