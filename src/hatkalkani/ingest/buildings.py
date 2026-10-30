"""Buildings in the AOI plus the WUI buffer: Overture Maps (DuckDB/S3), OSM fallback.

Output `data/interim/<aoi>/buildings.parquet` (EPSG:4326), columns:
source (overture|osm), source_id, dataset (upstream provider), class, subtype, height_m,
num_floors, geometry. Plus `buildings_meta.json` (release, counts, shares, license).
The raw Overture bbox extract is cached under data/raw/overture/ and tracked in MANIFEST.csv.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import yaml
from shapely import wkb
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from .common import (
    ODBL,
    ROOT,
    USER_AGENT,
    fetch_overpass,
    is_cached,
    load_aoi,
    manifest_upsert,
    processed_dir,
    raw_dir,
    read_manifest,
    register,
)

OVERTURE_STAC = "https://stac.overturemaps.org/catalog.json"
OVERTURE_FALLBACK_RELEASE = "2026-10-21.0"
OVERTURE_S3 = "s3://overturemaps-us-west-2/release/{release}/theme=buildings/type=building/*"
OUT_COLUMNS = [
    "source",
    "source_id",
    "dataset",
    "class",
    "subtype",
    "height_m",
    "num_floors",
]


# ------------------------------------------------------------------ pure functions
def corridor_buffer(boundary: BaseGeometry, metric_crs: str, buffer_m: float) -> BaseGeometry:
    """Boundary (EPSG:4326) buffered by `buffer_m` in the metric CRS; returned in EPSG:4326."""
    s = gpd.GeoSeries([boundary], crs="EPSG:4326").to_crs(metric_crs).buffer(buffer_m)
    return s.to_crs("EPSG:4326").iloc[0]


def clip_buildings(gdf: gpd.GeoDataFrame, area: BaseGeometry, metric_crs: str) -> gpd.GeoDataFrame:
    """Keep valid polygons lying entirely within `area` (EPSG:4326); drop empties/duplicates."""
    if gdf.crs is None:
        raise ValueError("buildings have no CRS; refusing to guess")
    g = gdf.to_crs("EPSG:4326")
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    g["geometry"] = g.geometry.make_valid()
    g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
    g = g[g.within(area)]
    g = g.drop_duplicates(subset=["source", "source_id"])
    return g.reset_index(drop=True)


def parse_osm_buildings(data: dict) -> gpd.GeoDataFrame:
    """Overpass `out geom` building ways -> GeoDataFrame (EPSG:4326)."""
    rows = []
    for el in data.get("elements", []):
        pts = el.get("geometry")
        tags = el.get("tags", {})
        if el.get("type") != "way" or not pts or len(pts) < 4 or "building" not in tags:
            continue
        coords = [(p["lon"], p["lat"]) for p in pts]
        if coords[0] != coords[-1]:
            continue
        b = tags["building"]
        h = tags.get("height", "").replace("m", "").strip()
        lv = tags.get("building:levels", "")
        rows.append(
            {
                "source": "osm",
                "source_id": f"w{el['id']}",
                "dataset": "OpenStreetMap",
                "class": None if b == "yes" else b,
                "subtype": None,
                "height_m": float(h) if h.replace(".", "", 1).isdigit() else None,
                "num_floors": int(lv) if lv.isdigit() else None,
                "geometry": Polygon(coords),
            }
        )
    return gpd.GeoDataFrame(
        rows, columns=[*OUT_COLUMNS, "geometry"], geometry="geometry", crs="EPSG:4326"
    )


def summarize(gdf: gpd.GeoDataFrame) -> dict:
    n = len(gdf)
    by_source = gdf["source"].value_counts().to_dict() if n else {}
    by_dataset = gdf["dataset"].value_counts().to_dict() if n else {}
    share = {k: round(v / n, 4) for k, v in by_dataset.items()} if n else {}
    return {"count": n, "by_source": by_source, "by_dataset": by_dataset, "dataset_share": share}


def summarize_licenses(licenses: pd.Series) -> str:
    """Distinct per-record licenses (Overture `sources[].license`), sorted and ';'-joined.

    Never assumes a license: missing values show up as 'unknown'.
    """
    if len(licenses) == 0:
        return "unknown"
    vals = licenses.fillna("unknown").astype(str).str.strip().replace("", "unknown")
    return "; ".join(sorted(vals.unique()))


def count_near_lines(
    buildings: gpd.GeoDataFrame, lines: gpd.GeoDataFrame, metric_crs: str, dist_m: float
) -> int:
    """Number of buildings within `dist_m` of any line (metric CRS distance)."""
    if len(buildings) == 0 or len(lines) == 0:
        return 0
    b = buildings.to_crs(metric_crs)
    corridor = lines.to_crs(metric_crs).geometry.buffer(dist_m).union_all()
    return int(b.intersects(corridor).sum())


# ------------------------------------------------------------------ network / files
def latest_overture_release() -> str:
    try:
        r = requests.get(OVERTURE_STAC, headers={"User-Agent": USER_AGENT}, timeout=30)
        r.raise_for_status()
        latest = r.json().get("latest")
        if latest:
            return str(latest)
    except (requests.RequestException, ValueError):
        pass
    return OVERTURE_FALLBACK_RELEASE


def fetch_overture(
    bbox: tuple[float, float, float, float], release: str, dest: Path, root: Path = ROOT
) -> Path:
    """Read the bbox from Overture S3 GeoParquet with DuckDB; write a local parquet (WKB)."""
    import duckdb

    if is_cached(dest, root):
        return dest
    xmin, ymin, xmax, ymax = bbox
    dest.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(3):
        try:
            con = duckdb.connect()
            con.execute("SET enable_progress_bar=false")
            con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
            con.execute("SET s3_region='us-west-2'")
            src = OVERTURE_S3.format(release=release)
            sql = f"""
                COPY (
                  SELECT id AS source_id,
                         sources[1].dataset AS dataset,
                         sources[1].license AS license,
                         class, subtype,
                         height AS height_m,
                         num_floors,
                         ST_AsWKB(geometry) AS wkb
                  FROM read_parquet('{src}', hive_partitioning=1)
                  WHERE bbox.xmin <= {xmax} AND bbox.xmax >= {xmin}
                    AND bbox.ymin <= {ymax} AND bbox.ymax >= {ymin}
                ) TO '{dest.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
            con.execute(sql)
            con.close()
            register(
                dest,
                "overture-buildings",
                f"{src}?bbox={xmin:.5f},{ymin:.5f},{xmax:.5f},{ymax:.5f}",
                summarize_licenses(pd.read_parquet(dest, columns=["license"])["license"]),
                root,
            )
            return dest
        except Exception as exc:  # duckdb raises several exception types
            last = exc
            time.sleep(5 * 2**attempt)
    raise RuntimeError(f"Overture read failed after retries: {last}")


