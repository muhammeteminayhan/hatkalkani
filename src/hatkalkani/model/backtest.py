"""Retrospective test of the as_of risk map against the next fire season (spec section 5).

Protocol: ADR-013 (registered before the real-data run). The risk map of
``periods.backtest_asof`` is compared with NASA FIRMS VIIRS detections of
``periods.backtest_season``: detections are clustered in space-time, each cluster's first
overpass is the ignition proxy, and for clusters within ``buffers_m.event_line_distance``
of a segment the nearest segment's risk percentile is read. Shares of events in the top
10 % / 20 % of segments are compared with the share expected by chance (lift), with
bootstrap and exact binomial intervals and the same numbers for simple baselines.

CLI (pipeline stage ``backtest``)::

    uv run python -m hatkalkani.model.backtest --aoi izmir_menderes

writes ``backtest.json`` and ``events_<season year>.geojson`` under
``data/processed/<aoi>/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import yaml
from scipy import stats
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from hatkalkani.export import write_geojson
from hatkalkani.features.asof import LOCAL_TZ, AsOf, local_day_start
from hatkalkani.features.build import read_features
from hatkalkani.features.context import VIIRS_PRODUCT_PREFIX, firms_type_filter
from hatkalkani.ingest import common
from hatkalkani.model.config import load_model_config
from hatkalkani.model.run import read_risk
from hatkalkani.model.score import (
    combine_risk,
    factor_metas_from_rows,
    mid_rank_percentile,
    score_features,
)

log = logging.getLogger("hatkalkani.model.backtest")

SCHEMA_VERSION = "backtest-0.1"
SHARE_TOL = 1e-9  # top set = percentile >= 1 - share (minus float tolerance)
DEC = 4  # rounding of shares, lifts and intervals in backtest.json
CASE_DAY = date(2025, 6, 29)  # F1-3 I-1: Menderes fire reported (media) as line-caused


class BacktestLeakageError(RuntimeError):
    """The risk map used data stamped at/after the as_of cutoff or after the season start."""


@dataclass(frozen=True)
class BacktestConfig:
    as_of: date
    season: tuple[date, date]
    metric_crs: str
    event_line_distance_m: float
    cluster_distance_m: float
    cluster_gap_days: int
    top_shares: tuple[float, ...]
    bootstrap_n: int
    bootstrap_seed: int
    sensitivity_distances_m: tuple[float, ...]


def load_backtest_config(root: Path) -> BacktestConfig:
    a = yaml.safe_load((root / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    rw = yaml.safe_load((root / "config" / "risk_weights.yaml").read_text(encoding="utf-8"))
    b = rw.get("backtest")
    if not isinstance(b, Mapping):
        raise SystemExit("config/risk_weights.yaml has no `backtest` block (ADR-013)")
    p = a["periods"]
    return BacktestConfig(
        as_of=date.fromisoformat(str(p["backtest_asof"])),
        season=(date.fromisoformat(str(p["backtest_season"][0])),
                date.fromisoformat(str(p["backtest_season"][1]))),
        metric_crs=str(a["metric_crs"]),
        event_line_distance_m=float(a["buffers_m"]["event_line_distance"]),
        cluster_distance_m=float(b["cluster_distance_m"]),
        cluster_gap_days=int(b["cluster_gap_days"]),
        top_shares=tuple(float(s) for s in b["top_shares"]),
        bootstrap_n=int(b["bootstrap_n"]),
        bootstrap_seed=int(b["bootstrap_seed"]),
        sensitivity_distances_m=tuple(float(d) for d in b["sensitivity_line_distance_m"]),
    )


# ----------------------------------------------------------------- pure functions
def cluster_events(xy: np.ndarray, day: np.ndarray, distance_m: float,
                   gap_days: int) -> np.ndarray:
    """Single-linkage space-time clusters: i~j if |xy_i - xy_j| <= distance_m and
    |day_i - day_j| <= gap_days. Labels are numbered by each cluster's first row."""
    n = len(xy)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    pairs = cKDTree(np.asarray(xy, dtype="float64")).query_pairs(r=distance_m,
                                                                 output_type="ndarray")
    d = np.asarray(day, dtype=np.int64)
    if len(pairs):
        pairs = pairs[np.abs(d[pairs[:, 0]] - d[pairs[:, 1]]) <= gap_days]
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])) if len(pairs)
                       else (np.zeros(0), (np.zeros(0, int), np.zeros(0, int))), shape=(n, n))
    _, labels = connected_components(graph, directed=False)
    uniq, first = np.unique(labels, return_index=True)
    rank = np.empty(len(uniq), dtype=np.int64)
    rank[np.argsort(first, kind="stable")] = np.arange(len(uniq))
    return rank[np.searchsorted(uniq, labels)]


