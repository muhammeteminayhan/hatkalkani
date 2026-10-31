"""AOI-internal percentile normalisation and the documented NaN policy (ADR-010).

Percentile = mid-rank: (#values below + 0.5 * #equal values) / n over the finite values.
Ties share one value (the F3-1 data have 47 % zeros in vegetation_encroachment), the AOI
mean of every normalised factor is exactly 0.5 and a constant factor maps to 0.5.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

DIRECTIONS = ("higher", "lower")
# Reference segment for contributions: every factor at the AOI mid-percentile.
REFERENCE_PERCENTILE = 0.5
# NaN reason -> normalised value. "all_water": the corridor has no vegetation at all, so
# the vegetation-based factor is at its least risky (F3-1 recommendation).
NAN_FILL_BY_REASON: dict[str, float] = {"all_water": 0.0}
# Any other documented reason means "no information": the neutral reference value, which
# contributes exactly 0 points; the segment is flagged in the `imputed` column.
NAN_FILL_DEFAULT = REFERENCE_PERCENTILE


def percentile_rank(values: np.ndarray, *, direction: str) -> np.ndarray:
    """Mid-rank AOI percentile in (0, 1); ``direction="lower"`` ranks low raw values high.

    NaN stays NaN (filled later by :func:`fill_missing`).
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {DIRECTIONS}, got {direction!r}")
    x = np.asarray(values, dtype="float64")
    out = np.full(x.shape, np.nan)
    finite = np.isfinite(x)
    n = int(finite.sum())
    if n == 0:
        return out
    v = x[finite] if direction == "higher" else -x[finite]
    ranks = pd.Series(v).rank(method="average").to_numpy()  # 1..n, ties averaged
    out[finite] = (ranks - 0.5) / n
    return out


def parse_nan_reasons(cell: str) -> dict[str, str]:
    """``"fuel_dryness:all_water;slope:no_dem_pixels"`` -> {factor: reason}."""
    out: dict[str, str] = {}
    for part in str(cell or "").split(";"):
        if ":" in part:
            name, reason = part.split(":", 1)
            out[name.strip()] = reason.strip()
    return out


def fill_missing(
    norm: np.ndarray,
    reasons: list[str],
    *,
    fill_by_reason: Mapping[str, float] = NAN_FILL_BY_REASON,
    default: float = NAN_FILL_DEFAULT,
) -> np.ndarray:
    """Replace NaN percentiles following the reason recorded by the feature build."""
    out = np.asarray(norm, dtype="float64").copy()
    for i in np.flatnonzero(np.isnan(out)):
        out[i] = fill_by_reason.get(reasons[i], default)
    return out
