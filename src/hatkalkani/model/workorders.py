"""Work packages for pruning / drone inspection (risk-model-spec section 4).

Consecutive ``kritik`` / ``yuksek`` segments of one line are merged into a span. Two
segments are consecutive when their ``seq`` numbers follow each other *and* the second
starts where the first ends: lines clipped by the district boundary are split into parts
whose ``seq`` runs on across the gap, and a span must not jump over such a gap.
"""

from __future__ import annotations

from collections.abc import Mapping

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import linemerge

WORK_TIERS = ("kritik", "yuksek")  # spec section 4
# Numerical tolerance for "the next segment starts where this one ends". Segments cut from
# one line part share their end points exactly; the smallest real gap in the pilot is
# 12.7 m (a line leaving and re-entering the district).
CONTIGUITY_TOLERANCE_M = 1.0
REASONS_IN_TEXT = 3
COORD_DECIMALS = 6  # ~0.1 m
MAP_URL = "https://www.google.com/maps?q={lat:.6f},{lon:.6f}"

WORKORDER_COLUMNS = [
    # risk-model-spec section 4 fields
    "span_id", "line_id", "voltage_class", "length_m", "risk_max", "risk_mean",
    "main_reason_tr", "strike_tree_count", "start_lat", "start_lon", "end_lat", "end_lon",
    "map_url",
    # additions for ranking, the TR/EN interface and traceability
    "priority", "tier_max", "n_segments", "segment_ids", "voltage_level", "voltage_kv",
    "main_reason_key", "main_reason_en", "reasons_tr", "reasons_en", "strike_tall_count",
    "as_of",
]
_REQUIRED = ("segment_id", "line_id", "seq", "tier", "risk", "length_m", "geometry")
# raw strike-tree cluster count: risk frames carry it as raw_strike_trees
STRIKE_COLUMNS = ("raw_strike_trees", "strike_trees")


def _runs(group: gpd.GeoDataFrame) -> list[list[int]]:
    """Index runs of consecutive, contiguous work-tier segments of one line (metric CRS)."""
    runs: list[list[int]] = []
    prev_idx = None
    for idx, row in group.iterrows():
        if row["tier"] not in WORK_TIERS:
            prev_idx = None
            continue
        if prev_idx is not None:
            prev = group.loc[prev_idx]
            gap = Point(prev.geometry.coords[-1]).distance(Point(row.geometry.coords[0]))
            if row["seq"] == prev["seq"] + 1 and gap <= CONTIGUITY_TOLERANCE_M:
                runs[-1].append(idx)
                prev_idx = idx
                continue
        runs.append([idx])
        prev_idx = idx
    return runs


def _merge_geometry(parts: list[LineString]) -> LineString:
    coords = list(parts[0].coords)
    for g in parts[1:]:
        c = list(g.coords)
        coords.extend(c[1:] if Point(coords[-1]).distance(Point(c[0])) <= 1e-6 else c)
    merged = LineString(coords)
    return merged if merged.is_valid else linemerge(parts)


def _reasons(seg: pd.DataFrame, contrib_cols: list[str], weights: np.ndarray,
             labels: Mapping[str, Mapping[str, str]]) -> list[str]:
    """Factor keys ordered by length-weighted mean contribution (positive ones only)."""
    if not contrib_cols:
        return []
    means = (seg[contrib_cols].to_numpy() * weights[:, None]).sum(axis=0) / weights.sum()
    order = np.lexsort((np.arange(len(contrib_cols)), -np.round(means, 6)))
    return [contrib_cols[j].removeprefix("contrib_") for j in order if means[j] > 0]


