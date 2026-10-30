"""NASA FIRMS active-fire detections for the AOI bbox (+ margin), 2015-2025 season.

Run: ``uv run python -m hatkalkani.ingest.firms --aoi izmir_menderes``

The MAP_KEY is read from the environment (.env via python-dotenv) and is always masked in
logs, URLs recorded in MANIFEST and error messages.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import math
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import yaml

from hatkalkani.ingest.common import (
    ROOT,
    USER_AGENT,
    is_cached,
    load_aoi,
    manifest_remove,
    processed_dir,
    read_manifest,
    register,
)

log = logging.getLogger("hatkalkani.ingest.firms")

BASE = "https://firms.modaps.eosdis.nasa.gov/api"
SOURCES = ["VIIRS_SNPP", "VIIRS_NOAA20", "MODIS"]
LICENSE = "NASA FIRMS open data; cite: NASA FIRMS (LANCE/EOSDIS)"
MARGIN_KM = 5.0
CHUNK_DAYS = 5  # API accepts 1..5 days per request
SLEEP_S = 0.1  # polite spacing; far below the 5000 transactions / 10 min quota
KEEP_COLUMNS = [
    "satellite",
    "product",
    "acq_datetime_utc",
    "acq_date",
    "latitude",
    "longitude",
    "confidence",
    "frp",
    "daynight",
    "scan",
    "track",
]


class FirmsKeyError(RuntimeError):
    """Raised when FIRMS rejects the MAP_KEY or the key is missing."""


def mask(text: str, key: str | None) -> str:
    return text.replace(key, "***") if key else text


def expand_bbox(
    west: float, south: float, east: float, north: float, margin_km: float
) -> tuple[float, float, float, float]:
    dlat = margin_km / 111.0
    dlon = margin_km / (111.0 * math.cos(math.radians((south + north) / 2)))
    return west - dlon, south - dlat, east + dlon, north + dlat


def date_chunks(start: date, end: date, days: int = CHUNK_DAYS) -> list[tuple[date, int]]:
    """Split [start, end] into (chunk_start, n_days) pieces of at most `days` days."""
    out: list[tuple[date, int]] = []
    cur = start
    while cur <= end:
        n = min(days, (end - cur).days + 1)
        out.append((cur, n))
        cur += timedelta(days=n)
    return out


def parse_firms_csv(text: str, source: str) -> pd.DataFrame:
    """Parse a FIRMS area CSV into a normalized frame (empty frame when no rows)."""
    head = text.lstrip()[:200].lower()
    if not head.startswith("latitude"):
        if "invalid" in head or "map_key" in head or "key" in head:
            raise FirmsKeyError("FIRMS rejected the MAP_KEY")
        if head == "":
            return pd.DataFrame(columns=KEEP_COLUMNS)
        raise RuntimeError(f"Unexpected FIRMS response: {head[:80]!r}")
    df = pd.read_csv(io.StringIO(text), dtype={"acq_time": str})
    if df.empty:
        return pd.DataFrame(columns=KEEP_COLUMNS)
    hhmm = df["acq_time"].astype(str).str.zfill(4)
    df["acq_datetime_utc"] = pd.to_datetime(
        df["acq_date"].astype(str) + " " + hhmm, format="%Y-%m-%d %H%M", utc=True
    )
    df["product"] = source
    if "satellite" not in df:
        df["satellite"] = source
    df["confidence"] = df["confidence"].astype(str)  # VIIRS: l/n/h, MODIS: 0-100
    for col in KEEP_COLUMNS:
        if col not in df:
            df[col] = pd.NA
    return df[KEEP_COLUMNS]


def normalize_confidence(conf: pd.Series) -> pd.Series:
    """Map VIIRS l/n/h and MODIS 0-100 to a common 0-100 numeric score."""
    mapping = {"l": 25.0, "n": 60.0, "h": 90.0}
    s = conf.astype(str).str.strip().str.lower()
    num = pd.to_numeric(s, errors="coerce")
    return num.fillna(s.map(mapping))


def get_key() -> str:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not key:
        raise FirmsKeyError("FIRMS_MAP_KEY not set")
    return key


def http_get(url: str, key: str, timeout: int = 60) -> str:
    last: str = ""
    errors = 0
    quota_waits = 0
    while errors < 3 and quota_waits < 12:
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            if r.status_code == 200:
                return r.text
            body = r.text.lower()
            last = f"HTTP {r.status_code}"
            if "map_key" in body or r.status_code == 401:
                raise FirmsKeyError(f"FIRMS HTTP {r.status_code}")
            if "limit" in body or r.status_code in (400, 403, 429):
                # Quota window (5000 transactions / 10 min): wait it out, then retry.
                quota_waits += 1
                log.info(
                    "FIRMS HTTP %s (%s), waiting 90 s (%d)",
                    r.status_code,
                    mask(r.text[:60], key).strip(),
                    quota_waits,
                )
                time.sleep(90)
                continue
        except requests.RequestException as exc:
            last = mask(str(exc), key)
        errors += 1
        time.sleep(5 * 2**errors)
    raise RuntimeError(f"FIRMS request failed: {last}")


def availability(key: str) -> dict[str, tuple[date, date]]:
    """Per data-set (min_date, max_date) from /api/data_availability."""
    text = http_get(f"{BASE}/data_availability/csv/{key}/ALL", key)
    df = pd.read_csv(io.StringIO(text))
    out: dict[str, tuple[date, date]] = {}
    for _, r in df.iterrows():
        out[str(r["data_id"])] = (
            datetime.strptime(str(r["min_date"]), "%Y-%m-%d").date(),
            datetime.strptime(str(r["max_date"]), "%Y-%m-%d").date(),
        )
    return out


def fetch_range(
    key: str, product: str, bbox: tuple[float, float, float, float], start: date, end: date
) -> pd.DataFrame:
    area = ",".join(f"{v:.4f}" for v in bbox)
    frames = []
    for d0, n in date_chunks(start, end):
        url = f"{BASE}/area/csv/{key}/{product}/{area}/{n}/{d0.isoformat()}"
        frames.append(parse_firms_csv(http_get(url, key), product))
        time.sleep(SLEEP_S)
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=KEEP_COLUMNS)


def year_file(aoi_id: str, source: str, year: int, root: Path = ROOT) -> Path:
    """Per-AOI raw cache path: data/raw/firms/<aoi_id>/<source>_<year>.csv."""
    return root / "data" / "raw" / "firms" / aoi_id / f"{source}_{year}.csv"


def legacy_year_file(source: str, year: int, root: Path = ROOT) -> Path:
    return root / "data" / "raw" / "firms" / f"{source}_{year}.csv"


def sidecar_path(dest: Path) -> Path:
    return dest.with_suffix(".meta.json")


def expected_meta(
    aoi_id: str,
    source: str,
    year: int,
    bbox: tuple[float, float, float, float],
    last_day: date,
) -> dict[str, object]:
    """What a cached year file must have been built from (no data_ids; those are a result)."""
    return {
        "aoi_id": aoi_id,
        "source": source,
        "year": year,
        "bbox": [round(v, 4) for v in bbox],
        "start": date(year, 1, 1).isoformat(),
        "end": min(date(year, 12, 31), last_day).isoformat(),
    }


def is_fresh(dest: Path, expected: dict[str, object], root: Path = ROOT) -> bool:
    """Cached bytes (sha256 in MANIFEST) built from the same AOI, bbox and date window.

    Files containing NRT data are provisional: standard-processing data may supersede them.
    """
    side = sidecar_path(dest)
    if not is_cached(dest, root) or not side.exists():
        return False
    try:
        got = json.loads(side.read_text(encoding="utf-8"))
    except ValueError:
        return False
    if any(got.get(k) != v for k, v in expected.items()):
        return False
    return not any(str(d).endswith("_NRT") for d in got.get("data_ids", []))


def _firms_url(data_ids: list[str], meta: dict[str, object]) -> str:
    bb = ",".join(f"{v:.4f}" for v in meta["bbox"])  # type: ignore[attr-defined]
    return f"{BASE}/area/csv/***/{'|'.join(data_ids)}/{bb}/{meta['start']}..{meta['end']}"


def write_year_meta(
    dest: Path, expected: dict[str, object], data_ids: list[str], root: Path = ROOT
) -> None:
    meta = {**expected, "data_ids": data_ids}
    sidecar_path(dest).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    register(dest, f"firms:{expected['source']}", _firms_url(data_ids, meta), LICENSE, root)


def migrate_legacy(
    aoi_id: str, source: str, year: int, expected: dict[str, object], root: Path = ROOT
) -> bool:
    """Move a pre-AOI-keyed year file into the new layout when its recorded bbox matches.

    The legacy MANIFEST url holds the bbox; rows must all be standard processing (_SP) and
    lie inside the expected date window. Returns True when the file was migrated.
    """
    old = legacy_year_file(source, year, root)
    if not old.exists():
        return False
    rel = old.relative_to(root).as_posix()
    rows = [r for r in read_manifest(root) if r["yerel_yol"] == rel]
    if not rows or not is_cached(old, root):
        return False
    parts = rows[0]["url"].split("/")
    try:
        old_bbox = [round(float(v), 4) for v in parts[-2].split(",")]
    except ValueError:
        return False
    if old_bbox != expected["bbox"] or parts[-1] != str(year):
        return False
    df = pd.read_csv(old, dtype={"confidence": str})
    if not df.empty:
        days = pd.to_datetime(df["acq_date"]).dt.date
        if days.min() < date.fromisoformat(str(expected["start"])):
            return False
        if days.max() > date.fromisoformat(str(expected["end"])):
            return False
    products = sorted(df["product"].dropna().unique().tolist()) if not df.empty else []
    data_ids = products or [f"{source}_SP"]
    if not all(p.startswith(f"{source}_") and p.endswith("_SP") for p in data_ids):
        return False
    new = year_file(aoi_id, source, year, root)
    new.parent.mkdir(parents=True, exist_ok=True)
    old.replace(new)
    manifest_remove(rel, root)
    write_year_meta(new, expected, data_ids, root)
    return True


def fetch_year(
    key: str,
    aoi_id: str,
    source: str,
    year: int,
    bbox: tuple[float, float, float, float],
    avail: dict[str, tuple[date, date]],
    last_day: date,
) -> Path:
    dest = year_file(aoi_id, source, year)
    expected = expected_meta(aoi_id, source, year, bbox, last_day)
    start = date.fromisoformat(str(expected["start"]))
    end = date.fromisoformat(str(expected["end"]))
    sp_id, nrt_id = f"{source}_SP", f"{source}_NRT"
    sp_min, sp_max = avail.get(sp_id, (date.max, date.min))
    parts = []
    used: list[str] = []
    # Standard-processing where available; NRT fills the remaining tail.
    s0, s1 = max(start, sp_min), min(end, sp_max)
    if s0 <= s1:
        parts.append(fetch_range(key, sp_id, bbox, s0, s1))
        used.append(sp_id)
    tail0 = max(start, s1 + timedelta(days=1)) if s0 <= s1 else start
    if tail0 <= end and nrt_id in avail:
        n0, n1 = avail[nrt_id]
        t0, t1 = max(tail0, n0), min(end, n1)
        if t0 <= t1:
            parts.append(fetch_range(key, nrt_id, bbox, t0, t1))
            used.append(nrt_id)
    parts = [p for p in parts if not p.empty]
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=KEEP_COLUMNS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dest, index=False, encoding="utf-8")
    write_year_meta(dest, expected, used)
    return dest


def build(aoi_id: str) -> Path:
    cfg = yaml.safe_load((ROOT / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    load_aoi(aoi_id)  # validates AOI id
    import geopandas as gpd

    b = gpd.read_parquet(processed_dir(aoi_id) / "boundary.parquet").to_crs("EPSG:4326")
    bbox = expand_bbox(*b.total_bounds, MARGIN_KM)
    first = date.fromisoformat(cfg["periods"]["firms_history"][0])
    last = date.fromisoformat(cfg["periods"]["backtest_season"][1])
    out = ROOT / "data" / "interim" / aoi_id / "firms.parquet"

    years = range(first.year, last.year + 1)
    needed = [(s, y) for s in SOURCES for y in years]
    key = None
    avail: dict[str, tuple[date, date]] = {}
    paths = []
    for s, y in needed:
        expected = expected_meta(aoi_id, s, y, bbox, last)
        dest = year_file(aoi_id, s, y)
        if is_fresh(dest, expected) or migrate_legacy(aoi_id, s, y, expected):
            paths.append(dest)
            continue
        if key is None:
            key = get_key()
            avail = availability(key)
        log.info("fetching %s %d", s, y)
        paths.append(fetch_year(key, aoi_id, s, y, bbox, avail, last))
    frames = []
    for p in paths:
        df = pd.read_csv(p, dtype={"confidence": str})
        if not df.empty:
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["acq_datetime_utc"] = pd.to_datetime(df["acq_datetime_utc"], utc=True)
    df["confidence_pct"] = normalize_confidence(df["confidence"])
    df = df[(df["acq_datetime_utc"].dt.date >= first) & (df["acq_datetime_utc"].dt.date <= last)]
    df = df.drop_duplicates(["product", "satellite", "acq_datetime_utc", "latitude", "longitude"])
    df = df.sort_values("acq_datetime_utc").reset_index(drop=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info("wrote %s rows=%d", out, len(df))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--aoi", required=True)
    args = ap.parse_args()
    try:
        build(args.aoi)
    except FirmsKeyError as exc:
        raise SystemExit(f"FIRMS anahtar sorunu: {exc}") from None


if __name__ == "__main__":
    main()
