"""Split lines into ~100 m segments (risk-model-spec section 1) -> segments.parquet."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import substring

from .common import ROOT, load_aoi, processed_dir

CARRY = [
    "source",
    "line_id",
    "source_id",
    "power",
    "voltage_kv",
    "voltage_class",
    "voltage_level",
    "voltage_source",
]


def cut_points(length: float, seg_len: float, min_last: float) -> list[float]:
    """Cumulative cut distances [0, ..., length]. A trailing piece shorter than
    `min_last` is merged into the previous one (so the last segment may reach seg_len+min_last)."""
    n_full = math.floor(length / seg_len)
    cuts = [i * seg_len for i in range(n_full + 1)]
    rem = length - cuts[-1]
    if rem > 1e-9:
        if rem < min_last and n_full >= 1:
            cuts[-1] = length
        else:
            cuts.append(length)
    elif cuts[-1] != length:
        cuts[-1] = length
    return cuts


def split_line(
    geom: LineString | MultiLineString, seg_len: float, min_last: float
) -> list[LineString]:
    """Split a (multi)line given in a metric CRS. Parts are cut independently."""
    parts = list(geom.geoms) if isinstance(geom, MultiLineString) else [geom]
    out: list[LineString] = []
    for part in parts:
        if part.length <= 0:
            continue
        cuts = cut_points(part.length, seg_len, min_last)
        for a, b in zip(cuts[:-1], cuts[1:], strict=True):
            out.append(substring(part, a, b))
    return out


def build_segments(
    lines: gpd.GeoDataFrame, metric_crs: str, seg_len: float, min_last: float
) -> gpd.GeoDataFrame:
    if lines.crs is None:
        raise ValueError("lines has no CRS")
    m = lines.to_crs(metric_crs)
    rows = []
    for _, r in m.iterrows():
        for i, seg in enumerate(split_line(r.geometry, seg_len, min_last), start=1):
            rows.append(
                {
                    "segment_id": f"{r['line_id']}_{i:04d}",
                    "seq": i,
                    **{c: r[c] for c in CARRY},
                    "length_m": seg.length,
                    "geometry": seg,
                }
            )
    out = gpd.GeoDataFrame(rows, crs=metric_crs).to_crs("EPSG:4326")
    return out


def run(aoi_id: str, root: Path = ROOT) -> Path:
    cfg = load_aoi(aoi_id)
    lines = gpd.read_parquet(processed_dir(aoi_id, root) / "lines.parquet")
    segs = build_segments(lines, cfg.metric_crs, cfg.segment_length_m, cfg.min_last_segment_m)
    out = processed_dir(aoi_id, root) / "segments.parquet"
    segs.to_parquet(out, index=False)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    args = ap.parse_args()
    out = run(args.aoi)
    g = gpd.read_parquet(out)
    ln = gpd.read_parquet(processed_dir(args.aoi) / "lines.parquet")
    print(f"{out} bytes={out.stat().st_size} rows={len(g)} crs=EPSG:{g.crs.to_epsg()}")
    print(
        f"segments_km={g.length_m.sum() / 1000:.3f} lines_km={ln.length_m.sum() / 1000:.3f} "
        f"len min/med/max={g.length_m.min():.1f}/{g.length_m.median():.1f}/{g.length_m.max():.1f}"
    )
    print((g.groupby("voltage_class").length_m.sum() / 1000).round(1).to_string())


if __name__ == "__main__":
    main()
