"""Per-segment CHM v2 imagery acquisition date from the tile metadata footprints.

CLI: ``python -m hatkalkani.ingest.chm_dates --aoi izmir_menderes``

The v2 bucket carries ``metadata/<quadkey>.geojson`` next to every ``chm/<quadkey>.tif``;
each feature is one source-image footprint with ``properties.acq_date`` (YYYY-MM-DD).
The CHM is a mosaic, so a segment corridor can touch several dates.

Steps: download (and cache + MANIFEST) the metadata of the tiles used by ``chm.py``,
intersect footprints with each segment's +/- half-width corridor (metric CRS) and
summarise per segment. Pure computation is kept apart from network / file I/O.
The S3 object is a plain GeoJSON (no server-side bbox filter), so the whole file is
downloaded once; the bbox filter is applied when reading the cached local file.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import shapely
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from hatkalkani.ingest import chm, common

SOURCE_NAME = "chm_v2_metadata"
OUT_NAME = "chm_acq_segment.parquet"
META_NAME = "chm_acq_segment.meta.json"
# Overlaps smaller than this (m2) are treated as boundary slivers, not coverage.
MIN_OVERLAP_M2 = 1.0
COLUMNS = [
    "segment_id",
    "chm_acq_min",
    "chm_acq_max",
    "chm_acq_dominant",
    "chm_acq_year",
    "chm_acq_coverage",
]


# ------------------------------------------------------------------ pure logic
def metadata_url(qk: str) -> str:
    return f"{chm.V2_BASE}/metadata/{qk}.geojson"


def clean_footprints(fp: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Keep valid polygons with a parseable ``acq_date``; add a ``date`` column."""
    if "acq_date" not in fp.columns:
        return fp.iloc[0:0].assign(date=pd.Series(dtype="datetime64[ns]"))
    dates = pd.to_datetime(fp["acq_date"], format="%Y-%m-%d", errors="coerce")
    keep = dates.notna() & fp.geometry.notna() & ~fp.geometry.is_empty
    out = fp.loc[keep].copy()
    out["date"] = dates[keep]
    out["geometry"] = shapely.make_valid(out.geometry.values)
    return out[["date", "geometry"]]


def union_by_date(fp_m: gpd.GeoDataFrame) -> dict[pd.Timestamp, BaseGeometry]:
    """One merged footprint geometry per acquisition date (metric CRS)."""
    out: dict[pd.Timestamp, BaseGeometry] = {}
    for d, grp in fp_m.groupby("date"):
        out[d] = shapely.union_all(grp.geometry.values)
    return out


def segment_dates(
    corridor: BaseGeometry,
    date_geoms: dict[pd.Timestamp, BaseGeometry],
    tree: STRtree,
    keys: list[pd.Timestamp],
    min_overlap_m2: float = MIN_OVERLAP_M2,
) -> dict[str, object]:
    """Date summary of one corridor polygon."""
    area = corridor.area
    per_date: dict[pd.Timestamp, float] = {}
    pieces = []
    if area > 0:
        for i in tree.query(corridor, predicate="intersects"):
            inter = corridor.intersection(date_geoms[keys[int(i)]])
            if inter.area >= min_overlap_m2:
                per_date[keys[int(i)]] = inter.area
                pieces.append(inter)
    if not per_date:
        return {
            "chm_acq_min": pd.NaT,
            "chm_acq_max": pd.NaT,
            "chm_acq_dominant": pd.NaT,
            "chm_acq_year": pd.NA,
            "chm_acq_coverage": 0.0,
        }
    # ties on area resolve to the most recent date (deterministic)
    dominant = max(per_date, key=lambda d: (per_date[d], d))
    covered = shapely.union_all(pieces).area
    return {
        "chm_acq_min": min(per_date),
        "chm_acq_max": max(per_date),
        "chm_acq_dominant": dominant,
        "chm_acq_year": int(dominant.year),
        "chm_acq_coverage": float(min(1.0, covered / area)),
    }


def compute_segment_dates(
    segments_m: gpd.GeoDataFrame, footprints_m: gpd.GeoDataFrame, half_width_m: float
) -> pd.DataFrame:
    """One row per segment; both inputs must share the same projected CRS."""
    if segments_m.crs is None or footprints_m.crs is None or segments_m.crs != footprints_m.crs:
        raise ValueError("segments and footprints must share one projected CRS")
    corridors = chm.segment_corridors(segments_m, half_width_m)
    date_geoms = union_by_date(footprints_m)
    keys = sorted(date_geoms)
    tree = STRtree([date_geoms[k] for k in keys])
    rows = [
        {"segment_id": sid, **segment_dates(cor, date_geoms, tree, keys)}
        for sid, cor in zip(segments_m["segment_id"], corridors, strict=True)
    ]
    df = pd.DataFrame(rows, columns=COLUMNS)
    for c in ("chm_acq_min", "chm_acq_max", "chm_acq_dominant"):
        df[c] = pd.to_datetime(df[c])
    df["chm_acq_year"] = df["chm_acq_year"].astype("Int64")
    df["chm_acq_coverage"] = df["chm_acq_coverage"].astype("float64")
    return df


