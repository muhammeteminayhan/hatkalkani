"""F3-2 score summary tables (markdown) for docs/reports/F3-2-skor.md.

Run: ``uv run python notebooks/f3_2_score_summary.py --aoi izmir_menderes``
Reads the produced risk / work-order files and the feature files; writes nothing.
Sensitivity variants are recomputed in memory (config is not modified).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

from hatkalkani.features.build import read_features
from hatkalkani.model.config import load_model_config
from hatkalkani.model.run import read_risk
from hatkalkani.model.score import factor_metas_from_rows, score_features

ROOT = Path(__file__).resolve().parents[1]
TIERS = ["kritik", "yuksek", "orta", "dusuk"]


def f2(v: float, nd: int = 2) -> str:
    return "–" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.{nd}f}"


def table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def tier_table(risk: gpd.GeoDataFrame) -> str:
    rows = []
    for t in TIERS:
        s = risk[risk["tier"] == t]
        rows.append([t, len(s), f"{len(s) / len(risk):.1%}", f2(s["risk"].min(), 1),
                     f2(s["risk"].max(), 1), f2(s["length_m"].sum() / 1000, 1)])
    return table(["kademe", "segment", "pay", "risk min", "risk max", "km"], rows)


def dist_table(risk: gpd.GeoDataFrame) -> str:
    rows = []
    for col in ("risk", "p_ignition", "consequence"):
        s = risk[col]
        q = s.quantile([0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 1]).tolist()
        nd = 1 if col == "risk" else 3
        rows.append([col, f2(s.mean(), nd), f2(s.std(), nd), *[f2(v, nd) for v in q]])
    return table(["alan", "ort", "std", "min", "p10", "p25", "p50", "p75", "p90", "p95", "max"],
                 rows)


def top1_table(risk: gpd.GeoDataFrame, names: list[str]) -> str:
    rows = []
    for t in TIERS:
        s = risk[risk["tier"] == t]
        firsts = [json.loads(x)[0]["key"] if json.loads(x) else "(yok)" for x in s["top_factors"]]
        vc = pd.Series(firsts).value_counts()
        rows.append([t] + [int(vc.get(n, 0)) for n in names] + [int(vc.get("(yok)", 0))])
    return table(["kademe", *names, "(yok)"], rows)


def mean_contrib_table(risk: gpd.GeoDataFrame, names: list[str]) -> str:
    rows = []
    for t in TIERS:
        s = risk[risk["tier"] == t]
        rows.append([t] + [f2(s[f"contrib_{n}"].mean(), 1) for n in names])
    return table(["kademe", *names], rows)


def examples(risk: gpd.GeoDataFrame) -> str:
    r = risk.sort_values("risk", ascending=False).reset_index(drop=True)
    picks = [r.iloc[0], r[r["tier"] == "yuksek"].iloc[len(r[r["tier"] == "yuksek"]) // 2],
             r[r["tier"] == "dusuk"].iloc[-1]]
    rows = []
    for p in picks:
        tops = "; ".join(f"{t['label_tr']} +{t['contribution']:.1f}"
                         for t in json.loads(p["top_factors"])) or "(skoru yükselten faktör yok)"
        rows.append([p["segment_id"], p["tier"], f2(p["risk"], 1), f2(p["p_ignition"], 3),
                     f2(p["consequence"], 3), tops])
    return table(["segment", "kademe", "risk", "P", "C", "top_factors (puan)"], rows)


def workorder_tables(wo: gpd.GeoDataFrame) -> str:
    lens = wo["length_m"]
    summ = table(
        ["span", "toplam km", "segment", "uzunluk p50 (m)", "uzunluk max (m)", "kritik içeren",
         "1 segmentlik"],
        [[len(wo), f2(lens.sum() / 1000, 1), int(wo["n_segments"].sum()), f2(lens.median(), 0),
          f2(lens.max(), 0), int((wo["tier_max"] == "kritik").sum()),
          int((wo["n_segments"] == 1).sum())]])
    vc = wo["main_reason_tr"].value_counts()
    reasons = table(["ana neden", "span"], [[k, int(v)] for k, v in vc.items()])
    cols = ["priority", "span_id", "voltage_class", "length_m", "risk_max", "risk_mean",
            "main_reason_tr", "strike_tree_count", "start_lat", "start_lon", "end_lat",
            "end_lon", "map_url"]
    top = table(cols, wo.head(3)[cols].values.tolist())
    return summ + "\n\n" + reasons + "\n\n" + top


def overlap(a: pd.Series, b: pd.Series, q: float) -> float:
    """|top(a) & top(b)| / |top(a)|; top = mid-rank percentile >= q (the tier rule)."""
    def top(s: pd.Series) -> set:
        return set(s.index[(s.round(9).rank(method="average") - 0.5) / len(s) >= q])

    ta, tb = top(a), top(b)
    return len(ta & tb) / max(len(ta), 1)


def sensitivity(features: pd.DataFrame, fmeta: dict, base_risk: pd.Series) -> str:
    cfg = load_model_config(ROOT)
    metas = factor_metas_from_rows(fmeta["factors"])
    rows = []
    variants: list[tuple[str, object]] = []
    for comp in ("ignition", "consequence"):
        for name, w in getattr(cfg, comp).items():
            if w <= 0:
                continue
            for k in (0.8, 1.2):
                weights = {**getattr(cfg, comp), name: w * k}
                variants.append((f"{name} ×{k}", dataclasses.replace(cfg, **{comp: weights})))
    variants.append(("combine: linear", dataclasses.replace(cfg, combine="linear")))
    for label, vcfg in variants:
        res = score_features(features, metas, vcfg).frame
        r = pd.Series(res["risk"].to_numpy(), index=base_risk.index)
        rho = base_risk.rank().corr(r.rank())
        c = res["consequence"]
        rows.append([label, f2(rho, 3), f2(overlap(base_risk, r, 0.80), 3),
                     f2(overlap(base_risk, r, 0.95), 3), f2(c.std(), 3),
                     f2(c.quantile(0.75) - c.quantile(0.25), 3)])
    return table(["varyant", "Spearman", "üst-%20 örtüşme", "üst-%5 örtüşme", "C std",
                  "C IQR"], rows)


def euler_vs_shapley(risk: gpd.GeoDataFrame, names: list[str], cfg_w: dict) -> str:
    """Share-of-score split (w*f scaled so P and C each get half) vs the Shapley values."""
    hi = risk[risk["tier"].isin(["kritik", "yuksek"])]
    p, c = hi["p_ignition"].to_numpy(), hi["consequence"].to_numpy()
    euler = np.column_stack([
        hi[f"norm_{n}"].fillna(0).to_numpy() * cfg_w.get(n, 0.0)
        * (50 * np.sqrt(c / p) if n in cfg_w["_ign"] else 50 * np.sqrt(p / c))
        for n in names])
    shap = hi[[f"contrib_{n}" for n in names]].to_numpy()
    rows = []
    methods = (("pay bölüşümü (w·f, P ve C yarı yarıya)", euler), ("Shapley (ADR-010)", shap))
    for label, m in methods:
        top = m.argmax(axis=1)
        pct = hi[[f"norm_{n}" for n in names]].to_numpy()[np.arange(len(hi)), top]
        vc = pd.Series(np.array(names)[top]).value_counts()
        rows.append([label, ", ".join(f"{k} {v}" for k, v in vc.items()),
                     f2(np.median(pct), 2), f"{(pct < 0.6).mean():.0%}"])
    return table(["yöntem", "1. neden dağılımı (kritik+yüksek, n=185)",
                  "1. nedenin yüzdelik medyanı", "1. nedeni yüzdelik < 0,6"], rows)


def asof_compare(a: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> str:
    ra, rb = a.set_index("segment_id")["risk"], b.set_index("segment_id")["risk"]
    rho = ra.rank().corr(rb.rank())
    ct = pd.crosstab(a["tier"], b["tier"]).reindex(index=TIERS, columns=TIERS, fill_value=0)
    rows = [[t, *[int(ct.loc[t, u]) for u in TIERS]] for t in TIERS]
    head = (f"Spearman(risk) = {rho:.3f}; üst-%20 örtüşme = {overlap(ra, rb, 0.80):.3f}; "
            f"üst-%5 örtüşme = {overlap(ra, rb, 0.95):.3f}\n\n")
    return head + table(["2025-05-31 \\ 2026-10-30", *TIERS], rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    args = ap.parse_args()
    proc = ROOT / "data" / "processed" / args.aoi
    cfg_aoi = yaml.safe_load((ROOT / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    dates = [str(cfg_aoi["periods"]["backtest_asof"]), str(cfg_aoi["periods"]["current_asof"])]
    cfg = load_model_config(ROOT)
    eff = cfg.effective_weights()
    names = [n for n in cfg.weighted_factors() if eff[cfg.component(n)][n] > 0]
    cfg_w = {**eff["ignition"], **eff["consequence"], "_ign": set(eff["ignition"])}
    risks = {}
    for d in dates:
        risk, meta = read_risk(proc / f"risk_{d}.parquet")
        risks[d] = risk
        wo = gpd.read_parquet(proc / f"risk_{d}.parquet")  # sanity: same file reads twice
        assert len(wo) == len(risk)
        wo = gpd.read_file(proc / f"workorders_{d}.gpkg")
        print(f"\n## as_of {d}\n")
        print(f"imputed: {meta['imputed_counts']}; reference risk {meta['reference']['risk']:.1f}"
              f"; warnings: {meta['warnings']}\n")
        print(tier_table(risk), "\n")
        print(dist_table(risk), "\n")
        print("### 1. neden (top_factors[0]) kademeye göre\n")
        print(top1_table(risk, names), "\n")
        print("### ortalama katkı (puan) kademeye göre\n")
        print(mean_contrib_table(risk, names), "\n")
        print("### top_factors örnekleri\n")
        print(examples(risk), "\n")
        print("### iş paketleri\n")
        print(workorder_tables(wo), "\n")
        print("### katkı yöntemi karşılaştırması\n")
        print(euler_vs_shapley(risk, names, cfg_w), "\n")
        features, fmeta = read_features(proc / f"features_{d}.parquet")
        print("### ±%20 ağırlık duyarlılığı (tek ağırlık, bileşen içinde yeniden normalize)\n")
        print(sensitivity(features, fmeta, risk.set_index("segment_id")["risk"]), "\n")
    print("\n## as_of karşılaştırması\n")
    print(asof_compare(risks[dates[0]], risks[dates[1]]))


if __name__ == "__main__":
    main()
