"""API tests on a tiny synthetic AOI (no real data, no network)."""

from __future__ import annotations

import json
import sys
import time
import types
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, box

from hatkalkani.api import create_app

AOI = "syn"
FACTORS = ["fuel_continuity", "slope"]
LABELS = {
    "fuel_continuity": {"tr": "Kesintisiz orman/maki", "en": "Continuous forest/shrub fuel"},
    "slope": {"tr": "Dik yamaç", "en": "Steep slope"},
}


def _write_asof(d: Path, as_of: str, chm: bool = False) -> None:
    rows = [("1_0001", "kritik", 0.0), ("1_0002", "dusuk", 0.01), ("2_0001", "orta", 0.5)]
    feats, recs, frecs = [], [], []
    for i, (sid, tier, x) in enumerate(rows):
        lon = 27.0 + x
        geom = LineString([(lon, 38.0), (lon + 0.001, 38.001)])
        top = [{"key": "slope", "label_tr": "Dik yamaç", "label_en": "Steep slope",
                "contribution": 3.0}]
        feats.append({"type": "Feature", "geometry": json.loads(gpd.GeoSeries([geom]).to_json())
                      ["features"][0]["geometry"],
                      "properties": {"segment_id": sid, "line_id": sid.split("_")[0],
                                     "voltage_class": "mv", "risk": 60.0 - i, "tier": tier,
                                     "p_ignition": 0.5, "consequence": 0.5, "top_factors": top}})
        recs.append({"segment_id": sid, "length_m": 100.0, "voltage_level": "mv",
                     "voltage_kv": 34.5, "risk_pct": 0.9, "imputed": "", "chm_year": None,
                     "contrib_fuel_continuity": 5.0, "contrib_slope": 3.0,
                     "norm_fuel_continuity": 0.9, "norm_slope": 0.8,
                     "raw_fuel_continuity": 0.1, "raw_slope": float("nan")})
        frecs.append({"segment_id": sid, "fuel_continuity": 0.91, "slope": 12.5})
    (d / f"risk_{as_of}.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    if chm:
        for k, rec in enumerate(recs):
            rec.update(chm_year=2019, chm_acq_min=f"2018-0{k + 1}-01",
                       chm_acq_max=f"2020-0{k + 1}-15", chm_acq_dominant="2019-07-01")
    pd.DataFrame(recs).to_parquet(d / f"risk_{as_of}.parquet")
    pd.DataFrame(frecs).to_parquet(d / f"features_{as_of}.parquet")
    (d / f"risk_{as_of}.meta.json").write_text(json.dumps({"labels": LABELS}), encoding="utf-8")
    wo = [{"type": "Feature", "geometry": feats[0]["geometry"],
           "properties": {"span_id": f"s{k}", "priority": k + 1, "risk_max": 70 - k,
                          "main_reason_tr": "Dik yamaç", "as_of": as_of}} for k in range(3)]
    (d / f"workorders_{as_of}.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": wo}), encoding="utf-8")
    (d / f"workorders_{as_of}.csv").write_bytes(
        "span_id,main_reason_tr\ns0,Dik yamaç\n".encode("utf-8-sig"))
    (d / f"workorders_{as_of}.gpkg").write_bytes(b"GPKG")


@pytest.fixture
def client(tmp_path: Path, request: pytest.FixtureRequest) -> TestClient:
    chm = getattr(request, "param", False)
    root = tmp_path / "processed"
    d = root / AOI
    d.mkdir(parents=True)
    for as_of in ("2025-05-31", "2026-10-30"):
        _write_asof(d, as_of, chm=chm and as_of == "2026-10-30")
    gpd.GeoDataFrame({"il": ["Test"], "ilce": ["Sentetik"]}, geometry=[box(26.9, 37.9, 27.6, 38.1)],
                     crs="EPSG:4326").to_parquet(d / "boundary.parquet")
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "aoi.yaml").write_text(
        f"selected: {AOI}\nperiods:\n  current_asof: '2026-10-30'\n", encoding="utf-8")
    (cfg / "sources.yaml").write_text(
        "sources:\n  - {name: OSM, license: ODbL, attribution: x, url: 'http://a'}\n",
        encoding="utf-8")
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>hello</html>", encoding="utf-8")
    return TestClient(create_app(root, config_dir=cfg, web_dir=web))


