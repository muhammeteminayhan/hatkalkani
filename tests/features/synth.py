"""Synthetic AOI builder for feature tests (no network, no real data).

Layout (EPSG:32635, metres):
  line 1001 (hv): (510000, 4220000) -> (510300, 4220000), segments 1001_0001..0003
  line 2002 (mv): (510000, 4220400) -> (510200, 4220400), segments 2002_0001..0002
Designed values are documented next to each raster below; the tests rely on them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import yaml
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

METRIC = "EPSG:32635"
AOI = "syn"
AS_OF = date(2025, 5, 31)
CURRENT = date(2026, 10, 30)
TO_LL = Transformer.from_crs(METRIC, "EPSG:4326", always_xy=True)

AOI_YAML = {
    "selected": AOI,
    "storage_crs": "EPSG:4326",
    "metric_crs": METRIC,
    "candidates": [{"id": AOI, "il": "Test", "ilce": "Sentetik"}],
    "segmentation": {"segment_length_m": 100, "min_last_segment_m": 50},
    "buffers_m": {
        "chm_corridor_half_width": 30,
        "dryness": 50,
        "slope": 100,
        "fuel": 1000,
        "wui": 500,
        "history_kernel": 2000,
        "event_line_distance": 500,
        "affected_building": 300,
    },
    "periods": {
        "backtest_asof": "2025-05-31",
        "backtest_s2_window": ["2025-04-15", "2025-05-31"],
        "backtest_season": ["2025-06-01", "2025-09-30"],
        "firms_history": ["2015-01-01", "2024-12-31"],
        "wind_climatology_summers": [2022, 2023, 2024],
        "current_window_days": 45,
        "current_asof": "2026-10-30",
    },
    "demo": {"scenario_date_candidates": ["2025-06-27", "2025-06-30"]},
}
RISK_YAML = {
    "version": "test",
    "normalization": "percentile",
    "combine": "geometric",
    "ignition": {
        "vegetation_encroachment": 0.35,
        "strike_trees": 0.25,
        "fuel_dryness": 0.25,
        "wind_exposure": 0.15,
    },
    "consequence": {
        "fuel_continuity": 0.40,
        "wui_exposure": 0.30,
        "slope": 0.20,
        "fire_history": 0.10,
        "asset_condition": 0.0,
    },
    "parameters": {
        "clearance_band_m": {"lv": 1.0, "mv": 3.0, "hv": 5.0},
        "placeholder_unverified": True,
        "min_encroach_canopy_m": 4.0,
        "strike_margin_m": 1.0,
        "strike_max_distance_m": 30,
        "strike_min_cluster_px": 4,
    },
    "tiers": {"kritik": 0.95, "yuksek": 0.80, "orta": 0.50},  # used by the model tests
    "scenario": {"gust_threshold_kmh": 50, "risk_threshold_tier": "yuksek"},
    "backtest": {"cluster_distance_m": 1000, "cluster_gap_days": 2, "top_shares": [0.1, 0.2],
                 "bootstrap_n": 500, "bootstrap_seed": 7,
                 "sensitivity_line_distance_m": [1000, 2000]},
}

SEGMENTS = {  # segment_id: (line_id, level, x0, x1, y)
    "1001_0001": ("1001", "hv", 510000, 510100, 4220000),
    "1001_0002": ("1001", "hv", 510100, 510200, 4220000),
    "1001_0003": ("1001", "hv", 510200, 510300, 4220000),
    "2002_0001": ("2002", "mv", 510000, 510100, 4220400),
    "2002_0002": ("2002", "mv", 510100, 510200, 4220400),
}
# Every centre is >= 20 m away from any segment's 500 m WUI edge (no ambiguous cases).
BUILDING_CENTRES = [(510050, 4220300), (509680, 4219950), (510600, 4219650), (511000, 4222000)]
WIND_CELLS = {"g00": (509000, 4220200), "g01": (511200, 4220200), "g02": (509000, 4220200)}


def midpoint(sid: str) -> tuple[float, float]:
    _, _, x0, x1, y = SEGMENTS[sid]
    return ((x0 + x1) / 2, y)


def ll(x: float, y: float) -> tuple[float, float]:
    return TO_LL.transform(x, y)


def write_raster(path: Path, arr: np.ndarray, x0: float, y1: float, res: float,
                 nodata: float | int | None) -> None:
    with rasterio.open(
        path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
        dtype=str(arr.dtype), crs=METRIC, transform=from_origin(x0, y1, res, res),
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)


def set_block(arr: np.ndarray, x0g: float, y1g: float, res: float,
              x0: float, x1: float, y0: float, y1: float, value: float) -> None:
    """Set pixels whose centres fall in [x0, x1) x [y0, y1) (grid origin x0g, top y1g)."""
    rows, cols = np.indices(arr.shape)
    cx = x0g + (cols + 0.5) * res
    cy = y1g - (rows + 0.5) * res
    arr[(cx >= x0) & (cx < x1) & (cy >= y0) & (cy < y1)] = value


# ------------------------------------------------------------------ builders
def firms_frame(rows: list[tuple[str, datetime, float, float]]) -> pd.DataFrame:
    """rows: (product, utc datetime, x, y) -> frame shaped like ingest firms.parquet."""
    recs = []
    for product, t, x, y in rows:
        lon, lat = ll(x, y)
        ts = pd.Timestamp(t, tz="UTC")
        recs.append({
            "satellite": "N" if "SNPP" in product else ("N20" if "NOAA20" in product else "Aqua"),
            "product": product,
            "acq_datetime_utc": ts,
            "acq_date": ts.strftime("%Y-%m-%d"),
            "latitude": lat,
            "longitude": lon,
            "confidence": "n",
            "frp": 5.0,
            "daynight": "D",
            "scan": 0.4,
            "track": 0.4,
            "confidence_pct": 60.0,
        })
    df = pd.DataFrame(recs)
    df["acq_datetime_utc"] = pd.to_datetime(df["acq_datetime_utc"], utc=True)
    return df


BASE_FIRMS = [
    ("VIIRS_SNPP_SP", datetime(2020, 7, 1, 10, 30), *midpoint("1001_0001")),
    ("VIIRS_NOAA20_SP", datetime(2020, 7, 1, 11, 20), 510070, 4220010),  # same cell-day
    ("VIIRS_SNPP_SP", datetime(2024, 8, 10, 11, 0), 510150, 4221000),
    ("MODIS_SP", datetime(2023, 7, 1, 9, 0), *midpoint("1001_0002")),  # MODIS: ignored
    ("VIIRS_SNPP_SP", datetime(2025, 5, 31, 20, 30), *midpoint("2002_0002")),  # 23:30 local
    ("VIIRS_SNPP_SP", datetime(2025, 5, 31, 21, 30), *midpoint("1001_0003")),  # 00:30 next
    ("VIIRS_NOAA20_SP", datetime(2025, 7, 15, 10, 0), *midpoint("1001_0003")),  # season
    ("VIIRS_SNPP_SP", datetime(2014, 12, 31, 21, 30), 509000, 4219000),  # before window
]


def wind_frame(extra: list[tuple[str, datetime, float]] | None = None) -> pd.DataFrame:
    """Hourly gusts: g00/g02 (same cell) 8 + hour%6 m/s, g01 twice that; 2022-24 Jun-Sep
    plus scenario days 2025-06-27..30 at 60 m/s (outside the climatology years)."""
    times: list[datetime] = []
    for y in (2022, 2023, 2024):
        t, end = datetime(y, 6, 1), datetime(y, 10, 1)
        while t < end:
            times.append(t)
            t += timedelta(hours=1)
    scen = [datetime(2025, 6, 27) + timedelta(hours=h) for h in range(96)]
    recs = []
    for pid, (x, y) in WIND_CELLS.items():
        lon, lat = ll(x, y)
        for t in times:
            g = 8.0 + t.hour % 6
            recs.append((pid, lat, lon, t, g * (2 if pid == "g01" else 1)))
        for t in scen:
            recs.append((pid, lat, lon, t, 60.0))
    for pid, t, g in extra or []:
        x, y = WIND_CELLS[pid]
        lon, lat = ll(x, y)
        recs.append((pid, lat, lon, t, g))
    df = pd.DataFrame(recs, columns=["point_id", "lat", "lon", "time_local", "wind_gust_10m_ms"])
    df["time_local"] = pd.to_datetime(df["time_local"])
    df["wind_speed_10m_ms"] = df["wind_gust_10m_ms"] / 2
    df["wind_direction_10m_deg"] = 0.0
    df["time_utc"] = df["time_local"].dt.tz_localize("Europe/Istanbul").dt.tz_convert("UTC")
    return df


def s2_meta(extra: dict | None = None) -> dict:
    periods = {
        "backtest": {
            "window": ["2025-04-15", "2025-05-31"],
            "scenes": [{"id": "a", "datetime": "2025-04-16T09:00:00+00:00"},
                       {"id": "b", "datetime": "2025-05-31T09:10:00+00:00"}],
        },
        "current": {
            "window": ["2026-09-15", "2026-10-30"],
            "scenes": [{"id": "c", "datetime": "2026-09-15T09:10:00+00:00"},
                       {"id": "d", "datetime": "2026-10-25T09:10:00+00:00"}],
        },
    }
    periods.update(extra or {})
    return {"collection": "synthetic", "periods": periods}


@dataclass
class SynRoot:
    root: Path

    @property
    def interim(self) -> Path:
        return self.root / "data" / "interim" / AOI

    @property
    def processed(self) -> Path:
        return self.root / "data" / "processed" / AOI

    def write_firms(self, rows: list[tuple[str, datetime, float, float]]) -> None:
        firms_frame(rows).to_parquet(self.interim / "firms.parquet", index=False)

    def write_wind(self, extra: list[tuple[str, datetime, float]] | None = None) -> None:
        wind_frame(extra).to_parquet(self.interim / "wind_hourly.parquet", index=False)

    def write_s2_meta(self, extra: dict | None = None) -> None:
        (self.interim / "s2_meta.json").write_text(json.dumps(s2_meta(extra)), encoding="utf-8")

    def s2_grid(self) -> tuple[float, float, float]:
        return (507800.0, 4222610.0, 20.0)  # y shifted 10 m: no pixel centre on an edge

    def write_s2(self, name: str, arr: np.ndarray) -> None:
        x0, y1, res = self.s2_grid()
        write_raster(self.interim / f"s2_ndmi_{name}.tif", arr.astype("float32"), x0, y1,
                     res, float("nan"))

    def write_chm(self, arr: np.ndarray, nodata: int = 255, **profile_overrides) -> None:
        prof = dict(driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
                    dtype=str(arr.dtype), crs=METRIC,
                    transform=from_origin(509900, 4220500, 1.0, 1.0), nodata=nodata)
        prof.update(profile_overrides)
        with rasterio.open(self.interim / "chm_corridor.tif", "w", **prof) as dst:
            dst.write(arr, 1)


def base_s2_backtest(root: SynRoot) -> np.ndarray:
    x0, y1, res = root.s2_grid()
    a = np.full((240, 240), -0.2, dtype="float32")
    set_block(a, x0, y1, res, 510100, 510200, 4219950, 4220050, 0.4)  # 1001_0002 wet
    # 1001_0003: land rows -0.3/-0.2/-0.1 (median -0.2); water rows 0.9 must be masked
    set_block(a, x0, y1, res, 510200, 510300, 4219950, 4219970, -0.3)
    set_block(a, x0, y1, res, 510200, 510300, 4219990, 4220010, -0.1)
    set_block(a, x0, y1, res, 510200, 510300, 4220010, 4220050, 0.9)
    set_block(a, x0, y1, res, 510100, 510200, 4220350, 4220450, np.nan)  # 2002_0002 cloud
    return a


def base_chm() -> np.ndarray:
    """1 m grid x 509900..510400, y 4219900..4220500 (500 x 600 px)."""
    a = np.zeros((600, 500), dtype="uint8")
    g = (509900, 4220500, 1.0)
    set_block(a, *g, 510010, 510030, 4220000, 4220004, 10)  # 80 px in hv band, strike
    set_block(a, *g, 510060, 510063, 4220020, 4220023, 25)  # 9 px strike at d~21 m
    set_block(a, *g, 510080, 510081, 4220010, 4220011, 30)  # 1 px: below min cluster
    set_block(a, *g, 510090, 510095, 4219999, 4220000, 2)  # 5 px shrub strike, not tall
    set_block(a, *g, 510200, 510300, 4219960, 4220040, 255)  # 1001_0003: no coverage
    set_block(a, *g, 510000, 510100, 4220370, 4220430, 15)  # 2002_0001 full canopy
    return a


def make_syn_root(root: Path) -> SynRoot:
    s = SynRoot(root)
    (root / "config").mkdir(parents=True)
    (root / "config" / "aoi.yaml").write_text(yaml.safe_dump(AOI_YAML), encoding="utf-8")
    (root / "config" / "risk_weights.yaml").write_text(yaml.safe_dump(RISK_YAML),
                                                       encoding="utf-8")
    s.interim.mkdir(parents=True)
    s.processed.mkdir(parents=True)

    rows = []
    for sid, (line, level, x0, x1, y) in SEGMENTS.items():
        rows.append({
            "segment_id": sid, "seq": int(sid[-4:]), "source": "osm", "line_id": line,
            "source_id": line, "power": "line" if level == "hv" else "minor_line",
            "voltage_kv": 154.0 if level == "hv" else None,
            "voltage_class": "ge154kv" if level == "hv" else "etiketsiz",
            "voltage_level": level, "voltage_source": "tag" if level == "hv" else "assumed",
            "length_m": float(x1 - x0), "geometry": LineString([(x0, y), (x1, y)]),
        })
    gpd.GeoDataFrame(rows, crs=METRIC).to_crs("EPSG:4326").to_parquet(
        s.processed / "segments.parquet", index=False)
    gpd.GeoDataFrame({"aoi_id": [AOI]}, geometry=[box(508000, 4218000, 512400, 4222400)],
                     crs=METRIC).to_crs("EPSG:4326").to_parquet(
        s.processed / "boundary.parquet", index=False)

    s.write_chm(base_chm())
    s.write_s2("backtest", base_s2_backtest(s))
    s.write_s2("current", np.full((240, 240), 0.3, dtype="float32"))
    s.write_s2_meta()

    wc = np.full((480, 480), 30, dtype="uint8")  # grassland
    set_block(wc, 507800, 4222600, 10.0, 0, 1e9, 4220200, 1e9, 10)  # tree north of 4220200
    set_block(wc, 507800, 4222600, 10.0, 510200, 510300, 4220010, 4220050, 80)  # water
    write_raster(s.interim / "worldcover.tif", wc, 507800, 4222600, 10.0, 0)

    write_raster(s.interim / "dem_slope.tif", np.full((160, 160), 12.5, dtype="float32"),
                 507800, 4222600, 30.0, -9999.0)
    tpi = np.full((160, 160), -20.0, dtype="float32")
    set_block(tpi, 507800, 4222600, 30.0, 0, 1e9, 4220200, 1e9, 20.0)
    write_raster(s.interim / "dem_tpi.tif", tpi, 507800, 4222600, 30.0, -9999.0)

    gpd.GeoDataFrame(
        {"source": "overture", "source_id": [f"b{i}" for i in range(len(BUILDING_CENTRES))]},
        geometry=[box(x - 5, y - 5, x + 5, y + 5) for x, y in BUILDING_CENTRES], crs=METRIC,
    ).to_crs("EPSG:4326").to_parquet(s.interim / "buildings.parquet")
    s.write_firms(BASE_FIRMS)
    s.write_wind()
    (s.interim / "chm_meta.json").write_text(json.dumps({
        "chm_version": "synthetic", "image_dates": {"v2": "unknown"},
        "value_semantics": "uint8 canopy height in metres; 255 = outside corridor / no data",
    }), encoding="utf-8")
    side = root / "data" / "raw" / "firms" / AOI
    side.mkdir(parents=True)
    (side / "VIIRS_SNPP_2025.meta.json").write_text(json.dumps({
        "bbox": [26.9, 38.0, 27.3, 38.2], "start": "2025-01-01", "end": "2025-09-30",
    }), encoding="utf-8")
    return s
