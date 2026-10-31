"""Acceptance checks on the produced pilot feature files (skipped when not built yet)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
import yaml

from hatkalkani.features import FACTORS
from hatkalkani.features.build import read_features

ROOT = Path(__file__).resolve().parents[2]
CFG = yaml.safe_load((ROOT / "config" / "aoi.yaml").read_text(encoding="utf-8"))
AOI = CFG["selected"]
PROC = ROOT / "data" / "processed" / AOI
DATES = [str(CFG["periods"]["backtest_asof"]), str(CFG["periods"]["current_asof"])]


@pytest.mark.parametrize("as_of", DATES)
def test_pilot_features_file(as_of):
    path = PROC / f"features_{as_of}.parquet"
    if not path.exists():
        pytest.skip(f"{path.name} not built yet (run --stage features)")
    df, meta = read_features(path)
    segs = gpd.read_parquet(PROC / "segments.parquet")
    assert len(df) == len(segs) and df["segment_id"].tolist() == segs["segment_id"].tolist()
    assert meta["as_of"] == as_of and (df["as_of"] == as_of).all()
    for name, spec in FACTORS.items():
        nan = df[name].isna()
        if spec.temporal == "unavailable":
            assert nan.all() and name in meta["unavailable_factors"]
        else:
            assert (nan == df["nan_reasons"].str.contains(f"{name}:", regex=False)).all(), name
    cutoff = pd.Timestamp(meta["cutoff_utc_exclusive"])
    for prov in meta["provenance"].values():
        latest = prov.get("max_time_used_utc")
        assert latest is None or pd.Timestamp(latest) < cutoff