# -------------------------------------------------------------------- file I/O
def download_metadata(qk: str, root: Path = common.ROOT, timeout: int = 120) -> Path:
    """Cache ``metadata/<qk>.geojson`` under data/raw/chm_meta/; skip when sha256 matches."""
    dest = root / "data" / "raw" / "chm_meta" / f"{qk}.geojson"
    if common.is_cached(dest, root):
        return dest
    url = metadata_url(qk)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    last: Exception | None = None
    for attempt in range(3):
        try:
            with requests.get(
                url, headers={"User-Agent": common.USER_AGENT}, timeout=timeout, stream=True
            ) as r:
                r.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            tmp.replace(dest)
            common.register(dest, SOURCE_NAME, url, chm.CHM_LICENSE, root)
            return dest
        except requests.RequestException as exc:
            last = exc
            time.sleep(2 * 2**attempt)
    raise RuntimeError(f"metadata download failed for {qk}: {last}")


def read_footprints(
    paths: list[Path], bbox_4326: tuple[float, float, float, float]
) -> gpd.GeoDataFrame:
    """Read cached metadata files with a bbox filter (EPSG:4326) and clean them."""
    parts = []
    for p in paths:
        g = gpd.read_file(p, bbox=bbox_4326, engine="pyogrio")
        if g.crs is None:
            g = g.set_crs("EPSG:4326")
        parts.append(clean_footprints(g.to_crs("EPSG:4326")))
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:4326")


def _iso(ts: object) -> str | None:
    return None if pd.isna(ts) else pd.Timestamp(ts).date().isoformat()


def run(aoi_id: str, root: Path = common.ROOT, log=print) -> dict[str, object]:
    t0 = time.time()
    aoi = common.load_aoi(aoi_id, root / "config" / "aoi.yaml")
    params = chm.load_params(root)
    interim = root / "data" / "interim" / aoi_id
    chm_meta = json.loads((interim / chm.META_NAME).read_text(encoding="utf-8"))
    tile_ids: list[str] = list(chm_meta["tile_ids"])

    segs = gpd.read_parquet(common.processed_dir(aoi_id, root) / "segments.parquet")
    segs_m = segs.to_crs(aoi.metric_crs)
    corridor_union = chm.segment_corridors(segs_m, params.half_width_m).union_all()
    bbox = tuple(
        gpd.GeoSeries([corridor_union], crs=aoi.metric_crs).to_crs("EPSG:4326").total_bounds
    )

    paths = [download_metadata(qk, root) for qk in tile_ids]
    log(f"metadata files: {[p.name for p in paths]}")
    fp = read_footprints(paths, bbox)
    fp_m = fp.to_crs(aoi.metric_crs)
    log(f"footprints in bbox: {len(fp_m)}")

    df = compute_segment_dates(segs_m, fp_m, params.half_width_m)
    if len(df) != len(segs) or df["segment_id"].duplicated().any():
        raise RuntimeError("output rows do not match segments")
    out = interim / OUT_NAME
    df.to_parquet(out, index=False)

    has = df["chm_acq_dominant"].notna()
    meta = {
        "aoi": aoi_id,
        "source": "Meta/WRI CHM v2 tile metadata (properties.acq_date)",
        "source_base_url": f"{chm.V2_BASE}/metadata/",
        "license": chm.CHM_LICENSE,
        "access_date": date.today().isoformat(),
        "tile_ids": tile_ids,
        "metadata_files": {
            p.name: {"sha256": common.sha256_file(p), "bytes": p.stat().st_size} for p in paths
        },
        "corridor_half_width_m": params.half_width_m,
        "min_overlap_m2": MIN_OVERLAP_M2,
        "oldest_date": _iso(df["chm_acq_min"].min()),
        "newest_date": _iso(df["chm_acq_max"].max()),
        "n_footprints_in_bbox": int(len(fp_m)),
        "n_segments": int(len(df)),
        "n_segments_with_date": int(has.sum()),
        "year_counts_dominant": {
            str(k): int(v) for k, v in df["chm_acq_year"].value_counts().sort_index().items()
        },
        "coverage_summary": {
            k: round(float(v), 4) for k, v in df["chm_acq_coverage"].describe().items()
        },
        "semantics": "CHM is a mosaic; dominant = date with the largest corridor area.",
        "output": {"path": out.relative_to(root).as_posix(), "crs": "none (table)"},
        "elapsed_s": round(time.time() - t0, 1),
    }
    (interim / META_NAME).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(f"done: {int(has.sum())}/{len(df)} segments dated in {time.time() - t0:.0f}s")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    args = ap.parse_args()
    os.environ.setdefault("PYTHONUTF8", "1")
    run(args.aoi)


if __name__ == "__main__":
    main()
