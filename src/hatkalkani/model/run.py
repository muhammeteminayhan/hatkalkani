"""Score stage: features_<as_of>.parquet -> risk + work orders + exports (spec sections 3-4).

CLI::

    uv run python -m hatkalkani.model.run --aoi izmir_menderes --as-of backtest current

Writes to ``data/processed/<aoi>/``:
``risk_<as_of>.parquet`` (GeoParquet, EPSG:4326, metadata under ``hatkalkani_risk``),
``risk_<as_of>.meta.json``, ``risk_<as_of>.geojson`` (API segment properties only) and
``workorders_<as_of>.{csv,geojson,gpkg}``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq

from hatkalkani.export import write_csv, write_geojson, write_gpkg
from hatkalkani.features.build import _jsonable, peak_memory_mb, read_features, resolve_as_of
from hatkalkani.features.context import load_feature_config
from hatkalkani.ingest import common
from hatkalkani.model.config import load_model_config
from hatkalkani.model.score import factor_metas_from_rows, score_features
from hatkalkani.model.workorders import build_workorders

log = logging.getLogger("hatkalkani.model")

META_KEY = b"hatkalkani_risk"
SEGMENT_COLUMNS = ["segment_id", "line_id", "seq", "voltage_class", "voltage_level",
                   "voltage_kv", "length_m", "geometry"]
# GET /api/segments properties (docs/ARCHITECTURE.md)
API_SEGMENT_PROPERTIES = ["segment_id", "line_id", "voltage_class", "risk", "tier",
                          "p_ignition", "consequence", "top_factors"]
GEOJSON_DECIMALS = {"risk": 1, "p_ignition": 3, "consequence": 3}


def output_paths(processed: Path, as_of: str) -> dict[str, Path]:
    return {
        "risk_parquet": processed / f"risk_{as_of}.parquet",
        "risk_meta": processed / f"risk_{as_of}.meta.json",
        "risk_geojson": processed / f"risk_{as_of}.geojson",
        "workorders_csv": processed / f"workorders_{as_of}.csv",
        "workorders_geojson": processed / f"workorders_{as_of}.geojson",
        "workorders_gpkg": processed / f"workorders_{as_of}.gpkg",
    }


def read_risk(path: Path) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    """Risk GeoDataFrame plus the embedded metadata."""
    raw = (pq.read_schema(path).metadata or {}).get(META_KEY)
    if raw is None:
        raise ValueError(f"{path} has no {META_KEY.decode()} metadata")
    return gpd.read_parquet(path), json.loads(raw.decode("utf-8"))


def _write_risk_parquet(gdf: gpd.GeoDataFrame, meta: dict[str, Any], path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    gdf.to_parquet(tmp, index=False, compression="zstd")
    table = pq.read_table(tmp)
    payload = json.dumps(meta, ensure_ascii=False, sort_keys=True).encode("utf-8")
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), META_KEY: payload})
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)


def api_segments_frame(risk: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Simplified segment layer for the map: API properties, rounded numbers, real arrays."""
    g = gpd.GeoDataFrame(risk[[*API_SEGMENT_PROPERTIES, "geometry"]].copy(),
                         geometry="geometry", crs=risk.crs)
    for col, nd in GEOJSON_DECIMALS.items():
        g[col] = g[col].round(nd)
    g["top_factors"] = [json.loads(s) for s in g["top_factors"]]
    return g


