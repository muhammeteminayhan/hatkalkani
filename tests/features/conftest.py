"""Fixtures for feature tests; the synthetic AOI itself lives in ``synth.py``."""

from __future__ import annotations

from pathlib import Path

import pytest
from synth import SynRoot, make_syn_root


@pytest.fixture
def syn(tmp_path: Path) -> SynRoot:
    """Fresh synthetic project root (config + ingest outputs) per test."""
    return make_syn_root(tmp_path / "proj")
