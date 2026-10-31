"""Score-level time leakage: data stamped after the as_of cutoff must not move any score.

End-to-end on the synthetic AOI: features are rebuilt from the modified ingest files and
scored again. The positive control shows the same pipeline does react to data stamped
*before* the cutoff, so the negative test can detect leakage.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from synth import AOI, AS_OF, BASE_FIRMS, SEGMENTS, midpoint

from hatkalkani.features.asof import AsOf
from hatkalkani.model.run import score_as_of


def _score(syn) -> dict:
    from hatkalkani.features.build import build_features, output_path, write_features
    from hatkalkani.features.context import FeatureContext

    ctx = FeatureContext(AOI, syn.root)
    df, meta, _ = build_features(ctx, as_of=AS_OF)
    write_features(df, meta, output_path(ctx, AsOf(AS_OF)))
    return score_as_of(AOI, AS_OF, root=syn.root, write=False)


def _model_columns(risk: pd.DataFrame) -> pd.DataFrame:
    keep = ["segment_id", "risk", "risk_pct", "tier", "p_ignition", "consequence",
            "top_factors"] + [c for c in risk.columns if c.startswith(("contrib_", "norm_"))]
    return pd.DataFrame(risk[keep])


def _inject_future(syn) -> None:
    future = []
    for sid in SEGMENTS:
        x, y = midpoint(sid)
        future += [
            ("VIIRS_SNPP_SP", datetime(2025, 5, 31, 21, 0), x, y),  # exactly at the cutoff
            ("VIIRS_NOAA20_NRT", datetime(2025, 6, 1, 10, 0), x + 50, y),
            ("VIIRS_SNPP_NRT", datetime(2025, 6, 29, 11, 0), x, y + 50),
            ("VIIRS_SNPP_SP", datetime(2026, 8, 1, 11, 0), x - 50, y),
        ]
    syn.write_firms(BASE_FIRMS + future)
    p = syn.interim / "wind_hourly.parquet"
    w = pd.read_parquet(p)
    w.loc[w["time_utc"] >= AsOf(AS_OF).cutoff_utc, "wind_gust_10m_ms"] = 99.0
    w.to_parquet(p, index=False)
    syn.write_s2("late", np.full((240, 240), -0.9, dtype="float32"))
    syn.write_s2_meta({"late": {"window": ["2025-06-01", "2025-06-30"],
                                "scenes": [{"id": "z", "datetime": "2025-06-20T09:00:00+00:00"}]}})


def test_future_data_leaves_scores_tiers_reasons_and_workorders_unchanged(syn):
    before = _score(syn)
    _inject_future(syn)
    after = _score(syn)
    pd.testing.assert_frame_equal(_model_columns(before["risk"]), _model_columns(after["risk"]))
    pd.testing.assert_frame_equal(
        pd.DataFrame(before["workorders"].drop(columns="geometry")),
        pd.DataFrame(after["workorders"].drop(columns="geometry")))


def test_positive_control_detections_before_cutoff_raise_the_score(syn):
    before = _score(syn)
    x, y = midpoint("1001_0003")
    extra = [("VIIRS_SNPP_SP", datetime(2024, 7, d, 10, 0), x, y) for d in range(1, 7)]
    syn.write_firms(BASE_FIRMS + extra)
    after = _score(syn)
    b = before["risk"].set_index("segment_id")
    a = after["risk"].set_index("segment_id")
    assert a.loc["1001_0003", "norm_fire_history"] > b.loc["1001_0003", "norm_fire_history"]
    assert a.loc["1001_0003", "risk"] > b.loc["1001_0003", "risk"]
