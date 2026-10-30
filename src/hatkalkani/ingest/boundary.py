"""District boundary: OSM admin_level=6 relation via Overpass -> boundary.parquet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import linemerge, polygonize, unary_union

from .common import ROOT, AoiConfig, fetch_overpass, load_aoi, processed_dir, raw_dir


def boundary_query(il: str, ilce: str) -> str:
    return (
        f'[out:json][timeout:200];area["name"="{il}"]["admin_level"="4"]->.a;'
        f'rel(area.a)["name"="{ilce}"]["admin_level"="6"]["boundary"="administrative"];'
        "out geom;"
    )


def relation_to_geom(rel: dict) -> Polygon | MultiPolygon | None:
    """Assemble an Overpass `out geom` relation into a (multi)polygon (EPSG:4326)."""
    outers: list[LineString] = []
    inners: list[LineString] = []
    for m in rel.get("members", []):
        pts = m.get("geometry")
        if m.get("type") != "way" or not pts or len(pts) < 2:
            continue
        ls = LineString([(p["lon"], p["lat"]) for p in pts])
        (inners if m.get("role") == "inner" else outers).append(ls)
    if not outers:
        return None
    shell = unary_union(list(polygonize(linemerge(outers))))
    if inners:
        shell = shell.difference(unary_union(list(polygonize(linemerge(inners)))))
    return None if shell.is_empty else shell


def parse_boundary(data: dict, cfg: AoiConfig) -> gpd.GeoDataFrame:
    rels = [e for e in data.get("elements", []) if e.get("type") == "relation"]
    if len(rels) != 1:
        raise ValueError(f"expected exactly 1 boundary relation for {cfg.ilce}, got {len(rels)}")
    rel = rels[0]
    geom = relation_to_geom(rel)
    if geom is None:
        raise ValueError("boundary relation has no assembled geometry")
    gdf = gpd.GeoDataFrame(
        [
            {
                "aoi_id": cfg.aoi_id,
                "il": cfg.il,
                "ilce": cfg.ilce,
                "osm_rel": int(rel["id"]),
                "geometry": geom,
            }
        ],
        crs="EPSG:4326",
    )
    gdf["area_km2"] = gdf.to_crs(cfg.metric_crs).area / 1e6
    return gdf


def run(aoi_id: str, root: Path = ROOT) -> Path:
    cfg = load_aoi(aoi_id)
    raw = fetch_overpass(
        boundary_query(cfg.il, cfg.ilce),
        raw_dir(aoi_id, root) / "boundary_overpass.json",
        source="osm_boundary",
        root=root,
    )
    gdf = parse_boundary(json.loads(raw.read_text(encoding="utf-8")), cfg)
    out = processed_dir(aoi_id, root) / "boundary.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(out, index=False)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    args = ap.parse_args()
    out = run(args.aoi)
    g = gpd.read_parquet(out)
    print(
        f"{out} bytes={out.stat().st_size} rows={len(g)} crs=EPSG:{g.crs.to_epsg()} "
        f"area_km2={g.area_km2.iloc[0]:.1f}"
    )


if __name__ == "__main__":
    main()
