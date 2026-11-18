"""Precompute scenario grids for the static demo (web/mock/scenario_<date>.json).

Runs the real API in-process (no server) for every scenario date x gust threshold x
min tier and stores each answer compactly: targeted segments are index lists into the
per-date segment id table; the page rebuilds features from mock/segments_<as_of>.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from hatkalkani.api import create_app

OUT = Path(__file__).resolve().parents[1] / "web" / "mock"
GUST_MIN, GUST_MAX, GUST_STEP = 30, 90, 5
MIN_TIERS = ["kritik", "yuksek", "orta"]


def main() -> None:
    client = TestClient(create_app())
    dates = client.get("/api/scenario/dates").json()
    steps = list(range(GUST_MIN, GUST_MAX + 1, GUST_STEP))
    index = {
        "_mock": True,
        "gust_min": GUST_MIN,
        "gust_max": GUST_MAX,
        "gust_step": GUST_STEP,
        "min_tiers": MIN_TIERS,
        "dates": {},
    }
    total = 0
    for d in dates:
        day = d["date"]
        default = client.get("/api/scenario", params={"date": day}).json()
        as_of = default["inputs"]["as_of_used"]
        seg = json.loads((OUT / f"segments_{as_of}.json").read_text(encoding="utf-8"))
        ids = [f["properties"]["segment_id"] for f in seg["features"]]
        pos = {s: i for i, s in enumerate(ids)}
        gust = [None] * len(ids)
        combos: dict[str, dict] = {}
        for g in steps:
            for tier in MIN_TIERS:
                r = client.get(
                    "/api/scenario", params={"date": day, "gust_kmh": g, "min_tier": tier}
                ).json()
                sel = []
                for f in r["segments"]["features"]:
                    i = pos[f["properties"]["segment_id"]]
                    sel.append(i)
                    gust[i] = f["properties"]["gust_kmh"]
                combos[f"{g}|{tier}"] = {
                    "inputs": r["inputs"],
                    "district_wide": r["district_wide"],
                    "targeted": r["targeted"],
                    "sensitivity_segment_unit": r.get("sensitivity_segment_unit"),
                    "idx": sorted(sel),
                }
        doc = {
            "_mock": True,
            "date": day,
            "ids": ids,
            "gust_kmh": gust,
            "wind": default["wind"],
            "note_tr": default.get("note_tr"),
            "note_en": default.get("note_en"),
            "default_inputs": default["inputs"],
            "combos": combos,
        }
        path = OUT / f"scenario_{day}.json"
        path.write_text(
            json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        total += path.stat().st_size
        index["dates"][day] = path.name
        print(day, as_of, path.stat().st_size)
    (OUT / "scenario_index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print("total bytes", total)


if __name__ == "__main__":
    main()
