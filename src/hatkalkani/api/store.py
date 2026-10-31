"""In-memory data store: everything is read once at start-up, requests only filter.

No network access and no heavy computation happen while serving.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import yaml

from .labels import merged_labels

log = logging.getLogger("hatkalkani.api")

ROOT = Path(__file__).resolve().parents[3]
TIERS = ("kritik", "yuksek", "orta", "dusuk")
_RISK_RE = re.compile(r"^risk_(\d{4}-\d{2}-\d{2})\.parquet$")
CHM_YEAR_NOTE_TR = "Bu parça için ağaç yüksekliği görüntü tarihi bulunamadı."
CHM_YEAR_NOTE_EN = "No tree-height imagery date was found for this segment."
DEFAULT_GUST_KMH = 50.0  # used only if config/risk_weights.yaml has no scenario block
DEFAULT_MIN_TIER = "yuksek"


def plain(value: Any) -> Any:
    """JSON-safe value: NaN/inf -> None, numpy scalars -> Python scalars."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [plain(v) for v in value]
    if value is pd.NA or value is pd.NaT:
        return None
    if hasattr(value, "item") and not isinstance(value, str | bytes):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            return str(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _date_str(value: Any) -> str | None:
    """YYYY-MM-DD text for a date-like cell, None if missing."""
    value = plain(value)
    if value is None or value == "":
        return None
    return str(value)[:10]


def chm_note(min_: str | None, max_: str | None, dominant: str | None) -> tuple[str, str]:
    """Build the CHM image-date note from data; fall back to the "unknown" note."""
    if not dominant:
        return CHM_YEAR_NOTE_TR, CHM_YEAR_NOTE_EN
    span = max_ and min_
    tr = f"Ağaç yüksekliği görüntü tarihi: {dominant}"
    en = f"Tree-height imagery date: {dominant}"
    if span:
        tr += f" (bu parçada {min_}–{max_}; Meta/WRI CHM v2 mozaiği)"
        en += f" (this segment {min_}–{max_}; Meta/WRI CHM v2 mosaic)"
    else:
        tr += " (Meta/WRI CHM v2 mozaiği)"
        en += " (Meta/WRI CHM v2 mosaic)"
    return tr, en


def _geom_bbox(geom: dict[str, Any]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    def walk(c: Any) -> None:
        if c and isinstance(c[0], int | float):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for part in c:
                walk(part)

    walk(geom["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


@dataclass
class AsOfData:
    """Everything served for one ``as_of``."""

    as_of: str
    features: list[dict[str, Any]]  # risk geojson features (API properties only)
    bboxes: list[tuple[float, float, float, float]]
    index: dict[str, int]  # segment_id -> position in ``features``
    detail: dict[str, dict[str, Any]]  # segment_id -> raw / contrib / norm / ...
    meta: dict[str, Any]
    workorders: list[dict[str, Any]]  # geojson features, priority order
    workorder_files: dict[str, Path]  # format -> file
    line_km: float
    tier_counts: dict[str, int]
    bbox: list[float]
    chm_acq_range: list[str] | None = None


@dataclass
class Store:
    data_root: Path
    aoi_id: str
    config_dir: Path
    name: str = ""
    boundary: dict[str, Any] | None = None
    by_asof: dict[str, AsOfData] = field(default_factory=dict)
    labels: dict[str, dict[str, str]] = field(default_factory=dict)
    default_as_of: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    scenario_gust_kmh: float = DEFAULT_GUST_KMH
    scenario_min_tier: str = DEFAULT_MIN_TIER

    @property
    def aoi_dir(self) -> Path:
        return self.data_root / self.aoi_id

    @property
    def as_ofs(self) -> list[str]:
        return sorted(self.by_asof)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def load_sources(path: Path) -> list[dict[str, Any]]:
    data = _read_yaml(path).get("sources", [])
    return [dict(s) for s in data] if isinstance(data, list) else []


def _load_asof(aoi_dir: Path, as_of: str, factors: list[str]) -> AsOfData | None:
    risk_pq = aoi_dir / f"risk_{as_of}.parquet"
    risk_gj = aoi_dir / f"risk_{as_of}.geojson"
    if not risk_gj.exists():
        log.warning("skip as_of %s: %s missing", as_of, risk_gj.name)
        return None
    features = json.loads(risk_gj.read_text(encoding="utf-8"))["features"]
    bboxes = [_geom_bbox(f["geometry"]) for f in features]
    index = {f["properties"]["segment_id"]: i for i, f in enumerate(features)}

    meta_path = aoi_dir / f"risk_{as_of}.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    # raw values come from features_<as_of>.parquet, contributions from the risk parquet
    raw_df = None
    feat_pq = aoi_dir / f"features_{as_of}.parquet"
    if feat_pq.exists():
        raw_df = pd.read_parquet(feat_pq).set_index("segment_id")
    risk_df = pd.read_parquet(risk_pq).drop(columns=["geometry"], errors="ignore")
    risk_df = risk_df.set_index("segment_id")
    detail: dict[str, dict[str, Any]] = {}
    for sid in index:
        if sid not in risk_df.index:
            continue
        r = risk_df.loc[sid]
        raw_src = raw_df.loc[sid] if raw_df is not None and sid in raw_df.index else None
        raw: dict[str, Any] = {}
        for fac in factors:
            if raw_src is not None and fac in raw_src.index:
                raw[fac] = plain(raw_src[fac])
            elif f"raw_{fac}" in r.index:
                raw[fac] = plain(r[f"raw_{fac}"])
        detail[sid] = {
            "raw": raw,
            "contrib": {f: plain(r[f"contrib_{f}"]) for f in factors if f"contrib_{f}" in r.index},
            "norm": {f: plain(r[f"norm_{f}"]) for f in factors if f"norm_{f}" in r.index},
            "length_m": plain(r.get("length_m")),
            "voltage_level": plain(r.get("voltage_level")),
            "voltage_kv": plain(r.get("voltage_kv")),
            "risk_pct": plain(r.get("risk_pct")),
            "imputed": plain(r.get("imputed")) or "",
            "chm_year": plain(r.get("chm_year")),
            "chm_acq_min": _date_str(r.get("chm_acq_min")),
            "chm_acq_max": _date_str(r.get("chm_acq_max")),
            "chm_acq_dominant": _date_str(r.get("chm_acq_dominant")),
        }

    wo_files = {
        ext: p for ext in ("csv", "geojson", "gpkg")
        if (p := aoi_dir / f"workorders_{as_of}.{ext}").exists()
    }
    workorders: list[dict[str, Any]] = []
    if "geojson" in wo_files:
        workorders = json.loads(wo_files["geojson"].read_text(encoding="utf-8"))["features"]

    tier_counts = {t: 0 for t in TIERS}
    for f in features:
        t = f["properties"].get("tier")
        if t in tier_counts:
            tier_counts[t] += 1
    line_km = sum(d.get("length_m") or 0.0 for d in detail.values()) / 1000.0
    bbox = (
        [min(b[0] for b in bboxes), min(b[1] for b in bboxes),
         max(b[2] for b in bboxes), max(b[3] for b in bboxes)]
        if bboxes else []
    )
    mins = [d["chm_acq_min"] for d in detail.values() if d["chm_acq_min"]]
    maxs = [d["chm_acq_max"] for d in detail.values() if d["chm_acq_max"]]
    chm_range = [min(mins), max(maxs)] if mins and maxs else None
    return AsOfData(as_of, features, bboxes, index, detail, meta, workorders, wo_files,
                    round(line_km, 3), tier_counts, bbox, chm_range)


def load_store(data_root: Path, aoi_id: str, config_dir: Path) -> Store:
    store = Store(data_root=data_root, aoi_id=aoi_id, config_dir=config_dir)
    aoi_dir = store.aoi_dir
    cfg = _read_yaml(config_dir / "aoi.yaml")
    store.sources = load_sources(config_dir / "sources.yaml")
    scen = _read_yaml(config_dir / "risk_weights.yaml").get("scenario") or {}
    store.scenario_gust_kmh = float(scen.get("gust_threshold_kmh", DEFAULT_GUST_KMH))
    store.scenario_min_tier = str(scen.get("risk_threshold_tier", DEFAULT_MIN_TIER))

    store.name = aoi_id
    for cand in cfg.get("candidates", []) or []:
        if cand.get("id") == aoi_id:
            store.name = f"{cand.get('il', '')} / {cand.get('ilce', '')}".strip(" /")
    boundary_pq = aoi_dir / "boundary.parquet"
    if boundary_pq.exists():
        b = gpd.read_parquet(boundary_pq)
        if b.crs is None:
            raise ValueError(f"{boundary_pq} has no CRS; refusing to guess")
        if b.crs.to_epsg() != 4326:
            b = b.to_crs("EPSG:4326")
        row = b.iloc[0]
        if row.get("il") and row.get("ilce"):
            store.name = f"{row['il']} / {row['ilce']}"
        store.boundary = json.loads(b.to_json(drop_id=True))

    as_ofs = (
        sorted(m.group(1) for p in aoi_dir.glob("risk_*.parquet") if (m := _RISK_RE.match(p.name)))
        if aoi_dir.exists() else []
    )
    first_meta: dict[str, Any] = {}
    for as_of in as_ofs:
        meta_path = aoi_dir / f"risk_{as_of}.meta.json"
        if meta_path.exists():
            first_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            break
    store.labels = merged_labels(first_meta.get("labels"))
    factors = list(store.labels)
    for as_of in as_ofs:
        data = _load_asof(aoi_dir, as_of, factors)
        if data is not None:
            store.by_asof[as_of] = data

    wanted = str((cfg.get("periods") or {}).get("current_asof") or "")
    if wanted in store.by_asof:
        store.default_as_of = wanted
    elif store.by_asof:
        store.default_as_of = max(store.by_asof)
    return store
