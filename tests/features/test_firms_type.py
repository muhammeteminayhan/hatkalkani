"""FIRMS `type` filter (ADR-013): only presumed vegetation fires (type 0) and rows without
a type (NRT) reach fire_history; static land sources (2) and offshore (3) never do."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from synth import AOI, AS_OF, BASE_FIRMS, firms_frame, midpoint

from hatkalkani.features.build import build_features
from hatkalkani.features.context import FeatureContext, firms_type_filter


def test_type_filter_keeps_vegetation_and_missing_only():
    df = pd.DataFrame({"type": pd.array([0, 2, 3, None, 1, 0], dtype="Int64")})
    keep, prov = firms_type_filter(df)
    assert keep.tolist() == [True, False, False, True, False, True]
    assert prov["n_excluded_by_type"] == {"1": 1, "2": 1, "3": 1}
    assert prov["n_type_missing_kept"] == 1
    keep, prov = firms_type_filter(pd.DataFrame({"x": [1, 2]}))  # older ingest: no column
    assert keep.all() and prov == {"type_column": False}


def _fire_history(syn, rows, types) -> tuple[pd.Series, dict]:
    df = firms_frame(rows)
    df["type"] = pd.array(types, dtype="Int64")
    df.to_parquet(syn.interim / "firms.parquet", index=False)
    feats, meta, _ = build_features(FeatureContext(AOI, syn.root), as_of=AS_OF)
    return feats.set_index("segment_id")["fire_history"], meta["provenance"]["fire_history"]


def test_static_and_offshore_detections_do_not_move_fire_history(syn):
    base_types = [0] * len(BASE_FIRMS)
    ref, _ = _fire_history(syn, BASE_FIRMS, base_types)
    static = ("VIIRS_SNPP_SP", datetime(2023, 7, 2, 10, 0), *midpoint("1001_0002"))
    sea = ("VIIRS_NOAA20_SP", datetime(2022, 8, 3, 10, 0), *midpoint("2002_0001"))
    got, prov = _fire_history(syn, [*BASE_FIRMS, static, sea], [*base_types, 2, 3])
    pd.testing.assert_series_equal(got, ref)
    assert prov["type_filter"]["n_excluded_by_type"] == {"2": 1, "3": 1}
    # the same detection without a type (NRT) is kept and counted: the filter is not a no-op
    nrt = ("VIIRS_SNPP_NRT", datetime(2023, 7, 2, 10, 0), *midpoint("1001_0002"))
    got, prov = _fire_history(syn, [*BASE_FIRMS, nrt], [*base_types, None])
    assert got["1001_0002"] > ref["1001_0002"] * (1 + 1e-6)
    assert prov["type_filter"]["n_type_missing_kept"] == 1
    assert got.drop("1001_0002").gt(0).all()
    assert prov["n_viirs_in_window"] == pytest.approx(5)