def ignition_proxies(det: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """One row per cluster: centroid of the first-overpass detections (ADR-013), dates and
    counts. ``det`` needs x, y, t (UTC timestamps) and day (local date)."""
    d = det.assign(label=labels)
    first_t = d.groupby("label")["t"].transform("min")
    first = d[d["t"] == first_t].groupby("label")[["x", "y"]].mean()
    g = d.groupby("label")
    out = pd.DataFrame({
        "x": first["x"], "y": first["y"],
        "first_time_utc": g["t"].min(), "start_date": g["day"].min(),
        "end_date": g["day"].max(), "n_detections": g.size(),
    })
    return out.sort_index()


def top_mask(pct: np.ndarray, share: float) -> np.ndarray:
    return np.asarray(pct, dtype="float64") >= 1.0 - share - SHARE_TOL


def lift_block(in_top: np.ndarray, expected: float, boot: np.ndarray) -> dict[str, Any]:
    """Share of events in a top set, lift, bootstrap and exact binomial intervals."""
    n = int(len(in_top))
    if n == 0 or expected <= 0:
        return {"share": None, "expected": _r(expected), "lift": None, "ci95": None,
                "n_events": n, "n_in_top": 0, "ci95_binomial": None,
                "p_value_binomial": None}
    k = int(in_top.sum())
    share = k / n
    shares = in_top[boot].mean(axis=1)
    lo, hi = np.percentile(shares / expected, [2.5, 97.5])
    ci_share = stats.binomtest(k, n, p=expected).proportion_ci(confidence_level=0.95,
                                                                method="exact")
    p = stats.binomtest(k, n, p=expected, alternative="greater").pvalue
    return {
        "share": _r(share), "expected": _r(expected), "lift": _r(share / expected),
        "ci95": [_r(lo), _r(hi)], "n_events": n, "n_in_top": k,
        "ci95_binomial": [_r(ci_share.low / expected), _r(ci_share.high / expected)],
        "p_value_binomial": _r(p),
    }


def null_block(n: int, p_top: float, expected: float, rng: np.random.Generator,
               draws: int) -> dict[str, Any]:
    """Chance baseline: share and lift if each of n events fell in the top set with
    probability p_top; ci95 is the 95 % range of the null lift for this many events."""
    if n == 0 or expected <= 0:
        return {"share": _r(p_top), "lift": _r(p_top / expected) if expected else None,
                "ci95": None, "n_events": n}
    lifts = rng.binomial(n, p_top, size=draws) / n / expected
    lo, hi = np.percentile(lifts, [2.5, 97.5])
    return {"share": _r(p_top), "lift": _r(p_top / expected), "ci95": [_r(lo), _r(hi)],
            "n_events": n}


def _r(x: float | None, nd: int = DEC) -> float | None:
    if x is None or not np.isfinite(x):
        return None
    return float(round(float(x), nd))


# ------------------------------------------------------------------- data access
def check_no_leakage(risk_meta: Mapping[str, Any], features_meta: Mapping[str, Any],
                     cfg: BacktestConfig) -> AsOf:
    """Refuse a risk map that is not the configured as_of map or that used later data."""
    as_of = AsOf(cfg.as_of)
    if str(risk_meta.get("as_of")) != cfg.as_of.isoformat():
        raise BacktestLeakageError(f"risk map as_of {risk_meta.get('as_of')!r} != "
                                   f"periods.backtest_asof {cfg.as_of.isoformat()}")
    if str(features_meta.get("as_of")) != cfg.as_of.isoformat():
        raise BacktestLeakageError(f"features as_of {features_meta.get('as_of')!r} != "
                                   f"{cfg.as_of.isoformat()}")
    season_start = local_day_start(cfg.season[0])
    if as_of.cutoff_utc > season_start:
        raise BacktestLeakageError("as_of cutoff falls after the season start")
    for name, prov in (features_meta.get("provenance") or {}).items():
        latest = (prov or {}).get("max_time_used_utc")
        if latest is not None and pd.Timestamp(latest) >= as_of.cutoff_utc:
            raise BacktestLeakageError(f"{name}: data at {latest} is not before the as_of "
                                       f"cutoff {as_of.cutoff_utc.isoformat()}")
    return as_of


def season_detections(firms: pd.DataFrame, cfg: BacktestConfig
                      ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """VIIRS detections of the season's local days, FIRMS type filter applied."""
    t = firms["acq_datetime_utc"]
    if not isinstance(t.dtype, pd.DatetimeTZDtype):
        raise ValueError("FIRMS acq_datetime_utc must be time-zone aware")
    start = local_day_start(cfg.season[0])
    end = local_day_start(cfg.season[1] + timedelta(days=1))
    in_season = (t >= start) & (t < end)
    viirs = firms["product"].astype(str).str.startswith(VIIRS_PRODUCT_PREFIX)
    sel = firms[in_season & viirs]
    keep, type_prov = firms_type_filter(sel)
    sel = sel[keep].sort_values(["acq_datetime_utc", "latitude", "longitude"],
                                kind="mergesort").reset_index(drop=True)
    pts = gpd.GeoSeries(gpd.points_from_xy(sel["longitude"], sel["latitude"]),
                        crs="EPSG:4326").to_crs(cfg.metric_crs)
    det = pd.DataFrame({
        "x": pts.x.to_numpy(dtype="float64"), "y": pts.y.to_numpy(dtype="float64"),
        "t": sel["acq_datetime_utc"].to_numpy(),
        "day": sel["acq_datetime_utc"].dt.tz_convert(LOCAL_TZ).dt.date.to_numpy(),
        "product": sel["product"].astype(str).to_numpy(),
        "frp": (pd.to_numeric(sel["frp"], errors="coerce").to_numpy(dtype="float64")
                if "frp" in sel.columns else np.full(len(sel), np.nan)),
    })
    det["t"] = pd.to_datetime(det["t"], utc=True)
    prov = {
        "window_local": [cfg.season[0].isoformat(), cfg.season[1].isoformat()],
        "n_rows_in_season": int(in_season.sum()),
        "n_viirs_in_season": int((in_season & viirs).sum()),
        "n_used": int(len(det)),
        "products": {k: int(v) for k, v in det["product"].value_counts().sort_index().items()},
        "type_filter": type_prov,
        "min_time_utc": det["t"].min().isoformat() if len(det) else None,
        "max_time_utc": det["t"].max().isoformat() if len(det) else None,
    }
    return det, prov


# ---------------------------------------------------------------------- the test
@dataclass
class BacktestResult:
    summary: dict[str, Any]
    events: gpd.GeoDataFrame


def _rankings(risk: pd.DataFrame, features: pd.DataFrame, fmeta: Mapping[str, Any],
              root: Path) -> dict[str, np.ndarray]:
    """Percentile of every ranking compared (model, baselines, labelled variants)."""
    out = {"model": risk["risk_pct"].to_numpy(dtype="float64")}
    for key, col in (("vegetation_chm", "norm_vegetation_encroachment"),
                     ("tree_shrub_cover", "norm_fuel_continuity"),
                     ("buildings", "norm_wui_exposure"),
                     ("fire_history", "norm_fire_history")):
        out[key] = mid_rank_percentile(risk[col].to_numpy(dtype="float64"))
    out["linear"] = mid_rank_percentile(combine_risk(
        risk["p_ignition"].to_numpy(dtype="float64"),
        risk["consequence"].to_numpy(dtype="float64"), "linear"))
    if "aux_strike_tall_clusters" in features.columns:  # F3-1 O8, labelled sensitivity
        f = features.copy()
        f["strike_trees"] = f["aux_strike_tall_clusters"]
        res = score_features(f, factor_metas_from_rows(fmeta["factors"]),
                             load_model_config(root))
        pct = pd.Series(res.frame["risk_pct"].to_numpy(), index=res.frame["segment_id"])
        out["strike_tall"] = pct.loc[risk["segment_id"]].to_numpy(dtype="float64")
    return out


BASELINE_LABELS = {
    "expected": ("Beklenen değer (rastgele segment)", "Expected value (random segment)"),
    "length": ("Uzunluğa orantılı rastgele", "Random, proportional to line length"),
    "vegetation_chm": ("Yalnız bitki (CHM: hatta yakın yüksek ağaç)",
                       "Vegetation only (CHM: tall vegetation near line)"),
    "tree_shrub_cover": ("Yalnız ağaç/çalı örtüsü (WorldCover)",
                         "Tree/shrub cover only (WorldCover)"),
    "buildings": ("Yalnız bina yakınlığı", "Building proximity only"),
    "fire_history": ("Yalnız geçmiş yangın yoğunluğu", "Past fire density only"),
    "linear": ("Doğrusal birleştirme (aynı ağırlıklar)", "Linear combination (same weights)"),
}


def _distance_table(seg_m: gpd.GeoSeries, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(pts) == 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    tree = shapely.STRtree(seg_m.to_numpy())
    (src, dst), dist = tree.query_nearest(shapely.points(pts), return_distance=True,
                                          all_matches=False)
    order = np.argsort(src, kind="stable")
    return dst[order].astype(np.int64), dist[order]


def run_backtest(aoi_id: str, root: Path | None = None) -> BacktestResult:
    root = Path(root) if root is not None else common.ROOT
    cfg = load_backtest_config(root)
    proc = root / "data" / "processed" / aoi_id
    interim = root / "data" / "interim" / aoi_id
    risk, rmeta = read_risk(proc / f"risk_{cfg.as_of.isoformat()}.parquet")
    features, fmeta = read_features(proc / f"features_{cfg.as_of.isoformat()}.parquet")
    as_of = check_no_leakage(rmeta, fmeta, cfg)
    if risk.crs is None:
        raise ValueError("risk parquet has no CRS")
    risk = risk.reset_index(drop=True)
    seg_m = risk.geometry.to_crs(cfg.metric_crs)
    if not seg_m.crs.is_projected:
        raise ValueError(f"metric_crs {cfg.metric_crs} is not projected")
    n_seg = len(risk)
    length = risk["length_m"].to_numpy(dtype="float64")
    boundary = gpd.read_parquet(proc / "boundary.parquet")
    if boundary.crs is None:
        raise ValueError("boundary.parquet has no CRS")
    district = boundary.to_crs(cfg.metric_crs).union_all()

    det, det_prov = season_detections(pd.read_parquet(interim / "firms.parquet"), cfg)
    xy = det[["x", "y"]].to_numpy()
    labels = cluster_events(xy, np.array([d.toordinal() for d in det["day"]], dtype=np.int64),
                            cfg.cluster_distance_m, cfg.cluster_gap_days)
    clusters = ignition_proxies(det, labels)
    seg_idx, dist = _distance_table(seg_m, clusters[["x", "y"]].to_numpy())
    det_seg, det_dist = _distance_table(seg_m, xy)
    min_any = pd.Series(det_dist).groupby(labels).min().reindex(clusters.index).to_numpy()
    inside = shapely.contains_xy(district, clusters["x"].to_numpy(), clusters["y"].to_numpy())
    pct_model = risk["risk_pct"].to_numpy(dtype="float64")
    ids = risk["segment_id"].astype(str).to_numpy()
    year = cfg.season[0].year
    clusters = clusters.assign(
        inside_aoi=inside, dist_to_line_m=dist, min_dist_any_detection_m=min_any,
        nearest_segment_id=ids[seg_idx] if len(seg_idx) else [],
        risk_pct_nearest=pct_model[seg_idx] if len(seg_idx) else [],
        tier_nearest=risk["tier"].astype(str).to_numpy()[seg_idx] if len(seg_idx) else [],
    )
    clusters["event_id"] = [f"E{year}_{k + 1:03d}" for k in range(len(clusters))]
    max_frp = det.groupby(labels)["frp"].max().reindex(clusters.index)
    universe = clusters[clusters["inside_aoi"]].copy()

    rankings = _rankings(risk, features, fmeta, root)
    rng = np.random.default_rng(cfg.bootstrap_seed)

    def evaluate(distance_m: float, keys: Sequence[str]) -> dict[str, Any]:
        ev = universe[universe["dist_to_line_m"] <= distance_m]
        seg = pd.Index(ids).get_indexer(ev["nearest_segment_id"].to_numpy())
        n = len(ev)
        boot = rng.integers(0, n, size=(cfg.bootstrap_n, n)) if n else np.zeros((0, 0), int)
        res: dict[str, Any] = {"n_events": n}
        for key in keys:
            res[key] = {}
            for share in cfg.top_shares:
                top = top_mask(rankings[key], share)
                res[key][_top_key(share)] = lift_block(top[seg], float(top.mean()), boot)
        # chance baselines on the model's own top sets
        for share in cfg.top_shares:
            top = top_mask(rankings["model"], share)
            exp = float(top.mean())
            res.setdefault("expected", {})[_top_key(share)] = null_block(
                n, exp, exp, rng, cfg.bootstrap_n)
            res.setdefault("length", {})[_top_key(share)] = null_block(
                n, float(length[top].sum() / length.sum()), exp, rng, cfg.bootstrap_n)
            res["model"][_top_key(share)]["expected_length"] = _r(
                float(length[top].sum() / length.sum()))
        return res

    keys = ["model", *[k for k in BASELINE_LABELS if k in rankings],
            *(["strike_tall"] if "strike_tall" in rankings else [])]
    primary = evaluate(cfg.event_line_distance_m, keys)
    sens = {f"{d:.0f}": evaluate(d, keys) for d in cfg.sensitivity_distances_m}

    def baselines(block: Mapping[str, Any]) -> dict[str, Any]:
        out = {}
        for key, (tr, en) in BASELINE_LABELS.items():
            if key not in block:
                continue
            out[key] = {"label_tr": tr, "label_en": en,
                        **{_top_key(s): _baseline_view(block[key][_top_key(s)])
                           for s in cfg.top_shares}}
        return out

    events = _events_frame(universe, max_frp, cfg)
    case = _case_studies(clusters, cfg)
    near = int(primary["n_events"])
    summary = {
        "schema_version": SCHEMA_VERSION,
        "as_of": cfg.as_of.isoformat(),
        "season": f"{cfg.season[0].isoformat()}..{cfg.season[1].isoformat()}",
        "n_events": near,
        "n_events_total": int(len(universe)),
        "event_line_distance_m": cfg.event_line_distance_m,
        **{_top_key(s): primary["model"][_top_key(s)] for s in cfg.top_shares},
        "baselines": baselines(primary),
        "sensitivity_line_distance": {
            "label_tr": "DUYARLILIK ANALİZİ — birincil eşik değildir. Önceden kayıtlı "
                        f"birincil eşik {cfg.event_line_distance_m:.0f} m'dir (ADR-013).",
            "label_en": "SENSITIVITY ANALYSIS — not the primary threshold. The "
                        f"pre-registered primary threshold is {cfg.event_line_distance_m:.0f} "
                        "m (ADR-013).",
            "results": {
                d: {"n_events": b["n_events"],
                    **{_top_key(s): b["model"][_top_key(s)] for s in cfg.top_shares},
                    "baselines": baselines(b)}
                for d, b in sens.items()
            },
        },
        "sensitivity_variants": ({
            "strike_tall": {
                "label_tr": "DUYARLILIK: strike_trees yerine yalnız ≥4 m kümeler "
                            "(aux_strike_tall_clusters; F3-1 O8)",
                "label_en": "SENSITIVITY: strike_trees replaced by clusters >= 4 m only "
                            "(aux_strike_tall_clusters; F3-1 O8)",
                "by_distance_m": {
                    f"{cfg.event_line_distance_m:.0f}": {
                        _top_key(s): primary["strike_tall"][_top_key(s)]
                        for s in cfg.top_shares},
                    **{d: {_top_key(s): b["strike_tall"][_top_key(s)] for s in cfg.top_shares}
                       for d, b in sens.items()},
                },
            }} if "strike_tall" in rankings else {}),
        "case_studies": case,
        "events_summary": {
            "detections": det_prov,
            "n_clusters_all": int(len(clusters)),
            "n_clusters_outside_aoi": int((~clusters["inside_aoi"]).sum()),
            "n_outside_aoi_within_event_distance": int(
                ((~clusters["inside_aoi"]) &
                 (clusters["dist_to_line_m"] <= cfg.event_line_distance_m)).sum()),
            "n_segments": n_seg,
        },
        "method": {
            "events": "FIRMS VIIRS (S-NPP, NOAA-20; SP+NRT) of the season's local days; type 0 "
                      "or missing (ADR-013)",
            "clustering": f"single linkage: <= {cfg.cluster_distance_m:.0f} m and <= "
                          f"{cfg.cluster_gap_days} local days",
            "ignition_proxy": "centroid of the cluster's first-overpass detections",
            "universe": "clusters whose ignition proxy lies inside the district boundary",
            "near_line": "ignition proxy within event_line_distance_m of a segment",
            "risk_percentile": "risk_pct of the nearest segment (ADR-010 mid-rank AOI "
                               "percentile) in the as_of risk map",
            "top_set": "segments with percentile >= 1 - share",
            "expected": "share of segments in the top set (count); expected_length = "
                        "length share",
            "ci95": f"percentile bootstrap over events (B={cfg.bootstrap_n}, "
                    f"seed={cfg.bootstrap_seed}); ci95_binomial = Clopper-Pearson / expected",
            "chance_baselines": "expected/length: lift of the model's top set if events fell "
                                "on random segments (uniform / by length); ci95 = 95 % range "
                                "of that null for this many events",
            "as_of_cutoff_utc": as_of.cutoff_utc.isoformat(),
        },
        "limitations_tr": _limitations_tr(near, len(universe), cfg),
        "limitations_en": _limitations_en(near, len(universe), cfg),
    }
    return BacktestResult(summary=summary, events=events)


def _top_key(share: float) -> str:
    return f"top{round(share * 100):d}"


def _baseline_view(b: Mapping[str, Any]) -> dict[str, Any]:
    keep = ("share", "lift", "ci95", "expected", "n_in_top", "ci95_binomial",
            "p_value_binomial")
    return {k: b[k] for k in keep if k in b}


def _events_frame(universe: pd.DataFrame, max_frp: pd.Series,
                  cfg: BacktestConfig) -> gpd.GeoDataFrame:
    pts = gpd.GeoSeries(gpd.points_from_xy(universe["x"], universe["y"]), crs=cfg.metric_crs)
    near = universe["dist_to_line_m"] <= cfg.event_line_distance_m
    pct = universe["risk_pct_nearest"].astype(float)
    g = gpd.GeoDataFrame({
        "event_id": universe["event_id"].to_numpy(),
        "start_date": [d.isoformat() for d in universe["start_date"]],
        "end_date": [d.isoformat() for d in universe["end_date"]],
        "n_detections": universe["n_detections"].astype(int).to_numpy(),
        "dist_to_line_m": universe["dist_to_line_m"].round(1).to_numpy(),
        "near_line": near.to_numpy(),
        "nearest_segment_id": universe["nearest_segment_id"].astype(str).to_numpy(),
        "risk_pct_nearest": pct.round(4).to_numpy(),
        "tier_nearest": universe["tier_nearest"].astype(str).to_numpy(),
        "in_top10": (near & top_mask(pct.to_numpy(), 0.10)).to_numpy(),
        "in_top20": (near & top_mask(pct.to_numpy(), 0.20)).to_numpy(),
        "min_dist_any_detection_m": universe["min_dist_any_detection_m"].round(1).to_numpy(),
        "first_time_utc": [pd.Timestamp(t).isoformat() for t in universe["first_time_utc"]],
        "max_frp": max_frp.reindex(universe.index).round(2).to_numpy(),
    }, geometry=pts.to_numpy(), crs=cfg.metric_crs)
    return g.to_crs("EPSG:4326")


def _case_studies(clusters: pd.DataFrame, cfg: BacktestConfig) -> list[dict[str, Any]]:
    """F1-3 I-1: 29.06.2025 Menderes fire (line cause reported by media only)."""
    c = clusters[clusters["start_date"] == CASE_DAY]
    pts = gpd.GeoSeries(gpd.points_from_xy(c["x"], c["y"]), crs=cfg.metric_crs).to_crs(
        "EPSG:4326")
    rows = []
    for (_, r), p in zip(c.iterrows(), pts, strict=True):
        rows.append({
            "event_id": r["event_id"], "start_date": r["start_date"].isoformat(),
            "end_date": r["end_date"].isoformat(), "n_detections": int(r["n_detections"]),
            "lon": round(p.x, 5), "lat": round(p.y, 5), "inside_aoi": bool(r["inside_aoi"]),
            "dist_to_line_m": round(float(r["dist_to_line_m"]), 1),
            "min_dist_any_detection_m": round(float(r["min_dist_any_detection_m"]), 1),
            "near_line": bool(r["dist_to_line_m"] <= cfg.event_line_distance_m),
            "nearest_segment_id": str(r["nearest_segment_id"]),
            "risk_pct_nearest": _r(float(r["risk_pct_nearest"])),
            "tier_nearest": str(r["tier_nearest"]),
            "first_time_utc": pd.Timestamp(r["first_time_utc"]).isoformat(),
        })
    return [{
        "name": "29.06.2025 Menderes",
        "source_tr": "F1-3 I-1: hat kaynaklı olduğu yalnız basında (itfaiye raporu aktarımı) "
                     "bildirildi; resmî tespit yok",
        "source_en": "F1-3 I-1: line cause reported by the media only (fire-brigade report "
                     "quoted); no official finding",
        "clusters_starting_that_day": rows,
    }]


def _limitations_tr(n: int, total: int, cfg: BacktestConfig) -> list[str]:
    return [
        f"Olay sayısı küçük: hat yakınında {n} olay (ilçede toplam {total} küme); güven "
        "aralıkları geniştir ve sonuç istatistiksel olarak zayıftır.",
        "FIRMS VIIRS pikseli ~375 m'dir; tespit tutuşma noktası değildir ve ilk uydu geçişi "
        "tutuşmadan saatler sonra olabilir.",
        "Nedeni bilinmeyen tüm yangınlar olaylara dahildir; çoğu hat kaynaklı değildir.",
        "Tarım ve anız yakmaları gürültü katar; FIRMS type filtresi yalnız statik kaynak ve "
        "deniz tespitlerini dışlar.",
        "OSM hatlarının çoğu iletim hattıdır; dağıtım (OG/AG) hatları haritada yoktur. Dağıtım "
        "hattı kaynaklı bir yangın 'hat yakını' sayılmayabilir.",
        "CHM görüntü tarihleri 2016-07-22…2020-02-19 arasıdır (as_of'tan 5–9 yıl önce); ağaç "
        "büyümesi eksik tahmin edilebilir.",
        "Kademeler ve yüzdelikler AOI içinde görelidir; skor bir olasılık değildir.",
        f"Birincil eşik {cfg.event_line_distance_m:.0f} m önceden kayıtlıdır; 1000 ve 2000 m "
        "yalnız duyarlılık analizidir.",
    ]


def _limitations_en(n: int, total: int, cfg: BacktestConfig) -> list[str]:
    return [
        f"Few events: {n} near-line events ({total} clusters in the district); confidence "
        "intervals are wide and the evidence is statistically weak.",
        "FIRMS VIIRS pixels are ~375 m; a detection is not the ignition point and the first "
        "overpass may come hours after ignition.",
        "All fires of unknown cause are included; most are not line-caused.",
        "Agricultural and stubble burning add noise; the FIRMS type filter only removes "
        "static land sources and offshore detections.",
        "Most OSM lines are transmission lines; distribution (MV/LV) lines are missing, so a "
        "fire started by a distribution line may not count as near-line.",
        "CHM imagery dates are 2016-07-22…2020-02-19 (5–9 years before as_of); tree growth "
        "may be underestimated.",
        "Tiers and percentiles are relative within the AOI; the score is not a probability.",
        f"The {cfg.event_line_distance_m:.0f} m primary threshold was pre-registered; 1000 "
        "and 2000 m are sensitivity analyses only.",
    ]


# --------------------------------------------------------------------------- files
def write_outputs(res: BacktestResult, aoi_id: str, root: Path,
                  season_year: int) -> dict[str, Path]:
    proc = root / "data" / "processed" / aoi_id
    path = proc / "backtest.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(json.dumps(res.summary, ensure_ascii=False, allow_nan=False,
                               indent=2).encode("utf-8") + b"\n")
    os.replace(tmp, path)
    events = proc / f"events_{season_year}.geojson"
    write_geojson(res.events, events, precision=6)
    return {"backtest": path, "events": events}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--root", type=Path, default=common.ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("pyogrio").setLevel(logging.WARNING)
    t0 = time.perf_counter()
    res = run_backtest(args.aoi, args.root)
    cfg = load_backtest_config(Path(args.root))
    paths = write_outputs(res, args.aoi, Path(args.root), cfg.season[0].year)
    s = res.summary
    for k in ("top10", "top20"):
        b = s.get(k) or {}
        log.info("%s: share %s expected %s lift %s ci95 %s (n=%s)", k, b.get("share"),
                 b.get("expected"), b.get("lift"), b.get("ci95"), b.get("n_events"))
    log.info("backtest: %d near-line events of %d clusters -> %s, %s (%.1fs)", s["n_events"],
             s["n_events_total"], paths["backtest"].name, paths["events"].name,
             time.perf_counter() - t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
