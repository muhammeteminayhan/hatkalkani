"""F3-1 feature summary tables (markdown) for docs/reports/F3-1-ozellikler.md.

Run: ``uv run python notebooks/f3_1_feature_summary.py --aoi izmir_menderes``
Reads only the produced feature files and ingest outputs; writes nothing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

from hatkalkani.features import FACTORS
from hatkalkani.features.build import read_features

ROOT = Path(__file__).resolve().parents[1]
STAT_COLS = ["n", "nan", "sıfır", "ort", "std", "min", "p10", "p25", "p50", "p75", "p90", "p95",
             "max", "tekil"]


def fmt(v: float) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    a = abs(v)
    if a == 0:
        return "0"
    if a >= 100:
        return f"{v:.0f}"
    if a >= 1:
        return f"{v:.2f}"
    return f"{v:.3f}"


def describe(df: pd.DataFrame, cols: list[str]) -> str:
    rows = ["| faktör | " + " | ".join(STAT_COLS) + " |", "|" + "---|" * (len(STAT_COLS) + 1)]
    for c in cols:
        s = df[c].astype(float)
        v = s.dropna()
        if v.empty:
            rows.append(f"| {c} | 0 | {len(s)} | " + " | ".join(["–"] * 12) + " |")
            continue
        q = np.percentile(v, [10, 25, 50, 75, 90, 95])
        vals = [len(v), int(s.isna().sum()), int((v == 0).sum()), v.mean(), v.std(), v.min(),
                *q, v.max(), v.nunique()]
        rows.append(f"| {c} | " + " | ".join(
            str(x) if isinstance(x, int | np.integer) else fmt(float(x)) for x in vals) + " |")
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aoi", default="izmir_menderes")
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    proc = ROOT / "data" / "processed" / args.aoi
    interim = ROOT / "data" / "interim" / args.aoi
    dates = [str(cfg["periods"]["backtest_asof"]), str(cfg["periods"]["current_asof"])]
    frames = {d: read_features(proc / f"features_{d}.parquet") for d in dates}
    names = list(FACTORS)
    avail = [n for n in names if FACTORS[n].temporal != "unavailable"]

    print("## Faktör kaydı\n")
    print("| faktör | etiket | bileşen | birim | yön | zaman | kaynak | as_of kuralı |")
    print("|---|---|---|---|---|---|---|---|")
    for n, s in FACTORS.items():
        print(f"| `{n}` | {s.label_tr} | {s.component} | {s.unit} | {s.direction} | "
              f"{s.temporal} | {s.source} | {s.as_of_rule} |")

    for d, (df, meta) in frames.items():
        print(f"\n## Dağılım — as_of {d} (n = {len(df)})\n")
        print(describe(df, names))
        aux = [c for c in df.columns if c.startswith("aux_") and df[c].dtype.kind in "fiu"]
        print(f"\n### Yardımcı sütunlar — as_of {d}\n")
        print(describe(df, aux))
        print(f"\n### NaN — as_of {d}\n")
        print("| faktör | neden | sayı | örnek segment |\n|---|---|---|---|")
        for n in names:
            for reason, cnt in meta["nan_counts"].get(n, {}).items():
                ex = df.loc[df[n].isna(), "segment_id"].head(3).tolist()
                print(f"| {n} | {reason} | {cnt} | {', '.join(ex)} |")

    (a, ma), (b, _) = frames[dates[0]], frames[dates[1]]
    print("\n## İki as_of karşılaştırması\n")
    print("| faktör | özdeş mi | değişen segment | Spearman | medyan "
          f"{dates[0]} | medyan {dates[1]} |\n|---|---|---|---|---|---|")
    for n in avail:
        x, y = a[n], b[n]
        same = bool(((x == y) | (x.isna() & y.isna())).all())
        changed = int((~np.isclose(x, y, equal_nan=True)).sum())
        rho = x.corr(y, method="spearman")
        print(f"| {n} | {'evet' if same else 'hayır'} | {changed} | {fmt(rho)} | "
              f"{fmt(x.median())} | {fmt(y.median())} |")

    print(f"\n## Faktörler arası Spearman (as_of {dates[0]})\n")
    corr = a[avail].corr(method="spearman")
    print("| | " + " | ".join(avail) + " |\n|" + "---|" * (len(avail) + 1))
    for r in avail:
        print(f"| {r} | " + " | ".join(fmt(corr.loc[r, c]) for c in avail) + " |")

    print("\n## CHM çapraz kontrolü (ingest chm_segment_stats ile)\n")
    st = pd.read_parquet(interim / "chm_segment_stats.parquet").set_index("segment_id")
    j = a.set_index("segment_id").join(st, how="left")
    enc_diff = (j["vegetation_encroachment"] - j["chm_encroach_frac"]).abs().max()
    strike_eq = int((j["strike_trees"] == j["chm_strike_clusters"]).sum())
    print(f"- vegetation_encroachment vs chm_encroach_frac: max |fark| = {enc_diff:.3g}")
    print(f"- strike_trees == chm_strike_clusters: {strike_eq}/{len(j)} segment")
    tot, tall = a["strike_trees"].sum(), a["aux_strike_tall_clusters"].sum()
    only_low = int(((a["strike_trees"] > 0) & (a["aux_strike_tall_clusters"] == 0)).sum())
    print(f"- strike kümeleri: toplam {int(tot)}, en yüksek pikseli >= min_encroach_canopy_m "
          f"olan {int(tall)} (%{100 * tall / max(tot, 1):.0f}); strike > 0 olup hiç yüksek "
          f"kümesi olmayan segment: {only_low}")
    prov = ma["provenance"]["vegetation_encroachment"]
    print(f"- CHM doğrulaması: {prov['validation']}; okunan geçerli piksel "
          f"{prov['valid_px_read']}, yükseklik p50/p90/p99/max = "
          f"{prov['height_m_p50_p90_p99_max']} m")

    segs = gpd.read_parquet(proc / "segments.parquet")
    print("\n## Gerilim sınıfına göre medyanlar (as_of backtest)\n")
    g = a.groupby("voltage_level")[avail].median()
    print("| sınıf | n | " + " | ".join(avail) + " |\n|" + "---|" * (len(avail) + 2))
    for lvl, row in g.iterrows():
        n = int((a["voltage_level"] == lvl).sum())
        print(f"| {lvl} | {n} | " + " | ".join(fmt(row[c]) for c in avail) + " |")
    print(f"\n(segments: {len(segs)}; lines: {segs['line_id'].nunique()})")

    print("\n## Rüzgâr hücreleri (as_of backtest)\n")
    cells = ma["provenance"]["wind_exposure"]["cells"]
    used = a["aux_wind_cell"].value_counts()
    print("| hücre | lat | lon | hamle p95 (m/s) | saat | segment |\n|---|---|---|---|---|---|")
    for k, v in cells.items():
        print(f"| {k} | {v['lat']} | {v['lon']} | {fmt(v['gust_p95_ms'])} | {v['hours']} | "
              f"{int(used.get(k, 0))} |")

    print("\n## Kaynak özetleri\n")
    for d, (_, meta) in frames.items():
        f = meta["provenance"]["fire_history"]
        s = meta["provenance"]["fuel_dryness"]
        w = meta["provenance"]["wind_exposure"]
        print(f"- {d}: FIRMS VIIRS pencere {f['window_start_local']}..< "
              f"{f['window_end_exclusive_utc']}, kullanılan {f['n_viirs_in_window']} tespit -> "
              f"{f['n_after_cell_day_dedupe']} hücre-gün, son {f['max_time_used_utc']}, "
              f"kesim sonrası dışlanan {f['n_viirs_excluded_at_or_after_cutoff']}, kapsam sonu "
              f"{f['ingest_coverage_end']} (boşluk {f['coverage_gap_days']} gün); S2 "
              f"{s['selected']} {s['window']} {s['n_scenes']} sahne, son sahne "
              f"{s['max_time_used_utc']}; rüzgâr {w['years_used']} Haz-Eyl, son "
              f"{w['max_time_used_utc']}")


if __name__ == "__main__":
    main()
