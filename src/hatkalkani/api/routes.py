"""API routes (contract v0.1 + v0.2 addendum, ADR-011)."""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from .store import CHM_YEAR_NOTE_EN, CHM_YEAR_NOTE_TR, TIERS, AsOfData, Store

router = APIRouter(prefix="/api")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MEDIA = {
    "csv": "text/csv; charset=utf-8",
    "geojson": "application/geo+json",
    "gpkg": "application/geopackage+sqlite3",
}


def _store(request: Request) -> Store:
    return request.app.state.store


def _err(status: int, error: str, hint: str = "") -> HTTPException:
    return HTTPException(status_code=status, detail={"error": error, "hint": hint})


def _not_ready(tr: str, en: str) -> HTTPException:
    return HTTPException(status_code=503, detail={"detail_tr": tr, "detail_en": en})


def _asof(store: Store, as_of: str | None) -> AsOfData:
    if not store.by_asof:
        raise _err(
            503,
            "Risk verisi bulunamadı.",
            f"{store.aoi_dir} altında risk_<as_of>.parquet üretmek için "
            f"`scripts/run_pipeline.py --aoi {store.aoi_id} --stage model` çalıştırın.",
        )
    key = as_of or store.default_as_of
    if key is None or key not in store.by_asof:
        raise _err(404, f"as_of={key} için veri yok.", f"Mevcut tarihler: {store.as_ofs}")
    if as_of and not _DATE_RE.match(as_of):
        raise _err(422, "as_of YYYY-MM-DD biçiminde olmalı.", f"Mevcut tarihler: {store.as_ofs}")
    return store.by_asof[key]