def compute_outputs(
    features: pd.DataFrame, fmeta: dict[str, Any], segments: gpd.GeoDataFrame,
    root: Path, aoi: str,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict[str, Any]]:
    if segments.crs is None:
        raise ValueError("segments.parquet has no CRS; refusing to guess")
    if features["segment_id"].astype(str).tolist() != segments["segment_id"].astype(str).tolist():
        raise SystemExit("features and segments.parquet disagree on segment_id order; "
                         "rebuild features (--stage features)")
    cfg = load_model_config(root)
    res = score_features(features, factor_metas_from_rows(fmeta["factors"]), cfg)
    seg = segments[SEGMENT_COLUMNS].reset_index(drop=True)
    extra = [c for c in ("aux_strike_tall_clusters",) if c in features.columns]
    body = res.frame.drop(columns="segment_id")
    risk = pd.concat([seg.drop(columns="geometry"), pd.Series(fmeta["as_of"], index=seg.index,
                      name="as_of"), body, features[extra].reset_index(drop=True)], axis=1)
    risk["chm_year"] = pd.array([pd.NA] * len(risk), dtype="Int64")  # CHM v2 undated (ADR-008)
    risk = gpd.GeoDataFrame(risk, geometry=seg.geometry.to_numpy(), crs=segments.crs)
    risk = risk.to_crs("EPSG:4326")
    metric_crs = load_feature_config(aoi, root).metric_crs
    workorders = build_workorders(risk, labels=res.meta["labels"], metric_crs=metric_crs)
    meta = {
        **res.meta,
        "aoi": aoi,
        "as_of": fmeta["as_of"],
        "cutoff_utc_exclusive": fmeta.get("cutoff_utc_exclusive"),
        "features_schema_version": fmeta.get("schema_version"),
        "chm_year": None,
        "chm_year_note": "CHM v2 has no acquisition date (ADR-008); baseline year unknown",
        "workorders": {
            "tiers": ["kritik", "yuksek"],
            "n_spans": int(len(workorders)),
            "n_segments": int(workorders["n_segments"].sum()) if len(workorders) else 0,
            "length_km": round(float(workorders["length_m"].sum()) / 1000, 3),
            "sort": "risk_max desc, strike_tree_count desc, span_id asc",
            "risk_mean": "length-weighted mean of the span's segment risks",
            "main_reason": "factor with the largest length-weighted mean positive contribution",
            "strike_tree_count": "sum of strike_trees clusters of the span's segments",
            "map_url_point": "span midpoint (along the line)",
        },
    }
    return risk, workorders, _jsonable(meta)


def write_outputs(risk: gpd.GeoDataFrame, workorders: gpd.GeoDataFrame, meta: dict[str, Any],
                  processed: Path) -> dict[str, Path]:
    paths = output_paths(processed, meta["as_of"])
    processed.mkdir(parents=True, exist_ok=True)
    meta = {**meta, "inputs_sha256": meta.get("inputs_sha256", {})}
    _write_risk_parquet(risk, meta, paths["risk_parquet"])
    paths["risk_meta"].write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True,
                                             indent=2), encoding="utf-8")
    write_geojson(api_segments_frame(risk), paths["risk_geojson"], precision=6)
    write_csv(workorders, paths["workorders_csv"])
    write_geojson(workorders, paths["workorders_geojson"], precision=6)
    write_gpkg(workorders, paths["workorders_gpkg"], layer="workorders")
    return paths


def score_as_of(aoi: str, as_of: date | str, root: Path = common.ROOT, *,
                write: bool = True) -> dict[str, Any]:
    """Score one as_of from cached features; returns frames, metadata and written paths."""
    root = Path(root)
    processed = root / "data" / "processed" / aoi
    day = as_of if isinstance(as_of, str) else as_of.isoformat()
    fpath = processed / f"features_{day}.parquet"
    if not fpath.exists():
        raise SystemExit(f"missing {fpath.name}; run --stage features first")
    features, fmeta = read_features(fpath)
    segments = gpd.read_parquet(processed / "segments.parquet")
    risk, workorders, meta = compute_outputs(features, fmeta, segments, root, aoi)
    meta["inputs_sha256"] = {
        p.relative_to(root).as_posix(): common.sha256_file(p)
        for p in (fpath, processed / "segments.parquet", root / "config" / "risk_weights.yaml")
    }
    paths = write_outputs(risk, workorders, meta, processed) if write else {}
    return {"risk": risk, "workorders": workorders, "meta": meta, "paths": paths}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--as-of", required=True, nargs="+", metavar="DATE",
                    help="YYYY-MM-DD, or 'backtest' / 'current' (config/aoi.yaml periods)")
    ap.add_argument("--root", type=Path, default=common.ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("pyogrio").setLevel(logging.WARNING)  # "Created N records" noise
    t_all = time.perf_counter()
    periods = load_feature_config(args.aoi, args.root).periods
    dates = [resolve_as_of(tok, periods) for tok in args.as_of]
    for d in dict.fromkeys(dates):
        t0 = time.perf_counter()
        out = score_as_of(args.aoi, d, args.root)
        m = out["meta"]
        log.info("risk_%s: %d segments, tiers %s, %d spans (%.1f km), %.1fs", d.isoformat(),
                 m["n_segments"], m["tier_counts"], m["workorders"]["n_spans"],
                 m["workorders"]["length_km"], time.perf_counter() - t0)
        for w in m["warnings"]:
            log.warning("  warning: %s", w)
    peak = peak_memory_mb()
    log.info("score done in %.1fs; peak memory %s", time.perf_counter() - t_all,
             f"{peak:.0f} MB" if peak else "n/a")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
