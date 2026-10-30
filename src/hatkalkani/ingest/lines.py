"""Overhead power lines clipped to the district: OSM (Overpass) or an EDAS GIS file.

Output `lines.parquet` (EPSG:4326), one row per line, columns:
source (osm|edas), line_id, source_id, power (line|minor_line), voltage_raw, voltage_kv,
voltage_class (ge154kv|kv33_36|diger|etiketsiz), voltage_level (lv|mv|hv),
voltage_source (tag|assumed), length_m (metric CRS, clipped), geometry.
If data/manual/edas/ holds a GPKG/SHP, it replaces OSM.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge

from .common import (
    ROOT,
    AoiConfig,
    fetch_overpass,
    load_aoi,
    processed_dir,
    raw_dir,
    register,
)

DEFAULT_EDAS_DIR = ROOT / "data" / "manual" / "edas"
LINE_COLUMNS = [
    "source",
    "line_id",
    "source_id",
    "power",
    "voltage_raw",
    "voltage_kv",
    "voltage_class",
    "voltage_level",
    "voltage_source",
    "length_m",
]
EDAS_ID_COLS = ["source_id", "id", "hat_id", "hatid", "objectid", "fid", "gid"]
EDAS_VOLTAGE_COLS = ["voltage", "gerilim", "voltaj", "kv", "gerilim_kv", "voltage_kv"]
EDAS_VOLTAGE_V_COLS = ["gerilim_v", "voltage_v"]


# ------------------------------------------------------------------ pure functions
def parse_voltage_v(raw: str | float | None) -> float | None:
    """Highest value (volts) in a possibly ';'-separated OSM voltage tag, else None."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    vals: list[float] = []
    for part in re.split(r"[;/]", str(raw).replace(",", ".")):
        m = re.search(r"\d+(?:\.\d+)?", part)
        if m:
            vals.append(float(m.group()))
    return max(vals) if vals else None


def voltage_class(volts: float | None) -> str:
    if volts is None:
        return "etiketsiz"
    if volts >= 154000:
        return "ge154kv"
    if 33000 <= volts <= 36000:
        return "kv33_36"
    return "diger"


def voltage_level(volts: float | None, power: str) -> tuple[str, str]:
    """(lv|mv|hv, tag|assumed) following risk-model-spec section 1."""
    if volts is None:
        return ("mv" if power == "minor_line" else "hv"), "assumed"
    if volts < 1000:
        return "lv", "tag"
    if volts <= 36000:
        return "mv", "tag"
    return "hv", "tag"


def _require_crs(gdf: gpd.GeoDataFrame, name: str) -> None:
    if gdf.crs is None:
        raise ValueError(f"{name} has no CRS; refusing to guess")


def _classify(volts: float | None, power: str) -> dict:
    level, vsrc = voltage_level(volts, power)
    return {
        "voltage_kv": None if volts is None else volts / 1000.0,
        "voltage_class": voltage_class(volts),
        "voltage_level": level,
        "voltage_source": vsrc,
    }


