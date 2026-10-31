"""chm_year and CHM image dates in the risk parquet (ingest chm_acq_segment.parquet)."""

from __future__ import annotations

import json

import pandas as pd
from synth import AOI, SEGMENTS

from hatkalkani.model.run import main as model_main
from hatkalkani.model.run import read_risk

API_PROPS = {"segment_id", "line_id", "voltage_class", "risk", "tier", "p_ignition",
             "consequence", "top_factors"}


def _features(syn) -> None:
    from hatkalkani.features.build import main as features_main

    assert features_main(["--aoi", AOI, "--as-of", "2025-05-31", "--root", str(syn.root)]) == 0


def test_chm_dates_fill_chm_year_and_keep_geojson_schema(syn):
    _features(syn)
    ids = list(SEGMENTS)
    years = [2019, 2019, 2016, 2020, 2018]
    pd.DataFrame({
        "segment_id": ids[::-1],  # order must not matter
        "chm_acq_min": pd.to_datetime([f"{y}-03-10" for y in years[::-1]]),
        "chm_acq_max": pd.to_datetime([f"{y}-09-11" for y in years[::-1]]),
        "chm_acq_dominant": pd.to_datetime([f"{y}-05-17" for y in years[::-1]]),
        "chm_acq_year": pd.array(years[::-1], dtype="Int64"),
        "chm_acq_coverage": 1.0,
    }).to_parquet(syn.interim / "chm_acq_segment.parquet", index=False)
    assert model_main(["--aoi", AOI, "--as-of", "2025-05-31", "--root", str(syn.root)]) == 0
    risk, meta = read_risk(syn.processed / "risk_2025-05-31.parquet")
    risk = risk.set_index("segment_id").loc[ids]
    assert risk["chm_year"].tolist() == years
    assert risk["chm_acq_min"].tolist() == [f"{y}-03-10" for y in years]
    assert risk["chm_acq_dominant"].tolist() == [f"{y}-05-17" for y in years]
    assert meta["chm_dates"]["acq_min"] == "2016-03-10"
    assert meta["chm_dates"]["acq_max"] == "2020-09-11"
    assert meta["chm_year"] == {"2016": 1, "2018": 1, "2019": 2, "2020": 1}
    gj = json.loads((syn.processed / "risk_2025-05-31.geojson").read_text(encoding="utf-8"))
    assert all(set(f["properties"]) == API_PROPS for f in gj["features"])


def test_without_chm_dates_file_chm_year_is_missing(syn):
    _features(syn)
    assert model_main(["--aoi", AOI, "--as-of", "2025-05-31", "--root", str(syn.root)]) == 0
    risk, meta = read_risk(syn.processed / "risk_2025-05-31.parquet")
    assert risk["chm_year"].isna().all() and risk["chm_acq_min"].isna().all()
    assert meta["chm_dates"]["file"] is None
