"""Pure feature computations (arrays in, numbers out; no file or network I/O)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import ndimage
from scipy.spatial import cKDTree

# risk-model-spec section 2 (wind_exposure): gust percentile and the topographic exposure
# multiplier range derived from TPI.
GUST_PERCENTILE = 95.0
TOPO_MULTIPLIER_RANGE = (0.5, 1.5)


# ------------------------------------------------------------------- canopy
@dataclass(frozen=True)
class ChmMetrics:
    encroach: float  # vegetation_encroachment raw (fraction, NaN when undefined)
    strike: float  # strike_trees raw (cluster count, NaN when no CHM coverage)
    strike_tall: int  # strike clusters whose max height >= min canopy height (diagnostic)
    band_px: int  # valid CHM pixels inside the clearance band
    valid_frac: float  # valid CHM pixels / corridor pixels
    encroach_reason: str
    strike_reason: str


def chm_window_metrics(
    h: np.ndarray,
    inside: np.ndarray,
    dist_m: np.ndarray,
    *,
    nodata: int,
    clearance_m: float,
    min_canopy_m: float,
    strike_margin_m: float,
    strike_max_m: float,
    min_cluster_px: int,
) -> ChmMetrics:
    """Encroachment fraction and strike-tree clusters of one segment corridor.

    h: canopy heights (m) of a window; inside: corridor pixels; dist_m: horizontal distance
    of each pixel centre to the segment line. Strike condition (spec section 2):
    h >= d + margin within strike_max_m, 8-connected clusters of >= min_cluster_px pixels.
    """
    n_inside = int(inside.sum())
    if n_inside == 0:
        return ChmMetrics(math.nan, math.nan, 0, 0, 0.0, "empty_corridor", "empty_corridor")
    valid = inside & (h != nodata)
    n_valid = int(valid.sum())
    if n_valid == 0:
        return ChmMetrics(math.nan, math.nan, 0, 0, 0.0, "no_chm_coverage", "no_chm_coverage")
    hf = h.astype(np.float32)
    band = valid & (dist_m <= clearance_m)
    n_band = int(band.sum())
    if n_band:
        encroach, enc_reason = float((hf[band] >= min_canopy_m).mean()), ""
    else:
        encroach, enc_reason = math.nan, "no_chm_in_clearance_band"
    strike = valid & (dist_m <= strike_max_m) & (hf >= dist_m + strike_margin_m)
    labels, k = ndimage.label(strike, structure=np.ones((3, 3), dtype=int))
    n_strike = n_tall = 0
    if k:
        sizes = np.bincount(labels.ravel(), minlength=k + 1)[1:]
        big = sizes >= min_cluster_px
        tallest = np.asarray(ndimage.maximum(hf, labels=labels, index=np.arange(1, k + 1)))
        n_strike = int(big.sum())
        n_tall = int((big & (tallest >= min_canopy_m)).sum())
    return ChmMetrics(
        encroach=encroach,
        strike=float(n_strike),
        strike_tall=n_tall,
        band_px=n_band,
        valid_frac=n_valid / n_inside,
        encroach_reason=enc_reason,
        strike_reason="",
    )


# -------------------------------------------------------------- fire history
def dedupe_fire_cells(
    x: np.ndarray, y: np.ndarray, local_dates: np.ndarray, cell_m: float
) -> np.ndarray:
    """Keep mask: first detection per (local day, cell_m x cell_m metric cell)."""
    if cell_m <= 0:
        raise ValueError("cell_m must be positive")
    key = pd.DataFrame(
        {
            "d": pd.Series(local_dates, dtype="object"),
            "cx": np.floor(np.asarray(x, dtype=float) / cell_m).astype(np.int64),
            "cy": np.floor(np.asarray(y, dtype=float) / cell_m).astype(np.int64),
        }
    )
    return ~key.duplicated(keep="first").to_numpy()


def quartic_kde_per_km2(
    targets: np.ndarray, points: np.ndarray, bandwidth_m: float
) -> tuple[np.ndarray, np.ndarray]:
    """Quartic (biweight) kernel density of `points` evaluated at `targets` (metric x, y).

    K(d) = 3 / (pi h^2) * (1 - (d/h)^2)^2 for d < h, which integrates to 1 over the plane;
    the sum over points is scaled from per m^2 to per km^2. Returns (density, n within h).
    """
    if bandwidth_m <= 0:
        raise ValueError("bandwidth_m must be positive")
    t = np.asarray(targets, dtype=float).reshape(-1, 2)
    p = np.asarray(points, dtype=float).reshape(-1, 2)
    dens = np.zeros(len(t))
    n_in = np.zeros(len(t), dtype=np.int64)
    if len(t) and len(p):
        tree = cKDTree(p)
        for i, nb in enumerate(tree.query_ball_point(t, r=bandwidth_m)):
            if not nb:
                continue
            idx = np.sort(np.asarray(nb, dtype=np.int64))  # fixed summation order
            u = np.hypot(p[idx, 0] - t[i, 0], p[idx, 1] - t[i, 1]) / bandwidth_m
            w = np.where(u < 1.0, (1.0 - u * u) ** 2, 0.0)
            dens[i] = float(w.sum())
            n_in[i] = int((u < 1.0).sum())
    return dens * (3.0 / (math.pi * bandwidth_m**2) * 1e6), n_in


# ------------------------------------------------------------ wind exposure
def ecdf_midrank(reference_sorted: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Mid-rank empirical CDF of `x` within a sorted reference sample, in [0, 1]."""
    ref = np.asarray(reference_sorted, dtype=float)
    if ref.size == 0:
        raise ValueError("empty reference sample")
    if np.any(np.diff(ref) < 0):
        raise ValueError("reference sample must be sorted")
    xv = np.asarray(x, dtype=float)
    lo = np.searchsorted(ref, xv, side="left")
    hi = np.searchsorted(ref, xv, side="right")
    out = (lo + hi) / (2.0 * ref.size)
    return np.where(np.isnan(xv), np.nan, out)


def topo_multiplier(
    cdf: np.ndarray, value_range: tuple[float, float] = TOPO_MULTIPLIER_RANGE
) -> np.ndarray:
    """Linear map of a TPI percentile (0-1) onto the spec's exposure multiplier range."""
    lo, hi = value_range
    return lo + (hi - lo) * np.asarray(cdf, dtype=float)


def percentile_by_group(
    keys: pd.Series, values: pd.Series, q: float
) -> pd.DataFrame:
    """q-th percentile (linear interpolation) and sample size per key."""
    g = pd.DataFrame({"key": keys.to_numpy(), "v": values.to_numpy(dtype=float)})
    g = g[np.isfinite(g["v"])]
    out = g.groupby("key", sort=True)["v"].agg(
        p=lambda s: float(np.percentile(s.to_numpy(), q)), n="size"
    )
    return out
