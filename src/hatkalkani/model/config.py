"""Model configuration from ``config/risk_weights.yaml`` (risk-model-spec section 3).

Only validation and defaults live here; every number that tunes the model is read from
the YAML file. Spec-defined constants that are not (yet) config keys are named below and
documented in ADR-010.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from hatkalkani.ingest import common

COMPONENTS = ("ignition", "consequence")
COMBINE_MODES = ("geometric", "linear")
NORMALIZATIONS = ("percentile",)
TIERS = ("kritik", "yuksek", "orta", "dusuk")  # highest first; dusuk = below `orta`
TIER_BOUNDS = ("kritik", "yuksek", "orta")  # config keys: AOI percentile lower bounds
LINEAR_P_SHARE = 0.6  # spec section 3: linear risk = 100 * (0.6 P + 0.4 C)
TOP_N = 3  # spec section 3: three reasons per segment
WEIGHT_SUM_TOL = 1e-9


class ConfigError(ValueError):
    """risk_weights.yaml is not a valid model configuration."""


@dataclass(frozen=True)
class ModelConfig:
    version: str
    normalization: str
    combine: str
    ignition: dict[str, float]  # as configured
    consequence: dict[str, float]
    tiers: dict[str, float]  # kritik / yuksek / orta lower bounds (AOI risk percentile)
    labels: dict[str, dict[str, str]] = field(default_factory=dict)

    def component(self, name: str) -> str | None:
        for comp in COMPONENTS:
            if name in getattr(self, comp):
                return comp
        return None

    def weighted_factors(self) -> list[str]:
        """Every factor with a weight line, in config order (ignition first)."""
        return [*self.ignition, *self.consequence]

    def effective_weights(self) -> dict[str, dict[str, float]]:
        """Weights divided by their component sum, so P and C stay within [0, 1]."""
        out: dict[str, dict[str, float]] = {}
        for comp in COMPONENTS:
            w = getattr(self, comp)
            total = sum(w.values())
            out[comp] = {k: v / total for k, v in w.items()}
        return out

    def weight_warnings(self) -> list[str]:
        msgs = []
        for comp in COMPONENTS:
            total = sum(getattr(self, comp).values())
            if abs(total - 1.0) > WEIGHT_SUM_TOL:
                msgs.append(f"{comp} weights sum to {total:.6g}, not 1; renormalised")
        return msgs

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "normalization": self.normalization,
            "combine": self.combine,
            "ignition": dict(self.ignition),
            "consequence": dict(self.consequence),
            "tiers": dict(self.tiers),
        }


def _weights(raw: Any, comp: str) -> dict[str, float]:
    if not isinstance(raw, Mapping) or not raw:
        raise ConfigError(f"{comp}: expected a non-empty mapping of factor weights")
    out: dict[str, float] = {}
    for name, value in raw.items():
        try:
            w = float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{comp}.{name}: weight {value!r} is not a number") from exc
        if not w >= 0:  # also rejects NaN
            raise ConfigError(f"{comp}.{name}: negative or invalid weight {value!r}")
        out[str(name)] = w
    if sum(out.values()) <= 0:
        raise ConfigError(f"{comp}: at least one weight must be positive")
    return out


def model_config_from_dict(rw: Mapping[str, Any]) -> ModelConfig:
    normalization = str(rw.get("normalization", "percentile"))
    if normalization not in NORMALIZATIONS:
        raise ConfigError(f"normalization {normalization!r} not supported; use {NORMALIZATIONS}")
    combine = str(rw.get("combine", "geometric"))
    if combine not in COMBINE_MODES:
        raise ConfigError(f"combine {combine!r} not supported; use {COMBINE_MODES}")
    ignition = _weights(rw.get("ignition"), "ignition")
    consequence = _weights(rw.get("consequence"), "consequence")
    both = sorted(set(ignition) & set(consequence))
    if both:
        raise ConfigError(f"factors weighted in both components: {both}")
    raw_tiers = rw.get("tiers") or {}
    missing = [t for t in TIER_BOUNDS if t not in raw_tiers]
    if missing:
        raise ConfigError(f"tiers: missing lower bound(s) {missing}")
    tiers = {t: float(raw_tiers[t]) for t in TIER_BOUNDS}
    if not 0 < tiers["orta"] < tiers["yuksek"] < tiers["kritik"] < 1:
        raise ConfigError(f"tiers must satisfy 0 < orta < yuksek < kritik < 1, got {tiers}")
    labels = {
        str(k): {"tr": str(v.get("tr", k)), "en": str(v.get("en", k))}
        for k, v in (rw.get("labels") or {}).items()
        if isinstance(v, Mapping)
    }
    return ModelConfig(
        version=str(rw.get("version", "")),
        normalization=normalization,
        combine=combine,
        ignition=ignition,
        consequence=consequence,
        tiers=tiers,
        labels=labels,
    )


def load_model_config(root: Path = common.ROOT) -> ModelConfig:
    path = Path(root) / "config" / "risk_weights.yaml"
    return model_config_from_dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