def test_health_and_static(client: TestClient) -> None:
    j = client.get("/api/health").json()
    assert j == {"status": "ok", "aoi": AOI, "data_version": "2026-10-30",
                 "as_ofs": ["2025-05-31", "2026-10-30"]}
    assert "hello" in client.get("/").text


def test_aoi(client: TestClient) -> None:
    j = client.get("/api/aoi").json()
    assert j["name"] == "Test / Sentetik" and j["stats"]["segment_count"] == 3
    assert j["stats"]["tier_counts"] == {"kritik": 1, "yuksek": 0, "orta": 1, "dusuk": 1}
    assert j["stats"]["workorder_count"] == 3 and j["stats"]["line_km"] == 0.3
    assert len(j["bbox"]) == 4


def test_segments_filters(client: TestClient) -> None:
    assert len(client.get("/api/segments").json()["features"]) == 3
    f = client.get("/api/segments?tier=kritik,orta").json()["features"]
    assert {x["properties"]["tier"] for x in f} == {"kritik", "orta"}
    f = client.get("/api/segments?bbox=26.99,37.99,27.01,38.01").json()["features"]
    assert len(f) == 2
    assert client.get("/api/segments?tier=zzz").status_code == 422
    r = client.get("/api/segments?bbox=1,2,3")
    assert r.status_code == 422 and {"error", "hint"} <= set(r.json())


def test_segment_detail(client: TestClient) -> None:
    j = client.get("/api/segments/1_0001").json()
    assert j["raw"] == {"fuel_continuity": 0.91, "slope": 12.5}
    assert j["contrib"]["fuel_continuity"] == 5.0
    assert j["chm_year"] is None and "ADR-008" in j["chm_year_note_tr"]
    assert j["properties"]["tier"] == "kritik" and j["geometry"]["type"] == "LineString"
    assert j["factor_labels"]["slope"]["en"] == "Steep slope"
    r = client.get("/api/segments/nope")
    assert r.status_code == 404 and "error" in r.json()


def test_as_of(client: TestClient) -> None:
    assert client.get("/api/aoi?as_of=2025-05-31").json()["as_of"] == "2025-05-31"
    r = client.get("/api/segments?as_of=1999-01-01")
    assert r.status_code == 404 and "2025-05-31" in r.json()["hint"]


def test_workorders_and_export(client: TestClient) -> None:
    r = client.get("/api/workorders?limit=2")
    assert len(r.json()) == 2 and r.headers["x-total-count"] == "3"
    g = client.get("/api/workorders?format=geojson&limit=1").json()
    assert g["type"] == "FeatureCollection" and len(g["features"]) == 1
    csv = client.get("/api/workorders/export?format=csv")
    assert csv.content.startswith(b"\xef\xbb\xbf")
    assert "attachment" in csv.headers["content-disposition"]
    assert client.get("/api/workorders/export?format=gpkg").content == b"GPKG"
    assert client.get("/api/workorders/export?format=xls").status_code == 422


def test_not_ready_503(client: TestClient) -> None:
    sys.modules.pop("hatkalkani.model.scenario", None)
    for url in ("/api/backtest", "/api/backtest/events", "/api/scenario/dates",
                "/api/scenario?date=2025-06-28"):
        r = client.get(url)
        assert r.status_code == 503, url
        assert set(r.json()) == {"detail_tr", "detail_en"}


