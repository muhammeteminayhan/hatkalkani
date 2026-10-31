"""Feature context: configuration, segments and *as_of-filtered* data access.

Factor functions never read time-stamped files directly. FIRMS, wind and Sentinel-2 go
through ``firms_viirs``, ``wind_climatology`` and ``s2_composite``, which apply the as_of
cutoff (ADR-009) and return a provenance record with ``max_time_used_utc``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from hatkalkani.features.asof import (
    AsOf,
    before_cutoff,
    iso_utc,
    local_day_start,
    parse_as_of,
)
from hatkalkani.features.compute import dedupe_fire_cells
from hatkalkani.ingest import common

REQUIRED_SEGMENT_COLUMNS = ("segment_id", "line_id", "voltage_level", "length_m", "geometry")
# FIRMS products used for fire history: VIIRS only (375 m pixels; the backtest events are
# VIIRS as well). MODIS (1 km) is excluded (ADR-009).
VIIRS_PRODUCT_PREFIX = "VIIRS_"
VIIRS_PIXEL_M = 375.0  # nominal VIIRS I-band pixel, risk-model-spec section 5
SUMMER_MONTHS = (6, 7, 8, 9)  # Jun-Sep, risk-model-spec section 2 (wind_exposure)


@dataclass(frozen=True)
class FeatureConfig:
    aoi_id: str
    metric_crs: str
    storage_crs: str
    buffers_m: dict[str, float]
    parameters: dict[str, Any]
    periods: dict[str, Any]
    weights: dict[str, dict[str, float]]


def load_feature_config(aoi_id: str, root: Path = common.ROOT) -> FeatureConfig:
    cfg_dir = Path(root) / "config"
    aoi = common.load_aoi(aoi_id, cfg_dir / "aoi.yaml")  # validates the AOI id
    a = yaml.safe_load((cfg_dir / "aoi.yaml").read_text(encoding="utf-8"))
    rw = yaml.safe_load((cfg_dir / "risk_weights.yaml").read_text(encoding="utf-8"))
    return FeatureConfig(
        aoi_id=aoi_id,
        metric_crs=aoi.metric_crs,
        storage_crs=aoi.storage_crs,
        buffers_m={k: float(v) for k, v in a["buffers_m"].items()},
        parameters=dict(rw["parameters"]),
        periods=dict(a["periods"]),
        weights={
            "ignition": {k: float(v) for k, v in (rw.get("ignition") or {}).items()},
            "consequence": {k: float(v) for k, v in (rw.get("consequence") or {}).items()},
        },
    )


def validate_segments(segs: gpd.GeoDataFrame) -> None:
    missing = [c for c in REQUIRED_SEGMENT_COLUMNS if c not in segs.columns]
    if missing:
        raise ValueError(f"segments.parquet lacks columns {missing}")
    if segs.crs is None:
        raise ValueError("segments.parquet has no CRS; refusing to guess")
    if not segs["segment_id"].is_unique:
        raise ValueError("segment_id is not unique")
    if segs.geometry.isna().any() or segs.geometry.is_empty.any():
        raise ValueError("segments.parquet has empty geometries")


class FeatureContext:
    """Inputs of one AOI. Static intermediates are cached; time-filtered data are not."""

    def __init__(self, aoi_id: str, root: Path = common.ROOT) -> None:
        self.root = Path(root)
        self.cfg = load_feature_config(aoi_id, self.root)
        self.interim = self.root / "data" / "interim" / aoi_id
        self.processed = self.root / "data" / "processed" / aoi_id
        seg_path = self.processed / "segments.parquet"
        segs = gpd.read_parquet(seg_path)
        validate_segments(segs)
        self.segments = segs.reset_index(drop=True)
        self.segments_m = self.segments.to_crs(self.cfg.metric_crs)
        if not self.segments_m.crs.is_projected:
            raise ValueError(f"metric_crs {self.cfg.metric_crs} is not projected")
        self.ids = pd.Index(self.segments["segment_id"].astype(str), name="segment_id")
        self._cache: dict[str, Any] = {}
        self._used: set[Path] = {seg_path}

    # ------------------------------------------------------------------ helpers
    def use(self, name: str) -> Path:
        """Path of an ingest output under data/interim/<aoi>/ (recorded for provenance)."""
        p = self.interim / name
        if not p.exists():
            raise FileNotFoundError(f"missing ingest output {p}; run --stage ingest first")
        self._used.add(p)
        return p

    def used_files(self) -> list[Path]:
        return sorted(self._used)

    def cached(self, key: str, fn: Callable[[], Any]) -> Any:
        """Memoise a *static* intermediate (never call with as_of-dependent data)."""
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def series(self, values: Any, dtype: str = "float64") -> pd.Series:
        return pd.Series(np.asarray(values), index=self.ids, dtype=dtype)

    def midpoints_m(self) -> gpd.GeoSeries:
        return self.cached(
            "midpoints_m",
            lambda: self.segments_m.geometry.interpolate(0.5, normalized=True),
        )

    def boundary_m(self) -> BaseGeometry:
        path = self.processed / "boundary.parquet"

        def load() -> BaseGeometry:
            b = gpd.read_parquet(path)
            if b.crs is None:
                raise ValueError("boundary.parquet has no CRS")
            return b.to_crs(self.cfg.metric_crs).union_all()

        self._used.add(path)
        return self.cached("boundary_m", load)

    def building_points_m(self) -> np.ndarray:
        """Representative points of buildings as an (n, 2) metric array."""

        def load() -> np.ndarray:
            b = gpd.read_parquet(self.use("buildings.parquet"))
            if b.crs is None:
                raise ValueError("buildings.parquet has no CRS")
            pts = b.to_crs(self.cfg.metric_crs).geometry.representative_point()
            return np.column_stack([pts.x.to_numpy(), pts.y.to_numpy()])

        return self.cached("building_points_m", load)

    # ------------------------------------------------------ time-filtered data
    def firms_viirs(self, *, as_of: AsOf | str) -> tuple[pd.DataFrame, dict[str, Any]]:
        """VIIRS detections in [firms_history[0] local day, as_of cutoff), one per
        (local day, 375 m cell). Columns: x, y (metric), acq_datetime_utc, local_date."""
        as_of = parse_as_of(as_of)
        df = pd.read_parquet(self.use("firms.parquet"))
        start_day = date.fromisoformat(str(self.cfg.periods["firms_history"][0]))
        t = df["acq_datetime_utc"]
        is_viirs = df["product"].astype(str).str.startswith(VIIRS_PRODUCT_PREFIX)
        ok_time = before_cutoff(t, as_of, "FIRMS acq_datetime_utc") & (
            t >= local_day_start(start_day, as_of.tz)
        )
        sel = df[is_viirs & ok_time].sort_values(
            ["acq_datetime_utc", "latitude", "longitude"], kind="mergesort"
        ).reset_index(drop=True)
        pts = gpd.GeoSeries(
            gpd.points_from_xy(sel["longitude"], sel["latitude"]), crs="EPSG:4326"
        ).to_crs(self.cfg.metric_crs)
        out = pd.DataFrame(
            {
                "x": pts.x.to_numpy(dtype="float64"),
                "y": pts.y.to_numpy(dtype="float64"),
                "acq_datetime_utc": sel["acq_datetime_utc"],
                "local_date": sel["acq_datetime_utc"].dt.tz_convert(as_of.tz).dt.date,
                "product": sel["product"].astype(str),
            }
        )
        keep = dedupe_fire_cells(
            out["x"].to_numpy(), out["y"].to_numpy(), out["local_date"].to_numpy(),
            VIIRS_PIXEL_M,
        )
        out = out[keep].reset_index(drop=True)
        coverage_end = self._firms_coverage_end()
        late = is_viirs & ~before_cutoff(t, as_of, "FIRMS acq_datetime_utc")
        prov = {
            "file": "firms.parquet",
            "products": sorted(out["product"].unique().tolist()),
            "window_start_local": start_day.isoformat(),
            "window_end_exclusive_utc": iso_utc(as_of.cutoff_utc),
            "n_rows_file": int(len(df)),
            "n_viirs_rows": int(is_viirs.sum()),
            "n_viirs_excluded_at_or_after_cutoff": int(late.sum()),
            "n_viirs_in_window": int(len(sel)),
            "n_after_cell_day_dedupe": int(len(out)),
            "dedupe": f"one detection per (local day, {VIIRS_PIXEL_M:.0f} m cell)",
            "min_time_used_utc": iso_utc(out["acq_datetime_utc"].min()) if len(out) else None,
            "max_time_used_utc": iso_utc(out["acq_datetime_utc"].max()) if len(out) else None,
            "ingest_coverage_end": coverage_end.isoformat() if coverage_end else None,
            "coverage_gap_days": (
                max(0, (as_of.day - coverage_end).days) if coverage_end else None
            ),
            "bbox_covers_kernel": self._firms_bbox_covers(),
        }
        return out, prov

    def _firms_sidecars(self) -> list[dict[str, Any]]:
        d = self.root / "data" / "raw" / "firms" / self.cfg.aoi_id
        out = []
        for p in sorted(d.glob(f"{VIIRS_PRODUCT_PREFIX}*.meta.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except ValueError:
                continue
        return out

    def _firms_coverage_end(self) -> date | None:
        """Last day the ingest requested from FIRMS (sidecar ``end``), if recorded."""
        ends = []
        for m in self._firms_sidecars():
            try:
                ends.append(date.fromisoformat(str(m["end"])))
            except (KeyError, ValueError):
                continue
        return max(ends) if ends else None

    def _firms_bbox_covers(self) -> bool | None:
        """True when every FIRMS request bbox contains segments + history kernel radius."""
        boxes = [m.get("bbox") for m in self._firms_sidecars() if m.get("bbox")]
        if not boxes:
            return None
        h = self.cfg.buffers_m["history_kernel"]
        need = box(*self.segments_m.total_bounds).buffer(h)
        need_ll = gpd.GeoSeries([need], crs=self.cfg.metric_crs).to_crs("EPSG:4326").iloc[0]
        return all(box(*b).contains(need_ll) for b in boxes)

    def wind_climatology(self, *, as_of: AsOf | str) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Hourly wind of the climatology summers (Jun-Sep, local calendar), strictly
        before the cutoff; duplicated Open-Meteo cells are merged by (lat, lon)."""
        as_of = parse_as_of(as_of)
        df = pd.read_parquet(self.use("wind_hourly.parquet"))
        years = [int(y) for y in self.cfg.periods["wind_climatology_summers"]]
        tl = df["time_local"]
        in_clim = tl.dt.year.isin(years) & tl.dt.month.isin(SUMMER_MONTHS)
        ok_time = before_cutoff(df["time_utc"], as_of, "wind time_utc")
        sel = df[in_clim & ok_time].copy()
        sel["lat"] = sel["lat"].round(4)
        sel["lon"] = sel["lon"].round(4)
        sel = sel.sort_values(["lat", "lon", "time_utc", "point_id"], kind="mergesort")
        sel = sel.drop_duplicates(["lat", "lon", "time_utc"]).reset_index(drop=True)
        used_years = sorted(int(y) for y in sel["time_local"].dt.year.unique())
        per = sel.groupby([sel["time_local"].dt.year.rename("year"), "lat", "lon"]).size()
        hours = {
            str(int(y)): {"min": int(g.min()), "max": int(g.max())}
            for y, g in per.groupby(level="year")
        }
        prov = {
            "file": "wind_hourly.parquet",
            "years_configured": years,
            "years_used": used_years,
            "hours_per_cell_by_year": hours,
            "months_local": list(SUMMER_MONTHS),
            "n_rows_file": int(len(df)),
            "n_rows_excluded_outside_climatology": int((~in_clim).sum()),
            "n_rows_excluded_at_or_after_cutoff": int((in_clim & ~ok_time).sum()),
            "n_cells": int(sel.groupby(["lat", "lon"]).ngroups),
            "n_request_points": int(df["point_id"].nunique()),
            "max_time_used_utc": iso_utc(sel["time_utc"].max()) if len(sel) else None,
        }
        return sel, prov

    def s2_composite(
        self, index: str, *, as_of: AsOf | str
    ) -> tuple[Path | None, dict[str, Any]]:
        """Latest Sentinel-2 composite whose window ends on/before as_of and whose scenes
        are all before the cutoff (s2_meta.json is required to prove the dates)."""
        as_of = parse_as_of(as_of)
        meta = json.loads(self.use("s2_meta.json").read_text(encoding="utf-8"))
        cands: list[dict[str, Any]] = []
        for name, p in sorted(meta.get("periods", {}).items()):
            scenes = [pd.Timestamp(s["datetime"]) for s in p.get("scenes", [])]
            scenes = [s.tz_localize("UTC") if s.tzinfo is None else s for s in scenes]
            w_end = date.fromisoformat(str(p["window"][1]))
            latest = max(scenes) if scenes else None
            eligible = bool(
                scenes and w_end <= as_of.day and latest is not None
                and latest < as_of.cutoff_utc
            )
            cands.append({
                "name": name,
                "window": [str(p["window"][0]), str(p["window"][1])],
                "n_scenes": len(scenes),
                "first_scene_utc": iso_utc(min(scenes)) if scenes else None,
                "last_scene_utc": iso_utc(latest),
                "eligible": eligible,
                "_end": w_end,
            })
        elig = [c for c in cands if c["eligible"]]
        public = [{k: v for k, v in c.items() if not k.startswith("_")} for c in cands]
        if not elig:
            return None, {"selected": None, "candidates": public, "max_time_used_utc": None}
        best = max(elig, key=lambda c: (c["_end"], c["last_scene_utc"]))
        path = self.use(f"s2_{index}_{best['name']}.tif")
        prov = {
            "selected": best["name"],
            "file": path.name,
            "window": best["window"],
            "n_scenes": best["n_scenes"],
            "first_scene_utc": best["first_scene_utc"],
            "max_time_used_utc": best["last_scene_utc"],
            "staleness_days": (as_of.day - best["_end"]).days,
            "candidates": public,
        }
        return path, prov
