"""Retrospective test of the as_of risk map against the next fire season (spec section 5).

Protocol: ADR-013 and its FIX-F3 note. The 500 m primary threshold dates from the project
skeleton; the rest of the protocol was committed together with the first result. The risk
map of ``periods.backtest_asof`` is compared with NASA FIRMS VIIRS detections of
``periods.backtest_season``: detections are clustered in space-time, each cluster's first
overpass is the ignition proxy, and for clusters within ``buffers_m.event_line_distance``
of a segment the nearest segment's risk percentile is read. Shares of events in the top
10 % / 20 % of segments are compared with the share expected by chance (lift), with
bootstrap and exact binomial intervals and the same numbers for simple baselines.
Time-stamped inputs after the as_of cutoff are refused; static layers that do not predate
as_of (current building and line snapshots) are declared in ``leakage``, and ``verdict``
says whether the season had enough near-line events to inform at all.

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
import re
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

SCHEMA_VERSION = "backtest-0.2"  # 0.2 (FIX-F3): verdict, leakage, ci95 null if degenerate
SHARE_TOL = 1e-9  # top set = percentile >= 1 - share (minus float tolerance)
DEC = 4  # rounding of shares, lifts and intervals in backtest.json
CASE_DAY = date(2025, 6, 29)  # F1-3 I-1: Menderes fire reported (media) as line-caused

# REV-F3F4 O2: with k in {0, n} every bootstrap resample has the same share, so the
# percentile interval collapses to one point; it is written as null with this note.
# Invariant of backtest.json: ci95 is null exactly when ci95_note is set.
CI_NOTE_DEGENERATE = "degenerate"
CI_NOTE_NO_EVENTS = "no_events"
CI_NOTE_EMPTY_TOP = "empty_top_set"  # the ranking has no segment in the top set (ties)

# Verdict (FIX-F3): a backtest informs only with at least this many near-line events.
# From n = 38 on, a one-sided exact binomial test (alpha 0.05) keeps >= 80 % power to
# detect lift 2 in the top 20 % (share 0.40 vs 0.20); test_backtest recomputes it.
MIN_EVENTS_INFORMATIVE = 38
VERDICT_RULE = ("informative iff n_events >= {n}: from n = {n} on, a one-sided exact "
                "binomial test (alpha 0.05) keeps >= 80 % power to detect lift 2 in the top "
                "20 % (share 0.40 vs 0.20)")

# REV-F3F4 D2: what the repository can show about the registration of the protocol.
PRIMARY_DISTANCE_SINCE = (500.0, "c423a81")  # event_line_distance fixed since the skeleton

# REV-F3F4 Y1: a static layer has no observation time. It is declared (not refused: there
# is no as_of snapshot to use instead) when its temporal_status says "after_", when its
# release, snapshot or imagery date is on or after as_of, or when that date is unknown for
# a layer that changes over time (lines, boundary, CHM).
AFTER_STATUS_TOKEN = "after_"
RELEASE_KEYS = ("overture_release", "release", "snapshot_date", "access_date")
# static inputs outside the feature registry: layer -> (MANIFEST `kaynak` values, users)
BASE_LAYERS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "lines": (("osm_power_lines", "edas"), ("segments", "all_factors", "near_line_events")),
    "boundary": (("osm_boundary",), ("segments", "event_universe")),
}
LAYER_LABELS = {"buildings": ("bina", "building"), "lines": ("hat/segment", "line/segment"),
                "boundary": ("ilçe sınırı", "district boundary"),
                "chm": ("ağaç yüksekliği (CHM)", "canopy height (CHM)")}
SOURCE_LABELS = {"overture": "Overture", "osm": "OSM", "osm_power_lines": "OSM",
                 "osm_boundary": "OSM", "edas": "EDAŞ", "meta_wri_chm": "Meta/WRI"}
TIME_VARYING_LABELS = {"fire_history": ("FIRMS", "FIRMS"),
                       "fuel_dryness": ("Sentinel-2", "Sentinel-2"),
                       "wind_exposure": ("rüzgâr", "wind")}
# single-factor baselines: ranking key -> factor (spec section 5 b, c and extras)
BASELINE_FACTORS = {"vegetation_chm": "vegetation_encroachment",
                    "tree_shrub_cover": "fuel_continuity",
                    "buildings": "wui_exposure",
                    "fire_history": "fire_history"}
CHM_FACTORS = ("vegetation_encroachment", "strike_trees")


class BacktestLeakageError(RuntimeError):
    """The risk map used data stamped at/after the as_of cutoff or after the season start."""


@dataclass(frozen=True)
class LeakageCheck:
    """Result of :func:`check_no_leakage`: the as_of and the declared static layers."""

    as_of: AsOf
    static_after_as_of: tuple[dict[str, Any], ...]


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
    """Share of events in a top set, lift, bootstrap and exact binomial intervals.

    With k in {0, n} the bootstrap interval is degenerate (every resample has the same
    share): ``ci95`` is None and ``ci95_note`` says why; ``ci95_binomial`` still holds."""
    n = int(len(in_top))
    if n == 0 or expected <= 0:
        return {"share": None, "expected": _r(expected), "lift": None, "ci95": None,
                "ci95_note": CI_NOTE_NO_EVENTS if n == 0 else CI_NOTE_EMPTY_TOP,
                "n_events": n, "n_in_top": 0, "ci95_binomial": None,
                "p_value_binomial": None}
    k = int(in_top.sum())
    share = k / n
    ci: list[float | None] | None = None
    note = CI_NOTE_DEGENERATE
    if 0 < k < n:
        shares = in_top[boot].mean(axis=1)
        lo, hi = np.percentile(shares / expected, [2.5, 97.5])
        ci, note = [_r(lo), _r(hi)], None
    ci_share = stats.binomtest(k, n, p=expected).proportion_ci(confidence_level=0.95,
                                                                method="exact")
    p = stats.binomtest(k, n, p=expected, alternative="greater").pvalue
    return {
        "share": _r(share), "expected": _r(expected), "lift": _r(share / expected),
        "ci95": ci, "ci95_note": note, "n_events": n, "n_in_top": k,
        "ci95_binomial": [_r(ci_share.low / expected), _r(ci_share.high / expected)],
        "p_value_binomial": _r(p),
    }


def null_block(n: int, p_top: float, expected: float, rng: np.random.Generator,
               draws: int) -> dict[str, Any]:
    """Chance baseline: share and lift if each of n events fell in the top set with
    probability p_top; ci95 is the 95 % range of the null lift for this many events."""
    if n == 0 or expected <= 0:
        return {"share": _r(p_top), "lift": _r(p_top / expected) if expected else None,
                "ci95": None,
                "ci95_note": CI_NOTE_NO_EVENTS if n == 0 else CI_NOTE_EMPTY_TOP,
                "n_events": n}
    lifts = rng.binomial(n, p_top, size=draws) / n / expected
    lo, hi = np.percentile(lifts, [2.5, 97.5])
    return {"share": _r(p_top), "lift": _r(p_top / expected), "ci95": [_r(lo), _r(hi)],
            "ci95_note": None, "n_events": n}


def verdict(n_events: int, min_events: int = MIN_EVENTS_INFORMATIVE) -> dict[str, Any]:
    """Whether the season had enough near-line events to inform (MIN_EVENTS_INFORMATIVE)."""
    if n_events >= min_events:
        return {
            "informative": True, "n_events": n_events, "min_events": min_events,
            "reason_tr": f"Bilgi verir: hat yakınında {n_events} olay var (eşik "
                         f"{min_events}). Sonucu lift ve güven aralıklarıyla birlikte okuyun.",
            "reason_en": f"Informative: {n_events} near-line events (threshold "
                         f"{min_events}). Read the result together with the lift and its "
                         "intervals.",
        }
    return {
        "informative": False, "n_events": n_events, "min_events": min_events,
        "reason_tr": f"Bilgi vermiyor: hat yakınında yalnız {n_events} olay var; en az "
                     f"{min_events} gerekir. Bu eşik, üst %20 kümesinde 2 katlık lifti tek "
                     "yönlü kesin binom testiyle (α = 0,05) en az %80 güçle saptamak için "
                     "gereken olay sayısıdır. Bu sonuç modeli ne doğrular ne çürütür.",
        "reason_en": f"Not informative: only {n_events} near-line events; at least "
                     f"{min_events} are needed. That is the number of events from which a "
                     "one-sided exact binomial test (α = 0.05) has at least 80% power to "
                     "detect lift 2 in the top 20% set. This result neither confirms nor "
                     "refutes the model.",
    }


def _r(x: float | None, nd: int = DEC) -> float | None:
    if x is None or not np.isfinite(x):
        return None
    return float(round(float(x), nd))


# ----------------------------------------------------------- leakage declaration
def _leading_date(value: Any) -> date | None:
    """ISO date at the start of a release or snapshot label ('2026-10-21.0' -> 2026-10-21)."""
    m = re.match(r"\s*(\d{4}-\d{2}-\d{2})", str(value)) if value else None
    try:
        return date.fromisoformat(m.group(1)) if m else None
    except ValueError:
        return None


def _static_entry(layer: str, source: Any, release: Any, used_by: Sequence[str],
                  basis: str, release_date: date | None = None) -> dict[str, Any]:
    rdate = release_date or _leading_date(release)
    tr, en = LAYER_LABELS.get(layer, (layer, layer))
    return {"layer": layer, "label_tr": tr, "label_en": en,
            "source": None if source is None else str(source),
            "release": None if release is None else str(release),
            "release_date": rdate.isoformat() if rdate else None,
            "used_by": list(used_by), "basis": basis}


def static_layers_after_as_of(features_meta: Mapping[str, Any],
                              base_layers: Sequence[Mapping[str, Any]], as_of: date,
                              chm_dates: Mapping[str, Any] | None = None
                              ) -> list[dict[str, Any]]:
    """Static inputs that are not shown to predate ``as_of`` (REV-F3F4 Y1).

    Feature provenance entries without an observation time are grouped by input file and
    declared when ``temporal_status`` contains "after_", when a release date
    (``RELEASE_KEYS``) is on or after as_of, or when a ``static_<year>`` status is not
    before the as_of year. Base layers (segments, district: MANIFEST access date) and the
    CHM imagery (risk meta ``chm_dates``) are declared when their date is on or after
    as_of or unknown."""
    iso = as_of.isoformat()
    groups: dict[str, dict[str, Any]] = {}
    for name, prov in sorted((features_meta.get("provenance") or {}).items()):
        prov = prov or {}
        if prov.get("max_time_used_utc") is not None or prov.get("status") == "unavailable":
            continue  # time-stamped (refused above when late) or not computed
        status = str(prov.get("temporal_status") or "")
        release = next((prov[k] for k in RELEASE_KEYS if prov.get(k)), None)
        rdate = _leading_date(release)
        reasons = []
        if AFTER_STATUS_TOKEN in status:
            reasons.append(f"temporal_status {status}")
        if rdate is not None and rdate >= as_of:
            reasons.append(f"release date {rdate.isoformat()} >= as_of {iso}")
        year = re.fullmatch(r"static_(\d{4})", status)
        if year and int(year.group(1)) >= as_of.year:
            reasons.append(f"static year {year.group(1)} >= as_of year {as_of.year}")
            release = release or year.group(1)
        if not reasons:
            continue
        layer = Path(str(prov.get("file") or name)).stem
        g = groups.setdefault(layer, {"source": prov.get("source"), "release": release,
                                      "factors": [], "reasons": []})
        g["factors"].append(name)
        g["reasons"] += [r for r in reasons if r not in g["reasons"]]
    out = []
    for layer, g in groups.items():
        used = [*g["factors"], *(f"baselines.{b}" for b, f in BASELINE_FACTORS.items()
                                 if f in g["factors"])]
        out.append(_static_entry(layer, g["source"], g["release"], used,
                                 "; ".join(g["reasons"])))
    if chm_dates is not None:
        lo, hi = _leading_date(chm_dates.get("acq_min")), _leading_date(chm_dates.get("acq_max"))
        used = [*CHM_FACTORS, "baselines.vegetation_chm"]
        if hi is None:
            out.append(_static_entry("chm", "meta_wri_chm", None, used,
                                     "imagery date unknown; cannot show it predates as_of"))
        elif hi >= as_of:
            out.append(_static_entry("chm", "meta_wri_chm", f"{lo}…{hi}", used,
                                     f"imagery dates up to {hi} >= as_of {iso}", hi))
    for b in base_layers:
        rdate = _leading_date(b.get("release"))
        if rdate is None:
            basis = "snapshot date unknown (no MANIFEST record); cannot show it predates as_of"
        elif rdate >= as_of:
            basis = f"snapshot (access) date {rdate.isoformat()} >= as_of {iso}"
        else:
            continue
        out.append(_static_entry(str(b["layer"]), b.get("source"), b.get("release"),
                                 b.get("used_by") or [], basis))
    return out


def base_layer_dates(root: Path, aoi_id: str) -> list[dict[str, Any]]:
    """Snapshot dates of the static inputs behind segments and the district boundary.

    The date is the MANIFEST access date (``tarih``) of the raw file; OSM is a live
    database, so the access date is the snapshot date. Only rows of this AOI are used
    (EDAŞ files are AOI-specific by definition); with several rows the latest date wins."""
    rows = common.read_manifest(root)
    out = []
    for layer, (sources, used_by) in BASE_LAYERS.items():
        hits = [r for r in rows if r.get("kaynak") in sources and (
            r.get("kaynak") == "edas"
            or f"/{aoi_id}/" in "/" + str(r.get("yerel_yol", "")).replace("\\", "/"))]
        dated = sorted((d, str(r["kaynak"])) for r in hits
                       if (d := _leading_date(r.get("tarih"))) is not None)
        out.append({"layer": layer, "source": dated[-1][1] if dated else None,
                    "release": dated[-1][0].isoformat() if dated else None,
                    "used_by": list(used_by)})
    return out


def check_no_leakage(risk_meta: Mapping[str, Any], features_meta: Mapping[str, Any],
                     cfg: BacktestConfig, base_layers: Sequence[Mapping[str, Any]] = ()
                     ) -> LeakageCheck:
    """Refuse a risk map that is not the configured as_of map or that used time-stamped
    data at/after the cutoff; collect the static layers that do not predate as_of."""
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
    static = static_layers_after_as_of(features_meta, base_layers, cfg.as_of,
                                       risk_meta.get("chm_dates"))
    return LeakageCheck(as_of=as_of, static_after_as_of=tuple(static))


def _join(items: Sequence[str], last: str) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} {last} {items[-1]}"


def _layer_phrase(e: Mapping[str, Any], lang: str) -> str:
    label = e["label_tr"] if lang == "tr" else e["label_en"]
    src = SOURCE_LABELS.get(str(e.get("source")), e.get("source"))
    when = e.get("release") or ("tarih bilinmiyor" if lang == "tr" else "date unknown")
    return f"{label} ({src} {when})" if src else f"{label} ({when})"


def _uses_building_baseline(static: Sequence[Mapping[str, Any]]) -> bool:
    return any("baselines.buildings" in e.get("used_by", ()) for e in static)


def leakage_block(check: LeakageCheck, features_meta: Mapping[str, Any]) -> dict[str, Any]:
    """``leakage`` field of backtest.json: what predates the cutoff and what does not."""
    prov = features_meta.get("provenance") or {}
    tv = [{"layer": n, "max_time_used_utc": str(p["max_time_used_utc"])}
          for n, p in sorted(prov.items()) if (p or {}).get("max_time_used_utc") is not None]
    names = [t["layer"] for t in tv]
    order = [n for n in TIME_VARYING_LABELS if n in names] + [
        n for n in names if n not in TIME_VARYING_LABELS]
    tv_tr = ", ".join(TIME_VARYING_LABELS.get(n, (n, n))[0] for n in order) or "yok"
    tv_en = ", ".join(TIME_VARYING_LABELS.get(n, (n, n))[1] for n in order) or "none"
    static = list(check.static_after_as_of)
    iso = check.as_of.isoformat()
    if not static:
        note_tr = (f"Zamanla değişen veriler ({tv_tr}) kesimden öncedir; as_of'tan "
                   f"({iso}) sonraya ait statik katman bulunmadı.")
        note_en = (f"Time-varying inputs ({tv_en}) predate the cutoff; no static layer "
                   f"dated after as_of ({iso}) was found.")
    else:
        note_tr = (f"Zamanla değişen veriler ({tv_tr}) kesimden öncedir; "
                   f"{_join([_layer_phrase(e, 'tr') for e in static], 've')} katmanları "
                   f"güncel anlık görüntüdür ve as_of'tan ({iso}) sonraya aittir. Bu "
                   "katmanların sonuca etkisi ölçülmedi.")
        note_en = (f"Time-varying inputs ({tv_en}) predate the cutoff; the "
                   f"{_join([_layer_phrase(e, 'en') for e in static], 'and')} layers are "
                   f"current snapshots dated after as_of ({iso}). Their effect on the "
                   "result was not measured.")
        if _uses_building_baseline(static):
            note_tr += (" Bina yakınlığı taban çizgisi ve wui_exposure bu bina katmanına "
                        "dayanır; katman as_of'taki değil sonraki durumu gösterdiği için "
                        "bu taban çizgisinin sonucu iyimser olabilir.")
            note_en += (" The building-proximity baseline and wui_exposure rely on this "
                        "building layer, which shows a later state than as_of, so the "
                        "baseline's result may be optimistic.")
    return {"cutoff_utc": check.as_of.cutoff_utc.isoformat(),
            "time_varying_before_cutoff": tv, "static_after_as_of": static,
            "note_tr": note_tr, "note_en": note_en}


# ------------------------------------------------------------------- data access


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
    for key, factor in BASELINE_FACTORS.items():
        out[key] = mid_rank_percentile(risk[f"norm_{factor}"].to_numpy(dtype="float64"))
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
    leak = check_no_leakage(rmeta, fmeta, cfg, base_layer_dates(root, aoi_id))
    as_of = leak.as_of
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
    lim_tr, lim_en = limitations(near, len(universe), cfg, chm_dates=rmeta.get("chm_dates"),
                                 static_layers=leak.static_after_as_of,
                                 type_filter=det_prov.get("type_filter") or {})
    summary = {
        "schema_version": SCHEMA_VERSION,
        "as_of": cfg.as_of.isoformat(),
        "season": f"{cfg.season[0].isoformat()}..{cfg.season[1].isoformat()}",
        "n_events": near,
        "n_events_total": int(len(universe)),
        "event_line_distance_m": cfg.event_line_distance_m,
        "verdict": verdict(near),
        **{_top_key(s): primary["model"][_top_key(s)] for s in cfg.top_shares},
        "baselines": baselines(primary),
        "sensitivity_line_distance": {
            "label_tr": "DUYARLILIK ANALİZİ — birincil eşik değildir. Birincil eşik "
                        f"{cfg.event_line_distance_m:.0f} m'dir (ADR-013).",
            "label_en": "SENSITIVITY ANALYSIS — not the primary threshold. The primary "
                        f"threshold is {cfg.event_line_distance_m:.0f} m (ADR-013).",
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
            "ci95_note": "ci95 is null exactly when ci95_note is set. "
                         f"'{CI_NOTE_DEGENERATE}': k in {{0, n}}, every resample has the same "
                         "share (read ci95_binomial); "
                         f"'{CI_NOTE_NO_EVENTS}': n = 0; "
                         f"'{CI_NOTE_EMPTY_TOP}': the ranking has no segment in the top set",
            "chance_baselines": "expected/length: lift of the model's top set if events fell "
                                "on random segments (uniform / by length); ci95 = 95 % range "
                                "of that null for this many events",
            "verdict": VERDICT_RULE.format(n=MIN_EVENTS_INFORMATIVE),
            "leakage": "time-stamped inputs at/after the cutoff are refused; static layers "
                       "whose temporal_status says after_, whose release/snapshot/imagery "
                       "date is >= as_of, or whose date is unknown are declared in "
                       "leakage.static_after_as_of",
            "as_of_cutoff_utc": as_of.cutoff_utc.isoformat(),
        },
        "leakage": leakage_block(leak, fmeta),
        "limitations_tr": lim_tr,
        "limitations_en": lim_en,
    }
    return BacktestResult(summary=summary, events=events)


def _top_key(share: float) -> str:
    return f"top{round(share * 100):d}"


def _baseline_view(b: Mapping[str, Any]) -> dict[str, Any]:
    keep = ("share", "lift", "ci95", "ci95_note", "expected", "n_in_top", "ci95_binomial",
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


def chm_limitation(chm_dates: Mapping[str, Any] | None, as_of: date) -> tuple[str, str]:
    """CHM limitation sentence from the risk meta ``chm_dates`` (REV-F3F4 O1)."""
    d = chm_dates or {}
    lo, hi = _leading_date(d.get("acq_min")), _leading_date(d.get("acq_max"))
    if lo is None or hi is None:
        return ("CHM görüntü tarihleri bilinmiyor (risk meta verisinde chm_dates yok); ağaç "
                "yüksekliği güncel olmayabilir.",
                "CHM imagery dates are unknown (no chm_dates in the risk metadata); canopy "
                "heights may be out of date.")
    if hi >= as_of:
        return (f"CHM görüntü tarihleri {lo}…{hi} arasıdır; bir kısmı as_of'tan sonradır "
                "(leakage.static_after_as_of).",
                f"CHM imagery dates are {lo}…{hi}; some imagery is dated after as_of "
                "(leakage.static_after_as_of).")
    new, old = ((as_of - x).days / 365.25 for x in (hi, lo))
    return (f"CHM görüntü tarihleri {lo}…{hi} arasıdır (as_of'tan "
            f"{f'{new:.1f}–{old:.1f}'.replace('.', ',')} yıl önce); ağaç büyümesi eksik "
            "tahmin edilebilir.",
            f"CHM imagery dates are {lo}…{hi} ({new:.1f}–{old:.1f} years before as_of); "
            "tree growth may be underestimated.")


def limitations(n: int, total: int, cfg: BacktestConfig, *,
                chm_dates: Mapping[str, Any] | None,
                static_layers: Sequence[Mapping[str, Any]],
                type_filter: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """``limitations_tr`` and ``limitations_en`` (same order, same length)."""
    tr: list[str] = []
    en: list[str] = []

    def add(t: str, e: str) -> None:
        tr.append(t)
        en.append(e)

    if n < MIN_EVENTS_INFORMATIVE:
        add(f"Olay sayısı küçük: hat yakınında {n} olay (ilçede toplam {total} küme; "
            f"bilgi vermesi için en az {MIN_EVENTS_INFORMATIVE} gerekir); güven aralıkları "
            "geniştir ve sonuç istatistiksel olarak zayıftır.",
            f"Few events: {n} near-line events ({total} clusters in the district; at least "
            f"{MIN_EVENTS_INFORMATIVE} are needed to inform); confidence intervals are wide "
            "and the evidence is statistically weak.")
    add("FIRMS VIIRS pikseli ~375 m'dir; tespit tutuşma noktası değildir ve ilk uydu geçişi "
        "tutuşmadan saatler sonra olabilir.",
        "FIRMS VIIRS pixels are ~375 m; a detection is not the ignition point and the first "
        "overpass may come hours after ignition.")
    add("Nedeni bilinmeyen tüm yangınlar olaylara dahildir; çoğu hat kaynaklı değildir.",
        "All fires of unknown cause are included; most are not line-caused.")
    add("Tarım ve anız yakmaları gürültü katar; FIRMS type filtresi yalnız statik kaynak ve "
        "deniz tespitlerini dışlar.",
        "Agricultural and stubble burning add noise; the FIRMS type filter only removes "
        "static land sources and offshore detections.")
    add("OSM hatlarının çoğu iletim hattıdır; dağıtım (OG/AG) hatları haritada yoktur. Dağıtım "
        "hattı kaynaklı bir yangın 'hat yakını' sayılmayabilir.",
        "Most OSM lines are transmission lines; distribution (MV/LV) lines are missing, so a "
        "fire started by a distribution line may not count as near-line.")
    add(*chm_limitation(chm_dates, cfg.as_of))
    if static_layers:
        t = ("Statik katmanlar as_of'tan sonraki anlık görüntülerdir: "
             f"{_join([_layer_phrase(e, 'tr') for e in static_layers], 've')}.")
        e = ("Static layers are snapshots dated after as_of: "
             f"{_join([_layer_phrase(x, 'en') for x in static_layers], 'and')}.")
        if _uses_building_baseline(static_layers):
            t += " Bina yakınlığı taban çizgisi bu bina katmanına dayanır ve iyimser olabilir."
            e += (" The building-proximity baseline relies on this building layer and may "
                  "be optimistic.")
        add(t, e)
    add("Kademeler ve yüzdelikler AOI içinde görelidir; skor bir olasılık değildir.",
        "Tiers and percentiles are relative within the AOI; the score is not a probability.")
    year = cfg.season[0].year
    case = CASE_DAY.strftime("%d.%m.%Y")
    if year == CASE_DAY.year:
        add(f"Seçim yanlılığı: pilot ilçe ve senaryo günleri {case} yangını ve 2024–25 "
            f"yangınları gerekçesiyle seçildi (ADR-006, ADR-012); backtest de aynı {year} "
            "sezonunu kullanıyor. Test bölgesi sonuç bilinerek seçildiği için olumlu bir "
            f"sonuç iyimser olurdu; çok yıllı testte {year} ayrı raporlanmalıdır.",
            f"Selection bias: the pilot district and the scenario days were chosen because "
            f"of the {case} fire and the 2024–25 fires (ADR-006, ADR-012), and the backtest "
            f"uses the same {year} season. The test area was chosen with the outcome known, "
            f"so a positive result would be optimistic; a multi-year test should report "
            f"{year} separately.")
    else:
        add(f"Seçim yanlılığı: pilot ilçe {case} yangını gerekçesiyle seçildi (ADR-006); "
            "sonuçlar başka ilçelere taşınmadan önce yeniden test edilmelidir.",
            f"Selection bias: the pilot district was chosen because of the {case} fire "
            "(ADR-006); results must be retested before they are carried to other districts.")
    d = cfg.event_line_distance_m
    dist, commit = PRIMARY_DISTANCE_SINCE
    since_tr = (f"ilk iskelet commit'inden ({commit}) beri config'te sabittir" if d == dist
                else "config'te tanımlıdır")
    since_en = (f"has been fixed in config since the first skeleton commit ({commit})"
                if d == dist else "is set in config")
    if type_filter.get("type_column"):
        k = sum(int(v) for v in (type_filter.get("n_excluded_by_type") or {}).values())
        tf_tr = f"FIRMS type filtresi sezonda {k} tespit dışladı."
        tf_en = f"The FIRMS type filter removed {k} season detections."
    else:
        tf_tr = "FIRMS dosyasında type sütunu yok; type filtresi uygulanmadı."
        tf_en = "The FIRMS file has no type column; the type filter was not applied."
    sens = [f"{x:.0f}" for x in cfg.sensitivity_distances_m]
    add(f"Birincil eşik {d:.0f} m'dir ve {since_tr}. ADR-013 protokolünün geri kalanı "
        "sonuçla aynı commit'te kaydedildi; protokolün sonuçtan önce yazıldığı depodan "
        f"doğrulanamaz. {tf_tr} {_join(sens, 've')} m yalnız duyarlılık analizidir.",
        f"The {d:.0f} m primary threshold {since_en}. The rest of the ADR-013 protocol was "
        "committed in the same commit as the result, so the repository cannot show that it "
        f"was written before the result. {tf_en} {_join(sens, 'and')} m are sensitivity "
        "analyses only.")
    return tr, en


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
