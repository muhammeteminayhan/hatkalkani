"""Acceptance checks on the produced pilot backtest.json (skipped if not built).

REV-F3F4: the leakage declaration (Y1), CHM dates from the data (O1), null degenerate
intervals (O2), the verdict field and the softened registration wording (D2)."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from hatkalkani.model import backtest as bt
from hatkalkani.model.run import read_risk

ROOT = Path(__file__).resolve().parents[2]
CFG = yaml.safe_load((ROOT / "config" / "aoi.yaml").read_text(encoding="utf-8"))
PROC = ROOT / "data" / "processed" / CFG["selected"]
AS_OF = str(CFG["periods"]["backtest_asof"])


@pytest.fixture(scope="module")
def summary() -> dict:
    path = PROC / "backtest.json"
    if not path.exists():
        pytest.skip("backtest.json not built yet (run --stage backtest)")
    s = json.loads(path.read_text(encoding="utf-8"))
    if "leakage" not in s:
        pytest.skip("backtest.json predates FIX-F3 (rerun --stage backtest)")
    return s


def test_static_layers_after_as_of_are_declared(summary):
    lk = summary["leakage"]
    layers = {e["layer"]: e for e in lk["static_after_as_of"]}
    assert {"buildings", "lines"} <= set(layers)
    fmeta = json.loads((PROC / f"features_{AS_OF}.meta.json").read_text(encoding="utf-8"))
    release = fmeta["provenance"]["wui_exposure"]["overture_release"]
    assert layers["buildings"]["release"] == release
    assert "baselines.buildings" in layers["buildings"]["used_by"]
    for e in lk["static_after_as_of"]:
        assert e["release_date"] is None or date.fromisoformat(e["release_date"]) >= \
            date.fromisoformat(AS_OF)
    assert f"Overture {release}" in lk["note_tr"] and f"Overture {release}" in lk["note_en"]
    assert any("Bina yakınlığı taban çizgisi" in s and "iyimser" in s
               for s in summary["limitations_tr"])


def test_chm_limitation_matches_the_risk_meta(summary):
    _, rmeta = read_risk(PROC / f"risk_{AS_OF}.parquet")
    d = rmeta["chm_dates"]
    rng = f"{d['acq_min']}…{d['acq_max']}"
    assert any(rng in s for s in summary["limitations_tr"])
    assert any(rng in s for s in summary["limitations_en"])


def test_degenerate_intervals_are_null_and_verdict_follows_the_event_count(summary):
    n = summary["n_events"]
    blocks = [summary["top10"], summary["top20"]]
    for key, b in summary["baselines"].items():
        if key not in ("expected", "length"):
            blocks += [b["top10"], b["top20"]]
    for b in blocks:
        k = b["n_in_top"]
        if n and k in (0, n):
            assert b["ci95"] is None and b["ci95_note"] == bt.CI_NOTE_DEGENERATE
        elif n:
            assert b["ci95"] is not None and b["ci95_note"] is None
    v = summary["verdict"]
    assert v["informative"] is (summary["n_events"] >= bt.MIN_EVENTS_INFORMATIVE)
    assert v["min_events"] == bt.MIN_EVENTS_INFORMATIVE


def test_no_unverifiable_registration_claim(summary):
    text = json.dumps(summary, ensure_ascii=False)
    assert not re.search(r"[Öö]nceden kayıtlı|sonuç görülmeden|pre-registered", text)
