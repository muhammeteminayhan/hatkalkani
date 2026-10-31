"""as_of semantics shared by every feature (ADR-009).

A feature computed "as of" a date D may use data stamped up to and including the *local*
calendar day D in the AOI time zone (Europe/Istanbul). The exclusive cutoff is therefore
``D + 1 day 00:00 local`` (``D 21:00 UTC`` since Turkey's permanent UTC+3 in 2016).
Timestamps are always compared time-zone aware; naive timestamps are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

from hatkalkani.ingest.weather import TZ as LOCAL_TZ  # time zone the wind data was requested in


class TemporalLeakageError(RuntimeError):
    """Raised when data stamped at/after the as_of cutoff would reach a feature."""


@dataclass(frozen=True)
class AsOf:
    """The as_of date plus its exclusive cutoff instant."""

    day: date
    tz: str = LOCAL_TZ

    @property
    def cutoff_local(self) -> pd.Timestamp:
        """First instant that is NOT allowed (start of the next local day)."""
        return pd.Timestamp(self.day + timedelta(days=1)).tz_localize(self.tz)

    @property
    def cutoff_utc(self) -> pd.Timestamp:
        return self.cutoff_local.tz_convert("UTC")

    def isoformat(self) -> str:
        return self.day.isoformat()

    def __str__(self) -> str:
        return self.isoformat()


def parse_as_of(value: AsOf | date | str) -> AsOf:
    """Accept an AsOf, a ``date`` or an ISO ``YYYY-MM-DD`` string. Datetimes are refused:
    the rule is defined on local calendar days, a clock time would be ambiguous."""
    if isinstance(value, AsOf):
        return value
    if isinstance(value, datetime):
        raise TypeError("as_of must be a calendar date, not a datetime")
    if isinstance(value, date):
        return AsOf(value)
    if isinstance(value, str):
        return AsOf(date.fromisoformat(value.strip()))
    raise TypeError(f"unsupported as_of type: {type(value).__name__}")


def local_day_start(day: date, tz: str = LOCAL_TZ) -> pd.Timestamp:
    """Start of a local calendar day as a UTC timestamp (inclusive window starts)."""
    return pd.Timestamp(day).tz_localize(tz).tz_convert("UTC")


def _require_aware(times: pd.Series, what: str) -> None:
    if not isinstance(times.dtype, pd.DatetimeTZDtype):
        raise ValueError(f"{what}: timestamps must be time-zone aware; refusing to guess")


def before_cutoff(times: pd.Series, as_of: AsOf, what: str = "timestamps") -> pd.Series:
    """Boolean mask: True where the timestamp is strictly before the as_of cutoff.
    Missing timestamps (NaT) are treated as NOT allowed."""
    _require_aware(times, what)
    return (times < as_of.cutoff_utc).fillna(False).astype(bool)


def assert_before_cutoff(latest: pd.Timestamp | str | None, as_of: AsOf, what: str) -> None:
    """Runtime guard used on every provenance record ('max_time_used_utc')."""
    if latest is None:
        return
    ts = pd.Timestamp(latest)
    if pd.isna(ts):
        return
    if ts.tzinfo is None:
        raise ValueError(f"{what}: naive timestamp {latest!r}")
    if ts >= as_of.cutoff_utc:
        raise TemporalLeakageError(
            f"{what}: data at {ts.isoformat()} is not before the as_of cutoff "
            f"{as_of.cutoff_utc.isoformat()} (as_of={as_of})"
        )


def iso_utc(ts: pd.Timestamp | None) -> str | None:
    """JSON-friendly UTC ISO string (None for missing)."""
    if ts is None or pd.isna(ts):
        return None
    return pd.Timestamp(ts).tz_convert("UTC").isoformat()
