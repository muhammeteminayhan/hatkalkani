"""F3-3 / F3-4 report tables (printed as Markdown). Reads only data/processed outputs.

Run: ``uv run python notebooks/f3_34_tables.py > data/interim/logs/f3_34_tables.md``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hatkalkani.model.run import read_risk  # noqa: E402
from hatkalkani.model.scenario import compute_scenario, sensitivity_grid  # noqa: E402

AOI = "izmir_menderes"
PROC = ROOT / "data" / "processed" / AOI


def md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def scenario_tables() -> None:
    for day in ("2025-06-29", "2025-06-28"):
        g = sensitivity_grid(AOI, day, [40, 50, 60, 70, 80], root=ROOT)
        g = g[["min_tier", "gust_kmh", "n_candidates", "n_lines", "line_km", "share_km",
               "buildings", "share_buildings", "risk_covered", "seg_km", "seg_buildings",
               "seg_risk_covered"]]
        print(f"\n### Senaryo duyarlılığı {day}\n")
        print(md(g))
    o = compute_scenario(AOI, "2025-06-29", root=ROOT)
    print("\nDefault:", json.dumps({k: o[k] for k in ("inputs", "district_wide", "targeted",
                                                     "sensitivity_segment_unit", "wind")},
                                   ensure_ascii=False))


def risk_tables() -> None:
    for d in ("2025-05-31", "2026-10-30"):
        r, m = read_risk(PROC / f"risk_{d}.parquet")
        print(f"\n### risk_{d}: tiers {m['tier_counts']}")
        print("risk summary", {k: round(v, 2) for k, v in m["risk_summary"].items()})
        by = r.groupby("tier").agg(n=("segment_id", "size"), km=("length_m", "sum"),
                                   risk_min=("risk", "min"), risk_max=("risk", "max"))
        by["km"] = (by["km"] / 1000).round(2)
        print(md(by.reset_index().round(2)))
    wo = pd.read_csv(PROC / "workorders_2026-10-30.csv", encoding="utf-8-sig")
    print("\n### Güncel iş paketleri (ilk 3)\n")
    print(md(wo[["priority", "span_id", "voltage_class", "length_m", "risk_max",
                 "main_reason_tr", "strike_tree_count", "map_url"]].head(3)))
    print("\nworkorders:", len(wo), "spans,", round(wo["length_m"].sum() / 1000, 2), "km")


if __name__ == "__main__":
    scenario_tables()
    risk_tables()
