"""Registered risk factors (risk-model-spec section 2), one decorated function each.

Raw values are stored un-normalised; ``direction`` tells the F3-2 percentile step which
end is riskier. Time-stamped data only arrive through the as_of-filtered accessors of
``FeatureContext``; static factors document why they cannot be filtered.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from scipy.spatial import cKDTree

from hatkalkani.features.asof import AsOf
from hatkalkani.features.compute import (
    GUST_PERCENTILE,
    ChmMetrics,
    chm_window_metrics,
    ecdf_midrank,
    percentile_by_group,
    quartic_kde_per_km2,
    topo_multiplier,
)
from hatkalkani.features.context import FeatureContext
from hatkalkani.features.rasterops import (
    CHM_NODATA,
    check_chm_values,
    check_crs,
    pixel_distance,
    read_zone,
    validate_chm_profile,
    values_in_polygon,
    water_fraction,
)
from hatkalkani.features.registry import FactorResult, factor

# ESA WorldCover v200 legend: 10 tree cover, 20 shrubland (spec section 2), 80 water.
WC_TREE, WC_SHRUB, WC_WATER = 10, 20, 80
CHM_STATIC_RULE = (
    "Statik taban: CHM v2 görüntü tarihi bilinmiyor (ADR-008; v1 referansı 2016-07..2020-02). "
    "Zaman damgası olmadığından as_of ile filtrelenemez; iki as_of için aynı değer, "
    "sınırlama olarak raporlanır."
)


def corridor(geoms: gpd.GeoSeries, half_width_m: float) -> gpd.GeoSeries:
    """Flat-cap ±half-width corridor along each segment ("koridor", spec section 2)."""
    if geoms.crs is None or not geoms.crs.is_projected:
        raise ValueError("corridors need a projected (metric) CRS")
    return geoms.buffer(half_width_m, cap_style="flat", join_style="mitre", mitre_limit=2.0)


def round_buffer(geoms: gpd.GeoSeries, distance_m: float) -> gpd.GeoSeries:
    """Round-cap buffer around each segment ("tampon", spec section 2)."""
    if geoms.crs is None or not geoms.crs.is_projected:
        raise ValueError("buffers need a projected (metric) CRS")
    return geoms.buffer(distance_m)


def _reasons(ctx: FeatureContext, reasons: list[str]) -> pd.Series:
    return pd.Series(reasons, index=ctx.ids, dtype="object").astype(str)


# --------------------------------------------------------------- canopy (CHM)
def chm_metrics(ctx: FeatureContext) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Per-segment CHM metrics from the 1 m corridor raster (static, computed once)."""

    def compute() -> tuple[pd.DataFrame, dict[str, Any]]:
        p = ctx.cfg.parameters
        half = ctx.cfg.buffers_m["chm_corridor_half_width"]
        bands = {str(k): float(v) for k, v in p["clearance_band_m"].items()}
        strike_max = float(p["strike_max_distance_m"])
        if strike_max > half or max(bands.values()) > half:
            raise ValueError(
                "strike_max_distance_m and clearance_band_m must not exceed "
                f"chm_corridor_half_width ({half} m): the CHM raster only covers that corridor"
            )
        levels = ctx.segments["voltage_level"].astype(str).tolist()
        unknown = sorted(set(levels) - set(bands))
        if unknown:
            raise ValueError(f"voltage_level {unknown} has no clearance_band_m entry")
        kw = {
            "nodata": CHM_NODATA,
            "min_canopy_m": float(p["min_encroach_canopy_m"]),
            "strike_margin_m": float(p["strike_margin_m"]),
            "strike_max_m": strike_max,
            "min_cluster_px": int(p["strike_min_cluster_px"]),
        }
        hist = np.zeros(256, dtype=np.int64)
        rows: list[ChmMetrics] = []
        path = ctx.use("chm_corridor.tif")
        with rasterio.open(path) as src:
            profile = validate_chm_profile(src, ctx.cfg.metric_crs)
            cors = corridor(ctx.segments_m.geometry, half)
            for sid, geom, cor, level in zip(
                ctx.ids, ctx.segments_m.geometry, cors, levels, strict=True
            ):
                z = read_zone(src, cor, pad=2)
                if z is None:
                    rows.append(ChmMetrics(math.nan, math.nan, 0, 0, 0.0,
                                           "outside_chm_raster", "outside_chm_raster"))
                    continue
                vals = z.values()
                check_chm_values(vals, f"chm_corridor.tif window of {sid}")
                hist += np.bincount(vals.astype(np.int64), minlength=256)[:256]
                dist = pixel_distance(geom, z.data.shape, z.transform)
                rows.append(chm_window_metrics(
                    z.data, z.inside, dist, clearance_m=bands[level], **kw
                ))
        df = pd.DataFrame([asdict(r) for r in rows], index=ctx.ids)
        n = int(hist.sum())
        cdf = np.cumsum(hist) / max(n, 1)
        meta_path = ctx.interim / "chm_meta.json"
        chm_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        stats = {
            "file": path.name,
            "validation": profile,
            "valid_px_read": n,
            "height_m_p50_p90_p99_max": [
                int(np.searchsorted(cdf, q)) for q in (0.5, 0.9, 0.99)
            ] + [int(np.flatnonzero(hist).max()) if n else None],
            "chm_version": chm_meta.get("chm_version"),
            "image_dates": chm_meta.get("image_dates", "unknown"),
            "value_semantics_declared_by_ingest": chm_meta.get("value_semantics"),
            "clearance_band_m": bands,
            "placeholder_unverified": bool(p.get("placeholder_unverified", True)),
            "temporal_status": "undated_static_baseline",
        }
        return df, stats

    return ctx.cached("chm_metrics", compute)