def load_overture_raw(path: Path) -> gpd.GeoDataFrame:
    df = pd.read_parquet(path)
    geom = [wkb.loads(bytes(b)) for b in df["wkb"]]
    gdf = gpd.GeoDataFrame(df.drop(columns=["wkb"]), geometry=geom, crs="EPSG:4326")
    gdf["source"] = "overture"
    gdf["dataset"] = gdf["dataset"].fillna("unknown")
    return gdf


def osm_buildings_query(bbox: tuple[float, float, float, float]) -> str:
    xmin, ymin, xmax, ymax = bbox
    return f'[out:json][timeout:240];way["building"]({ymin},{xmin},{ymax},{xmax});out geom;'


def _bbox_of(geom: BaseGeometry) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = geom.bounds
    return (x0, y0, x1, y1)


def _sync_manifest_license(path: Path, licence: str, root: Path) -> None:
    """Correct the MANIFEST license of a cached extract in place (keeps sha256 and date)."""
    rel = path.relative_to(root).as_posix()
    for r in read_manifest(root):
        if r["yerel_yol"] == rel and r["lisans"] != licence:
            manifest_upsert({**r, "lisans": licence}, root)


def _find_cached_overture(aoi_id: str, root: Path) -> Path | None:
    hits = sorted(raw_dir("overture", root).glob(f"buildings_{aoi_id}_*.parquet"))
    for p in reversed(hits):
        if is_cached(p, root):
            return p
    return None


