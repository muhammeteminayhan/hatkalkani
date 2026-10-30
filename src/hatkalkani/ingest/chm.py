"""Canopy height (Meta/WRI CHM v2) windowed extraction along the line corridor.

Pipeline (CLI: ``python -m hatkalkani.ingest.chm --aoi izmir_menderes``):
  1. corridor = union of flat-cap buffers (+/- half width) of every segment, in metric CRS;
  2. pick the v2 quadkey tiles that touch the corridor (HEAD check on S3, anonymous);
  3. read ONLY corridor windows from the remote tiled COGs, warped to a 1 m metric grid;
  4. write ``chm_corridor.tif`` (COG, nodata 255 outside corridor) and per-segment stats.

Pure computation (``segment_chm_stats`` & co.) is kept apart from network / file I/O.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.shutil
import requests
import shapely
import yaml
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import Affine, from_origin
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window
from scipy import ndimage
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shp_transform
from shapely.strtree import STRtree

from hatkalkani.ingest import common

NODATA = 255
WORLD_3857 = 2 * 20037508.342789244
V2_BASE = "https://dataforgood-fb-data.s3.amazonaws.com/forests/v2/global/dinov3_global_chm_v2_ml3"
V2_VERSION = "v2 (dinov3_global_chm_v2_ml3)"
CHM_LICENSE = (
    "CC BY 4.0; Meta and World Resources Institute (WRI) - 2024. "
    "High Resolution Canopy Height Maps (CHM)"
)
CHUNK_PX = 256
OUT_RES_M = 1.0
STATS_NAME = "chm_segment_stats.parquet"
TIF_NAME = "chm_corridor.tif"
META_NAME = "chm_meta.json"
# v1 imagery date range reported for this AOI by F1-1b (v2 tiles carry no dates).
F1_REPORT_DATES = "docs/reports/F1-1b-ortu.md"
F1_CORRIDORS_CSV = "data/interim/f1_candidates/candidate_corridors.csv"


# --------------------------------------------------------------------- config
@dataclass(frozen=True)
class ChmParams:
    half_width_m: float
    min_encroach_canopy_m: float
    strike_margin_m: float
    strike_max_distance_m: float
    strike_min_cluster_px: int
    clearance_band_m: dict[str, float]
    placeholder_unverified: bool = False


def load_params(root: Path = common.ROOT) -> ChmParams:
    aoi = yaml.safe_load((root / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    rw = yaml.safe_load((root / "config" / "risk_weights.yaml").read_text(encoding="utf-8"))
    p = rw["parameters"]
    return ChmParams(
        half_width_m=float(aoi["buffers_m"]["chm_corridor_half_width"]),
        min_encroach_canopy_m=float(p["min_encroach_canopy_m"]),
        strike_margin_m=float(p["strike_margin_m"]),
        strike_max_distance_m=float(p["strike_max_distance_m"]),
        strike_min_cluster_px=int(p["strike_min_cluster_px"]),
        clearance_band_m={k: float(v) for k, v in p["clearance_band_m"].items()},
        placeholder_unverified=bool(p.get("placeholder_unverified", False)),
    )


# ------------------------------------------------------------ pure: geometry
def quadkey_bounds_3857(qk: str) -> tuple[float, float, float, float]:
    """(minx, miny, maxx, maxy) of a Bing quadkey tile in EPSG:3857."""
    x = y = 0
    for ch in qk:
        d = int(ch)
        x = (x << 1) | (d & 1)
        y = (y << 1) | (d >> 1)
    size = WORLD_3857 / (1 << len(qk))
    minx = -WORLD_3857 / 2 + x * size
    maxy = WORLD_3857 / 2 - y * size
    return (minx, maxy - size, minx + size, maxy)


def tile_to_quadkey(x: int, y: int, z: int) -> str:
    digits = []
    for i in range(z, 0, -1):
        mask = 1 << (i - 1)
        digits.append(str((1 if x & mask else 0) + (2 if y & mask else 0)))
    return "".join(digits)


def candidate_quadkeys(geom_3857: BaseGeometry, zoom: int) -> list[str]:
    """Quadkeys at `zoom` whose tile box intersects the geometry."""
    size = WORLD_3857 / (1 << zoom)
    minx, miny, maxx, maxy = geom_3857.bounds
    x0 = int(math.floor((minx + WORLD_3857 / 2) / size))
    x1 = int(math.floor((maxx + WORLD_3857 / 2) / size))
    y0 = int(math.floor((WORLD_3857 / 2 - maxy) / size))
    y1 = int(math.floor((WORLD_3857 / 2 - miny) / size))
    shapely.prepare(geom_3857)
    out = []
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            qk = tile_to_quadkey(x, y, zoom)
            if geom_3857.intersects(box(*quadkey_bounds_3857(qk))):
                out.append(qk)
    return sorted(out)


def segment_corridors(segments_m: gpd.GeoDataFrame, half_width_m: float) -> gpd.GeoSeries:
    """Flat-cap +/- half_width buffer of each segment (metric CRS required)."""
    if segments_m.crs is None or not segments_m.crs.is_projected:
        raise ValueError("segments must be in a projected (metric) CRS")
    return segments_m.geometry.buffer(
        half_width_m, cap_style="flat", join_style="mitre", mitre_limit=2.0
    )


def grid_for(
    bounds: tuple[float, float, float, float], res: float = OUT_RES_M
) -> tuple[Affine, int, int]:
    """Integer-aligned grid covering `bounds`."""
    minx = math.floor(bounds[0] / res) * res
    maxy = math.ceil(bounds[3] / res) * res
    width = int(math.ceil((bounds[2] - minx) / res))
    height = int(math.ceil((maxy - bounds[1]) / res))
    return from_origin(minx, maxy, res, res), width, height


# ----------------------------------------------------------- pure: statistics
def _empty_stats(reason: str) -> dict[str, object]:
    return {
        "chm_n_px": 0,
        "chm_valid_frac": 0.0,
        "chm_mean": np.nan,
        "chm_p50": np.nan,
        "chm_p90": np.nan,
        "chm_max": np.nan,
        "chm_frac_ge_min_canopy": np.nan,
        "chm_band_px": 0,
        "chm_encroach_frac": np.nan,
        "chm_strike_clusters": np.nan,
        "chm_nan_reason": reason,
    }


def segment_chm_stats(
    chm: np.ndarray,
    corridor_mask: np.ndarray,
    dist_m: np.ndarray,
    params: ChmParams,
    clearance_m: float,
    nodata: int = NODATA,
) -> dict[str, object]:
    """Raw CHM statistics of one segment corridor.

    chm: 2-D heights (m); corridor_mask: pixels inside this segment's corridor;
    dist_m: horizontal distance of each pixel centre to the segment line;
    clearance_m: encroachment band half-width for the segment's voltage class.
    """
    total = int(corridor_mask.sum())
    if total == 0:
        return _empty_stats("empty_corridor")
    valid = corridor_mask & (chm != nodata)
    n = int(valid.sum())
    if n == 0:
        return _empty_stats("no_chm_coverage")
    h = chm[valid].astype(np.float32)
    band = valid & (dist_m <= clearance_m)
    n_band = int(band.sum())
    enc = float((chm[band] >= params.min_encroach_canopy_m).mean()) if n_band else np.nan
    strike = (
        valid
        & (dist_m <= params.strike_max_distance_m)
        & (chm.astype(np.float32) >= dist_m + params.strike_margin_m)
    )
    labels, k = ndimage.label(strike, structure=np.ones((3, 3), dtype=int))
    if k:
        sizes = np.bincount(labels.ravel())[1:]
        clusters = int((sizes >= params.strike_min_cluster_px).sum())
    else:
        clusters = 0
    frac = n / total
    return {
        "chm_n_px": n,
        "chm_valid_frac": float(frac),
        "chm_mean": float(h.mean()),
        "chm_p50": float(np.percentile(h, 50)),
        "chm_p90": float(np.percentile(h, 90)),
        "chm_max": float(h.max()),
        "chm_frac_ge_min_canopy": float((h >= params.min_encroach_canopy_m).mean()),
        "chm_band_px": n_band,
        "chm_encroach_frac": enc,
        "chm_strike_clusters": clusters,
        "chm_nan_reason": "partial_coverage" if frac < 0.5 else "",
    }


def compute_segment_stats(
    segments_m: gpd.GeoDataFrame, tif_path: Path, params: ChmParams
) -> pd.DataFrame:
    """One row per segment, reading windows from the local corridor raster."""
    rows = []
    with rasterio.open(tif_path) as src:
        if (
            src.crs.to_string() != str(segments_m.crs)
            and src.crs.to_epsg() != segments_m.crs.to_epsg()
        ):
            raise ValueError(f"CRS mismatch: raster {src.crs} vs segments {segments_m.crs}")
        corridors = segment_corridors(segments_m, params.half_width_m)
        for seg, cor in zip(segments_m.itertuples(index=False), corridors, strict=True):
            level = getattr(seg, "voltage_level", "mv")
            clearance = params.clearance_band_m.get(level, params.clearance_band_m["mv"])
            win = rasterio.windows.from_bounds(*cor.bounds, transform=src.transform)
            c0, r0 = math.floor(win.col_off), math.floor(win.row_off)
            win = Window(c0, r0, math.ceil(win.width) + 2, math.ceil(win.height) + 2)
            win = (
                win.intersection(Window(0, 0, src.width, src.height))
                if _overlaps(win, src)
                else None
            )
            if win is None:
                stats = _empty_stats("outside_raster")
            else:
                chm = src.read(1, window=win)
                tr = src.window_transform(win)
                mask = rasterize(
                    [(cor, 1)], out_shape=chm.shape, transform=tr, fill=0, dtype="uint8"
                ).astype(bool)
                dist = _pixel_distance(seg.geometry, chm.shape, tr)
                stats = segment_chm_stats(chm, mask, dist, params, clearance)
            rows.append({"segment_id": seg.segment_id, **stats})
    df = pd.DataFrame(rows)
    df["chm_n_px"] = df["chm_n_px"].astype("int64")
    df["chm_band_px"] = df["chm_band_px"].astype("int64")
    return df


def _overlaps(win: Window, src: rasterio.DatasetReader) -> bool:
    return (
        win.col_off < src.width
        and win.row_off < src.height
        and win.col_off + win.width > 0
        and win.row_off + win.height > 0
    )


def _pixel_distance(line: BaseGeometry, shape: tuple[int, int], tr: Affine) -> np.ndarray:
    rows, cols = np.indices(shape)
    xs, ys = tr @ (cols.ravel() + 0.5, rows.ravel() + 0.5)
    pts = shapely.points(xs, ys)
    return shapely.distance(line, pts).reshape(shape)


# ------------------------------------------------------------------ I/O: tiles
def tile_url(qk: str) -> str:
    return f"{V2_BASE}/chm/{qk}.tif"


def existing_tiles(qks: list[str], timeout: int = 30) -> tuple[list[str], list[str]]:
    """HEAD each candidate tile; returns (available, missing)."""
    ok, missing = [], []
    for qk in qks:
        last = None
        for attempt in range(3):
            try:
                r = requests.head(
                    tile_url(qk), headers={"User-Agent": common.USER_AGENT}, timeout=timeout
                )
                if r.status_code == 200:
                    ok.append(qk)
                elif r.status_code in (403, 404):
                    missing.append(qk)
                else:
                    r.raise_for_status()
                break
            except requests.RequestException as exc:
                last = exc
                time.sleep(2 * 2**attempt)
        else:
            raise RuntimeError(f"HEAD failed for {qk}: {last}")
    return ok, missing


def gdal_env() -> rasterio.Env:
    return rasterio.Env(
        AWS_NO_SIGN_REQUEST="YES",
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_TIMEOUT="60",
        GDAL_HTTP_MAX_RETRY="3",
        GDAL_HTTP_RETRY_DELAY="2",
        GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
        VSI_CACHE="TRUE",
        VSI_CACHE_SIZE=str(256 * 1024 * 1024),
        CPL_VSIL_CURL_CACHE_SIZE=str(256 * 1024 * 1024),
    )


def chunk_windows(
    corridor_union: BaseGeometry, transform: Affine, width: int, height: int, chunk: int = CHUNK_PX
) -> list[Window]:
    """Chunk windows of the output grid that touch the corridor."""
    shapely.prepare(corridor_union)
    wins = []
    for r0 in range(0, height, chunk):
        for c0 in range(0, width, chunk):
            w = Window(c0, r0, min(chunk, width - c0), min(chunk, height - r0))
            x0, y0 = transform @ (w.col_off, w.row_off)
            x1, y1 = transform @ (w.col_off + w.width, w.row_off + w.height)
            if corridor_union.intersects(box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))):
                wins.append(w)
    return wins


def merge_into(dst: np.ndarray, src_vals: np.ndarray, src_valid: np.ndarray) -> None:
    """Fill `dst` (NODATA = empty) with `src_vals` where `src_valid` and dst still empty."""
    take = src_valid & (dst == NODATA)
    dst[take] = src_vals[take]


def extract_corridor(
    tiles: dict[str, str],
    corridors: gpd.GeoSeries,
    out_tif: Path,
    transform: Affine,
    width: int,
    height: int,
    metric_crs: str,
    log=print,
) -> dict[str, list[tuple[float, float, float, float]]]:
    """Windowed read of corridor pixels from `tiles` ({id: path/url}) into a COG.

    Returns, per tile, the metric boxes that were actually read (for download estimates).
    """
    union = corridors.union_all()
    wins = chunk_windows(union, transform, width, height)
    log(f"chunks touching corridor: {len(wins)}")
    tmp = out_tif.with_suffix(".tmp.tif")
    read_boxes: dict[str, list[tuple[float, float, float, float]]] = {k: [] for k in tiles}
    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "count": 1,
        "width": width,
        "height": height,
        "crs": metric_crs,
        "transform": transform,
        "nodata": NODATA,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
        "SPARSE_OK": "TRUE",
    }
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    with gdal_env():
        srcs = {k: rasterio.open(p) for k, p in tiles.items()}
        vrts = {
            k: WarpedVRT(
                s,
                crs=metric_crs,
                transform=transform,
                width=width,
                height=height,
                resampling=Resampling.nearest,
                add_alpha=True,
                nodata=None,
            )
            for k, s in srcs.items()
        }
        to_3857 = {
            k: Transformer.from_crs(metric_crs, s.crs, always_xy=True) for k, s in srcs.items()
        }
        src_boxes = {k: box(*s.bounds) for k, s in srcs.items()}
        try:
            with rasterio.open(tmp, "w", **profile) as dst:
                for i, w in enumerate(wins):
                    tr = rasterio.windows.transform(w, transform)
                    shape = (int(w.height), int(w.width))
                    mask = rasterize(
                        [
                            (g, 1)
                            for g in corridors[
                                corridors.intersects(box(*rasterio.windows.bounds(w, transform)))
                            ]
                        ],
                        out_shape=shape,
                        transform=tr,
                        fill=0,
                        dtype="uint8",
                    ).astype(bool)
                    if not mask.any():
                        continue
                    ys, xs = np.nonzero(mask)
                    sub = Window(
                        w.col_off + xs.min(),
                        w.row_off + ys.min(),
                        xs.max() - xs.min() + 1,
                        ys.max() - ys.min() + 1,
                    )
                    sub_bounds = rasterio.windows.bounds(sub, transform)
                    merged = np.full((int(sub.height), int(sub.width)), NODATA, dtype=np.uint8)
                    sm = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
                    for k, vrt in vrts.items():
                        sb = shp_transform(to_3857[k].transform, box(*sub_bounds))
                        if not src_boxes[k].intersects(sb):
                            continue
                        data = vrt.read(window=sub)
                        vals, alpha = data[0], data[1] > 0
                        merge_into(merged, vals, alpha)
                        read_boxes[k].append(sub_bounds)
                    merged[~sm] = NODATA
                    dst.write(merged, 1, window=sub)
                    if (i + 1) % 100 == 0:
                        log(f"  chunk {i + 1}/{len(wins)}")
        finally:
            for v in vrts.values():
                v.close()
            for s in srcs.values():
                s.close()
    rasterio.shutil.copy(
        tmp,
        out_tif,
        driver="COG",
        COMPRESS="DEFLATE",
        BLOCKSIZE=256,
        OVERVIEWS="NONE",
        RESAMPLING="NEAREST",
    )
    tmp.unlink()
    return read_boxes


def estimate_download_bytes(
    tiles: dict[str, str],
    boxes: dict[str, list[tuple[float, float, float, float]]],
    metric_crs: str,
) -> int:
    """Sum of compressed sizes of the source blocks whose area was read (lower bound)."""
    total = 0
    with gdal_env():
        for k, path in tiles.items():
            if not boxes.get(k):
                continue
            with rasterio.open(path) as s:
                tf = Transformer.from_crs(metric_crs, s.crs, always_xy=True)
                bx = shapely.union_all([shp_transform(tf.transform, box(*b)) for b in boxes[k]])
                bw, bh = s.block_shapes[0][1], s.block_shapes[0][0]
                geoms, idx = [], []
                for r in range(0, s.height, bh):
                    for c in range(0, s.width, bw):
                        x0, y0 = s.transform @ (c, r)
                        x1, y1 = s.transform @ (c + bw, r + bh)
                        geoms.append(box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
                        idx.append((c // bw, r // bh))
                tree = STRtree(geoms)
                for j in tree.query(bx, predicate="intersects"):
                    bxi, byi = idx[int(j)]
                    sz = s.get_tag_item(f"BLOCK_SIZE_{bxi}_{byi}", "TIFF", bidx=1)
                    total += int(sz) if sz else 0
    return total


# ------------------------------------------------------------------- metadata
def reference_dates(root: Path, ilce: str) -> str | None:
    """v1 imagery date range for the district from the F1 corridor table (v2 has none)."""
    p = root / F1_CORRIDORS_CSV
    if not p.exists():
        return None
    df = pd.read_csv(p, encoding="utf-8")
    if "chm_dates" not in df.columns or "ilce" not in df.columns:
        return None
    hit = df[df["ilce"] == ilce]
    return str(hit["chm_dates"].iloc[0]) if len(hit) else None


def stats_cache_key(params: ChmParams) -> dict[str, object]:
    """Every config-derived parameter the per-segment statistics depend on."""
    return asdict(params)


def cache_decision(
    meta: dict[str, object],
    key: dict[str, object],
    stats_key: dict[str, object],
    raster_ok: bool,
    stats_exist: bool,
) -> str:
    """'hit' | 'stats' (re-derive statistics from cached raster) | 'full' (re-extract)."""
    if meta.get("cache_key") != key or not raster_ok:
        return "full"
    if stats_exist and meta.get("stats_key") == stats_key:
        return "hit"
    return "stats"


def cache_key(segments_path: Path, params: ChmParams, metric_crs: str) -> dict[str, object]:
    return {
        "segments_sha256": common.sha256_file(segments_path),
        "half_width_m": params.half_width_m,
        "metric_crs": metric_crs,
        "out_res_m": OUT_RES_M,
        "version": V2_VERSION,
    }


# ------------------------------------------------------------------------ run
def run(aoi_id: str, root: Path = common.ROOT, log=print) -> dict[str, object]:
    t0 = time.time()
    aoi = common.load_aoi(aoi_id, root / "config" / "aoi.yaml")
    params = load_params(root)
    seg_path = common.processed_dir(aoi_id, root) / "segments.parquet"
    out_dir = root / "data" / "interim" / aoi_id
    out_dir.mkdir(parents=True, exist_ok=True)
    tif, stats_pq, meta_path = out_dir / TIF_NAME, out_dir / STATS_NAME, out_dir / META_NAME

    segs = gpd.read_parquet(seg_path)
    if segs.crs is None:
        raise ValueError("segments.parquet has no CRS")
    segs_m = segs.to_crs(aoi.metric_crs)
    key = cache_key(seg_path, params, aoi.metric_crs)

    stats_key = stats_cache_key(params)
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    decision = cache_decision(
        meta, key, stats_key, common.is_cached(tif, root), stats_pq.exists()
    )
    if decision == "hit":
        log(f"cache hit: {tif.name} ({time.time() - t0:.1f}s)")
        meta["cache_hit"] = True
        return meta
    if decision == "stats":
        log("raster cache hit; statistics parameters changed -> recomputing statistics")
        stats = compute_segment_stats(segs_m, tif, params)
        if len(stats) != len(segs) or stats["segment_id"].duplicated().any():
            raise RuntimeError("stats rows do not match segments")
        stats.to_parquet(stats_pq, index=False)
        meta["stats_key"] = stats_key
        meta["placeholder_unverified"] = params.placeholder_unverified
        meta["cache_hit"] = "raster_only"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return meta

    corridors = segment_corridors(segs_m, params.half_width_m)
    union = corridors.union_all()
    to_3857 = Transformer.from_crs(aoi.metric_crs, "EPSG:3857", always_xy=True)
    zoom = 10
    cands = candidate_quadkeys(shp_transform(to_3857.transform, union), zoom)
    tiles_ok, tiles_missing = existing_tiles(cands)
    if not tiles_ok:
        raise RuntimeError("no CHM v2 tile found for corridor")
    log(f"v2 tiles: {tiles_ok} (missing: {tiles_missing})")
    tiles = {qk: f"/vsicurl/{tile_url(qk)}" for qk in tiles_ok}

    transform, width, height = grid_for(union.bounds)
    boxes = extract_corridor(tiles, corridors, tif, transform, width, height, aoi.metric_crs, log)
    est_bytes = estimate_download_bytes(tiles, boxes, aoi.metric_crs)
    common.register(tif, "chm_v2_corridor_window", V2_BASE + "/chm/<tile>.tif", CHM_LICENSE, root)

    stats = compute_segment_stats(segs_m, tif, params)
    if len(stats) != len(segs) or stats["segment_id"].duplicated().any():
        raise RuntimeError("stats rows do not match segments")
    stats.to_parquet(stats_pq, index=False)

    with rasterio.open(tif) as r:
        valid_px = 0
        for _, w in r.block_windows(1):
            valid_px += int((r.read(1, window=w) != NODATA).sum())
        crs, shape = r.crs.to_string(), (r.height, r.width)
    meta = {
        "aoi": aoi_id,
        "chm_version": V2_VERSION,
        "license": CHM_LICENSE,
        "source_base_url": V2_BASE,
        "tile_ids": tiles_ok,
        "tiles_missing": tiles_missing,
        "image_dates": {
            "v2": "unknown (v2 tiles carry no acquisition date)",
            "v1_reference_range_same_area": reference_dates(root, aoi.ilce),
            "source": F1_CORRIDORS_CSV,
        },
        "value_semantics": "uint8 canopy height in metres; 255 = outside corridor / no data",
        "corridor_half_width_m": params.half_width_m,
        "output": {
            "path": tif.relative_to(root).as_posix(),
            "crs": crs,
            "shape_hw": list(shape),
            "res_m": OUT_RES_M,
            "valid_px": valid_px,
            "bytes": tif.stat().st_size,
        },
        "download_bytes_estimate": est_bytes,
        "n_segments": int(len(segs)),
        "cache_key": key,
        "stats_key": stats_key,
        "placeholder_unverified": params.placeholder_unverified,
        "cache_hit": False,
        "elapsed_s": round(time.time() - t0, 1),
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"done in {time.time() - t0:.0f}s; est download {est_bytes / 1e6:.0f} MB")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    args = ap.parse_args()
    os.environ.setdefault("PYTHONUTF8", "1")
    run(args.aoi)


if __name__ == "__main__":
    main()
