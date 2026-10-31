"""Factor registry: spec coverage, config consistency and the required ``as_of`` contract."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from hatkalkani.features import FACTORS, FactorResult, factor
from hatkalkani.features.registry import check_against_config, check_as_of_signature

ROOT = Path(__file__).resolve().parents[2]
SPEC_FACTORS = {
    "vegetation_encroachment", "strike_trees", "fuel_dryness", "wind_exposure",
    "fuel_continuity", "slope", "wui_exposure", "fire_history", "asset_condition",
}


def _live_weights() -> tuple[dict, dict]:
    rw = yaml.safe_load((ROOT / "config" / "risk_weights.yaml").read_text(encoding="utf-8"))
    return {"ignition": rw["ignition"], "consequence": rw["consequence"]}, rw.get("labels", {})


def test_every_spec_factor_is_registered_with_documentation():
    assert set(FACTORS) == SPEC_FACTORS
    for spec in FACTORS.values():
        assert spec.unit and spec.source and spec.as_of_rule and spec.definition
        assert spec.label_tr and spec.label_en
    assert FACTORS["fuel_dryness"].direction == "lower"  # low NDMI = dry
    assert all(s.direction == "higher" for n, s in FACTORS.items() if n != "fuel_dryness")
    time_filtered = {n for n, s in FACTORS.items() if s.temporal == "time_filtered"}
    assert time_filtered == {"fuel_dryness", "wind_exposure", "fire_history"}
    assert FACTORS["asset_condition"].temporal == "unavailable"


def test_registry_matches_live_risk_weights_and_labels():
    weights, labels = _live_weights()
    assert check_against_config(weights) == []
    for name, spec in FACTORS.items():
        if name in labels:
            assert labels[name] == {"tr": spec.label_tr, "en": spec.label_en}


def test_check_against_config_reports_each_mismatch():
    weights = {"ignition": {"strike_trees": 1.0, "new_one": 0.0},
               "consequence": {"fuel_dryness": 1.0}}
    problems = " | ".join(check_against_config(weights))
    assert "new_one: has a weight" in problems
    assert "fuel_dryness: registered as ignition" in problems
    assert "slope: registered factor without a weight line" in problems


def test_every_factor_function_requires_keyword_only_as_of():
    for spec in FACTORS.values():
        p = inspect.signature(spec.func).parameters["as_of"]
        assert p.kind is inspect.Parameter.KEYWORD_ONLY
        assert p.default is inspect.Parameter.empty
        with pytest.raises(TypeError):
            spec.func(object())  # no as_of -> refused before any data is touched


@pytest.mark.parametrize(
    "src",
    [
        "def f(ctx):\n    pass",
        "def f(ctx, as_of):\n    pass",
        "def f(ctx, *, as_of=None):\n    pass",
    ],
)
def test_registration_refuses_functions_without_required_as_of(src):
    ns: dict = {}
    exec(src, ns)  # tiny literal test functions
    with pytest.raises(TypeError, match="as_of"):
        check_as_of_signature(ns["f"])


def test_decorator_registers_into_given_registry_and_rejects_duplicates():
    reg: dict = {}
    kw = dict(component="consequence", unit="adet", source="test", as_of_rule="static",
              temporal="static", direction="higher", label_tr="t", label_en="t",
              definition="d", registry=reg)

    @factor(name="extra", **kw)
    def extra(ctx: object, *, as_of: object) -> FactorResult:
        raise AssertionError("not called")

    assert list(reg) == ["extra"] and "extra" not in FACTORS
    with pytest.raises(ValueError, match="duplicate"):
        factor(name="extra", **kw)(extra)
    with pytest.raises(ValueError, match="component"):
        factor(name="x", **{**kw, "component": "bogus"})
