"""Copernicus DEM GLO-30 -> dem.tif, dem_slope.tif, dem_tpi.tif (EPSG:32635, 30 m, COG).

Usage: ``uv run python -m hatkalkani.ingest.dem --aoi izmir_menderes``
"""

from __future__ import annotations

import argparse
import logging
import time

import numpy as np

from hatkalkani.ingest import common
from hatkalkani.ingest.rasters import (
    EARTH_SEARCH,
    TPI_RADIUS_M,
    grid_transform,
    interim_dir,
    make_geobox,
    slope_degrees,
    target_bounds,
    tpi,
    write_cog,
)

log = logging.getLogger(__name__)
RES = 30.0
LICENSE = "Copernicus DEM GLO-30: free use with attribution (ESA/Copernicus)"
OUTPUTS = ["dem.tif", "dem_slope.tif", "dem_tpi.tif"]


def run(aoi_id: str) -> None:
    out = interim_dir(aoi_id)
    if all(common.is_cached(out / n) for n in OUTPUTS):
        log.info("cache hit: DEM products unchanged")
        return
    import odc.stac
    from pystac_client import Client

    margin = TPI_RADIUS_M + 2 * RES  # extra ring so slope/TPI have no edge artefacts
    bounds_big, crs = target_bounds(aoi_id, RES, margin_m=np.ceil(margin / RES) * RES)
    bounds, _ = target_bounds(aoi_id, RES)
    client = Client.open(EARTH_SEARCH, timeout=60)
    bb_ll = _to_ll(bounds_big, crs)
    items = list(client.search(collections=["cop-dem-glo-30"], bbox=bb_ll).items())
    if not items:
        raise RuntimeError("no cop-dem-glo-30 tiles found")
    odc.stac.configure_rio(cloud_defaults=True, aws={"aws_unsigned": True})
    gb = make_geobox(bounds_big, crs, RES)
    ds = odc.stac.load(items, bands=["data"], geobox=gb, resampling="bilinear", dtype="float32",
                       chunks={"x": 512, "y": 512})
    dem = np.asarray(ds["data"].isel(time=0).compute(scheduler="threads").values, "float32")
    if not np.isfinite(dem).all():
        dem = np.where(np.isfinite(dem), dem, 0.0).astype("float32")  # sea / voids -> 0 m
    s = slope_degrees(dem, RES)
    t = tpi(dem, RES)
    pad = int(round((bounds[0] - bounds_big[0]) / RES))
    sl = (slice(pad, dem.shape[0] - pad), slice(pad, dem.shape[1] - pad))
    # rows: pad from north edge equals pad from south edge by symmetric construction
    tr = grid_transform(bounds, RES)
    for name, arr in zip(OUTPUTS, (dem, s, t), strict=True):
        write_cog(out / name, arr[sl], tr, crs, -9999.0, resampling="average")
        common.register(out / name, "Copernicus DEM GLO-30 (Earth Search cop-dem-glo-30)",
                        f"{EARTH_SEARCH}/collections/cop-dem-glo-30", LICENSE)


def _to_ll(bounds, crs: str) -> list[float]:
    from pyproj import Transformer

    t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    x0, y0 = t.transform(bounds[0], bounds[1])
    x1, y1 = t.transform(bounds[2], bounds[3])
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    t0 = time.time()
    run(args.aoi)
    print(f"dem done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