def test_backtest_files_and_scenario_module(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = tmp_path / "processed" / AOI
    (d / "backtest.json").write_text('{"n_events": 2}', encoding="utf-8")
    (d / "scenario_dates.json").write_text('[{"date":"2025-06-28","max_gust_kmh":60}]')
    assert client.get("/api/backtest").json() == {"n_events": 2}
    assert client.get("/api/scenario/dates").json()[0]["max_gust_kmh"] == 60
    mod = types.ModuleType("hatkalkani.model.scenario")
    mod.compute_scenario = lambda aoi, date, gust, tier: {"date": date, "inputs": [aoi, gust, tier]}
    monkeypatch.setitem(sys.modules, "hatkalkani.model.scenario", mod)
    j = client.get("/api/scenario?date=2025-06-28&gust_kmh=55&min_tier=orta").json()
    assert j == {"date": "2025-06-28", "inputs": [AOI, 55.0, "orta"]}


def test_sources_boundary_and_json_404(client: TestClient) -> None:
    assert client.get("/api/meta/sources").json()[0]["name"] == "OSM"
    assert client.get("/api/aoi/boundary").json()["type"] == "FeatureCollection"
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and "error" in r.json()


def test_missing_data_is_json_error(tmp_path: Path) -> None:
    c = TestClient(create_app(tmp_path / "none", aoi_id="x", config_dir=tmp_path,
                              web_dir=tmp_path / "w"))
    assert c.get("/api/health").json()["status"] == "degraded"
    r = c.get("/api/segments")
    assert r.status_code == 503 and {"error", "hint"} <= set(r.json())


REAL = Path(__file__).resolve().parents[2] / "data" / "processed" / "izmir_menderes"


@pytest.mark.skipif(not (REAL / "risk_2026-10-30.parquet").exists(), reason="real data absent")
def test_real_data_smoke() -> None:
    c = TestClient(create_app())
    t = time.perf_counter()
    r = c.get("/api/segments?tier=kritik")
    assert r.status_code == 200 and time.perf_counter() - t < 0.5
    assert len(r.json()["features"]) == 46
    assert c.get("/api/workorders/export?format=csv").content.startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("client", [True], indirect=True)
def test_chm_dates_present(client: TestClient) -> None:
    j = client.get("/api/segments/1_0001").json()
    assert j["chm_year"] == 2019 and j["chm_acq_dominant"] == "2019-07-01"
    assert j["chm_year_note_tr"] == (
        "Ağaç yüksekliği görüntü tarihi: 2019-07-01 "
        "(bu parçada 2018-01-01–2020-01-15; Meta/WRI CHM v2 mozaiği)")
    assert "Tree-height imagery date: 2019-07-01" in j["chm_year_note_en"]
    assert client.get("/api/aoi").json()["stats"]["chm_acq_range"] == ["2018-01-01", "2020-03-15"]


def test_chm_dates_absent(client: TestClient) -> None:
    j = client.get("/api/segments/1_0001").json()
    assert j["chm_acq_dominant"] is None and "ADR-008" in j["chm_year_note_tr"]
    assert client.get("/api/aoi").json()["stats"]["chm_acq_range"] is None


@pytest.mark.skipif(
    not (REAL / "scenario_dates.json").exists(), reason="real scenario data absent"
)
def test_real_scenario_smoke() -> None:
    c = TestClient(create_app())
    dates = c.get("/api/scenario/dates")
    assert dates.status_code == 200
    assert "2025-06-29" in [x["date"] for x in dates.json()]
    r = c.get("/api/scenario?date=2025-06-29&gust_kmh=50&min_tier=yuksek")
    assert r.status_code == 200
    j = r.json()
    assert j["targeted"]["line_km"] <= j["district_wide"]["line_km"]
    assert "sensitivity_segment_unit" in j
    if not (REAL / "backtest.json").exists():
        assert c.get("/api/backtest").status_code == 503


def test_warmup_failure_does_not_crash(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "processed" / AOI / "scenario_dates.json").write_text("not json")
    c = TestClient(create_app(tmp_path / "processed", config_dir=tmp_path / "config"))
    assert c.get("/api/health").status_code == 200
