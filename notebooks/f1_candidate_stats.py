# ruff: noqa: E501
"""F1-1b: tree + shrub cover (ESA WorldCover v200, 2021) per Izmir district and
along the power-line corridor of candidate districts.

Usage:
    uv run python notebooks/f1_candidate_stats.py --districts Menderes Çeşme Ödemiş

Outputs (data/interim/f1_candidates/):
    izmir_landcover.csv       all Izmir districts: area, tree %, shrub %, tree+shrub %
    candidate_corridors.csv   candidate districts: line lengths, corridor tree+shrub %,
                              intersecting CHM tiles (quadkeys) and their dates
Downloads are cached under data/interim/f1_candidates/cache/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
import yaml
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.windows import Window, from_bounds
from shapely.geometry import LineString, MultiPolygon, Polygon, box, shape
from shapely.ops import linemerge, polygonize, unary_union

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "interim" / "f1_candidates"
CACHE = OUT / "cache"
CHM_CSV = ROOT / "data" / "interim" / "f1_chm_tiles_izmir.csv"
UA = {"User-Agent": "HatKalkani/0.1 (research prototype)"}
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
WC_URL = (
    "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
)
TREE, SHRUB = 10, 20


def fold(s: str) -> str:
    """ASCII-fold a Turkish name for matching."""
    s = s.replace("İ", "I").replace("ı", "i")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


# --------------------------------------------------------------------------- network
def overpass(query: str, cache_file: Path) -> dict:
    """POST an Overpass query with retries/endpoint fallback; JSON cached on disk."""
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    last: Exception | None = None
    for attempt in range(3):
        for url in OVERPASS:
            try:
                r = requests.post(url, data={"data": query}, headers=UA, timeout=240)
                r.raise_for_status()
                data = r.json()
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(data), encoding="utf-8")
                return data
            except Exception as exc:  # noqa: BLE001
                last = exc
                print(f"  overpass {url} failed: {type(exc).__name__}")
        time.sleep(5 * 2**attempt)
    raise RuntimeError(f"Overpass failed: {last}")


# --------------------------------------------------------------------------- geometry
def relation_to_geom(rel: dict) -> Polygon | MultiPolygon | None:
    outers, inners = [], []
    for m in rel.get("members", []):
        if m.get("type") != "way" or "geometry" not in m:
            continue
        ls = LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        (inners if m.get("role") == "inner" else outers).append(ls)
    if not outers:
        return None
    shell = unary_union(list(polygonize(linemerge(outers))))
    if inners:
        shell = shell.difference(unary_union(list(polygonize(linemerge(inners)))))
    return shell if not shell.is_empty else None


def load_districts() -> gpd.GeoDataFrame:
    q = (
        '[out:json][timeout:200];area["name"="İzmir"]["admin_level"="4"]->.a;'
        'rel(area.a)["admin_level"="6"]["boundary"="administrative"];out geom;'
    )
    data = overpass(q, CACHE / "izmir_districts.json")
    rows = []
    for el in data["elements"]:
        g = relation_to_geom(el)
        if g is not None:
            rows.append({"ilce": el["tags"].get("name"), "osm_rel": el["id"], "geometry": g})
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    return gdf.sort_values("ilce").reset_index(drop=True)


def load_lines(name: str, bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    w, s, e, n = bbox
    q = (
        f"[out:json][timeout:200];way[\"power\"~\"^(line|minor_line)$\"]"
        f"({s:.5f},{w:.5f},{n:.5f},{e:.5f});out geom;"
    )
    data = overpass(q, CACHE / f"lines_{fold(name)}.json")
    rows = []
    for el in data["elements"]:
        pts = el.get("geometry")
        if el["type"] != "way" or not pts or len(pts) < 2:
            continue
        rows.append(
            {
                "osm_id": el["id"],
                "power": el["tags"]["power"],
                "voltage": el["tags"].get("voltage", ""),
                "geometry": LineString([(p["lon"], p["lat"]) for p in pts]),
            }
        )
    return gpd.GeoDataFrame(rows, columns=["osm_id", "power", "voltage", "geometry"], crs="EPSG:4326")


def voltage_class(v: str) -> str:
    """Class by the highest value in a (possibly ';'-separated) voltage tag."""
    vals = []
    for part in str(v or "").replace(",", ".").split(";"):
        try:
            vals.append(float(part.strip()))
        except ValueError:
            continue
    if not vals:
        return "etiketsiz"
    m = max(vals)
    if m >= 154000:
        return "ge154kv"
    if 33000 <= m <= 36000:
        return "kv33_36"
    return "diger"


def wc_tile_names(bbox: tuple[float, float, float, float]) -> list[str]:
    w, s, e, n = bbox
    tiles = []
    for lat0 in range(math.floor(s / 3) * 3, math.floor(n / 3) * 3 + 1, 3):
        for lon0 in range(math.floor(w / 3) * 3, math.floor(e / 3) * 3 + 1, 3):
            tiles.append(f"N{lat0:02d}E{lon0:03d}")
    return tiles


def read_window(name: str, tile: str, bbox: tuple[float, float, float, float]):
    """Windowed WorldCover read for one tile, cached as compressed npz."""
    cf = CACHE / "wc" / f"{fold(name)}_{tile}_{hashlib.sha1(repr(bbox).encode()).hexdigest()[:8]}.npz"
    if cf.exists():
        z = np.load(cf)
        return z["arr"], tuple(z["origin"])
    url = WC_URL.format(tile=tile)
    last: Exception | None = None
    for attempt in range(3):
        try:
            with rasterio.Env(
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                GDAL_HTTP_TIMEOUT="60",
                GDAL_HTTP_MAX_RETRY="3",
            ), rasterio.open(url) as ds:
                full = Window(0, 0, ds.width, ds.height)
                win = from_bounds(*bbox, transform=ds.transform).round_offsets().round_lengths()
                try:
                    win = win.intersection(full)
                except Exception:  # noqa: BLE001
                    return None, None
                if win.width <= 0 or win.height <= 0:
                    return None, None
                arr = ds.read(1, window=win)
                t = ds.window_transform(win)
                origin = (t.c, t.f, abs(t.a), abs(t.e))
            cf.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cf, arr=arr, origin=np.array(origin))
            return arr, origin
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(3 * 2**attempt)
    raise RuntimeError(f"WorldCover read failed {tile}: {last}")


def class_shares(name: str, geom, bbox) -> dict:
    """Area-weighted class shares (% of polygon area) inside geom (EPSG:4326)."""
    tree = shrub = total = 0.0
    for tile in wc_tile_names(bbox):
        arr, origin = read_window(name, tile, bbox)
        if arr is None:
            continue
        x0, y0, px, py = origin
        transform = from_origin(x0, y0, px, py)
        h, w = arr.shape
        lat = y0 - (np.arange(h) + 0.5) * py
        wgt = np.cos(np.radians(lat))
        mask = geometry_mask([geom], out_shape=(h, w), transform=transform, invert=True)
        if not mask.any():
            continue
        total += float((mask.sum(axis=1) * wgt).sum())
        tree += float((((arr == TREE) & mask).sum(axis=1) * wgt).sum())
        shrub += float((((arr == SHRUB) & mask).sum(axis=1) * wgt).sum())
    if total == 0:
        return {"tree_pct": np.nan, "shrub_pct": np.nan, "treeshrub_pct": np.nan}
    return {
        "tree_pct": 100 * tree / total,
        "shrub_pct": 100 * shrub / total,
        "treeshrub_pct": 100 * (tree + shrub) / total,
    }


def cached_json(key: str, fn):
    f = CACHE / "stats" / f"{hashlib.sha1(key.encode()).hexdigest()}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    val = fn()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(val), encoding="utf-8")
    return val


# --------------------------------------------------------------------------- CHM tiles
def quadkey_bounds(qk: str) -> tuple[float, float, float, float]:
    x = y = 0
    z = len(qk)
    for i, ch in enumerate(qk):
        bit = z - i - 1
        d = int(ch)
        if d & 1:
            x |= 1 << bit
        if d & 2:
            y |= 1 << bit
    n = 2**z

    def lat(yy: int) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))

    return (x / n * 360 - 180, lat(y + 1), (x + 1) / n * 360 - 180, lat(y))


V1_BASE = "https://dataforgood-fb-data.s3.amazonaws.com/forests/v1/alsgedi_global_v6_float"
META_BUDGET = 180e6  # bytes of per-tile metadata we may download (task limit 200 MB incl. tiles.geojson)
_meta_state = {"spent": 0.0}


def fetch_v1_metadata(tile: str) -> Path | None:
    """Download metadata/<tile>.geojson (acq_date polygons) within the byte budget."""
    f = CACHE / "chm_meta" / f"{tile}.geojson"
    if f.exists():
        return f
    url = f"{V1_BASE}/metadata/{tile}.geojson"
    try:
        size = int(requests.head(url, headers=UA, timeout=30).headers.get("Content-Length", 0))
    except Exception:  # noqa: BLE001
        return None
    already = sum(x.stat().st_size for x in (CACHE / "chm_meta").glob("*.geojson")) if (CACHE / "chm_meta").exists() else 0
    if size <= 0 or already + size > META_BUDGET:
        print(f"  skip metadata {tile} ({size / 1e6:.0f} MB, budget)")
        return None
    f.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with requests.get(url, headers=UA, timeout=120, stream=True) as r:
                r.raise_for_status()
                with open(f.with_suffix(".part"), "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            f.with_suffix(".part").replace(f)
            return f
        except Exception as exc:  # noqa: BLE001
            print(f"  metadata {tile} failed: {type(exc).__name__}")
            time.sleep(3 * 2**attempt)
    return None


def tile_dates_in(tile: str, geom) -> list[str] | None:
    """acq_date values of v1 tile polygons that intersect geom (None = no metadata)."""
    def run():
        f = fetch_v1_metadata(tile)
        if f is None:
            return None
        feats = json.loads(f.read_text(encoding="utf-8"))["features"]
        out = set()
        for ft in feats:
            g = shape(ft["geometry"])
            if g.intersects(geom):
                out.add(ft["properties"].get("acq_date", ""))
        return sorted(d for d in out if d)

    res = cached_json(f"chmdates|{tile}|{geom.wkb_hex}", run)
    if res is None:  # do not keep a budget-skip result cached
        key = hashlib.sha1(f"chmdates|{tile}|{geom.wkb_hex}".encode()).hexdigest()
        (CACHE / "stats" / f"{key}.json").unlink(missing_ok=True)
    return res


def chm_for_district(geom) -> tuple[list[str], str]:
    """Quadkeys of CHM tiles intersecting geom, and a date summary for v1 tiles.

    Dates come from the CSV when present, otherwise from v1 per-tile metadata
    (polygons clipped to the district). v2 tiles carry no acquisition date.
    """
    csv = pd.read_csv(CHM_CSV, dtype=str)
    ids, dates, undated_v1, covered_v1 = [], set(), [], []
    for _, r in csv.iterrows():
        qk = r["tile_id"]
        if not box(*quadkey_bounds(qk)).intersects(geom):
            continue
        ids.append(qk)
        if r.get("surum") != "v1":
            continue
        csv_dates = [x.split(":")[0] for x in str(r.get("acq_date") or "").split(";") if x[:2] == "20"]
        if csv_dates:  # CSV dates are tile-wide
            dates.update(csv_dates)
            covered_v1.append(qk)
            continue
        got = tile_dates_in(qk, geom)
        if got is None:
            undated_v1.append(qk)
        else:
            dates.update(got)
            covered_v1.append(qk)
    ds = sorted(dates)
    rng = f"{ds[0]}..{ds[-1]}" if ds else ""
    note = f"v1 tarihli: {len(covered_v1)}"
    if undated_v1:
        note += f"; tarihsiz v1 (butce): {'/'.join(undated_v1)}"
    note += "; v2 karolarda tarih yok"
    return ids, f"{rng} ({note})"


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--districts", nargs="+", default=["Menderes", "Çeşme", "Ödemiş"])
    args = ap.parse_args()
    t0 = time.time()
    cfg = yaml.safe_load((ROOT / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    metric = cfg["metric_crs"]
    half = float(cfg["buffers_m"]["chm_corridor_half_width"])
    OUT.mkdir(parents=True, exist_ok=True)

    gdf = load_districts()
    print(f"districts: {len(gdf)}")
    gm = gdf.to_crs(metric)

    rows = []
    for i, r in gdf.iterrows():
        g = r.geometry
        key = f"lc|{r.osm_rel}|{g.wkb_hex}"
        sh = cached_json(key, lambda g=g, n=r.ilce: class_shares(n, g, g.bounds))
        rows.append(
            {
                "ilce": r.ilce,
                "osm_rel": r.osm_rel,
                "alan_km2": round(gm.geometry.iloc[i].area / 1e6, 2),
                "agac_pct": round(sh["tree_pct"], 2),
                "cali_pct": round(sh["shrub_pct"], 2),
                "agac_cali_pct": round(sh["treeshrub_pct"], 2),
            }
        )
    lc = pd.DataFrame(rows)
    lc.to_csv(OUT / "izmir_landcover.csv", index=False, encoding="utf-8")
    print(f"izmir_landcover.csv: {len(lc)} rows ({time.time() - t0:.0f}s)")

    byname = {fold(n): n for n in gdf.ilce}
    crow = []
    for want in args.districts:
        n = byname.get(fold(want))
        if n is None:
            raise SystemExit(f"district not found: {want}")
        idx = gdf.index[gdf.ilce == n][0]
        geom, geom_m = gdf.geometry.iloc[idx], gm.geometry.iloc[idx]
        lines = load_lines(n, geom.bounds).to_crs(metric)
        lines["geometry"] = lines.geometry.intersection(geom_m)
        lines = lines[~lines.geometry.is_empty]
        lens = lines.groupby("power").geometry.apply(lambda s: s.length.sum() / 1000)

        lines["vclass"] = lines["voltage"].map(voltage_class)
        vkm = lines.groupby("vclass").geometry.apply(lambda s: s.length.sum() / 1000)

        def corridor(sub: gpd.GeoDataFrame, n=n, geom=geom, geom_m=geom_m):
            if sub.empty:
                return {"treeshrub_pct": None}
            cor = unary_union(sub.geometry.buffer(half)).intersection(geom_m)
            cor4326 = gpd.GeoSeries([cor], crs=metric).to_crs("EPSG:4326").iloc[0]
            return class_shares(n, cor4326, geom.bounds)

        base = f"cor|{n}|{half}|{geom.wkb_hex}|"
        res_all = cached_json(base + f"all|{len(lines)}|{lines.length.sum():.1f}", lambda lines=lines: corridor(lines))
        res_l = cached_json(base + f"line|{lines.power.eq('line').sum()}", lambda lines=lines: corridor(lines[lines.power == "line"]))
        res_m = cached_json(base + f"minor|{lines.power.eq('minor_line').sum()}", lambda lines=lines: corridor(lines[lines.power == "minor_line"]))
        ids, dates = chm_for_district(geom)
        crow.append(
            {
                "ilce": n,
                "line_km": round(float(lens.get("line", 0.0)), 2),
                "minor_line_km": round(float(lens.get("minor_line", 0.0)), 2),
                "toplam_km": round(float(lens.sum()), 2),
                "kv_ge154_km": round(float(vkm.get("ge154kv", 0.0)), 2),
                "kv_33_36_km": round(float(vkm.get("kv33_36", 0.0)), 2),
                "kv_diger_km": round(float(vkm.get("diger", 0.0)), 2),
                "kv_etiketsiz_km": round(float(vkm.get("etiketsiz", 0.0)), 2),
                "koridor_yari_genislik_m": half,
                "koridor_agac_cali_pct": None if res_all["treeshrub_pct"] is None else round(res_all["treeshrub_pct"], 2),
                "koridor_line_agac_cali_pct": None if res_l["treeshrub_pct"] is None else round(res_l["treeshrub_pct"], 2),
                "koridor_minor_agac_cali_pct": None if res_m["treeshrub_pct"] is None else round(res_m["treeshrub_pct"], 2),
                "ilce_agac_cali_pct": float(lc.loc[lc.ilce == n, "agac_cali_pct"].iloc[0]),
                "chm_tiles": ";".join(ids),
                "chm_dates": dates,
            }
        )
        print(f"  {n}: {crow[-1]['toplam_km']} km")
    pd.DataFrame(crow).to_csv(OUT / "candidate_corridors.csv", index=False, encoding="utf-8")
    print(f"candidate_corridors.csv: {len(crow)} rows; total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
