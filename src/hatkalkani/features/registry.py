"""Factor registry: one decorated function per factor (risk-model-spec section 2).

Adding a factor = one ``@factor(...)`` function in ``factors.py`` + one weight line in
``config/risk_weights.yaml`` (``ignition:`` or ``consequence:``). ``check_against_config``
keeps the two in sync and the build picks every registered factor up automatically.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from hatkalkani.features.asof import AsOf, parse_as_of

COMPONENTS = ("ignition", "consequence")
# time_filtered: reads time-stamped data, filtered at the as_of cutoff;
# static: data without per-record time (terrain, land cover, canopy, buildings);
# unavailable: no data source yet (column is all-NaN, documented in metadata).
TEMPORAL = ("time_filtered", "static", "unavailable")
# Which raw values mean "riskier": the F3-2 percentile normalisation flips "lower".
DIRECTIONS = ("higher", "lower")


@dataclass(frozen=True)
class FactorResult:
    """Raw values of one factor, indexed by segment_id.

    nan_reason: "" where the value is finite, a short machine-readable reason where NaN.
    aux: auxiliary per-segment columns (prefix ``aux_``) that explain the raw value.
    provenance: JSON-serialisable record of the data actually used. Time-filtered factors
    must set ``max_time_used_utc`` (checked against the cutoff by the build).
    """

    values: pd.Series
    nan_reason: pd.Series
    aux: pd.DataFrame = field(default_factory=pd.DataFrame)
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FactorSpec:
    name: str
    component: str
    unit: str
    source: str
    as_of_rule: str
    temporal: str
    direction: str
    label_tr: str
    label_en: str
    definition: str
    func: Callable[..., FactorResult]

    def describe(self) -> dict[str, str]:
        """Registry row without the function (for metadata and reports)."""
        return {
            "name": self.name,
            "component": self.component,
            "unit": self.unit,
            "source": self.source,
            "as_of_rule": self.as_of_rule,
            "temporal": self.temporal,
            "direction": self.direction,
            "label_tr": self.label_tr,
            "label_en": self.label_en,
            "definition": self.definition,
        }


FACTORS: dict[str, FactorSpec] = {}


def check_as_of_signature(func: Callable[..., Any]) -> None:
    """Every factor function must take a *required keyword-only* ``as_of`` parameter."""
    p = inspect.signature(func).parameters.get("as_of")
    if (
        p is None
        or p.kind is not inspect.Parameter.KEYWORD_ONLY
        or p.default is not inspect.Parameter.empty
    ):
        raise TypeError(
            f"factor function {func.__name__!r} must declare a required keyword-only "
            "parameter `as_of` (def f(ctx, *, as_of): ...)"
        )


def factor(
    *,
    name: str,
    component: str,
    unit: str,
    source: str,
    as_of_rule: str,
    temporal: str,
    direction: str,
    label_tr: str,
    label_en: str,
    definition: str,
    registry: dict[str, FactorSpec] | None = None,
) -> Callable[[Callable[..., FactorResult]], Callable[..., FactorResult]]:
    """Register a factor function. The wrapper normalises ``as_of`` (date | str | AsOf)."""
    if component not in COMPONENTS:
        raise ValueError(f"{name}: component must be one of {COMPONENTS}")
    if temporal not in TEMPORAL:
        raise ValueError(f"{name}: temporal must be one of {TEMPORAL}")
    if direction not in DIRECTIONS:
        raise ValueError(f"{name}: direction must be one of {DIRECTIONS}")
    for key, val in {"unit": unit, "source": source, "as_of_rule": as_of_rule}.items():
        if not val.strip():
            raise ValueError(f"{name}: {key} must not be empty")
    reg = FACTORS if registry is None else registry

    def deco(func: Callable[..., FactorResult]) -> Callable[..., FactorResult]:
        check_as_of_signature(func)
        if name in reg:
            raise ValueError(f"duplicate factor name: {name}")

        @functools.wraps(func)
        def wrapper(ctx: Any, *, as_of: AsOf | str) -> FactorResult:
            return func(ctx, as_of=parse_as_of(as_of))

        reg[name] = FactorSpec(
            name=name,
            component=component,
            unit=unit,
            source=source,
            as_of_rule=as_of_rule,
            temporal=temporal,
            direction=direction,
            label_tr=label_tr,
            label_en=label_en,
            definition=definition,
            func=wrapper,
        )
        return wrapper

    return deco


def check_against_config(
    weights: Mapping[str, Mapping[str, float]], registry: Mapping[str, FactorSpec] | None = None
) -> list[str]:
    """Problems between the registry and ``risk_weights.yaml`` (empty list = consistent).

    weights: {"ignition": {factor: w}, "consequence": {factor: w}}.
    """
    reg = FACTORS if registry is None else registry
    problems: list[str] = []
    seen: dict[str, str] = {}
    for comp in COMPONENTS:
        for fname in (weights.get(comp) or {}):
            if fname in seen:
                problems.append(f"{fname}: weighted in both {seen[fname]} and {comp}")
            seen[fname] = comp
            if fname not in reg:
                problems.append(f"{fname}: has a weight in {comp} but no registered factor")
            elif reg[fname].component != comp:
                problems.append(
                    f"{fname}: registered as {reg[fname].component}, weighted under {comp}"
                )
    for fname in reg:
        if fname not in seen:
            problems.append(f"{fname}: registered factor without a weight line in config")
    return problems
