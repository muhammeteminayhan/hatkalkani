"""Segment risk score 0-100, tiers and factor contributions (risk-model-spec section 3).

Pure functions: ``score_features`` takes a features frame (``features_<as_of>.parquet``)
and returns per-segment model columns plus a metadata record. No file access here.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from hatkalkani.model.config import COMPONENTS, LINEAR_P_SHARE, TOP_N, ModelConfig
from hatkalkani.model.explain import shapley_values, top_factor_lists
from hatkalkani.model.normalize import (
    NAN_FILL_BY_REASON,
    NAN_FILL_DEFAULT,
    REFERENCE_PERCENTILE,
    fill_missing,
    parse_nan_reasons,
    percentile_rank,
)

SCHEMA_VERSION = "risk-0.1"
RANK_DECIMALS = 9  # risk is rounded before ranking so float noise never breaks a tie


class ScoreError(ValueError):
    """Features and model configuration cannot be scored together."""


@dataclass(frozen=True)
class FactorMeta:
    name: str
    component: str
    direction: str
    temporal: str
    label_tr: str
    label_en: str


@dataclass(frozen=True)
class ScoreResult:
    frame: pd.DataFrame
    meta: dict[str, Any]


def factor_metas_from_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, FactorMeta]:
    """Registry rows as stored in the features metadata (``meta["factors"]``)."""
    return {
        str(r["name"]): FactorMeta(
            name=str(r["name"]),
            component=str(r["component"]),
            direction=str(r["direction"]),
            temporal=str(r["temporal"]),
            label_tr=str(r.get("label_tr", r["name"])),
            label_en=str(r.get("label_en", r["name"])),
        )
        for r in rows
    }


def combine_risk(p: np.ndarray, c: np.ndarray, mode: str) -> np.ndarray:
    """risk = 100 * sqrt(P * C) (geometric) or 100 * (0.6 P + 0.4 C) (linear)."""
    if mode == "geometric":
        return 100.0 * np.sqrt(np.clip(p, 0, None) * np.clip(c, 0, None))
    if mode == "linear":
        return 100.0 * (LINEAR_P_SHARE * p + (1 - LINEAR_P_SHARE) * c)
    raise ScoreError(f"unknown combine mode {mode!r}")


def mid_rank_percentile(values: np.ndarray) -> np.ndarray:
    return percentile_rank(np.round(np.asarray(values, dtype="float64"), RANK_DECIMALS),
                           direction="higher")


def assign_tiers(risk: np.ndarray, bounds: Mapping[str, float]) -> tuple[np.ndarray, np.ndarray]:
    """AOI risk percentile and tier (kritik >= bounds.kritik > yuksek >= ... > dusuk)."""
    pct = mid_rank_percentile(risk)
    tier = np.full(len(pct), "dusuk", dtype=object)
    for name in ("orta", "yuksek", "kritik"):  # ascending: higher tiers overwrite
        tier[pct >= bounds[name]] = name
    return pct, tier


def _labels(name: str, meta: FactorMeta | None, cfg: ModelConfig) -> dict[str, str]:
    if name in cfg.labels:  # UI labels in config win (renamable without a feature rebuild)
        return cfg.labels[name]
    if meta is not None:
        return {"tr": meta.label_tr, "en": meta.label_en}
    return {"tr": name, "en": name}


def _check_inputs(features: pd.DataFrame, factors: Mapping[str, FactorMeta],
                  cfg: ModelConfig) -> None:
    for col in ("segment_id", "nan_reasons"):
        if col not in features:
            raise ScoreError(f"features frame lacks column {col!r}")
    if not features["segment_id"].is_unique:
        raise ScoreError("segment_id is not unique")
    for name in cfg.weighted_factors():
        comp = cfg.component(name)
        if name not in factors:
            raise ScoreError(f"{name}: weighted in {comp} but not in the feature registry; "
                             "rebuild features (--stage features)")
        if name not in features:
            raise ScoreError(f"{name}: no column in the features file; rebuild features")
        if factors[name].component != comp:
            raise ScoreError(f"{name}: registered as {factors[name].component}, "
                             f"weighted under {comp}")


def score_features(
    features: pd.DataFrame, factors: Mapping[str, FactorMeta], cfg: ModelConfig
) -> ScoreResult:
    """Normalise, combine, explain and tier every segment of one as_of."""
    _check_inputs(features, factors, cfg)
    df = features.reset_index(drop=True)
    n = len(df)
    eff = cfg.effective_weights()
    reasons = [parse_nan_reasons(c) for c in df["nan_reasons"].fillna("").astype(str)]
    names = cfg.weighted_factors()
    # factors present in the file but not weighted are still carried (raw/norm, 0 points)
    carried = [f for f in factors if f in df.columns and f not in names]
    out = pd.DataFrame({"segment_id": df["segment_id"].astype(str).to_numpy()})
    norm: dict[str, np.ndarray] = {}
    imputed: list[list[str]] = [[] for _ in range(n)]
    imputed_counts: dict[str, dict[str, int]] = {}
    unavailable: list[str] = []
    for name in [*names, *carried]:
        meta = factors[name]
        raw = pd.to_numeric(df[name], errors="raise").to_numpy(dtype="float64")
        weight = eff.get(cfg.component(name) or "", {}).get(name, 0.0)
        if meta.temporal == "unavailable" or np.isnan(raw).all():
            if weight > 0:
                raise ScoreError(f"{name}: weight {weight:g} but the factor has no data "
                                 "(unavailable); set its weight to 0")
            unavailable.append(name)
            norm[name] = np.full(n, np.nan)
            continue
        is_nan = np.isnan(raw)
        why = [reasons[i].get(name, "") for i in range(n)]
        undocumented = [df["segment_id"].iloc[i] for i in np.flatnonzero(is_nan) if not why[i]]
        if undocumented:
            raise ScoreError(f"{name}: NaN without a documented reason, e.g. {undocumented[:3]}")
        pct = percentile_rank(raw, direction=meta.direction)
        norm[name] = fill_missing(pct, why)
        for i in np.flatnonzero(is_nan):
            imputed[i].append(f"{name}:{why[i]}")
            imputed_counts.setdefault(name, {}).setdefault(why[i], 0)
            imputed_counts[name][why[i]] += 1
    players = [f for f in names if f not in unavailable and
               eff[cfg.component(f) or ""].get(f, 0.0) > 0]
    X = np.column_stack([norm[f] for f in players]) if players else np.zeros((n, 0))
    w_ign = np.array([eff["ignition"].get(f, 0.0) for f in players])
    w_con = np.array([eff["consequence"].get(f, 0.0) for f in players])

    def value(m: np.ndarray) -> np.ndarray:
        # explicit elementwise sums (no BLAS) keep results identical across platforms
        return combine_risk((m * w_ign).sum(axis=1), (m * w_con).sum(axis=1), cfg.combine)

    p = (X * w_ign).sum(axis=1)
    c = (X * w_con).sum(axis=1)
    risk = combine_risk(p, c, cfg.combine)
    ref = np.full(len(players), REFERENCE_PERCENTILE)
    ref_risk = float(value(ref.reshape(1, -1))[0])
    phi = shapley_values(X, ref, value)
    pct, tier = assign_tiers(risk, cfg.tiers)
    out["risk"] = risk
    out["risk_pct"] = pct
    out["tier"] = pd.array(tier, dtype="str")
    out["p_ignition"] = p
    out["consequence"] = c
    for name in [*names, *carried]:
        out[f"norm_{name}"] = norm[name]
    for name in [*names, *carried]:
        out[f"contrib_{name}"] = phi[:, players.index(name)] if name in players else 0.0
    for name in [*names, *carried]:
        out[f"raw_{name}"] = pd.to_numeric(df[name]).to_numpy(dtype="float64")
    out["imputed"] = [";".join(x) for x in imputed]
    labels = {f: _labels(f, factors.get(f), cfg) for f in [*names, *carried]}
    tops = top_factor_lists(phi, players, labels, n=TOP_N)
    out["top_factors"] = [json.dumps(t, ensure_ascii=False) for t in tops]
    if not np.isfinite(out["risk"]).all():
        raise ScoreError("non-finite risk values")
    tier_counts = {t: int((tier == t).sum()) for t in ("kritik", "yuksek", "orta", "dusuk")}
    meta = {
        "schema_version": SCHEMA_VERSION,
        "n_segments": n,
        "config": cfg.snapshot(),
        "weights_effective": eff,
        "warnings": cfg.weight_warnings(),
        "factors_scored": players,
        "factors_unavailable": unavailable,
        "factors_carried_unweighted": carried,
        "labels": labels,
        "normalization": {
            "method": "mid-rank AOI percentile: (#below + 0.5 #equal) / n over finite values",
            "direction_lower": [f for f in [*names, *carried] if factors[f].direction == "lower"],
            "nan_fill_by_reason": dict(NAN_FILL_BY_REASON),
            "nan_fill_default": NAN_FILL_DEFAULT,
        },
        "imputed_counts": imputed_counts,
        "reference": {"percentile": REFERENCE_PERCENTILE, "risk": ref_risk},
        "contributions": (
            "exact Shapley values of risk minus the reference segment's risk (all factors at "
            "the AOI mid-percentile); contrib_* add up to risk - reference.risk (ADR-010)"
        ),
        "top_factors": f"up to {TOP_N} factors with the largest positive contribution",
        "tier_rule": "AOI mid-rank percentile of risk >= tiers lower bound (ties share a tier)",
        "tier_counts": tier_counts,
        "risk_summary": _summary(risk),
        "components": {comp: _summary(arr) for comp, arr in zip(COMPONENTS, (p, c),
                                                                  strict=True)},
    }
    return ScoreResult(frame=out, meta=meta)


def _summary(x: np.ndarray) -> dict[str, float]:
    q = np.quantile(x, [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0])
    keys = ["min", "p10", "p25", "p50", "p75", "p90", "p95", "max"]
    return {"mean": float(np.mean(x)), "std": float(np.std(x)),
            **{k: float(v) for k, v in zip(keys, q, strict=True)}}
