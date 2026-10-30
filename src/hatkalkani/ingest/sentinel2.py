"""Sentinel-2 L2A NDVI/NDMI median composites (Earth Search ``sentinel-2-c1-l2a``).

Usage: ``uv run python -m hatkalkani.ingest.sentinel2 --aoi izmir_menderes``
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date, timedelta

import numpy as np
import yaml

from hatkalkani.ingest import common
from hatkalkani.ingest.rasters import (
    EARTH_SEARCH,
    SCL_BAD,
    grid_transform,
    interim_dir,
    make_geobox,
    target_bounds,
    write_cog,
)

log = logging.getLogger(__name__)
COLLECTION = "sentinel-2-c1-l2a"
RES = 20.0  # B8A/B11 are native 20 m; B04/B08 are averaged from 10 m
MAX_CLOUD = 80
OFFSET, SCALE = -0.1, 0.0001  # processing baseline >= 04.00 (checked in STAC raster:bands)
LICENSE = "Copernicus Sentinel data terms (free, open); Contains modified Copernicus Sentinel data"
OUTPUTS = [
    "s2_ndvi_backtest.tif",
    "s2_ndmi_backtest.tif",
    "s2_ndvi_current.tif",
    "s2_ndmi_current.tif",
    "s2_meta.json",
]


def periods(today: date | None = None) -> dict[str, tuple[str, str]]:
    """Backtest and current windows from config/aoi.yaml.

    The current window ends at ``today`` if given, else ``periods.current_asof``
    (a fixed date keeps the cache valid across days), else today's date.
    """
    cfg = yaml.safe_load((common.ROOT / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    p = cfg["periods"]
    asof = p.get("current_asof")
    if today is None and asof:
        today = asof if isinstance(asof, date) else date.fromisoformat(str(asof))
    today = today or date.today()
    start = today - timedelta(days=int(p["current_window_days"]))
    return {
        "backtest": (p["backtest_s2_window"][0], p["backtest_s2_window"][1]),
        "current": (start.isoformat(), today.isoformat()),
    }


def search_items(bbox_ll: list[float], window: tuple[str, str]) -> list:
    from pystac_client import Client

    last: Exception | None = None
    for attempt in range(3):
        try:
            client = Client.open(EARTH_SEARCH, timeout=60)
            search = client.search(
                collections=[COLLECTION],
                bbox=bbox_ll,
                datetime=f"{window[0]}/{window[1]}",
                query={"eo:cloud_cover": {"lt": MAX_CLOUD}},
            )
            return list(search.items())
        except Exception as exc:  # noqa: BLE001 - network retry
            last = exc
            time.sleep(5 * 2**attempt)
    raise RuntimeError(f"STAC search failed: {last}")


def composite(items: list, bounds, crs: str) -> tuple[np.ndarray, np.ndarray, int]:
    """Per-scene index with cloud masking, then median over time. Returns (ndvi, ndmi, n_days)."""
    import odc.stac

    odc.stac.configure_rio(cloud_defaults=True, aws={"aws_unsigned": True})
    gb = make_geobox(bounds, crs, RES)
    ds = odc.stac.load(
        items,
        bands=["red", "nir", "nir08", "swir16", "scl"],
        geobox=gb,
        groupby="solar_day",
        chunks={"x": 512, "y": 512, "time": 1},
        resampling={"*": "average", "scl": "nearest"},
        dtype="uint16",
        nodata=0,
    )
    n_days = int(ds.sizes["time"])
    refl = {b: (ds[b].astype("float32") * SCALE + OFFSET).clip(min=0) for b in
            ("red", "nir", "nir08", "swir16")}
    good = ~ds["scl"].isin(list(SCL_BAD)) & (ds["red"] > 0)
    ndvi = ((refl["nir"] - refl["red"]) / (refl["nir"] + refl["red"])).where(good)
    ndmi = ((refl["nir08"] - refl["swir16"]) / (refl["nir08"] + refl["swir16"])).where(good)
    out_v = ndvi.median("time", skipna=True).compute(scheduler="threads", num_workers=4)
    out_m = ndmi.median("time", skipna=True).compute(scheduler="threads", num_workers=4)
    v = np.clip(np.asarray(out_v.values, dtype="float32"), -1, 1)
    m = np.clip(np.asarray(out_m.values, dtype="float32"), -1, 1)
    return v, m, n_days


def run(aoi_id: str, today: date | None = None) -> dict:
    out = interim_dir(aoi_id)
    out.mkdir(parents=True, exist_ok=True)
    wins = periods(today)
    meta_path = out / "s2_meta.json"
    if all(common.is_cached(out / n) for n in OUTPUTS):
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        if all(tuple(old["periods"][k]["window"]) == wins[k] for k in wins):
            log.info("cache hit: Sentinel-2 composites unchanged")
            return old
    bounds, crs = target_bounds(aoi_id, RES)
    from pyproj import Transformer

    t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    x0, y0 = t.transform(bounds[0], bounds[1])
    x1, y1 = t.transform(bounds[2], bounds[3])
    bbox_ll = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
    meta: dict = {
        "collection": COLLECTION,
        "crs": crs,
        "resolution_m": RES,
        "bounds": list(bounds),
        "cloud_mask": f"SCL classes {list(SCL_BAD)} masked (0 no-data, 3 cloud shadow, "
        "8/9 cloud medium/high, 10 thin cirrus); NDVI/NDMI per scene, then temporal median",
        "scene_cloud_cover_lt": MAX_CLOUD,
        "reflectance": f"DN*{SCALE}{OFFSET:+}",
        "ndvi": "(B08-B04)/(B08+B04)",
        "ndmi": "(B8A-B11)/(B8A+B11)",
        "attribution": "Contains modified Copernicus Sentinel data",
        "periods": {},
    }
    for name, win in wins.items():
        t0 = time.time()
        items = search_items(bbox_ll, win)
        if not items:
            raise RuntimeError(f"no Sentinel-2 scenes for {name} {win}")
        ndvi, ndmi, n_days = composite(items, bounds, crs)
        tr = grid_transform(bounds, RES)
        write_cog(out / f"s2_ndvi_{name}.tif", ndvi, tr, crs, float("nan"))
        write_cog(out / f"s2_ndmi_{name}.tif", ndmi, tr, crs, float("nan"))
        meta["periods"][name] = {
            "window": list(win),
            "n_scenes": len(items),
            "n_acquisition_days": n_days,
            "valid_pixel_fraction": float(np.isfinite(ndvi).mean()),
            "scenes": sorted(
                [{"id": i.id, "datetime": i.datetime.isoformat(),
                  "cloud_cover": i.properties.get("eo:cloud_cover")} for i in items],
                key=lambda s: s["datetime"],
            ),
            "seconds": round(time.time() - t0, 1),
        }
        log.info("%s: %d scenes in %.0fs", name, len(items), time.time() - t0)
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    for n in OUTPUTS:
        common.register(out / n, "sentinel-2-c1-l2a (Earth Search composite)", EARTH_SEARCH,
                        LICENSE)
    return meta


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    meta = run(args.aoi)
    for k, v in meta["periods"].items():
        print(k, v["window"], "scenes:", v["n_scenes"], "days:", v["n_acquisition_days"])


if __name__ == "__main__":
    main()