def build_workorders(
    risk: gpd.GeoDataFrame,
    *,
    labels: Mapping[str, Mapping[str, str]],
    metric_crs: str,
) -> gpd.GeoDataFrame:
    """Spans sorted by risk_max (desc), then strike_tree_count (desc); EPSG:4326."""
    if risk.crs is None:
        raise ValueError("risk frame has no CRS; refusing to guess")
    strike = next((c for c in STRIKE_COLUMNS if c in risk.columns), None)
    missing = [c for c in _REQUIRED if c not in risk.columns] + ([] if strike else ["strike_trees"])
    if missing:
        raise ValueError(f"risk frame lacks columns {missing}")
    m = risk.to_crs(metric_crs)
    if not m.crs.is_projected:
        raise ValueError(f"metric_crs {metric_crs} is not projected")
    to_ll = Transformer.from_crs(m.crs, "EPSG:4326", always_xy=True)
    contrib_cols = [c for c in m.columns if c.startswith("contrib_")]
    rows = []
    for _, group in m.sort_values(["line_id", "seq"], kind="mergesort").groupby(
            "line_id", sort=True):
        for run in _runs(group):
            seg = group.loc[run]
            first, last = seg.iloc[0], seg.iloc[-1]
            geom = _merge_geometry(list(seg.geometry))
            lengths = seg["length_m"].to_numpy(dtype="float64")
            keys = _reasons(seg, contrib_cols, lengths, labels)
            lab = [labels.get(k, {"tr": k, "en": k}) for k in keys]
            (x0, y0), (x1, y1) = geom.coords[0], geom.coords[-1]
            mid = geom.interpolate(0.5, normalized=True)
            lon0, lat0 = to_ll.transform(x0, y0)
            lon1, lat1 = to_ll.transform(x1, y1)
            mlon, mlat = to_ll.transform(mid.x, mid.y)
            tall = seg["aux_strike_tall_clusters"] if "aux_strike_tall_clusters" in seg else None
            rows.append({
                "span_id": f"{first['line_id']}_{int(first['seq']):04d}-{int(last['seq']):04d}",
                "line_id": str(first["line_id"]),
                "voltage_class": first.get("voltage_class"),
                "length_m": round(float(lengths.sum()), 1),
                "risk_max": round(float(seg["risk"].max()), 2),
                "risk_mean": round(float(np.average(seg["risk"], weights=lengths)), 2),
                "main_reason_tr": lab[0]["tr"] if lab else "",
                "strike_tree_count": int(np.nansum(seg[strike])),
                "start_lat": round(lat0, COORD_DECIMALS),
                "start_lon": round(lon0, COORD_DECIMALS),
                "end_lat": round(lat1, COORD_DECIMALS),
                "end_lon": round(lon1, COORD_DECIMALS),
                "map_url": MAP_URL.format(lat=mlat, lon=mlon),
                "priority": 0,
                "tier_max": "kritik" if (seg["tier"] == "kritik").any() else "yuksek",
                "n_segments": len(seg),
                "segment_ids": ";".join(seg["segment_id"].astype(str)),
                "voltage_level": first.get("voltage_level"),
                "voltage_kv": first.get("voltage_kv"),
                "main_reason_key": keys[0] if keys else "",
                "main_reason_en": lab[0]["en"] if lab else "",
                "reasons_tr": "; ".join(x["tr"] for x in lab[:REASONS_IN_TEXT]),
                "reasons_en": "; ".join(x["en"] for x in lab[:REASONS_IN_TEXT]),
                "strike_tall_count": int(np.nansum(tall)) if tall is not None else None,
                "as_of": first.get("as_of"),
                "geometry": geom,
            })
    if not rows:
        return gpd.GeoDataFrame(columns=[*WORKORDER_COLUMNS, "geometry"], geometry="geometry",
                                crs="EPSG:4326")
    wo = gpd.GeoDataFrame(rows, geometry="geometry", crs=m.crs)
    wo = wo.sort_values(["risk_max", "strike_tree_count", "span_id"],
                        ascending=[False, False, True], kind="mergesort").reset_index(drop=True)
    wo["priority"] = np.arange(1, len(wo) + 1)
    return wo[[*WORKORDER_COLUMNS, "geometry"]].to_crs("EPSG:4326")
