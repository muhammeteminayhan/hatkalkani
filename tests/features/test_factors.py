"""Factor values on the synthetic AOI (designed in synth.py), computed end to end.

Expected numbers come from independent references (shapely areas, brute-force distances,
the kernel formula written out), not from the code under test.
"""

from __future__ import annotations

import math
from datetime import date

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, Point, box
from synth import AOI, AS_OF, BUILDING_CENTRES, CURRENT, METRIC, SEGMENTS, midpoint

from hatkalkani.features.build import build_features
from hatkalkani.features.context import FeatureContext


@pytest.fixture
def built(syn):
    ctx = FeatureContext(AOI, syn.root)
    df, meta, _ = build_features(ctx, as_of=AS_OF)
    return df.set_index("segment_id"), meta


def _seg(sid: str) -> LineString:
    _, _, x0, x1, y = SEGMENTS[sid]
    return LineString([(x0, y), (x1, y)])


def test_canopy_factors(built):
    df, meta = built
    a = df.loc["1001_0001"]
    assert a["aux_chm_band_px"] == 1000  # 10 rows (|d| <= 5 m, hv) x 100 columns
    assert a["vegetation_encroachment"] == pytest.approx(80 / 1000)
    assert a["strike_trees"] == 3 and a["aux_strike_tall_clusters"] == 2
    assert df.loc["1001_0002", ["vegetation_encroachment", "strike_trees"]].tolist() == [0, 0]
    c = df.loc["1001_0003"]
    assert math.isnan(c["vegetation_encroachment"]) and math.isnan(c["strike_trees"])
    assert "vegetation_encroachment:no_chm_coverage" in c["nan_reasons"]
    assert "strike_trees:no_chm_coverage" in c["nan_reasons"]
    b = df.loc["2002_0001"]  # mv band 3 m: 6 rows x 100 columns of 15 m canopy
    assert b["aux_chm_band_px"] == 600 and b["vegetation_encroachment"] == 1.0
    assert b["strike_trees"] == 1
    prov = meta["provenance"]["vegetation_encroachment"]
    assert prov["validation"]["dtype"] == "uint8" and prov["temporal_status"].startswith("undated")


def test_fuel_dryness_masks_water_and_documents_nan(built):
    df, meta = built
    assert df.loc["1001_0001", "fuel_dryness"] == pytest.approx(-0.2)
    assert df.loc["1001_0002", "fuel_dryness"] == pytest.approx(0.4)
    # land median -0.2; including the 10 water pixels (0.9) would give -0.1
    assert df.loc["1001_0003", "fuel_dryness"] == pytest.approx(-0.2)
    assert df.loc["1001_0003", "aux_ndmi_water_px_excluded"] == 10
    assert df.loc["1001_0003", "aux_ndmi_px"] == 15
    assert math.isnan(df.loc["2002_0002", "fuel_dryness"])
    assert df.loc["2002_0002", "nan_reasons"] == "fuel_dryness:no_valid_ndmi_pixels"
    prov = meta["provenance"]["fuel_dryness"]
    assert prov["selected"] == "backtest" and prov["staleness_days"] == 0


def _tpi_multipliers() -> tuple[float, float]:
    """Independent mid-rank ECDF of the two TPI values over 30 m pixel centres in the AOI."""
    xs = 507800 + 15 + 30 * np.arange(160)
    ys = 4222600 - 15 - 30 * np.arange(160)
    gx, gy = np.meshgrid(xs, ys)
    inside = (gx > 508000) & (gx < 512400) & (gy > 4218000) & (gy < 4222400)
    north = inside & (gy >= 4220200)
    n, n_north = int(inside.sum()), int(north.sum())
    n_south = n - n_north
    f_south = (0 + n_south) / (2 * n)  # value -20: nothing below, n_south ties
    f_north = (n_south + n) / (2 * n)  # value +20: n_south below, n_north ties
    return 0.5 + f_south, 0.5 + f_north


