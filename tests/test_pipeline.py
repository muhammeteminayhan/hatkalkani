"""Pipeline orchestration tests (no network, no subprocess)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_pipeline.py"
spec = importlib.util.spec_from_file_location("run_pipeline", SCRIPT)
rp = importlib.util.module_from_spec(spec)
sys.modules["run_pipeline"] = rp
spec.loader.exec_module(rp)

ORDER = ["boundary", "lines", "segments", "sentinel2", "dem", "worldcover",
         "chm", "buildings", "firms", "weather"]


def _name(cmd: list[str]) -> str:
    return cmd[2].rsplit(".", 1)[1]


def test_order_and_args():
    calls: list[list[str]] = []

    def runner(c):
        calls.append(c)
        return 0

    rp.run_ingest("izmir_menderes", runner=runner, log=lambda s: None)
    assert [_name(c) for c in calls] == ORDER
    assert all(c[-2:] == ["--aoi", "izmir_menderes"] for c in calls)


def test_only_keeps_pipeline_order():
    assert rp.select_modules(["weather", "lines"]) == ["lines", "weather"]
    with pytest.raises(SystemExit):
        rp.select_modules(["nope"])


def test_failure_stops():
    calls: list[list[str]] = []

    def runner(c):
        calls.append(c)
        return 1 if _name(c) == "lines" else 0

    with pytest.raises(SystemExit):
        rp.run_ingest("a", runner=runner, log=lambda s: None)
    assert len(calls) == 2


def test_force_deletes_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(rp, "ROOT", tmp_path)
    out = tmp_path / "data/processed/a/boundary.parquet"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"x")
    rp.run_ingest("a", only=["boundary"], force=True, runner=lambda c: 0, log=lambda s: None)
    assert not out.exists()


def test_manifest_validation(tmp_path):
    from hatkalkani.ingest import common

    f = tmp_path / "data/raw/x.bin"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"abc")
    common.register(f, "s", "u", "l", root=tmp_path)
    assert rp.validate_manifest(tmp_path) == []
    f.write_bytes(b"abd")
    assert any("sha256" in p for p in rp.validate_manifest(tmp_path))
    f.unlink()
    assert any("missing file" in p for p in rp.validate_manifest(tmp_path))
    m = common.manifest_path(tmp_path)
    lines = m.read_text(encoding="utf-8").splitlines()
    m.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")
    assert any("duplicate" in p for p in rp.validate_manifest(tmp_path))


def test_sentinel2_current_asof():
    from hatkalkani.ingest import sentinel2

    assert sentinel2.periods()["current"][1] == "2026-10-30"
    assert sentinel2.periods(date(2026, 1, 10))["current"][1] == "2026-01-10"
