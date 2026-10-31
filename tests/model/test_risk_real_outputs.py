"""Acceptance checks on the produced pilot risk and work-order files (skipped if not built)."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import pytest
import yaml

from hatkalkani.model.run import API_SEGMENT_PROPERTIES, read_risk
from hatkalkani.model.workorders import WORKORDER_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
CFG = yaml.safe_load((ROOT / "config" / "aoi.yaml").read_text(encoding="utf-8"))
RW = yaml.safe_load((ROOT / "config" / "risk_weights.yaml").read_text(encoding="utf-8"))
AOI = CFG["selected"]
PROC = ROOT / "data" / "processed" / AOI
DATES = [str(CFG["periods"]["backtest_asof"]), str(CFG["periods"]["current_asof"])]


def _need(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"{path.name} not built yet (run --stage score)")


@pytest.mark.parametrize("as_of", DATES)
def test_pilot_risk_file(as_of):
    path = PROC / f"risk_{as_of}.parquet"
    _need(path)
    risk, meta = read_risk(path)
    segs = gpd.read_parquet(PROC / "segments.parquet")
    assert risk.crs.to_epsg() == 4326 and meta["as_of"] == as_of
    assert risk["segment_id"].tolist() == segs["segment_id"].tolist()
    assert risk["risk"].between(0, 100).all() and risk["tier"].notna().all()
    contrib = risk[[c for c in risk.columns if c.startswith("contrib_")]].sum(axis=1)
    np.testing.assert_allclose(contrib, risk["risk"] - meta["reference"]["risk"], atol=1e-8)
    # tier counts from an independent brute-force percentile of the stored risk values
    r = risk["risk"].round(9).to_numpy()
    pct = np.array([((r < v).sum() + 0.5 * (r == v).sum()) / len(r) for v in r])
    for tier, lo, hi in [("kritik", RW["tiers"]["kritik"], 2), ("yuksek", RW["tiers"]["yuksek"],
                         RW["tiers"]["kritik"]), ("orta", RW["tiers"]["orta"],
                         RW["tiers"]["yuksek"]), ("dusuk", -1, RW["tiers"]["orta"])]:
        assert (risk["tier"] == tier).sum() == ((pct >= lo) & (pct < hi)).sum(), tier
    for raw in risk["top_factors"]:
        items = json.loads(raw)
        assert len(items) <= 3 and all(t["contribution"] > 0 for t in items)


@pytest.mark.parametrize("as_of", DATES)
def test_pilot_exports(as_of):
    _need(PROC / f"workorders_{as_of}.gpkg")
    risk, _ = read_risk(PROC / f"risk_{as_of}.parquet")
    gj = json.loads((PROC / f"risk_{as_of}.geojson").read_text(encoding="utf-8"))
    assert "crs" not in gj and len(gj["features"]) == len(risk)
    assert set(gj["features"][0]["properties"]) == set(API_SEGMENT_PROPERTIES)
    raw = (PROC / f"workorders_{as_of}.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    csv = pd.read_csv(PROC / f"workorders_{as_of}.csv", encoding="utf-8-sig")
    assert list(csv.columns) == WORKORDER_COLUMNS
    assert "4326" in str(pyogrio.read_info(PROC / f"workorders_{as_of}.gpkg")["crs"])
    wo = gpd.read_file(PROC / f"workorders_{as_of}.geojson")
    assert wo.crs.to_epsg() == 4326 and len(wo) == len(csv)
    covered = {s for ids in csv["segment_ids"] for s in ids.split(";")}
    work = set(risk.loc[risk["tier"].isin(["kritik", "yuksek"]), "segment_id"])
    assert covered == work  # every kritik/yuksek segment sits in exactly one span
    assert csv["n_segments"].sum() == len(work)
    assert csv["risk_max"].is_monotonic_decreasing