def test_wind_exposure_uses_climatology_and_topography(built):
    df, meta = built
    hourly = np.tile(8.0 + np.arange(24) % 6, 3 * 122)  # 2022-24, Jun-Sep
    w95 = float(np.percentile(hourly, 95))
    e95 = float(np.percentile(2 * hourly, 95))
    m_south, m_north = _tpi_multipliers()
    expect = {
        "1001_0001": (w95, m_south, "g00"),
        "1001_0002": (e95, m_south, "g01"),
        "1001_0003": (e95, m_south, "g01"),
        "2002_0001": (w95, m_north, "g00"),
        "2002_0002": (e95, m_north, "g01"),
    }
    for sid, (gust, mult, cell) in expect.items():
        row = df.loc[sid]
        assert row["aux_wind_cell"] == cell
        assert row["aux_wind_gust_p95_ms"] == pytest.approx(gust)
        assert row["aux_topo_multiplier"] == pytest.approx(mult)
        assert row["wind_exposure"] == pytest.approx(gust * mult)
    prov = meta["provenance"]["wind_exposure"]
    assert prov["n_cells"] == 2  # g02 duplicates g00's Open-Meteo cell
    assert prov["years_used"] == [2022, 2023, 2024]
    assert prov["n_rows_excluded_outside_climatology"] == 3 * 96  # scenario days


def test_fuel_continuity_slope_and_wui(built, syn):
    df, _ = built
    north = box(-1e9, 4220200, 1e9, 1e9)
    pts = gpd.read_parquet(syn.interim / "buildings.parquet").to_crs(METRIC)
    rep = pts.geometry.representative_point()
    assert len(rep) == len(BUILDING_CENTRES)
    for sid in SEGMENTS:
        buf = _seg(sid).buffer(1000)
        row = df.loc[sid]
        assert row["fuel_continuity"] == pytest.approx(buf.intersection(north).area / buf.area,
                                                       abs=0.005)
        assert row["aux_fuel_shrub_frac"] == 0.0
        assert row["aux_fuel_coverage"] == pytest.approx(1.0, abs=0.01)
        assert row["slope"] == pytest.approx(12.5)
        n_bld = int(sum(_seg(sid).distance(p) <= 500 for p in rep))
        assert row["aux_wui_buildings"] == n_bld
        assert row["wui_exposure"] == pytest.approx(math.log1p(n_bld))
    assert df["aux_wui_buildings"].tolist() == [2, 2, 2, 1, 1]


def _kde(target: tuple[float, float], points: list[tuple[float, float]], h: float) -> float:
    total = 0.0
    for x, y in points:
        u = math.hypot(x - target[0], y - target[1]) / h
        if u < 1:
            total += (1 - u * u) ** 2
    return total * 3 / (math.pi * h * h) * 1e6


def test_fire_history_viirs_dedup_window_and_kernel(built):
    df, meta = built
    used = [midpoint("1001_0001"), (510150, 4221000), midpoint("2002_0002")]
    for sid in SEGMENTS:
        assert df.loc[sid, "fire_history"] == pytest.approx(_kde(midpoint(sid), used, 2000.0))
    prov = meta["provenance"]["fire_history"]
    assert prov["n_viirs_in_window"] == 4 and prov["n_after_cell_day_dedupe"] == 3
    assert prov["n_viirs_excluded_at_or_after_cutoff"] == 2
    assert prov["max_time_used_utc"] == "2025-05-31T20:30:00+00:00"
    assert prov["coverage_gap_days"] == 0 and prov["bbox_covers_kernel"] is True


def test_current_as_of_uses_current_composite_and_newer_fires(syn):
    ctx = FeatureContext(AOI, syn.root)
    df, meta, _ = build_features(ctx, as_of=CURRENT)
    df = df.set_index("segment_id")
    assert np.allclose(df["fuel_dryness"], 0.3)  # current composite, water still masked
    assert meta["provenance"]["fuel_dryness"]["selected"] == "current"
    fire = meta["provenance"]["fire_history"]
    assert fire["n_after_cell_day_dedupe"] == 5
    # FIRMS ingest ends 2025-09-30 (sidecar): the gap up to as_of is reported, not hidden
    assert fire["coverage_gap_days"] == (CURRENT - date(2025, 9, 30)).days


def test_asset_condition_is_documented_as_unavailable(built):
    df, meta = built
    assert df["asset_condition"].isna().all()
    assert meta["unavailable_factors"] == ["asset_condition"]
    assert meta["nan_counts"]["asset_condition"] == {"no_data_source": len(df)}
    assert not df["nan_reasons"].str.contains("asset_condition").any()


def test_point_is_shapely_point():
    # guards the brute-force reference above against API drift
    assert Point(0, 0).distance(LineString([(0, 1), (1, 1)])) == 1.0
