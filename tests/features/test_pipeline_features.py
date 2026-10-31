"""``scripts/run_pipeline.py --stage features`` wiring (no subprocess, no real data)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from synth import AOI

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_pipeline.py"
spec = importlib.util.spec_from_file_location("run_pipeline_features_under_test", SCRIPT)
rp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rp
spec.loader.exec_module(rp)


def test_feature_command_builds_both_config_dates(syn):
    calls: list[list[str]] = []
    res = rp.run_features(AOI, runner=lambda c: calls.append(c) or 0, log=lambda s: None,
                          root=syn.root)
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[1:3] == ["-m", "hatkalkani.features.build"]
    assert cmd[3:] == ["--aoi", AOI, "--as-of", "2025-05-31", "2026-10-30"]
    assert [o.name for o in res[0]["outputs"]] == [
        "features_2025-05-31.parquet", "features_2026-10-30.parquet"]


def test_missing_ingest_output_stops_before_running(syn):
    (syn.interim / "firms.parquet").unlink()
    with pytest.raises(SystemExit, match="firms.parquet"):
        rp.run_features(AOI, runner=lambda c: pytest.fail("must not run"), root=syn.root)


def test_failed_feature_process_is_an_error(syn):
    with pytest.raises(SystemExit, match="features"):
        rp.run_features(AOI, runner=lambda c: 3, log=lambda s: None, root=syn.root)


def test_main_dispatches_stages(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(rp, "run_ingest", lambda *a, **k: seen.append("ingest") or [])
    monkeypatch.setattr(rp, "run_features", lambda *a, **k: seen.append("features") or [])
    monkeypatch.setattr(rp, "run_score", lambda *a, **k: seen.append("score") or [])
    monkeypatch.setattr(rp, "_check_manifest", lambda: seen.append("manifest"))
    rp.main(["--aoi", AOI, "--stage", "features"])
    assert seen == ["features"]
    seen.clear()
    rp.main(["--aoi", AOI, "--stage", "all"])
    assert seen == ["ingest", "manifest", "features", "score"]
    seen.clear()
    rp.main(["--aoi", AOI])  # default stays ingest-only
    assert seen == ["ingest", "manifest"]
    with pytest.raises(SystemExit, match="ingest stage only"):
        rp.main(["--aoi", AOI, "--stage", "features", "--force"])
