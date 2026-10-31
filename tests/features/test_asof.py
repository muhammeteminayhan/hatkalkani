"""as_of semantics: local-day cutoff (ADR-009), parsing and the runtime leakage guard."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from hatkalkani.features.asof import (
    AsOf,
    TemporalLeakageError,
    assert_before_cutoff,
    before_cutoff,
    local_day_start,
    parse_as_of,
)


def test_cutoff_is_start_of_next_local_day():
    a = AsOf(date(2025, 5, 31))
    assert a.cutoff_local == pd.Timestamp("2025-06-01T00:00:00+03:00")
    assert a.cutoff_utc == pd.Timestamp("2025-05-31T21:00:00Z")


def test_cutoff_uses_historical_offset_before_2016():
    # Turkey used EET (UTC+2) in winter until 2016.
    assert AsOf(date(2015, 1, 10)).cutoff_utc == pd.Timestamp("2015-01-10T22:00:00Z")
    assert local_day_start(date(2015, 1, 1)) == pd.Timestamp("2014-12-31T22:00:00Z")


def test_before_cutoff_boundary_and_nat():
    t = pd.Series(pd.to_datetime(
        ["2025-05-31T20:59:59Z", "2025-05-31T21:00:00Z", None, "2025-06-02T00:00:00Z"],
        utc=True,
    ))
    assert before_cutoff(t, AsOf(date(2025, 5, 31))).tolist() == [True, False, False, False]


def test_before_cutoff_rejects_naive_timestamps():
    with pytest.raises(ValueError, match="time-zone aware"):
        before_cutoff(pd.Series(pd.to_datetime(["2025-05-31 10:00"])), AsOf(date(2025, 5, 31)))


def test_parse_as_of_variants():
    d = date(2026, 10, 30)
    assert parse_as_of("2026-10-30") == parse_as_of(d) == parse_as_of(AsOf(d)) == AsOf(d)
    with pytest.raises(TypeError):
        parse_as_of(datetime(2026, 10, 30, 12))
    with pytest.raises(ValueError):
        parse_as_of("30.10.2026")


def test_assert_before_cutoff_guard():
    a = AsOf(date(2025, 5, 31))
    assert_before_cutoff(None, a, "x")
    assert_before_cutoff("2025-05-31T20:59:59+00:00", a, "x")
    with pytest.raises(TemporalLeakageError):
        assert_before_cutoff("2025-05-31T21:00:00+00:00", a, "x")
    with pytest.raises(ValueError, match="naive"):
        assert_before_cutoff("2025-05-01T00:00:00", a, "x")