def parse_osm_lines(data: dict) -> gpd.GeoDataFrame:
    """Overpass `out geom` ways -> GeoDataFrame (EPSG:4326, unclipped)."""
    rows = []
    for el in data.get("elements", []):
        pts = el.get("geometry")
        tags = el.get("tags", {})
        if el.get("type") != "way" or not pts or len(pts) < 2:
            continue
        if tags.get("power") not in ("line", "minor_line"):
            continue
        if tags.get("location") in ("underground", "underwater"):
            continue
        volts = parse_voltage_v(tags.get("voltage"))
        rows.append(
            {
                "source": "osm",
                "line_id": str(el["id"]),
                "source_id": str(el["id"]),
                "power": tags["power"],
                "voltage_raw": tags.get("voltage", ""),
                **_classify(volts, tags["power"]),
                "geometry": LineString([(p["lon"], p["lat"]) for p in pts]),
            }
        )
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def clip_to_boundary(
    lines: gpd.GeoDataFrame, boundary: BaseGeometry, metric_crs: str
) -> gpd.GeoDataFrame:
    """Clip lines to the boundary polygon in the metric CRS; set length_m. Returns EPSG:4326."""
    _require_crs(lines, "lines")
    bnd = gpd.GeoSeries([boundary], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
    m = lines.to_crs(metric_crs)
    geoms = []
    for g in m.geometry:
        inter = g.intersection(bnd)
        parts = [
            p
            for p in getattr(inter, "geoms", [inter])
            if isinstance(p, LineString) and p.length > 0
        ]
        if not parts:
            geoms.append(None)
            continue
        merged = linemerge(parts) if len(parts) > 1 else parts[0]
        geoms.append(merged)
    m = m.assign(geometry=geoms)
    m = m[m.geometry.notna()].copy()
    m["length_m"] = m.geometry.length
    out = m.to_crs("EPSG:4326")
    return out.reset_index(drop=True)


def parse_edas(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Map an EDAS GIS layer onto the line schema.

    Voltage column: kV (values < 1000) or V; power = 'line' for >= 66 kV, else 'minor_line'.
    """
    _require_crs(gdf, "EDAS file")
    gdf = gdf.to_crs("EPSG:4326")
    cols = {c.lower(): c for c in gdf.columns}
    id_col = next((cols[c] for c in EDAS_ID_COLS if c in cols), None)
    v_col = next((cols[c] for c in EDAS_VOLTAGE_COLS if c in cols), None)
    vv_col = next((cols[c] for c in EDAS_VOLTAGE_V_COLS if c in cols), None)
    rows = []
    for i, (_, r) in enumerate(gdf.iterrows()):
        g = r.geometry
        if g is None or g.is_empty or not isinstance(g, (LineString, MultiLineString)):
            continue
        sid = str(r[id_col]) if id_col else str(i + 1)
        volts: float | None = None
        if vv_col:
            volts = parse_voltage_v(r[vv_col])
        elif v_col:
            v = parse_voltage_v(r[v_col])
            volts = None if v is None else (v * 1000.0 if v < 1000 else v)
        power = "line" if (volts is not None and volts >= 66000) else "minor_line"
        raw = "" if not (v_col or vv_col) else str(r[vv_col or v_col])
        rows.append(
            {
                "source": "edas",
                "line_id": f"edas_{sid}",
                "source_id": sid,
                "power": power,
                "voltage_raw": raw,
                **_classify(volts, power),
                "geometry": g,
            }
        )
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def find_edas_file(edas_dir: Path) -> Path | None:
    if not edas_dir.is_dir():
        return None
    for pat in ("*.gpkg", "*.shp"):
        hits = sorted(edas_dir.glob(pat))
        if hits:
            return hits[0]
    return None


# ------------------------------------------------------------------ I/O layer
def lines_query(bbox: tuple[float, float, float, float]) -> str:
    w, s, e, n = bbox
    return (
        '[out:json][timeout:200];way["power"~"^(line|minor_line)$"]'
        f"({s:.5f},{w:.5f},{n:.5f},{e:.5f});out geom;"
    )


def build_lines(cfg: AoiConfig, boundary: gpd.GeoDataFrame, root: Path, edas_dir: Path | None):
    edas_file = find_edas_file(edas_dir or DEFAULT_EDAS_DIR)
    if edas_file is not None:
        raw = gpd.read_file(edas_file)
        if edas_file.is_relative_to(root):
            register(edas_file, "edas", edas_file.as_posix(), "Sozlesmeye gore (EDAS)", root)
        lines = parse_edas(raw)
    else:
        w, s, e, n = boundary.total_bounds
        path = fetch_overpass(
            lines_query((w, s, e, n)),
            raw_dir(cfg.aoi_id, root) / "lines_overpass.json",
            source="osm_power_lines",
            root=root,
        )
        lines = parse_osm_lines(json.loads(path.read_text(encoding="utf-8")))
    clipped = clip_to_boundary(lines, boundary.geometry.iloc[0], cfg.metric_crs)
    return clipped[[*LINE_COLUMNS, "geometry"]]


def run(aoi_id: str, root: Path = ROOT, edas_dir: Path | None = None) -> Path:
    cfg = load_aoi(aoi_id)
    boundary = gpd.read_parquet(processed_dir(aoi_id, root) / "boundary.parquet")
    lines = build_lines(cfg, boundary, root, edas_dir)
    out = processed_dir(aoi_id, root) / "lines.parquet"
    lines.to_parquet(out, index=False)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--edas-dir", type=Path, default=None, help="default: data/manual/edas/")
    args = ap.parse_args()
    out = run(args.aoi, edas_dir=args.edas_dir)
    g = gpd.read_parquet(out)
    print(f"{out} bytes={out.stat().st_size} rows={len(g)} crs=EPSG:{g.crs.to_epsg()}")
    print(f"source={sorted(g.source.unique())} total_km={g.length_m.sum() / 1000:.1f}")
    print((g.groupby("voltage_class").length_m.sum() / 1000).round(1).to_string())


if __name__ == "__main__":
    main()
