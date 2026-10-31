"""Render the static application map (hillshade, boundary, CHM p90 segments, FIRMS)."""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
import yaml  # noqa: E402
from matplotlib.colors import LightSource  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIRMS_START, FIRMS_END = "2025-06-27", "2025-06-30"
TITLE = "HatKalkanı — Menderes pilotu (ön veri)"
SUBTITLE = (
    "Hat koridorunda ağaç yüksekliği (±30 m, CHM v2) ve 27–30 Haziran 2025 "
    "FIRMS tespitleri — risk skoru değildir"
)
ATTRIBUTION = (
    "© OpenStreetMap katkıcıları; Meta & WRI CHM v2; NASA FIRMS; Copernicus DEM"
)


def hillshade(dem: np.ndarray, cell: float) -> np.ndarray:
    """Return a 0..1 hillshade array for a DEM with square cells (metres)."""
    z = np.where(np.isfinite(dem), dem, np.nanmin(dem))
    ls = LightSource(azdeg=315, altdeg=40)
    return ls.hillshade(z, vert_exag=3, dx=cell, dy=cell)


def nice_bar(width_m: float) -> float:
    for v in (1000, 2000, 5000, 10000, 20000):
        if v >= width_m / 6:
            return float(v)
    return 20000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aoi", default="izmir_menderes")
    ap.add_argument("--out", default=str(ROOT / "docs/pitch/basvuru_harita.png"))
    a = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config/aoi.yaml").read_text(encoding="utf-8"))
    crs = cfg["metric_crs"]
    proc = ROOT / "data/processed" / a.aoi
    interim = ROOT / "data/interim" / a.aoi

    boundary = gpd.read_parquet(proc / "boundary.parquet").to_crs(crs)
    seg = gpd.read_parquet(proc / "segments.parquet").to_crs(crs)
    stats = pd.read_parquet(interim / "chm_segment_stats.parquet")[["segment_id", "chm_p90"]]
    seg = seg.merge(stats, on="segment_id", how="left")
    firms = pd.read_parquet(interim / "firms.parquet")
    d = firms["acq_date"].astype(str)
    firms = firms[(d >= FIRMS_START) & (d <= FIRMS_END)]
    fg = gpd.GeoDataFrame(
        firms,
        geometry=gpd.points_from_xy(firms.longitude, firms.latitude),
        crs="EPSG:4326",
    ).to_crs(crs)

    with rasterio.open(interim / "dem.tif") as src:
        if str(src.crs) != crs:
            raise SystemExit(f"DEM CRS {src.crs} != {crs}")
        dem = src.read(1, masked=True).astype("float32").filled(np.nan)
        b = src.bounds
        cell = abs(src.transform.a)
    hs = hillshade(dem, cell)

    minx, miny, maxx, maxy = boundary.total_bounds
    pad = 0.03 * max(maxx - minx, maxy - miny)
    xlim = (max(minx - pad, b.left), min(maxx + pad, b.right))
    ylim = (max(miny - pad, b.bottom), min(maxy + pad, b.top))
    in_b = fg[fg.within(boundary.geometry.union_all().buffer(1500))]

    plt.rcParams["font.family"] = "DejaVu Sans"
    fig = plt.figure(figsize=(13, 9.2), dpi=150, facecolor="white")
    ax = fig.add_axes([0.03, 0.075, 0.72, 0.80])
    ax.imshow(hs, cmap="gray", vmin=0.1, vmax=1.0, alpha=0.9,
              extent=(b.left, b.right, b.bottom, b.top), interpolation="bilinear", zorder=0)
    boundary.boundary.plot(ax=ax, color="#333333", linewidth=1.6, linestyle="--", zorder=2)

    vmax = 20.0
    cmap = plt.get_cmap("YlOrRd")
    seg = seg.sort_values("chm_p90")
    seg.plot(ax=ax, color="white", linewidth=4.4, zorder=3)
    seg.plot(ax=ax, column="chm_p90", cmap=cmap, vmin=0, vmax=vmax, linewidth=2.6, zorder=4)

    in_b.plot(ax=ax, marker="^", markersize=26, color="#1b6ca8", edgecolor="white",
              linewidth=0.5, zorder=5)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    for s in ax.spines.values():
        s.set_color("#777777")

    # scale bar
    L = nice_bar(xlim[1] - xlim[0])
    x0 = xlim[0] + 0.04 * (xlim[1] - xlim[0])
    y0 = ylim[0] + 0.04 * (ylim[1] - ylim[0])
    ax.plot([x0, x0 + L], [y0, y0], color="black", linewidth=5, solid_capstyle="butt", zorder=6)
    bar_label = f"{L / 1000:g}".replace(".", ",") + " km"
    ax.text(x0 + L / 2, y0 + 0.012 * (ylim[1] - ylim[0]), bar_label, ha="center",
            va="bottom", fontsize=12, weight="bold", zorder=6,
            bbox=dict(facecolor="white", alpha=0.75, edgecolor="none", pad=1.5))
    # north arrow
    nx = xlim[1] - 0.05 * (xlim[1] - xlim[0])
    ny = ylim[1] - 0.14 * (ylim[1] - ylim[0])
    ax.annotate("", xy=(nx, ny + 0.09 * (ylim[1] - ylim[0])), xytext=(nx, ny),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=2.5), zorder=6)
    ax.text(nx, ny + 0.10 * (ylim[1] - ylim[0]), "K", ha="center", va="bottom",
            fontsize=16, weight="bold", zorder=6)

    # legend panel
    cax = fig.add_axes([0.77, 0.52, 0.025, 0.26])
    grad = np.linspace(1, 0, 256).reshape(-1, 1)
    cax.imshow(grad, cmap=cmap, aspect="auto", extent=(0, 1, 0, vmax))
    cax.set_xticks([])
    cax.yaxis.tick_right()
    cax.set_yticks([0, 5, 10, 15, 20])
    cax.set_yticklabels(["0", "5", "10", "15", "≥20"], fontsize=12)
    fig.text(0.77, 0.80, "Ağaç yüksekliği\n(p90, metre)", fontsize=13, weight="bold", va="bottom")
    handles = [
        Line2D([], [], marker="^", color="none", markerfacecolor="#1b6ca8",
               markeredgecolor="white", markersize=10,
               label=(f"FIRMS tespiti\n27–30 Haziran 2025\n(n = {len(in_b)})"
                      f"\nilçe + 1,5 km; 3 uydu ürünü,\nolay sayısı değildir")),
        Line2D([], [], color="#333333", linestyle="--", linewidth=1.6,
               label="Menderes ilçe sınırı"),
    ]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.765, 0.46),
               frameon=False, fontsize=12, labelspacing=1.2)
    total_km = seg["length_m"].sum() / 1000
    km_txt = f"{total_km:.1f}".replace(".", ",")
    fig.text(0.77, 0.17,
             f"{len(seg)} hat parçası (100 m)\n{km_txt} km hat\n"
             "Zemin: Copernicus DEM\ngölgelendirilmiş rölyef",
             fontsize=11.5, color="#333333", va="bottom", linespacing=1.5)

    fig.text(0.03, 0.955, TITLE, fontsize=24, weight="bold", va="center")
    fig.text(0.03, 0.915, SUBTITLE, fontsize=12.5, color="#333333", va="center")
    fig.text(0.03, 0.035,
             "ÖN VERİ: yalnızca girdi katmanları gösterilir; risk puanı hesaplanmamıştır.",
             fontsize=11.5, color="#9a1f1f", weight="bold", va="center")
    fig.text(0.03, 0.012, ATTRIBUTION, fontsize=10.5, color="#444444", va="center")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, facecolor="white")
    print(f"saved {out} segments={len(seg)} firms_total={len(fg)} firms_plotted={len(in_b)}")


if __name__ == "__main__":
    main()
