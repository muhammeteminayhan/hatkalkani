"""Model CLI on the synthetic AOI and ``run_pipeline.py --stage score`` wiring."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import pytest
import yaml
from synth import AOI

from hatkalkani.model.run import main as model_main
from hatkalkani.model.run import read_risk

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_pipeline.py"
spec = importlib.util.spec_from_file_location("run_pipeline_score_under_test", SCRIPT)
rp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rp
spec.loader.exec_module(rp)

DATES = ["2025-05-31", "2026-10-30"]
OUT_NAMES = ["risk_{d}.parquet", "risk_{d}.meta.json", "risk_{d}.geojson",
             "workorders_{d}.csv", "workorders_{d}.geojson", "workorders_{d}.gpkg"]
SEGMENT_PROPS = {"segment_id", "line_id", "voltage_class", "risk", "tier", "p_ignition",
                 "consequence", "top_factors"}


def _features(syn) -> None:
    from hatkalkani.features.build import main as features_main

    assert features_main(["--aoi", AOI, "--as-of", *DATES, "--root", str(syn.root)]) == 0


def test_cli_writes_every_output_in_wgs84_and_is_reproducible(syn):
    _features(syn)
    assert model_main(["--aoi", AOI, "--as-of", "backtest", "current",
                       "--root", str(syn.root)]) == 0
    first = {}
    for d in DATES:
        for name in OUT_NAMES:
            p = syn.processed / name.format(d=d)
            assert p.exists(), p
            first[p.name] = p.read_bytes()
        risk, meta = read_risk(syn.processed / f"risk_{d}.parquet")
        assert len(risk) == 5 and risk.crs.to_epsg() == 4326 and meta["as_of"] == d
        assert risk["tier"].isin(["kritik", "yuksek", "orta", "dusuk"]).all()
        gj = json.loads((syn.processed / f"risk_{d}.geojson").read_text(encoding="utf-8"))
        assert gj["type"] == "FeatureCollection" and "crs" not in gj  # RFC 7946 = WGS84
        assert len(gj["features"]) == 5
        for feat in gj["features"]:
            assert set(feat["properties"]) == SEGMENT_PROPS
            assert isinstance(feat["properties"]["top_factors"], list)
            lon, lat = feat["geometry"]["coordinates"][0]
            assert 26 < lon < 28 and 37 < lat < 39
        info = pyogrio.read_info(syn.processed / f"workorders_{d}.gpkg")
        assert "4326" in str(info["crs"])
        csv = (syn.processed / f"workorders_{d}.csv").read_bytes()
        assert csv.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    assert model_main(["--aoi", AOI, "--as-of", *DATES, "--root", str(syn.root)]) == 0
    for name, data in first.items():
        if not name.endswith(".gpkg"):  # GeoPackage embeds a write timestamp
            assert (syn.processed / name).read_bytes() == data, name
    a = gpd.read_file(syn.processed / f"workorders_{DATES[0]}.gpkg")
    b = gpd.read_file(syn.processed / f"workorders_{DATES[0]}.geojson")
    # GDAL's GeoJSON reader turns "YYYY-MM-DD" strings into dates and all-null fields into
    # None; compare the remaining values with NaN/None unified
    def plain(g: gpd.GeoDataFrame) -> pd.DataFrame:
        d = pd.DataFrame(g.drop(columns=["geometry", "as_of"])).astype(object)
        return d.where(d.notna(), None)

    pd.testing.assert_frame_equal(plain(a), plain(b), check_dtype=False)


def test_cli_fails_clearly_without_features(syn):
    with pytest.raises(SystemExit, match="features_2025-05-31"):
        model_main(["--aoi", AOI, "--as-of", "2025-05-31", "--root", str(syn.root)])


def test_score_stage_command_and_missing_features(syn):
    calls: list[list[str]] = []
    with pytest.raises(SystemExit, match="features_2025-05-31.parquet"):
        rp.run_score(AOI, runner=lambda c: pytest.fail("must not run"), root=syn.root)
    _features(syn)
    res = rp.run_score(AOI, runner=lambda c: calls.append(c) or 0, log=lambda s: None,
                       root=syn.root)
    assert calls == [[sys.executable, "-m", "hatkalkani.model.run", "--aoi", AOI,
                      "--as-of", *DATES]]
    assert [o.name for o in res[0]["outputs"]] == [f"risk_{d}.parquet" for d in DATES]
    with pytest.raises(SystemExit, match="score"):
        rp.run_score(AOI, runner=lambda c: 2, log=lambda s: None, root=syn.root)


def test_main_dispatches_score_stage(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(rp, "run_ingest", lambda *a, **k: seen.append("ingest") or [])
    monkeypatch.setattr(rp, "run_features", lambda *a, **k: seen.append("features") or [])
    monkeypatch.setattr(rp, "run_score", lambda *a, **k: seen.append("score") or [])
    monkeypatch.setattr(rp, "_check_manifest", lambda: seen.append("manifest"))
    rp.main(["--aoi", AOI, "--stage", "score"])
    assert seen == ["score"]
    seen.clear()
    rp.main(["--aoi", AOI, "--stage", "all"])
    assert seen == ["ingest", "manifest", "features", "score"]
    with pytest.raises(SystemExit, match="ingest stage only"):
        rp.main(["--aoi", AOI, "--stage", "score", "--only", "firms"])


def test_config_weight_change_changes_cli_scores(syn):
    _features(syn)
    model_main(["--aoi", AOI, "--as-of", DATES[0], "--root", str(syn.root)])
    base, _ = read_risk(syn.processed / f"risk_{DATES[0]}.parquet")
    path = syn.root / "config" / "risk_weights.yaml"
    rw = yaml.safe_load(path.read_text(encoding="utf-8"))
    rw["ignition"] = {"vegetation_encroachment": 0.0, "strike_trees": 0.0,
                      "fuel_dryness": 0.0, "wind_exposure": 1.0}
    path.write_text(yaml.safe_dump(rw), encoding="utf-8")
    model_main(["--aoi", AOI, "--as-of", DATES[0], "--root", str(syn.root)])
    new, meta = read_risk(syn.processed / f"risk_{DATES[0]}.parquet")
    assert meta["weights_effective"]["ignition"]["wind_exposure"] == 1.0
    assert not base["risk"].equals(new["risk"])
    pd.testing.assert_series_equal(new["p_ignition"], new["norm_wind_exposure"],
                                   check_names=False)
