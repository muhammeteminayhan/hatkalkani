"""Offline tests for FIRMS and Open-Meteo parsing (sample responses, no network)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from hatkalkani.ingest import firms, weather

FIRMS_SAMPLE = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_ti5,frp,daynight\n"
    "38.10,27.20,330.1,0.4,0.4,2025-06-29,0042,N,VIIRS,h,2.0NRT,290.0,12.5,N\n"
    "38.11,27.21,320.0,0.4,0.4,2025-06-29,1305,N,VIIRS,l,2.0NRT,290.0,3.1,D\n"
)


def test_parse_firms_csv_datetime_and_columns():
    df = firms.parse_firms_csv(FIRMS_SAMPLE, "VIIRS_SNPP_NRT")
    assert len(df) == 2
    assert df["acq_datetime_utc"].iloc[0].hour == 0
    assert df["acq_datetime_utc"].iloc[0].minute == 42
    assert df["acq_datetime_utc"].iloc[1].hour == 13
    assert set(firms.KEEP_COLUMNS) <= set(df.columns)


def test_parse_firms_header_only_is_empty():
    header = FIRMS_SAMPLE.splitlines()[0] + "\n"
    assert firms.parse_firms_csv(header, "MODIS_SP").empty


def test_parse_firms_invalid_key_raises():
    with pytest.raises(firms.FirmsKeyError):
        firms.parse_firms_csv("Invalid MAP_KEY.", "MODIS_SP")


def test_normalize_confidence_mixed():
    import pandas as pd

    out = firms.normalize_confidence(pd.Series(["h", "l", "n", "85"]))
    assert out.tolist() == [90.0, 25.0, 60.0, 85.0]


def test_date_chunks_cover_range_without_overlap():
    chunks = firms.date_chunks(date(2025, 1, 1), date(2025, 1, 12), 5)
    assert [n for _, n in chunks] == [5, 5, 2]
    assert chunks[1][0] == date(2025, 1, 6)


def test_mask_hides_key():
    assert "SECRET" not in firms.mask("https://x/SECRET/y", "SECRET")


def test_expand_bbox_adds_margin():
    w, s, e, n = firms.expand_bbox(27.0, 38.0, 27.2, 38.2, 5.0)
    assert s < 38.0 and n > 38.2 and w < 27.0 and e > 27.2
    assert abs((38.0 - s) - 5 / 111) < 1e-9


def test_grid_points_spacing_and_inside():
    pts = weather.grid_points((26.94, 37.98, 27.31, 38.32))
    assert 9 <= len(pts) <= 25
    assert all(37.98 <= la <= 38.32 and 26.94 <= lo <= 27.31 for la, lo in pts)


def test_parse_open_meteo_converts_kmh_to_ms():
    payload = {
        "latitude": 38.1,
        "longitude": 27.2,
        "hourly": {
            "time": ["2025-06-29T00:00", "2025-06-29T01:00"],
            "wind_speed_10m": [36.0, 18.0],
            "wind_gusts_10m": [72.0, 36.0],
            "wind_direction_10m": [350, 10],
        },
    }
    df = weather.parse_response(payload, "g00")
    assert np.allclose(df["wind_speed_10m_ms"], [10.0, 5.0])
    assert np.allclose(df["wind_gust_10m_ms"], [20.0, 10.0])
    assert df["time_utc"].iloc[0].hour == 21  # UTC+3 local midnight


def test_periods_from_config():
    cfg = {
        "periods": {"wind_climatology_summers": [2022, 2023]},
        "demo": {"scenario_date_candidates": ["2025-06-30", "2025-06-27"]},
    }
    p = weather.periods_from_config(cfg)
    assert p[0] == (date(2022, 6, 1), date(2022, 9, 30))
    assert p[-1] == (date(2025, 6, 27), date(2025, 6, 30))


def _firms_root(tmp_path, bbox, product="MODIS_SP", day="2020-03-01"):
    import csv as _csv

    from hatkalkani.ingest import common

    root = tmp_path
    legacy = root / "data" / "raw" / "firms" / "MODIS_2020.csv"
    legacy.parent.mkdir(parents=True)
    pd.DataFrame({"product": [product], "acq_date": [day]}).to_csv(legacy, index=False)
    url = f"https://x/api/area/csv/***/MODIS_SP|NRT/{','.join(f'{v:.4f}' for v in bbox)}/2020"
    row = {
        "kaynak": "firms:MODIS", "url": url, "yerel_yol": "data/raw/firms/MODIS_2020.csv",
        "bayt": "1", "sha256": common.sha256_file(legacy), "tarih": "2026-10-30", "lisans": "L",
    }
    common.manifest_upsert(row, root)
    assert _csv  # keep import used
    return root, legacy


def test_firms_cache_keyed_by_aoi_bbox_and_window(tmp_path):
    from datetime import date as d

    bbox = (26.8865, 37.935, 27.371, 38.3641)
    root, legacy = _firms_root(tmp_path, bbox)
    last = d(2025, 9, 30)
    exp = firms.expected_meta("aoi_a", "MODIS", 2020, bbox, last)
    assert firms.migrate_legacy("aoi_a", "MODIS", 2020, exp, root)
    new = firms.year_file("aoi_a", "MODIS", 2020, root)
    assert new.exists() and not legacy.exists()
    assert firms.is_fresh(new, exp, root)
    # another AOI never reuses it
    assert not firms.is_fresh(
        firms.year_file("aoi_b", "MODIS", 2020, root),
        firms.expected_meta("aoi_b", "MODIS", 2020, bbox, last),
        root,
    )
    # changed bbox (e.g. MARGIN_KM) or shortened window -> stale
    other = firms.expected_meta("aoi_a", "MODIS", 2020, (26.0, 37.9, 27.3, 38.3), last)
    assert not firms.is_fresh(new, other, root)
    exp25 = firms.expected_meta("aoi_a", "MODIS", 2025, bbox, last)
    assert exp25["end"] == "2025-09-30"
    assert firms.expected_meta("aoi_a", "MODIS", 2025, bbox, d(2025, 6, 30))["end"] != exp25["end"]
    mism = {**exp, "end": "2020-06-30"}
    assert not firms.is_fresh(new, mism, root)


def test_firms_migration_refused_on_bbox_mismatch_and_nrt_is_provisional(tmp_path):
    from datetime import date as d

    root, legacy = _firms_root(tmp_path, (1.0, 2.0, 3.0, 4.0))
    real = (26.8865, 37.935, 27.371, 38.3641)
    exp = firms.expected_meta("aoi_a", "MODIS", 2020, real, d(2025, 9, 30))
    assert not firms.migrate_legacy("aoi_a", "MODIS", 2020, exp, root)
    assert legacy.exists()
    # NRT-filled file is never considered fresh
    dest = firms.year_file("aoi_a", "MODIS", 2020, root)
    dest.parent.mkdir(parents=True)
    pd.DataFrame({"product": ["MODIS_NRT"]}).to_csv(dest, index=False)
    firms.write_year_meta(dest, exp, ["MODIS_SP", "MODIS_NRT"], root)
    assert not firms.is_fresh(dest, exp, root)
