"""Placeholder until F3-2 adds the scoring model: the package imports and the features it
will consume expose a direction for every factor (needed for percentile normalisation)."""

from __future__ import annotations

import importlib


def test_model_package_imports():
    assert importlib.import_module("hatkalkani.model") is not None


def test_every_factor_declares_a_direction_for_normalisation():
    from hatkalkani.features import FACTORS

    assert {s.direction for s in FACTORS.values()} <= {"higher", "lower"}
