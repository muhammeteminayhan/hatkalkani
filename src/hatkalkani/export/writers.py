"""File writers for the exports: CSV (UTF-8 BOM), GeoJSON (RFC 7946) and GeoPackage.

Every writer converts to EPSG:4326 first (storage/API CRS) and writes atomically
(temporary file + rename) so the API never serves a half-written file.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import mapping

WGS84 = "EPSG:4326"


def ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS; refusing to guess")
    return gdf if gdf.crs.to_epsg() == 4326 else gdf.to_crs(WGS84)


def _tmp(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.with_name(path.name + ".tmp")


def _plain(value: Any) -> Any:
    """JSON-safe scalar / container (numpy types, NaN -> null)."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple | np.ndarray):
        return [_plain(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_ | bool):
        return bool(value)
    if isinstance(value, np.floating | float):
        v = float(value)
        return None if math.isnan(v) or math.isinf(v) else v
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    return value


def _round_coords(obj: Any, precision: int) -> Any:
    if isinstance(obj, list | tuple):
        if obj and isinstance(obj[0], int | float):
            return [round(float(c), precision) for c in obj]
        return [_round_coords(o, precision) for o in obj]
    return obj


def write_csv(df: pd.DataFrame, path: Path, *, sep: str = ",") -> Path:
    """UTF-8 with BOM (Excel opens Turkish text correctly), CRLF line ends, no geometry."""
    path = Path(path)
    table = pd.DataFrame(df.drop(columns=[c for c in ("geometry",) if c in df.columns]))
    tmp = _tmp(path)
    table.to_csv(tmp, index=False, sep=sep, encoding="utf-8-sig", lineterminator="\r\n")
    os.replace(tmp, path)
    return path


def geojson_dict(gdf: gpd.GeoDataFrame, *, precision: int = 6,
                 columns: Sequence[str] | None = None) -> dict[str, Any]:
    """RFC 7946 FeatureCollection (lon/lat, no ``crs`` member); nested values kept."""
    g = ensure_wgs84(gdf)
    cols = list(columns) if columns is not None else [
        c for c in g.columns if c != g.geometry.name]
    features = []
    for geom, props in zip(g.geometry, g[cols].to_dict(orient="records"), strict=True):
        gj = None
        if geom is not None and not geom.is_empty:
            m = mapping(geom)
            gj = {"type": m["type"], "coordinates": _round_coords(m["coordinates"], precision)}
        features.append({"type": "Feature", "properties": _plain(props), "geometry": gj})
    return {"type": "FeatureCollection", "features": features}


def write_geojson(gdf: gpd.GeoDataFrame, path: Path, *, precision: int = 6,
                  columns: Sequence[str] | None = None) -> Path:
    path = Path(path)
    payload = geojson_dict(gdf, precision=precision, columns=columns)
    tmp = _tmp(path)
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    os.replace(tmp, path)
    return path


def write_gpkg(gdf: gpd.GeoDataFrame, path: Path, *, layer: str) -> Path:
    """Single-layer GeoPackage in EPSG:4326; an existing file is replaced, not appended."""
    path = Path(path)
    g = ensure_wgs84(gdf)
    tmp = path.with_name(path.stem + ".tmp" + path.suffix)  # GDAL picks the driver by suffix
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    g.to_file(tmp, layer=layer, driver="GPKG", engine="pyogrio")
    os.replace(tmp, path)
    return path