def _fc(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    s = _store(request)
    return {
        "status": "ok" if s.by_asof else "degraded",
        "aoi": s.aoi_id,
        "data_version": s.default_as_of,
        "as_ofs": s.as_ofs,
    }


@router.get("/aoi")
def aoi(request: Request, as_of: str | None = None) -> dict[str, Any]:
    s = _store(request)
    d = _asof(s, as_of)
    return {
        "id": s.aoi_id,
        "name": s.name,
        "as_of": d.as_of,
        "bbox": d.bbox,
        "stats": {
            "line_km": d.line_km,
            "segment_count": len(d.features),
            "tier_counts": d.tier_counts,
            "workorder_count": len(d.workorders),
        },
    }


@router.get("/aoi/boundary")
def boundary(request: Request) -> JSONResponse:
    s = _store(request)
    if s.boundary is None:
        raise _err(503, "İlçe sınırı bulunamadı.", f"{s.aoi_dir / 'boundary.parquet'} eksik.")
    return JSONResponse(s.boundary, media_type="application/geo+json")


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    try:
        w, so, e, n = (float(x) for x in bbox.split(","))
    except ValueError:
        raise _err(422, "bbox geçersiz.", "Biçim: bbox=w,s,e,n (EPSG:4326 derece).") from None
    if w > e or so > n:
        raise _err(422, "bbox geçersiz.", "w<=e ve s<=n olmalı.")
    return w, so, e, n


@router.get("/segments")
def segments(
    request: Request,
    tier: str | None = None,
    bbox: str | None = None,
    as_of: str | None = None,
) -> JSONResponse:
    d = _asof(_store(request), as_of)
    tiers = {t.strip() for t in tier.split(",") if t.strip()} if tier else None
    if tiers and not tiers <= set(TIERS):
        bad = sorted(tiers - set(TIERS))
        raise _err(422, f"Bilinmeyen kademe: {bad}", f"Geçerli: {list(TIERS)}")
    box = _parse_bbox(bbox)
    out = []
    for f, b in zip(d.features, d.bboxes, strict=True):
        if tiers and f["properties"].get("tier") not in tiers:
            continue
        if box and (b[2] < box[0] or b[0] > box[2] or b[3] < box[1] or b[1] > box[3]):
            continue
        out.append(f)
    return JSONResponse(_fc(out), media_type="application/geo+json")


@router.get("/segments/{segment_id}")
def segment(request: Request, segment_id: str, as_of: str | None = None) -> dict[str, Any]:
    s = _store(request)
    d = _asof(s, as_of)
    i = d.index.get(segment_id)
    if i is None:
        raise _err(404, f"Segment bulunamadı: {segment_id}", "segment_id örn. 155462929_0001.")
    feat = d.features[i]
    extra = d.detail.get(segment_id, {})
    props = {
        **feat["properties"],
        "as_of": d.as_of,
        "raw": extra.get("raw", {}),
        "contrib": extra.get("contrib", {}),
        "norm": extra.get("norm", {}),
        "length_m": extra.get("length_m"),
        "voltage_level": extra.get("voltage_level"),
        "voltage_kv": extra.get("voltage_kv"),
        "risk_pct": extra.get("risk_pct"),
        "imputed": extra.get("imputed", ""),
        # CHM v2 has no image date (ADR-008): null, never a guess.
        "chm_year": extra.get("chm_year"),
        "chm_year_note_tr": CHM_YEAR_NOTE_TR,
        "chm_year_note_en": CHM_YEAR_NOTE_EN,
        "factor_labels": s.labels,
    }
    # Feature shape plus the same keys flat at the top level (frontend may use either).
    return {"type": "Feature", "geometry": feat["geometry"], "properties": props, **props}


@router.get("/workorders")
def workorders(
    request: Request,
    limit: int = Query(50, ge=1, le=5000),
    format: str = Query("json", pattern="^(json|geojson)$"),
    as_of: str | None = None,
) -> JSONResponse:
    d = _asof(_store(request), as_of)
    if not d.workorders:
        raise _err(503, "İş emri verisi yok.", f"workorders_{d.as_of}.geojson üretilmemiş.")
    feats = d.workorders[:limit]
    headers = {"X-Total-Count": str(len(d.workorders))}
    if format == "geojson":
        return JSONResponse(_fc(feats), media_type="application/geo+json", headers=headers)
    return JSONResponse([f["properties"] for f in feats], headers=headers)


@router.get("/workorders/export")
def workorders_export(
    request: Request,
    format: str = Query("csv", pattern="^(csv|geojson|gpkg)$"),
    as_of: str | None = None,
) -> FileResponse:
    d = _asof(_store(request), as_of)
    path = d.workorder_files.get(format)
    if path is None:
        raise _err(503, f"workorders_{d.as_of}.{format} yok.", "Model aşamasını çalıştırın.")
    return FileResponse(
        path, media_type=_MEDIA[format], filename=f"hatkalkani_isemri_{d.as_of}.{format}"
    )


def _processed_json(s: Store, name: str, tr: str, en: str) -> Any:
    path: Path = s.aoi_dir / name
    if not path.exists():
        raise _not_ready(tr, en)
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/scenario/dates")
def scenario_dates(request: Request) -> Any:
    return _processed_json(
        _store(request), "scenario_dates.json",
        "Senaryo günleri henüz hesaplanmadı.", "Scenario dates have not been computed yet.",
    )


@router.get("/scenario")
def scenario(
    request: Request,
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    gust_kmh: float = Query(50, ge=0, le=300),
    min_tier: str = Query("yuksek"),
) -> Any:
    s = _store(request)
    if min_tier not in TIERS:
        raise _err(422, f"Bilinmeyen kademe: {min_tier}", f"Geçerli: {list(TIERS)}")
    try:  # imported per request: the module arrives later (F3-4)
        mod = importlib.import_module("hatkalkani.model.scenario")
        compute = mod.compute_scenario
    except (ImportError, AttributeError):
        raise _not_ready(
            "Senaryo modülü henüz hazır değil.", "The scenario module is not available yet."
        ) from None
    try:
        return compute(s.aoi_id, date, gust_kmh, min_tier)
    except FileNotFoundError:
        raise _not_ready(
            "Senaryo girdileri henüz hesaplanmadı.", "Scenario inputs have not been computed yet."
        ) from None
    except ValueError as exc:
        raise _err(422, str(exc), "date, gust_kmh ve min_tier değerlerini kontrol edin.") from exc


@router.get("/backtest")
def backtest(request: Request) -> Any:
    return _processed_json(
        _store(request), "backtest.json",
        "Geriye dönük test henüz hesaplanmadı.", "The backtest has not been computed yet.",
    )


@router.get("/backtest/events")
def backtest_events(request: Request) -> Any:
    return _processed_json(
        _store(request), "events_2025.geojson",
        "Olay verisi henüz hesaplanmadı.", "Event data has not been computed yet.",
    )


@router.get("/meta/sources")
def sources(request: Request) -> list[dict[str, Any]]:
    return _store(request).sources


@router.get("/meta/factors")
def factors(request: Request) -> dict[str, dict[str, str]]:
    return _store(request).labels
