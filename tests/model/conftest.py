"""Fixtures for model tests. Helpers live in ``model_synth.py`` (a unique module name:
``conftest`` itself is ambiguous across test folders)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The synthetic AOI builder lives next to the feature tests; reuse it instead of copying.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features"))

from synth import SynRoot, make_syn_root  # noqa: E402


@pytest.fixture
def syn(tmp_path: Path) -> SynRoot:
    """Fresh synthetic project root (config + ingest outputs) per test."""
    return make_syn_root(tmp_path / "proj")