# ------------------------------------------------------------------ orchestration
def run(aoi_id: str, root: Path = ROOT, force_osm: bool = False) -> Path:
    cfg = load_aoi(aoi_id)
    acfg = yaml.safe_load((root / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    wui_m = float(acfg["buffers_m"]["wui"])
    near_m = float(acfg["buffers_m"]["affected_building"])
    boundary = gpd.read_parquet(processed_dir(aoi_id, root) / "boundary.parquet")
    area = corridor_buffer(boundary.to_crs("EPSG:4326").union_all(), cfg.metric_crs, wui_m)
    bbox = _bbox_of(area)

    source_used = "overture"
    release: str | None = None
    note = ""
    gdf: gpd.GeoDataFrame
    try:
        if force_osm:
            raise RuntimeError("force_osm")
        cached = _find_cached_overture(aoi_id, root)
        if cached is not None:
            dest = cached
            release = cached.stem.split("_")[-1]
        else:
            release = latest_overture_release()
            dest = raw_dir("overture", root) / f"buildings_{aoi_id}_{release}.parquet"
            fetch_overture(bbox, release, dest, root)
        gdf = load_overture_raw(dest)
    except Exception as exc:
        source_used = "osm"
        note = f"Overture unavailable ({exc}); OSM fallback"
        raw = raw_dir(aoi_id, root).parent / "osm" / f"buildings_{aoi_id}.json"
        fetch_overpass(osm_buildings_query(bbox), raw, "osm-buildings", ODBL, root)
        gdf = parse_osm_buildings(json.loads(raw.read_text(encoding="utf-8")))

    total_raw = len(gdf)
    keep_cols = [*OUT_COLUMNS, "geometry"]
    for c in keep_cols:
        if c not in gdf.columns:
            gdf[c] = None
    carry = ["license"] if "license" in gdf.columns else []
    gdf = clip_buildings(gdf[[*keep_cols, *carry]], area, cfg.metric_crs)
    if source_used == "overture":
        licence = summarize_licenses(gdf["license"]) if carry else "unknown"
    else:
        licence = ODBL
    gdf = gdf[keep_cols]
    if source_used == "overture" and carry:
        _sync_manifest_license(dest, licence, root)

    out_dir = root / "data" / "interim" / aoi_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "buildings.parquet"
    gdf.to_parquet(out)

    near = None
    lines_p = processed_dir(aoi_id, root) / "lines.parquet"
    if lines_p.exists():
        near = count_near_lines(gdf, gpd.read_parquet(lines_p), cfg.metric_crs, near_m)

    meta = {
        "aoi_id": aoi_id,
        "source": source_used,
        "overture_release": release if source_used == "overture" else None,
        "note": note,
        "bbox_wgs84": list(bbox),
        "buffer_m": wui_m,
        "raw_count_in_bbox": total_raw,
        **summarize(gdf),
        "within_affected_building_m_of_lines": near,
        "affected_building_m": near_m,
        "license": licence,
        "attribution": (
            "Overture Maps Foundation (buildings theme; sources incl. OpenStreetMap contributors, "
            "Microsoft, Google, Esri)"
            if source_used == "overture"
            else "(c) OpenStreetMap contributors"
        ),
        "crs": "EPSG:4326",
    }
    (out_dir / "buildings_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--force-osm", action="store_true", help="skip Overture, use OSM")
    args = ap.parse_args()
    out = run(args.aoi, force_osm=args.force_osm)
    meta = json.loads((out.parent / "buildings_meta.json").read_text(encoding="utf-8"))
    print(
        f"{out}: {meta['count']} buildings, source={meta['source']}, "
        f"near-lines={meta['within_affected_building_m_of_lines']}"
    )


if __name__ == "__main__":
    main()
