"""Feature build contract: rows, documented NaN, metadata, determinism, CLI, extensibility."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import yaml
from synth import AOI, AS_OF, CURRENT, base_chm

from hatkalkani.features import FACTORS, FactorResult, factor
from hatkalkani.features.asof import AsOf
from hatkalkani.features.build import (
    FeatureBuildError,
    build_features,
    main,
    read_features,
    write_features,
)
from hatkalkani.features.context import FeatureContext
from hatkalkani.features.rasterops import RasterValidationError
from hatkalkani.ingest.common import sha256_file


def test_one_row_per_segment_in_segment_order(syn):
    ctx = FeatureContext(AOI, syn.root)
    df, meta, _ = build_features(ctx, as_of=AS_OF)
    segs = gpd.read_parquet(syn.processed / "segments.parquet")
    assert df["segment_id"].tolist() == segs["segment_id"].tolist()
    assert df["segment_id"].is_unique and meta["n_segments"] == len(segs)
    assert (df["as_of"] == "2025-05-31").all()
    assert list(df.columns[:5]) == ["segment_id", "line_id", "voltage_level", "length_m", "as_of"]
    assert [c for c in df.columns if c in FACTORS] == list(FACTORS)


def test_every_nan_is_documented(syn):
    for as_of in (AS_OF, CURRENT):
        df, meta, _ = build_features(FeatureContext(AOI, syn.root), as_of=as_of)
        for name, spec in FACTORS.items():
            nan = df[name].isna()
            if spec.temporal == "unavailable":
                assert nan.all() and name in meta["unavailable_factors"]
                continue
            tagged = df["nan_reasons"].str.contains(f"{name}:", regex=False)
            assert (nan == tagged).all(), name
            assert sum(meta["nan_counts"][name].values()) == int(nan.sum())
        aux = [c for c in df.columns if c.startswith("aux_")]
        assert aux and not df[aux].select_dtypes("number").isin([np.inf, -np.inf]).any().any()


def test_metadata_roundtrip_and_inputs(syn, tmp_path):
    ctx = FeatureContext(AOI, syn.root)
    df, meta, _ = build_features(ctx, as_of=AS_OF)
    path = write_features(df, meta, tmp_path / "f.parquet")
    back, meta2 = read_features(path)
    pd.testing.assert_frame_equal(back, df)
    assert meta2 == meta and path.with_suffix(".meta.json").exists()
    assert meta["cutoff_utc_exclusive"] == "2025-05-31T21:00:00+00:00"
    assert meta["day_boundary"].startswith("local calendar day in Europe/Istanbul")
    inputs = set(meta["inputs_sha256"])
    for name in ("segments.parquet", "s2_ndmi_backtest.tif", "chm_corridor.tif",
                 "firms.parquet", "wind_hourly.parquet", "buildings.parquet"):
        assert any(p.endswith(name) for p in inputs), name
    assert not any(p.endswith("s2_ndmi_current.tif") for p in inputs)
    assert {f["name"] for f in meta["factors"]} == set(FACTORS)
    assert meta["registry_config_problems"] == []


def test_build_is_deterministic(syn, tmp_path):
    paths = []
    for i in range(2):
        df, meta, _ = build_features(FeatureContext(AOI, syn.root), as_of=AS_OF)
        paths.append(write_features(df, meta, tmp_path / f"run{i}" / "f.parquet"))
    assert sha256_file(paths[0]) == sha256_file(paths[1])


def test_cli_writes_both_config_dates(syn):
    assert main(["--aoi", AOI, "--as-of", "backtest", "current", "--root", str(syn.root)]) == 0
    for d in ("2025-05-31", "2026-10-30"):
        df, meta = read_features(syn.processed / f"features_{d}.parquet")
        assert len(df) == 5 and meta["as_of"] == d
    with pytest.raises(SystemExit):
        main(["--aoi", AOI, "--root", str(syn.root)])  # --as-of is required


def test_registry_config_mismatch_is_an_error(syn):
    p = syn.root / "config" / "risk_weights.yaml"
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    del cfg["consequence"]["slope"]
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(FeatureBuildError, match="slope"):
        build_features(FeatureContext(AOI, syn.root), as_of=AS_OF)


def test_new_factor_is_one_function_plus_one_config_line(syn):
    """Field feedback path: register a function, add its weight line, rebuild."""
    reg = dict(FACTORS)

    @factor(name="patrol_reports", component="consequence", unit="adet",
            source="saha formu", as_of_rule="kayıt tarihi < as_of kesimi", temporal="static",
            direction="higher", label_tr="Saha bildirimi", label_en="Field reports",
            definition="segment başına bildirim sayısı", registry=reg)
    def patrol_reports(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
        n = len(ctx.ids)
        return FactorResult(values=ctx.series(np.arange(n, dtype=float)),
                            nan_reason=ctx.series([""] * n, dtype="object"))

    ctx = FeatureContext(AOI, syn.root)
    with pytest.raises(FeatureBuildError, match="patrol_reports"):
        build_features(ctx, as_of=AS_OF, registry=reg)  # weight line still missing
    p = syn.root / "config" / "risk_weights.yaml"
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    cfg["consequence"]["patrol_reports"] = 0.0
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    df, meta, _ = build_features(FeatureContext(AOI, syn.root), as_of=AS_OF, registry=reg)
    assert df["patrol_reports"].tolist() == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert "patrol_reports" not in FACTORS


def _registry_returning(values, reasons, aux=None) -> dict:
    reg: dict = {}

    @factor(name="bad", component="ignition", unit="-", source="t", as_of_rule="t",
            temporal="static", direction="higher", label_tr="t", label_en="t",
            definition="d", registry=reg)
    def bad(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
        return FactorResult(values=ctx.series(values), nan_reason=ctx.series(reasons, "object"),
                            aux=pd.DataFrame(aux or {}, index=ctx.ids if aux else None))

    return reg


@pytest.mark.parametrize(
    "values, reasons, aux, msg",
    [
        ([np.nan, 1, 1, 1, 1], ["", "", "", "", ""], None, "NaN without a documented reason"),
        ([1, 1, 1, 1, 1], ["x", "", "", "", ""], None, "reason given for a finite value"),
        ([np.inf, 1, 1, 1, 1], [""] * 5, None, "infinite"),
        ([1, 1, 1, 1, 1], [""] * 5, {"no_prefix": [1, 2, 3, 4, 5]}, "aux_ prefix"),
        ([1, 1, 1, 1, 1], [""] * 5, {"aux_x": [np.nan, 1, 1, 1, 1]}, "NaN where"),
    ],
)
def test_contract_violations_fail_the_build(syn, values, reasons, aux, msg):
    ctx = FeatureContext(AOI, syn.root)
    with pytest.raises(FeatureBuildError, match=msg):
        build_features(ctx, as_of=AS_OF, registry=_registry_returning(values, reasons, aux),
                       strict_config=False)


def test_chm_dtype_and_range_are_validated_at_runtime(syn):
    syn.write_chm(base_chm().astype("uint16"))
    with pytest.raises(RasterValidationError, match="dtype"):
        build_features(FeatureContext(AOI, syn.root), as_of=AS_OF)
    arr = base_chm()
    arr[600 - 1 - 100, 150] = 150  # (510050.5, 4220000.5): inside 1001_0001's corridor
    syn.write_chm(arr)
    with pytest.raises(RasterValidationError, match="plausible"):
        build_features(FeatureContext(AOI, syn.root), as_of=AS_OF)


def test_config_guards_for_chm_corridor(syn):
    p = syn.root / "config" / "risk_weights.yaml"
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    cfg["parameters"]["strike_max_distance_m"] = 45
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="chm_corridor_half_width"):
        build_features(FeatureContext(AOI, syn.root), as_of=AS_OF)
    cfg["parameters"]["strike_max_distance_m"] = 30
    del cfg["parameters"]["clearance_band_m"]["mv"]
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="voltage_level"):
        build_features(FeatureContext(AOI, syn.root), as_of=AS_OF)
