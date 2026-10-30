"""ESA WorldCover 10 m v200 (2021) windowed read -> worldcover.tif (EPSG:32635, COG).

Usage: ``uv run python -m hatkalkani.ingest.worldcover --aoi izmir_menderes``
"""

from __future__ import annotations

import argparse
import logging
import math
import time

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import from_bounds

from hatkalkani.ingest import common
from hatkalkani.ingest.dem import _to_ll
from hatkalkani.ingest.rasters import grid_transform, interim_dir, target_bounds, write_cog

log = logging.getLogger(__name__)
RES = 10.0
BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
LICENSE = "CC BY 4.0; (c) ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data"
OUT = "worldcover.tif"


def tile_names(bbox_ll: list[float]) -> list[str]:
    """WorldCover 3x3 degree tile names covering a lon/lat bbox."""
    names = []
    for lat0 in range(math.floor(bbox_ll[1] / 3) * 3, math.ceil(bbox_ll[3] / 3) * 3, 3):
        for lon0 in range(math.floor(bbox_ll[0] / 3) * 3, math.ceil(bbox_ll[2] / 3) * 3, 3):
            ns = f"N{lat0:02d}" if lat0 >= 0 else f"S{-lat0:02d}"
            ew = f"E{lon0:03d}" if lon0 >= 0 else f"W{-lon0:03d}"
            names.append(f"ESA_WorldCover_10m_2021_v200_{ns}{ew}_Map.tif")
    return names


def run(aoi_id: str) -> None:
    out = interim_dir(aoi_id) / OUT
    if common.is_cached(out):
        log.info("cache hit: worldcover.tif unchanged")
        return
    bounds, crs = target_bounds(aoi_id, RES)
    width = int(round((bounds[2] - bounds[0]) / RES))
    height = int(round((bounds[3] - bounds[1]) / RES))
    tr = grid_transform(bounds, RES)
    mosaic = np.zeros((height, width), dtype="uint8")
    env = {"AWS_NO_SIGN_REQUEST": "YES", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
           "GDAL_HTTP_MAX_RETRY": "3", "GDAL_HTTP_RETRY_DELAY": "2", "GDAL_HTTP_TIMEOUT": "60"}
    urls = [f"{BASE}/{n}" for n in tile_names(_to_ll(bounds, crs))]
    with rasterio.Env(**env):
        for url in urls:
            with rasterio.open(url) as src, WarpedVRT(
                src, crs=crs, transform=tr, width=width, height=height,
                resampling=Resampling.nearest, nodata=0,
            ) as vrt:
                win = from_bounds(*bounds, transform=vrt.transform)
                data = vrt.read(1, window=win, out_shape=(height, width))
                mosaic = np.where(mosaic == 0, data, mosaic)
    write_cog(out, mosaic, tr, crs, 0)
    common.register(out, "ESA WorldCover v200 2021", BASE + "/", LICENSE)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    t0 = time.time()
    run(args.aoi)
    print(f"worldcover done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
