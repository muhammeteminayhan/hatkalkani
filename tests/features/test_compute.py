"""Pure computations with hand-checkable inputs."""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from hatkalkani.features.compute import (
    chm_window_metrics,
    dedupe_fire_cells,
    ecdf_midrank,
    percentile_by_group,
    quartic_kde_per_km2,
    topo_multiplier,
)

KW = dict(nodata=255, min_canopy_m=4.0, strike_margin_m=1.0, strike_max_m=30.0,
          min_cluster_px=4)


def _grid(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rows = np.indices(h.shape)[0]
    return np.ones_like(h, dtype=bool), np.abs(rows - 30) + 0.5  # d(row r) = |r - 30| + 0.5


def test_chm_metrics_encroachment_and_clusters():
    h = np.zeros((60, 40), dtype=np.uint8)
    inside, dist = _grid(h)
    h[28:32, 0:10] = 10  # 40 px, d <= 1.5: in band, strike, tall
    h[45:48, 20:23] = 20  # 9 px at d 15.5..17.5: strike, tall, outside 3 m band
    h[33, 30:35] = 3  # 5 px shrub at d 3.5: strike (3 >= 4.5? no) -> not strike
    h[30, 30:35] = 2  # 5 px shrub at d 0.5: strike, not tall; in band, not encroaching
    h[5, 5] = 50  # single tall pixel: cluster of 1 < 4
    m = chm_window_metrics(h, inside, dist, clearance_m=3.0, **KW)
    band_px = 5 * 40  # rows with d <= 3 -> 28..32
    assert m.band_px == band_px
    assert m.encroach == pytest.approx(40 / band_px)
    assert m.strike == 3.0 and m.strike_tall == 2
    assert m.valid_frac == 1.0 and m.encroach_reason == "" and m.strike_reason == ""


def test_chm_metrics_nodata_and_empty_band():
    h = np.full((10, 10), 255, dtype=np.uint8)
    inside, dist = np.ones_like(h, dtype=bool), np.full(h.shape, 10.0)
    m = chm_window_metrics(h, inside, dist, clearance_m=3.0, **KW)
    assert math.isnan(m.encroach) and math.isnan(m.strike)
    assert m.encroach_reason == m.strike_reason == "no_chm_coverage"
    h[:] = 0
    m = chm_window_metrics(h, inside, dist, clearance_m=3.0, **KW)
    assert math.isnan(m.encroach) and m.encroach_reason == "no_chm_in_clearance_band"
    assert m.strike == 0.0
    m = chm_window_metrics(h, np.zeros_like(inside), dist, clearance_m=3.0, **KW)
    assert m.encroach_reason == "empty_corridor"


def test_quartic_kde_values():
    h = 2000.0
    peak = 3.0 / (math.pi * h * h) * 1e6
    pts = np.array([[0.0, 0.0], [1000.0, 0.0], [5000.0, 0.0]])
    dens, n = quartic_kde_per_km2(np.array([[0.0, 0.0]]), pts, h)
    assert dens[0] == pytest.approx(peak * (1 + (1 - 0.25) ** 2))
    assert n.tolist() == [2]
    empty, n0 = quartic_kde_per_km2(np.array([[0.0, 0.0]]), np.empty((0, 2)), h)
    assert empty.tolist() == [0.0] and n0.tolist() == [0]
    with pytest.raises(ValueError):
        quartic_kde_per_km2(np.zeros((1, 2)), pts, 0)


def test_quartic_kde_integrates_to_one_detection():
    h, step = 500.0, 10.0
    xs = np.arange(-h, h + step, step)
    gx, gy = np.meshgrid(xs, xs)
    dens, _ = quartic_kde_per_km2(np.column_stack([gx.ravel(), gy.ravel()]),
                                  np.array([[0.0, 0.0]]), h)
    assert dens.sum() * (step * step) / 1e6 == pytest.approx(1.0, rel=1e-3)


def test_dedupe_fire_cells():
    x = np.array([10.0, 20.0, 10.0, 400.0])
    y = np.array([10.0, 30.0, 10.0, 10.0])
    d = np.array([date(2020, 7, 1), date(2020, 7, 1), date(2020, 7, 2), date(2020, 7, 1)])
    assert dedupe_fire_cells(x, y, d, 375.0).tolist() == [True, False, True, True]


def test_ecdf_midrank_and_multiplier():
    ref = np.array([-1.0, 0.0, 1.0, 2.0])
    out = ecdf_midrank(ref, np.array([0.0, -5.0, 5.0, np.nan]))
    assert out[:3].tolist() == [0.375, 0.0, 1.0] and np.isnan(out[3])
    with pytest.raises(ValueError):
        ecdf_midrank(np.array([2.0, 1.0]), np.array([1.0]))
    assert topo_multiplier(np.array([0.0, 0.5, 1.0])).tolist() == [0.5, 1.0, 1.5]


def test_percentile_by_group():
    keys = pd.Series(["a"] * 5 + ["b"] * 2)
    vals = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 10.0, np.nan])
    out = percentile_by_group(keys, vals, 95)
    assert out.loc["a", "p"] == pytest.approx(np.percentile([1, 2, 3, 4, 5], 95))
    assert out.loc["b", "n"] == 1
