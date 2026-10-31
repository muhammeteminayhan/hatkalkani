"""Preventive de-energisation scenario (risk-model-spec section 6, ADR-012).

``compute_scenario(aoi_id, date, gust_kmh, min_tier)`` answers ``GET /api/scenario``
(docs/ARCHITECTURE.md v0.2, ADR-011). For one local calendar day (ADR-009) it compares

* (A) district-wide: every overhead line segment of the AOI is switched off, and
* (B) targeted: only the OSM ways (``line_id``; a *proxy* for a switchable unit) holding a
  candidate segment. A candidate segment's nearest Open-Meteo cell has a daily maximum
  hourly gust strictly above ``gust_kmh`` on that day, and its tier is ``min_tier`` or
  higher in the latest risk map dated strictly before the day (``inputs.as_of_used``).

Metrics: switched-off line km, buildings whose representative point lies within
``buffers_m.affected_building`` of a switched-off segment (proxy for affected customers),
and the length-weighted share of the AOI risk that B covers. A labelled sensitivity uses
the candidate segment itself as the unit (idealised sectionalising, lower bound).

Static inputs are cached per AOI and rebuilt when an input file changes.

CLI (pipeline stage ``scenario``)::

    uv run python -m hatkalkani.model.scenario --aoi izmir_menderes

writes ``scenario_dates.json`` (``demo.scenario_date_candidates``) and
``scenario_<day>.json`` (default parameters, windiest candidate day) under
``data/processed/<aoi>/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import yaml
from scipy.spatial import cKDTree

from hatkalkani.features.asof import LOCAL_TZ
from hatkalkani.ingest import common
from hatkalkani.model.config import TIERS
from hatkalkani.model.run import API_SEGMENT_PROPERTIES, GEOJSON_DECIMALS, read_risk

log = logging.getLogger("hatkalkani.model.scenario")

KMH_PER_MS = 3.6  # wind_hourly.parquet stores m/s (ingest converted Open-Meteo km/h)
CELL_DECIMALS = 4  # duplicated Open-Meteo cells are merged on rounded (lat, lon), ADR-009 D5
COORD_DECIMALS = 6
KM_DECIMALS = 3
RATIO_DECIMALS = 4
GUST_DECIMALS = 1
RISK_FILE_RE = re.compile(r"^risk_(\d{4}-\d{2}-\d{2})\.parquet$")
WIND_SOURCE = ("Open-Meteo archive wind_gusts_10m; daily maximum of the hourly values of the "
               "local (Europe/Istanbul) calendar day at the segment's nearest grid cell")


class ScenarioDataError(RuntimeError):
    """Scenario inputs exist but are inconsistent (a pipeline problem, not a bad request)."""


# ---------------------------------------------------------------- pure functions
@dataclass(frozen=True)
class ScenarioNumbers:
    candidate: np.ndarray  # bool per segment
    cut_line: np.ndarray  # bool per line index
    targeted: np.ndarray  # bool per segment: its line is switched off
    district_km: float
    targeted_km: float
    district_buildings: int
    targeted_buildings: int
    risk_covered_ratio: float
    segment_unit_km: float
    segment_unit_buildings: int
    segment_unit_risk_ratio: float


def tier_ranks(tiers: Sequence[str]) -> np.ndarray:
    """0 = kritik ... 3 = dusuk (config TIERS order, highest first)."""
    bad = sorted({str(t) for t in tiers} - set(TIERS))
    if bad:
        raise ScenarioDataError(f"unknown tier value(s) in the risk file: {bad}")
    return np.array([TIERS.index(str(t)) for t in tiers], dtype=np.int64)


def evaluate_scenario(
    seg_gust_kmh: np.ndarray, seg_tier_rank: np.ndarray, seg_risk: np.ndarray,
    seg_length_m: np.ndarray, seg_line_idx: np.ndarray, pairs_seg: np.ndarray,
    pairs_bld: np.ndarray, *, n_lines: int, gust_kmh: float, min_tier: str,
) -> ScenarioNumbers:
    """Spec section 6 comparison on per-segment arrays.

    ``pairs_seg``/``pairs_bld`` list every (segment, building) pair within the affected-
    building distance. A NaN gust (no wind data) never makes a segment a candidate."""
    gust = np.asarray(seg_gust_kmh, dtype="float64")
    windy = np.isfinite(gust) & (gust > float(gust_kmh))
    candidate = windy & (np.asarray(seg_tier_rank) <= TIERS.index(min_tier))
    cut_line = np.zeros(n_lines, dtype=bool)
    cut_line[np.asarray(seg_line_idx)[candidate]] = True
    targeted = cut_line[np.asarray(seg_line_idx)]
    length = np.asarray(seg_length_m, dtype="float64")
    risk_len = np.asarray(seg_risk, dtype="float64") * length
    total = float(risk_len.sum())

    def buildings(mask: np.ndarray) -> int:
        return int(np.unique(pairs_bld[mask[pairs_seg]]).size) if len(pairs_seg) else 0

    def ratio(mask: np.ndarray) -> float:
        return float(risk_len[mask].sum() / total) if total > 0 else 0.0

    return ScenarioNumbers(
        candidate=candidate,
        cut_line=cut_line,
        targeted=targeted,
        district_km=float(length.sum()) / 1000,
        targeted_km=float(length[targeted].sum()) / 1000,
        district_buildings=buildings(np.ones(len(length), dtype=bool)),
        targeted_buildings=buildings(targeted),
        risk_covered_ratio=ratio(targeted),
        segment_unit_km=float(length[candidate].sum()) / 1000,
        segment_unit_buildings=buildings(candidate),
        segment_unit_risk_ratio=ratio(candidate),
    )


def as_of_before(day: date, as_ofs: Sequence[str]) -> str:
    """Latest risk as_of strictly before ``day``: the map available on the morning of the
    day (an as_of covers its whole local day, ADR-009)."""
    earlier = sorted(a for a in as_ofs if date.fromisoformat(a) < day)
    if not earlier:
        raise ValueError(f"no risk map dated before {day.isoformat()} "
                         f"(available as_of: {sorted(as_ofs)})")
    return earlier[-1]


def daily_max_gust_kmh(
    wind: pd.DataFrame, tz: str = LOCAL_TZ
) -> tuple[pd.DataFrame, list[date], np.ndarray, np.ndarray]:
    """Daily maximum hourly gust (km/h) per Open-Meteo cell and local calendar day.

    Returns ``cells`` (lat, lon, label, sorted by "lat,lon" key like the feature layer),
    the sorted list of local days, and (n_days x n_cells) arrays of the max gust (NaN when
    the cell has no hour that day) and of the number of distinct hours."""
    need = {"point_id", "lat", "lon", "time_utc", "wind_gust_10m_ms"}
    if missing := sorted(need - set(wind.columns)):
        raise ScenarioDataError(f"wind_hourly.parquet lacks columns {missing}")
    if not isinstance(wind["time_utc"].dtype, pd.DatetimeTZDtype):
        raise ScenarioDataError("wind time_utc must be time-zone aware; refusing to guess")
    w = wind[["point_id", "lat", "lon", "time_utc", "wind_gust_10m_ms"]].copy()
    w["lat"] = w["lat"].round(CELL_DECIMALS)
    w["lon"] = w["lon"].round(CELL_DECIMALS)
    cells = w.groupby(["lat", "lon"], sort=False)["point_id"].min().rename("label")
    cells = cells.reset_index()
    cells["key"] = [f"{a:.{CELL_DECIMALS}f},{o:.{CELL_DECIMALS}f}"
                    for a, o in zip(cells["lat"], cells["lon"], strict=True)]
    cells = cells.sort_values("key", kind="mergesort").reset_index(drop=True)
    w = w.merge(cells[["lat", "lon"]].reset_index(names="cell"), on=["lat", "lon"])
    # duplicated request points of one cell: keep the lowest point_id (as ADR-009 D5)
    w = w.sort_values(["cell", "time_utc", "point_id"], kind="mergesort")
    w = w.drop_duplicates(["cell", "time_utc"])
    w["day"] = w["time_utc"].dt.tz_convert(tz).dt.tz_localize(None).dt.normalize()
    g = w.groupby(["day", "cell"])["wind_gust_10m_ms"].agg(["max", "size"])
    days = sorted(g.index.get_level_values("day").unique())
    row = {d: i for i, d in enumerate(days)}
    kmh = np.full((len(days), len(cells)), np.nan)
    hours = np.zeros((len(days), len(cells)), dtype=np.int64)
    r = np.array([row[d] for d in g.index.get_level_values("day")], dtype=np.int64)
    c = g.index.get_level_values("cell").to_numpy(dtype=np.int64)
    kmh[r, c] = g["max"].to_numpy(dtype="float64") * KMH_PER_MS
    hours[r, c] = g["size"].to_numpy(dtype=np.int64)
    return cells.drop(columns="key"), [pd.Timestamp(d).date() for d in days], kmh, hours


def select_scenario_day(rows: Sequence[Mapping[str, Any]]) -> str:
    """Windiest candidate: highest segment max gust, then highest median, then earliest."""
    if not rows:
        raise ValueError("no candidate scenario day has wind data and an earlier risk map")
    best = sorted(rows, key=lambda r: (-float(r["max_gust_kmh"]),
                                       -float(r["median_gust_kmh"]), str(r["date"])))
    return str(best[0]["date"])


# ------------------------------------------------------------------- cached data
@dataclass
class RiskLayer:
    as_of: str
    risk: np.ndarray
    tier_rank: np.ndarray
    features: list[dict[str, Any]]  # GeoJSON features with /api/segments properties


@dataclass
class ScenarioData:
    aoi_id: str
    root: Path
    segment_ids: list[str]
    line_ids: list[str]  # sorted unique OSM way ids
    seg_line_idx: np.ndarray
    length_m: np.ndarray
    voltage_class: np.ndarray
    seg_cell: np.ndarray
    cells: pd.DataFrame
    days: dict[date, int]
    day_kmh: np.ndarray
    day_hours: np.ndarray
    pairs_seg: np.ndarray
    pairs_bld: np.ndarray
    as_ofs: list[str]
    defaults: dict[str, Any]
    candidates: list[str]
    note_tr: str
    note_en: str
    layers: dict[str, RiskLayer] = field(default_factory=dict)

    def layer(self, as_of: str) -> RiskLayer:
        if as_of not in self.layers:
            self.layers[as_of] = _load_layer(self, as_of)
        return self.layers[as_of]

    def segment_gust(self, day: date) -> tuple[np.ndarray, int]:
        if day not in self.days:
            raise ValueError(f"no wind data for {day.isoformat()} in wind_hourly.parquet")
        row = self.days[day]
        used = np.unique(self.seg_cell)
        return self.day_kmh[row, self.seg_cell], int(self.day_hours[row, used].min())


_CACHE: dict[tuple[str, str], tuple[tuple, ScenarioData]] = {}
_LOCK = threading.Lock()


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def _paths(aoi_id: str, root: Path) -> dict[str, Path]:
    proc = root / "data" / "processed" / aoi_id
    interim = root / "data" / "interim" / aoi_id
    return {
        "processed": proc,
        "segments": proc / "segments.parquet",
        "buildings": interim / "buildings.parquet",
        "wind": interim / "wind_hourly.parquet",
        "aoi_yaml": root / "config" / "aoi.yaml",
        "risk_yaml": root / "config" / "risk_weights.yaml",
    }


def _risk_files(processed: Path) -> dict[str, Path]:
    return {m.group(1): p for p in sorted(processed.glob("risk_*.parquet"))
            if (m := RISK_FILE_RE.match(p.name))}


def _signature(aoi_id: str, root: Path) -> tuple:
    p = _paths(aoi_id, root)
    if not p["processed"].is_dir():
        raise FileNotFoundError(f"{p['processed']} does not exist; run the pipeline first")
    files = [p[k] for k in ("segments", "buildings", "wind", "aoi_yaml", "risk_yaml")]
    files += list(_risk_files(p["processed"]).values())
    sig = []
    for f in files:
        try:
            st = f.stat()
        except FileNotFoundError:
            raise FileNotFoundError(f"missing scenario input {f}") from None
        sig.append((f.name, st.st_mtime_ns, st.st_size))
    if not _risk_files(p["processed"]):
        raise FileNotFoundError(f"no risk_<as_of>.parquet under {p['processed']}")
    return tuple(sig)


def _scenario_defaults(rw: Mapping[str, Any]) -> dict[str, Any]:
    """Default request parameters: risk_weights.yaml ``scenario`` (required keys)."""
    s = rw.get("scenario") or {}
    try:
        gust = float(s["gust_threshold_kmh"])
        tier = str(s["risk_threshold_tier"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ScenarioDataError(f"risk_weights.yaml scenario block is incomplete: {s}") from exc
    if tier not in TIERS or not math.isfinite(gust) or gust < 0:
        raise ScenarioDataError(f"config scenario defaults are invalid: {s}")
    return {"gust_kmh": gust, "min_tier": tier}


def _notes(voltage_class: np.ndarray, power: np.ndarray, length: np.ndarray,
           building_m: float) -> tuple[str, str]:
    total = float(length.sum()) or 1.0
    hv = float(length[voltage_class == "ge154kv"].sum()) / total
    line = float(length[power == "line"].sum()) / total
    line_tr = f"{100 * line:.1f}".replace(".", ",")  # Turkish decimal comma
    tr = (
        "Vekil hesap, gerçek kesinti planı değildir. "
        f"OSM hatlarının çoğu iletim hattıdır: havai hat uzunluğunun %{line_tr}'i "
        f"power=line etiketli, %{100 * hv:.0f}'si ≥154 kV etiketli. Gerçek önleyici kesinti "
        "birimi EDAŞ'ın dağıtım fideri ve anahtarlanabilir bölümüdür; burada aday segment "
        "içeren OSM hat yolu (way) bütünüyle kesilmiş sayılır. Bina sayısı, kesilen "
        f"hatlara {building_m:.0f} m içindeki yapı sayısıdır (Overture) ve etkilenen müşteri "
        "(abone) sayısının vekilidir; gerçek sayı fider–abone verisi gerektirir."
    )
    en = (
        "Proxy calculation, not an outage plan. "
        f"Most OSM lines are transmission lines: {100 * line:.1f}% of the overhead length is "
        f"tagged power=line and {100 * hv:.0f}% is tagged ≥154 kV. The real preventive "
        "outage unit is the EDAŞ distribution feeder and its switchable sections; here a "
        "whole OSM way holding a candidate segment counts as switched off. The building "
        f"count is the number of buildings (Overture) within {building_m:.0f} m of the "
        "switched-off lines, a proxy for affected customers; real numbers need "
        "feeder–customer data."
    )
    return tr, en


def _load_data(aoi_id: str, root: Path) -> ScenarioData:
    p = _paths(aoi_id, root)
    aoi_cfg = yaml.safe_load(p["aoi_yaml"].read_text(encoding="utf-8")) or {}
    rw = yaml.safe_load(p["risk_yaml"].read_text(encoding="utf-8")) or {}
    metric = str(aoi_cfg["metric_crs"])
    building_m = float(aoi_cfg["buffers_m"]["affected_building"])
    segs = gpd.read_parquet(p["segments"])
    if segs.crs is None:
        raise ScenarioDataError("segments.parquet has no CRS; refusing to guess")
    segs = segs.reset_index(drop=True)
    seg_m = segs.to_crs(metric)
    if not seg_m.crs.is_projected:
        raise ScenarioDataError(f"metric_crs {metric} is not projected")
    seg_ids = segs["segment_id"].astype(str).tolist()
    if len(set(seg_ids)) != len(seg_ids):
        raise ScenarioDataError("segment_id is not unique in segments.parquet")
    line_of = segs["line_id"].astype(str).to_numpy()
    line_ids = sorted(set(line_of))
    seg_line_idx = np.searchsorted(np.array(line_ids), line_of)

    cells, days, kmh, hours = daily_max_gust_kmh(pd.read_parquet(p["wind"]))
    cxy = gpd.GeoSeries(gpd.points_from_xy(cells["lon"], cells["lat"]),
                        crs="EPSG:4326").to_crs(metric)
    mids = seg_m.geometry.interpolate(0.5, normalized=True)  # as the feature layer
    _, seg_cell = cKDTree(np.column_stack([cxy.x, cxy.y])).query(
        np.column_stack([mids.x, mids.y]))

    b = gpd.read_parquet(p["buildings"], columns=["geometry"])
    if b.crs is None:
        raise ScenarioDataError("buildings.parquet has no CRS; refusing to guess")
    pts = b.to_crs(metric).geometry.representative_point()  # as wui_exposure
    if len(pts):
        tree = shapely.STRtree(pts.to_numpy())
        pairs_seg, pairs_bld = tree.query(seg_m.geometry.to_numpy(), predicate="dwithin",
                                          distance=building_m)
    else:
        pairs_seg = pairs_bld = np.zeros(0, dtype=np.int64)

    length = segs["length_m"].to_numpy(dtype="float64")
    vclass = segs["voltage_class"].astype(str).to_numpy()
    power = segs["power"].astype(str).to_numpy() if "power" in segs else np.full(
        len(segs), "")
    note_tr, note_en = _notes(vclass, power, length, building_m)
    return ScenarioData(
        aoi_id=aoi_id, root=root, segment_ids=seg_ids, line_ids=line_ids,
        seg_line_idx=seg_line_idx, length_m=length, voltage_class=vclass,
        seg_cell=np.asarray(seg_cell, dtype=np.int64), cells=cells,
        days={d: i for i, d in enumerate(days)}, day_kmh=kmh, day_hours=hours,
        pairs_seg=np.asarray(pairs_seg, dtype=np.int64),
        pairs_bld=np.asarray(pairs_bld, dtype=np.int64),
        as_ofs=sorted(_risk_files(p["processed"])), defaults=_scenario_defaults(rw),
        candidates=[str(d) for d in (aoi_cfg.get("demo") or {}).get(
            "scenario_date_candidates", [])],
        note_tr=note_tr, note_en=note_en,
    )


def _round(x: float, nd: int) -> float:
    return float(round(float(x), nd))


def _load_layer(data: ScenarioData, as_of: str) -> RiskLayer:
    path = _risk_files(data.root / "data" / "processed" / data.aoi_id)[as_of]
    risk, meta = read_risk(path)
    if str(meta.get("as_of")) != as_of:
        raise ScenarioDataError(f"{path.name}: embedded as_of {meta.get('as_of')!r}")
    if risk.crs is None:
        raise ScenarioDataError(f"{path.name} has no CRS")
    risk = risk.to_crs("EPSG:4326")
    ids = risk["segment_id"].astype(str)
    if sorted(ids) != sorted(data.segment_ids):
        raise ScenarioDataError(f"{path.name} and segments.parquet hold different segments; "
                                "rerun --stage score")
    risk = risk.set_index(ids).loc[data.segment_ids]
    feats = []
    for sid, row in zip(data.segment_ids, risk.itertuples(index=False), strict=True):
        props: dict[str, Any] = {}
        for k in API_SEGMENT_PROPERTIES:
            v = getattr(row, k)
            if k in GEOJSON_DECIMALS:
                v = _round(v, GEOJSON_DECIMALS[k])
            elif k == "top_factors":
                v = json.loads(v)
            else:
                v = str(v)
            props[k] = v
        props["segment_id"] = sid
        coords = shapely.get_coordinates(row.geometry)
        feats.append({"type": "Feature", "properties": props, "geometry": {
            "type": "LineString",
            "coordinates": [[_round(x, COORD_DECIMALS), _round(y, COORD_DECIMALS)]
                            for x, y in coords]}})
    return RiskLayer(as_of=as_of, risk=risk["risk"].to_numpy(dtype="float64"),
                     tier_rank=tier_ranks(risk["tier"].astype(str).tolist()), features=feats)


def _data(aoi_id: str, root: Path) -> ScenarioData:
    key = (str(root.resolve()), aoi_id)
    with _LOCK:
        sig = _signature(aoi_id, root)
        hit = _CACHE.get(key)
        if hit is None or hit[0] != sig:
            _CACHE[key] = (sig, _load_data(aoi_id, root))
        return _CACHE[key][1]


# ---------------------------------------------------------------------- public API
def _parse_day(value: date | str) -> date:
    if isinstance(value, datetime):  # the rule is defined on local calendar days
        raise ValueError("date must be a calendar date, not a datetime")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"date must be YYYY-MM-DD, got {value!r}") from exc


def compute_scenario(aoi_id: str, date: date | str, gust_kmh: float | None = None,
                     min_tier: str | None = None, *, root: Path | None = None) -> dict:
    """Scenario response of ``GET /api/scenario`` (ARCHITECTURE v0.2).

    Raises FileNotFoundError when the pipeline outputs are missing (API 503) and
    ValueError for a bad request: malformed date, negative/NaN gust, unknown tier, a day
    without wind data or without an earlier risk map (API 422)."""
    data = _data(aoi_id, Path(root) if root is not None else common.ROOT)
    day = _parse_day(date)
    gust = data.defaults["gust_kmh"] if gust_kmh is None else float(gust_kmh)
    if not math.isfinite(gust) or gust < 0:
        raise ValueError(f"gust_kmh must be a finite number >= 0, got {gust_kmh!r}")
    tier = data.defaults["min_tier"] if min_tier is None else str(min_tier)
    if tier not in TIERS:
        raise ValueError(f"min_tier must be one of {list(TIERS)}, got {min_tier!r}")
    as_of = as_of_before(day, data.as_ofs)
    seg_gust, hours = data.segment_gust(day)
    with _LOCK:
        layer = data.layer(as_of)
    res = evaluate_scenario(seg_gust, layer.tier_rank, layer.risk, data.length_m,
                            data.seg_line_idx, data.pairs_seg, data.pairs_bld,
                            n_lines=len(data.line_ids), gust_kmh=gust, min_tier=tier)
    feats = []
    for i in np.flatnonzero(res.targeted):
        f = layer.features[i]
        g = seg_gust[i]
        props = {**f["properties"],
                 "gust_kmh": _round(g, GUST_DECIMALS) if math.isfinite(g) else None,
                 "candidate": bool(res.candidate[i])}
        feats.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})
    finite = seg_gust[np.isfinite(seg_gust)]
    d_km, t_km = res.district_km, res.targeted_km
    d_b, t_b = res.district_buildings, res.targeted_buildings
    return {
        "date": day.isoformat(),
        "inputs": {"gust_kmh": gust, "min_tier": tier, "as_of_used": as_of},
        "district_wide": {
            "line_km": _round(d_km, KM_DECIMALS), "buildings": d_b,
            "n_lines": len(data.line_ids), "n_segments": len(data.segment_ids),
        },
        "targeted": {
            "line_km": _round(t_km, KM_DECIMALS), "buildings": t_b,
            "line_ids": [data.line_ids[k] for k in np.flatnonzero(res.cut_line)],
            "risk_covered_ratio": _round(res.risk_covered_ratio, RATIO_DECIMALS),
            "n_lines": int(res.cut_line.sum()), "n_segments": int(res.targeted.sum()),
            "n_candidate_segments": int(res.candidate.sum()),
            "share_line_km": _round(t_km / d_km, RATIO_DECIMALS) if d_km else 0.0,
            "share_buildings": _round(t_b / d_b, RATIO_DECIMALS) if d_b else 0.0,
        },
        "segments": {"type": "FeatureCollection", "features": feats},
        "wind": {
            "source": WIND_SOURCE,
            "max_gust_kmh": _round(finite.max(), GUST_DECIMALS) if finite.size else None,
            "min_gust_kmh": _round(finite.min(), GUST_DECIMALS) if finite.size else None,
            "hours_min_per_cell": hours,
            "n_cells_used": int(np.unique(data.seg_cell).size),
            "n_segments_over_threshold": int((finite > gust).sum()),
            "n_segments_without_wind": int((~np.isfinite(seg_gust)).sum()),
        },
        "sensitivity_segment_unit": {
            "label_tr": "Duyarlılık: kesinti birimi yalnız aday segment (anahtarlanabilir "
                        "bölüm varsayımı; alt sınır)",
            "label_en": "Sensitivity: outage unit = candidate segment only (assumes "
                        "switchable sections; lower bound)",
            "line_km": _round(res.segment_unit_km, KM_DECIMALS),
            "buildings": res.segment_unit_buildings,
            "risk_covered_ratio": _round(res.segment_unit_risk_ratio, RATIO_DECIMALS),
        },
        "note_tr": data.note_tr,
        "note_en": data.note_en,
    }


def scenario_dates(aoi_id: str, root: Path | None = None) -> list[dict[str, Any]]:
    """``scenario_dates.json`` rows for ``demo.scenario_date_candidates`` (ADR-012)."""
    base = Path(root) if root is not None else common.ROOT
    data = _data(aoi_id, base)
    rows = []
    for tok in data.candidates:
        day = _parse_day(tok)
        if day not in data.days:
            log.warning("scenario candidate %s has no wind data; skipped", tok)
            continue
        try:
            as_of = as_of_before(day, data.as_ofs)
        except ValueError:
            log.warning("scenario candidate %s has no earlier risk map; skipped", tok)
            continue
        seg, hours = data.segment_gust(day)
        grid = data.day_kmh[data.days[day]]
        rows.append({
            "date": day.isoformat(),
            "max_gust_kmh": _round(np.nanmax(seg), GUST_DECIMALS),
            "median_gust_kmh": _round(np.nanmedian(seg), GUST_DECIMALS),
            "max_gust_kmh_grid": _round(np.nanmax(grid), GUST_DECIMALS),
            "hours_min_per_cell": hours,
            "n_segments_over_default": int((seg > data.defaults["gust_kmh"]).sum()),
            "as_of_used": as_of,
        })
    rows.sort(key=lambda r: r["date"])
    if rows:
        chosen = select_scenario_day(rows)
        for r in rows:
            r["selected"] = r["date"] == chosen
    return rows


def sensitivity_grid(aoi_id: str, day: str, thresholds: Sequence[float],
                     tiers: Sequence[str] = ("kritik", "yuksek", "orta"),
                     root: Path | None = None) -> pd.DataFrame:
    """Gust threshold x min_tier table for the report (spec section 6 sensitivity)."""
    recs = []
    for tier in tiers:
        for thr in thresholds:
            o = compute_scenario(aoi_id, day, thr, tier, root=root)
            t, s, d = o["targeted"], o["sensitivity_segment_unit"], o["district_wide"]
            recs.append({
                "min_tier": tier, "gust_kmh": thr, "n_candidates": t["n_candidate_segments"],
                "n_lines": t["n_lines"], "line_km": t["line_km"],
                "share_km": t["share_line_km"], "buildings": t["buildings"],
                "share_buildings": t["share_buildings"],
                "risk_covered": t["risk_covered_ratio"], "seg_km": s["line_km"],
                "seg_buildings": s["buildings"], "seg_risk_covered": s["risk_covered_ratio"],
                "district_km": d["line_km"], "district_buildings": d["buildings"],
            })
    return pd.DataFrame(recs)


# --------------------------------------------------------------------------- files
def _write_json(obj: Any, path: Path, *, indent: int | None) -> None:
    text = json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=indent,
                      separators=None if indent else (",", ":"))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8") + b"\n")
    os.replace(tmp, path)


def write_scenario_outputs(aoi_id: str, root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else common.ROOT
    proc = base / "data" / "processed" / aoi_id
    rows = scenario_dates(aoi_id, base)
    _write_json(rows, proc / "scenario_dates.json", indent=2)
    day = select_scenario_day(rows)
    t0 = time.perf_counter()
    out = compute_scenario(aoi_id, day, root=base)
    dt_ms = (time.perf_counter() - t0) * 1000
    path = proc / f"scenario_{day}.json"
    _write_json(out, path, indent=None)
    return {"dates": rows, "day": day, "scenario": out, "path": path, "warm_ms": dt_ms}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--root", type=Path, default=common.ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    t0 = time.perf_counter()
    res = write_scenario_outputs(args.aoi, args.root)
    for r in res["dates"]:
        log.info("  %s max gust %.1f km/h (grid %.1f), as_of_used %s%s", r["date"],
                 r["max_gust_kmh"], r["max_gust_kmh_grid"], r["as_of_used"],
                 "  <- selected" if r["selected"] else "")
    o = res["scenario"]
    log.info("scenario_%s: district %.1f km / %d buildings; targeted %.1f km / %d buildings "
             "/ risk share %.3f (%d lines); compute %.0f ms; total %.1fs", res["day"],
             o["district_wide"]["line_km"], o["district_wide"]["buildings"],
             o["targeted"]["line_km"], o["targeted"]["buildings"],
             o["targeted"]["risk_covered_ratio"], o["targeted"]["n_lines"], res["warm_ms"],
             time.perf_counter() - t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