@factor(
    name="vegetation_encroachment",
    component="ignition",
    unit="oran (0-1)",
    source="Meta/WRI CHM v2 (chm_corridor.tif, 1 m) + hat gerilim sınıfı (OSM)",
    as_of_rule=CHM_STATIC_RULE,
    temporal="static",
    direction="higher",
    label_tr="Hatta yakın yüksek ağaç",
    label_en="Tall vegetation near line",
    definition=(
        "Açıklık bandındaki (gerilim sınıfına göre clearance_band_m) geçerli CHM "
        "piksellerinden yüksekliği >= min_encroach_canopy_m olanların oranı"
    ),
)
def vegetation_encroachment(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
    df, stats = chm_metrics(ctx)
    return FactorResult(
        values=df["encroach"],
        nan_reason=df["encroach_reason"].where(df["encroach"].isna(), ""),
        aux=pd.DataFrame(
            {"aux_chm_band_px": df["band_px"], "aux_chm_valid_frac": df["valid_frac"]}
        ),
        provenance=stats,
    )


@factor(
    name="strike_trees",
    component="ignition",
    unit="küme sayısı",
    source="Meta/WRI CHM v2 (chm_corridor.tif, 1 m)",
    as_of_rule=CHM_STATIC_RULE,
    temporal="static",
    direction="higher",
    label_tr="Hatta devrilebilecek ağaç",
    label_en="Potential strike trees",
    definition=(
        "±strike_max_distance_m koridorunda h >= d + strike_margin_m koşulunu sağlayan, "
        "8-komşulukla bağlı ve >= strike_min_cluster_px piksellik küme sayısı "
        "(d: hatta yatay uzaklık)"
    ),
)
def strike_trees(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
    df, stats = chm_metrics(ctx)
    return FactorResult(
        values=df["strike"],
        nan_reason=df["strike_reason"].where(df["strike"].isna(), ""),
        aux=pd.DataFrame({"aux_strike_tall_clusters": df["strike_tall"].astype("int64")}),
        provenance={k: stats[k] for k in ("file", "validation", "image_dates",
                                          "temporal_status")},
    )


# ------------------------------------------------------- Sentinel-2 dryness
@factor(
    name="fuel_dryness",
    component="ignition",
    unit="NDMI (-1..1; düşük = kuru)",
    source="Sentinel-2 L2A NDMI medyan kompoziti (s2_ndmi_<dönem>.tif, 20 m); su maskesi "
    "ESA WorldCover 2021",
    as_of_rule=(
        "Penceresi as_of günü ya da öncesinde biten ve tüm sahneleri kesimden önce olan en son "
        "kompozit seçilir (s2_meta.json sahne tarihleriyle kanıtlanır); yoksa NaN"
    ),
    temporal="time_filtered",
    direction="lower",
    label_tr="Kuru bitki örtüsü",
    label_en="Dry vegetation",
    definition=(
        "±buffers_m.dryness koridorundaki su olmayan (WorldCover 80 dışı) geçerli NDMI "
        "piksellerinin medyanı; AOI içi ters yüzdelik F3-2'de alınır"
    ),
)
def fuel_dryness(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
    path, prov = ctx.s2_composite("ndmi", as_of=as_of)
    n = len(ctx.ids)
    vals = np.full(n, np.nan)
    n_px = np.zeros(n, dtype=np.int64)
    n_water = np.zeros(n, dtype=np.int64)
    if path is None:
        reasons = ["no_s2_composite_before_as_of"] * n
    else:
        reasons = [""] * n
        cors = corridor(ctx.segments_m.geometry, ctx.cfg.buffers_m["dryness"])
        with rasterio.open(path) as s2, rasterio.open(ctx.use("worldcover.tif")) as wc:
            check_crs(s2, ctx.cfg.metric_crs, path.name)
            check_crs(wc, ctx.cfg.metric_crs, "worldcover.tif")
            for i, cor in enumerate(cors):
                z = read_zone(s2, cor)
                if z is None:
                    reasons[i] = "outside_s2_raster"
                    continue
                water = water_fraction(wc, z.data.shape, z.transform, s2.crs, WC_WATER) > 0
                land = z.valid & ~water
                n_water[i] = int((z.valid & water).sum())
                if land.any():
                    vals[i] = float(np.median(z.data[land]))
                    n_px[i] = int(land.sum())
                else:
                    reasons[i] = "all_water" if z.valid.any() else "no_valid_ndmi_pixels"
    prov = {
        **prov,
        "corridor_half_width_m": ctx.cfg.buffers_m["dryness"],
        "water_mask": f"S2 pixels overlapping WorldCover class {WC_WATER} are excluded",
    }
    return FactorResult(
        values=ctx.series(vals),
        nan_reason=_reasons(ctx, reasons),
        aux=pd.DataFrame(
            {"aux_ndmi_px": n_px, "aux_ndmi_water_px_excluded": n_water}, index=ctx.ids
        ),
        provenance=prov,
    )


# ---------------------------------------------------------------- wind (P)
def segment_tpi(ctx: FeatureContext) -> tuple[np.ndarray, np.ndarray]:
    """(mean TPI of DEM cells touched by each segment, sorted TPI of AOI pixels)."""

    def compute() -> tuple[np.ndarray, np.ndarray]:
        seg = np.full(len(ctx.ids), np.nan)
        with rasterio.open(ctx.use("dem_tpi.tif")) as src:
            check_crs(src, ctx.cfg.metric_crs, "dem_tpi.tif")
            for i, g in enumerate(ctx.segments_m.geometry):
                z = read_zone(src, g, all_touched=True)
                if z is not None and z.valid.any():
                    seg[i] = float(z.values().astype("float64").mean())
            ref = np.sort(values_in_polygon(src, ctx.boundary_m()))
        if ref.size == 0:
            raise ValueError("dem_tpi.tif has no valid pixel inside the AOI boundary")
        return seg, ref

    return ctx.cached("segment_tpi", compute)


@factor(
    name="wind_exposure",
    component="ignition",
    unit="m/s (hamle p95 × topoğrafik çarpan)",
    source="Open-Meteo saatlik rüzgâr hamlesi (wind_hourly.parquet) + Copernicus DEM TPI "
    "(dem_tpi.tif)",
    as_of_rule=(
        "Yalnız periods.wind_climatology_summers yıllarının Haz-Eyl saatleri (yerel takvim) "
        "ve kesimden önceki kayıtlar; senaryo günleri ve as_of sonrası saatler dışarıda"
    ),
    temporal="time_filtered",
    direction="higher",
    label_tr="Rüzgâra açıklık",
    label_en="Wind exposure",
    definition=(
        "En yakın Open-Meteo hücresinin saatlik hamle 95. yüzdeliği × (0,5 + segment TPI'sinin "
        "AOI TPI dağılımındaki yüzdeliği), çarpan 0,5-1,5"
    ),
)
def wind_exposure(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
    clim, prov = ctx.wind_climatology(as_of=as_of)
    n = len(ctx.ids)
    tpi_seg, tpi_ref = segment_tpi(ctx)
    mult = topo_multiplier(ecdf_midrank(tpi_ref, tpi_seg))
    gust = np.full(n, np.nan)
    cell_label = np.full(n, "", dtype=object)
    if clim.empty:
        reasons = ["no_wind_climatology_before_as_of"] * n
    else:
        key = clim["lat"].map("{:.4f}".format) + "," + clim["lon"].map("{:.4f}".format)
        p95 = percentile_by_group(key, clim["wind_gust_10m_ms"], GUST_PERCENTILE)
        cells = clim.assign(key=key).groupby("key", sort=True).agg(
            lat=("lat", "first"), lon=("lon", "first"), label=("point_id", "min")
        ).join(p95)
        xy = gpd.GeoSeries(
            gpd.points_from_xy(cells["lon"], cells["lat"]), crs="EPSG:4326"
        ).to_crs(ctx.cfg.metric_crs)
        mids = ctx.midpoints_m()
        _, idx = cKDTree(np.column_stack([xy.x, xy.y])).query(
            np.column_stack([mids.x, mids.y])
        )
        gust = cells["p"].to_numpy()[idx]
        cell_label = cells["label"].astype(str).to_numpy()[idx]
        reasons = ["" if np.isfinite(t) else "no_dem_on_segment" for t in tpi_seg]
        prov = {
            **prov,
            "gust_percentile": GUST_PERCENTILE,
            "cells": {
                str(r.label): {"lat": float(r.lat), "lon": float(r.lon), "gust_p95_ms": float(r.p),
                               "hours": int(r.n)}
                for r in cells.itertuples()
            },
        }
    prov["topo_multiplier"] = "0.5 + mid-rank ECDF of segment TPI within AOI TPI pixels"
    prov["tpi_reference_pixels"] = int(tpi_ref.size)
    return FactorResult(
        values=ctx.series(gust * mult),
        nan_reason=_reasons(ctx, reasons),
        aux=pd.DataFrame(
            {
                "aux_wind_cell": pd.Series(cell_label, index=ctx.ids, dtype="object").astype(str),
                "aux_wind_gust_p95_ms": gust,
                "aux_tpi_m": tpi_seg,
                "aux_topo_multiplier": mult,
            },
            index=ctx.ids,
        ),
        provenance=prov,
    )


# ----------------------------------------------------------- consequence (C)
@factor(
    name="fuel_continuity",
    component="consequence",
    unit="oran (0-1)",
    source="ESA WorldCover 2021 v200 (worldcover.tif, 10 m)",
    as_of_rule="Statik: WorldCover 2021 haritası (as_of tarihlerinden önce); filtre gerekmez",
    temporal="static",
    direction="higher",
    label_tr="Kesintisiz orman/maki",
    label_en="Continuous forest/shrub fuel",
    definition="buffers_m.fuel yuvarlak tamponunda WorldCover ağaç (10) + çalılık (20) oranı",
)
def fuel_continuity(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
    n = len(ctx.ids)
    tree = np.full(n, np.nan)
    shrub = np.full(n, np.nan)
    cover = np.zeros(n)
    reasons = [""] * n
    bufs = round_buffer(ctx.segments_m.geometry, ctx.cfg.buffers_m["fuel"])
    with rasterio.open(ctx.use("worldcover.tif")) as wc:
        check_crs(wc, ctx.cfg.metric_crs, "worldcover.tif")
        px_area = abs(wc.res[0] * wc.res[1])
        for i, b in enumerate(bufs):
            z = read_zone(wc, b)
            if z is None or not z.valid.any():
                reasons[i] = "no_worldcover_pixels"
                continue
            v = z.values()
            tree[i] = float((v == WC_TREE).mean())
            shrub[i] = float((v == WC_SHRUB).mean())
            cover[i] = min(1.0, float(z.valid.sum()) * px_area / b.area)
    return FactorResult(
        values=ctx.series(tree + shrub),
        nan_reason=_reasons(ctx, reasons),
        aux=pd.DataFrame(
            {"aux_fuel_tree_frac": tree, "aux_fuel_shrub_frac": shrub, "aux_fuel_coverage": cover},
            index=ctx.ids,
        ),
        provenance={"file": "worldcover.tif", "buffer_m": ctx.cfg.buffers_m["fuel"],
                    "classes": [WC_TREE, WC_SHRUB], "temporal_status": "static_2021"},
    )


@factor(
    name="slope",
    component="consequence",
    unit="derece",
    source="Copernicus DEM GLO-30 eğim (dem_slope.tif, 30 m)",
    as_of_rule="Statik arazi; filtre gerekmez",
    temporal="static",
    direction="higher",
    label_tr="Dik yamaç",
    label_en="Steep slope",
    definition="±buffers_m.slope koridorundaki DEM piksellerinin ortalama eğimi",
)
def slope(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
    n = len(ctx.ids)
    vals = np.full(n, np.nan)
    n_px = np.zeros(n, dtype=np.int64)
    reasons = [""] * n
    cors = corridor(ctx.segments_m.geometry, ctx.cfg.buffers_m["slope"])
    with rasterio.open(ctx.use("dem_slope.tif")) as src:
        check_crs(src, ctx.cfg.metric_crs, "dem_slope.tif")
        for i, cor in enumerate(cors):
            z = read_zone(src, cor)
            if z is None or not z.valid.any():
                reasons[i] = "no_dem_pixels"
                continue
            vals[i] = float(z.values().astype("float64").mean())
            n_px[i] = int(z.valid.sum())
    return FactorResult(
        values=ctx.series(vals),
        nan_reason=_reasons(ctx, reasons),
        aux=pd.DataFrame({"aux_slope_px": n_px}, index=ctx.ids),
        provenance={"file": "dem_slope.tif",
                    "corridor_half_width_m": ctx.cfg.buffers_m["slope"]},
    )


@factor(
    name="wui_exposure",
    component="consequence",
    unit="log1p(bina sayısı)",
    source="Overture Maps buildings (buildings.parquet; Microsoft ML + OSM)",
    as_of_rule=(
        "Statik vekil: Overture sürümü 2026-10-21.0, geriye dönük test as_of'undan sonra; "
        "kayıt bazlı tarih yok, yapı stoğu yavaş değiştiği varsayılır (sınırlama)"
    ),
    temporal="static",
    direction="higher",
    label_tr="Yerleşime yakınlık",
    label_en="Proximity to buildings",
    definition="buffers_m.wui yuvarlak tamponunda temsil noktası kalan bina sayısının log1p'si",
)
def wui_exposure(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
    pts = ctx.building_points_m()
    bufs = round_buffer(ctx.segments_m.geometry, ctx.cfg.buffers_m["wui"])
    counts = np.zeros(len(ctx.ids), dtype=np.int64)
    if len(pts):
        tree = shapely.STRtree(shapely.points(pts))
        hit_buf, _ = tree.query(bufs.to_numpy(), predicate="intersects")
        counts = np.bincount(hit_buf, minlength=len(ctx.ids)).astype(np.int64)
    meta_path = ctx.interim / "buildings_meta.json"
    bmeta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return FactorResult(
        values=ctx.series(np.log1p(counts)),
        nan_reason=_reasons(ctx, [""] * len(ctx.ids)),
        aux=pd.DataFrame({"aux_wui_buildings": counts}, index=ctx.ids),
        provenance={
            "file": "buildings.parquet",
            "buffer_m": ctx.cfg.buffers_m["wui"],
            "n_buildings_file": int(len(pts)),
            "source": bmeta.get("source"),
            "overture_release": bmeta.get("overture_release"),
            "temporal_status": "static_release_after_backtest_as_of",
        },
    )


@factor(
    name="fire_history",
    component="consequence",
    unit="hücre-gün / km² (VIIRS, quartic çekirdek)",
    source="NASA FIRMS VIIRS S-NPP + NOAA-20 (firms.parquet)",
    as_of_rule=(
        "periods.firms_history[0] yerel gün başından as_of kesimine (yerel gün sonu, hariç) "
        "kadar olan VIIRS tespitleri; as_of sonrası hiçbir tespit girmez"
    ),
    temporal="time_filtered",
    direction="higher",
    label_tr="Geçmiş yangın yoğunluğu",
    label_en="Past fire density",
    definition=(
        "(yerel gün, 375 m hücre) başına tekilleştirilmiş VIIRS tespitlerinin, segment orta "
        "noktasında buffers_m.history_kernel bant genişlikli quartic çekirdek yoğunluğu"
    ),
)
def fire_history(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
    det, prov = ctx.firms_viirs(as_of=as_of)
    h = ctx.cfg.buffers_m["history_kernel"]
    mids = ctx.midpoints_m()
    dens, n_in = quartic_kde_per_km2(
        np.column_stack([mids.x, mids.y]), det[["x", "y"]].to_numpy(dtype=float), h
    )
    return FactorResult(
        values=ctx.series(dens),
        nan_reason=_reasons(ctx, [""] * len(ctx.ids)),
        aux=pd.DataFrame({"aux_fire_cell_days_in_kernel": n_in}, index=ctx.ids),
        provenance={**prov, "kernel": "quartic (biweight)", "bandwidth_m": h,
                    "evaluated_at": "segment midpoint"},
    )


@factor(
    name="asset_condition",
    component="consequence",
    unit="-",
    source="EDAŞ varlık verisi (direk yaşı, iletken tipi); pilotta yok",
    as_of_rule="Veri yok. Şirket verisi gelince kayıt/bakım tarihine göre as_of filtresi gerekir",
    temporal="unavailable",
    direction="higher",
    label_tr="Tesis durumu",
    label_en="Asset condition",
    definition="Direk yaşı ve iletken tipinden türetilecek; demoda ağırlık 0",
)
def asset_condition(ctx: FeatureContext, *, as_of: AsOf) -> FactorResult:
    n = len(ctx.ids)
    return FactorResult(
        values=ctx.series(np.full(n, np.nan)),
        nan_reason=_reasons(ctx, ["no_data_source"] * n),
        provenance={"status": "unavailable", "reason": "no EDAŞ asset data in the pilot"},
    )
