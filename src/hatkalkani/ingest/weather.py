"""Open-Meteo hourly wind for the AOI (climatology summers + scenario days).

Run: ``uv run python -m hatkalkani.ingest.weather --aoi izmir_menderes``

Open-Meteo returns km/h by default; values are converted to m/s and the unit is part of the
column names. Times are requested in Europe/Istanbul (local) and also stored as UTC.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

from hatkalkani.ingest.common import (
    ROOT,
    USER_AGENT,
    is_cached,
    load_aoi,
    processed_dir,
    register,
)

log = logging.getLogger("hatkalkani.ingest.weather")

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
LICENSE = "CC BY 4.0; Weather data by Open-Meteo.com"
TZ = "Europe/Istanbul"
HOURLY = "wind_speed_10m,wind_gusts_10m,wind_direction_10m"
GRID_KM = 10.0
KMH_TO_MS = 1.0 / 3.6


def grid_points(
    bounds: tuple[float, float, float, float], step_km: float = GRID_KM
) -> list[tuple[float, float]]:
    """Cell-centre grid (lat, lon) covering the bbox with ~step_km spacing."""
    west, south, east, north = bounds
    mid_lat = (south + north) / 2
    dlat = step_km / 111.0
    dlon = step_km / (111.0 * np.cos(np.radians(mid_lat)))
    nlat = max(1, int(np.ceil((north - south) / dlat)))
    nlon = max(1, int(np.ceil((east - west) / dlon)))
    lats = south + (np.arange(nlat) + 0.5) * (north - south) / nlat
    lons = west + (np.arange(nlon) + 0.5) * (east - west) / nlon
    return [(round(float(a), 3), round(float(o), 3)) for a in lats for o in lons]


def periods_from_config(cfg: dict) -> list[tuple[date, date]]:
    """Climatology summers (Jun 1 - Sep 30) plus the scenario-day span."""
    out = [(date(y, 6, 1), date(y, 9, 30)) for y in cfg["periods"]["wind_climatology_summers"]]
    cands = sorted(date.fromisoformat(d) for d in cfg["demo"]["scenario_date_candidates"])
    out.append((cands[0], cands[-1]))
    return out


def parse_response(payload: dict, point_id: str) -> pd.DataFrame:
    """Convert an Open-Meteo hourly payload to the normalized frame (m/s)."""
    h = payload["hourly"]
    t_local = pd.to_datetime(h["time"])
    df = pd.DataFrame(
        {
            "point_id": point_id,
            "lat": payload["latitude"],
            "lon": payload["longitude"],
            "time_local": t_local,
            "wind_speed_10m_ms": np.asarray(h["wind_speed_10m"], dtype=float) * KMH_TO_MS,
            "wind_gust_10m_ms": np.asarray(h["wind_gusts_10m"], dtype=float) * KMH_TO_MS,
            "wind_direction_10m_deg": np.asarray(h["wind_direction_10m"], dtype=float),
        }
    )
    df["time_utc"] = df["time_local"].dt.tz_localize(TZ, ambiguous="NaT").dt.tz_convert("UTC")
    return df


def fetch_json(lat: float, lon: float, start: date, end: date) -> Path:
    dest = ROOT / "data" / "raw" / "open_meteo" / f"wind_{lat:.3f}_{lon:.3f}_{start}_{end}.json"
    if is_cached(dest):
        return dest
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": HOURLY,
        "wind_speed_unit": "kmh",
        "timezone": TZ,
    }
    last = ""
    for attempt in range(3):
        try:
            r = requests.get(
                ARCHIVE_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=60
            )
            if r.status_code == 200:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(r.json()), encoding="utf-8")
                register(dest, "open-meteo", r.url, LICENSE)
                time.sleep(0.5)
                return dest
            last = f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            last = str(exc)
        time.sleep(15 * 2**attempt)
    raise RuntimeError(f"Open-Meteo failed: {last}")


def build(aoi_id: str) -> Path:
    import geopandas as gpd

    cfg = yaml.safe_load((ROOT / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    load_aoi(aoi_id)
    b = gpd.read_parquet(processed_dir(aoi_id) / "boundary.parquet").to_crs("EPSG:4326")
    pts = grid_points(tuple(b.total_bounds))
    log.info("grid points: %d", len(pts))
    frames = []
    for i, (lat, lon) in enumerate(pts):
        for s, e in periods_from_config(cfg):
            p = fetch_json(lat, lon, s, e)
            frames.append(
                parse_response(json.loads(p.read_text(encoding="utf-8")), f"g{i:02d}")
            )
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(["point_id", "time_local"]).sort_values(["point_id", "time_local"])
    out = ROOT / "data" / "interim" / aoi_id / "wind_hourly.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.reset_index(drop=True).to_parquet(out, index=False)
    log.info("wrote %s rows=%d", out, len(df))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--aoi", required=True)
    build(ap.parse_args().aoi)


if __name__ == "__main__":
    main()
