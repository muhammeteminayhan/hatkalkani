"""Run the HatKalkani pipeline stages.

Usage: ``uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage ingest``
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROC = "data/processed/{aoi}/"
INTERIM = "data/interim/{aoi}/"
# (module, outputs relative to ROOT; "{aoi}" is substituted), in dependency order
INGEST_STAGES: list[tuple[str, list[str]]] = [
    ("boundary", [PROC + "boundary.parquet"]),
    ("lines", [PROC + "lines.parquet"]),
    ("segments", [PROC + "segments.parquet"]),
    ("sentinel2", [INTERIM + n for n in (
        "s2_ndvi_backtest.tif", "s2_ndmi_backtest.tif",
        "s2_ndvi_current.tif", "s2_ndmi_current.tif", "s2_meta.json")]),
    ("dem", [INTERIM + n for n in ("dem.tif", "dem_slope.tif", "dem_tpi.tif")]),
    ("worldcover", [INTERIM + "worldcover.tif"]),
    ("chm", [INTERIM + n for n in (
        "chm_corridor.tif", "chm_segment_stats.parquet", "chm_meta.json")]),
    ("buildings", [INTERIM + "buildings.parquet", INTERIM + "buildings_meta.json"]),
    ("firms", [INTERIM + "firms.parquet"]),
    ("weather", [INTERIM + "wind_hourly.parquet"]),
]
MODULES = [m for m, _ in INGEST_STAGES]


def stage_command(module: str, aoi: str) -> list[str]:
    return [sys.executable, "-m", f"hatkalkani.ingest.{module}", "--aoi", aoi]


def stage_outputs(module: str, aoi: str) -> list[Path]:
    return [ROOT / o.format(aoi=aoi) for o in dict(INGEST_STAGES)[module]]


def select_modules(only: list[str] | None) -> list[str]:
    """Modules to run, always in pipeline order."""
    if not only:
        return list(MODULES)
    bad = [m for m in only if m not in MODULES]
    if bad:
        raise SystemExit(f"unknown module(s): {bad}; choose from {MODULES}")
    return [m for m in MODULES if m in only]


def _subprocess_runner(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def run_ingest(
    aoi: str,
    only: list[str] | None = None,
    force: bool = False,
    runner: Callable[[list[str]], int] = _subprocess_runner,
    log: Callable[[str], None] = print,
) -> list[dict]:
    results: list[dict] = []
    for module in select_modules(only):
        outs = stage_outputs(module, aoi)
        if force:
            for o in outs:
                o.unlink(missing_ok=True)
        t0 = time.time()
        rc = runner(stage_command(module, aoi))
        dt = time.time() - t0
        results.append({"module": module, "seconds": dt, "rc": rc, "outputs": outs})
        shown = ", ".join(o.relative_to(ROOT).as_posix() for o in outs)
        log(f"[{module}] rc={rc} {dt:.1f}s -> {shown}")
        if rc != 0:
            raise SystemExit(f"stage '{module}' failed (rc={rc})")
    return results


def validate_manifest(root: Path = ROOT) -> list[str]:
    """Return a list of problems (empty list means OK)."""
    from hatkalkani.ingest import common

    path = common.manifest_path(root)
    if not path.exists():
        return [f"missing {path}"]
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except (csv.Error, UnicodeDecodeError) as exc:
        return [f"cannot parse MANIFEST: {exc}"]
    problems: list[str] = []
    seen: set[str] = set()
    for r in rows:
        key = r["yerel_yol"]
        if key in seen:
            problems.append(f"duplicate row: {key}")
        seen.add(key)
        f = root / key
        if not f.exists():
            problems.append(f"missing file: {key}")
        elif common.sha256_file(f) != r["sha256"]:
            problems.append(f"sha256 mismatch: {key}")
    return problems


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--stage", default="ingest", choices=["ingest"])
    ap.add_argument("--only", nargs="+", metavar="MODULE", help=f"subset of {MODULES}")
    ap.add_argument("--force", action="store_true", help="delete stage outputs and recompute")
    args = ap.parse_args(argv)
    t0 = time.time()
    results = run_ingest(args.aoi, args.only, args.force)
    print(f"{'module':<12}{'seconds':>9}")
    for r in results:
        print(f"{r['module']:<12}{r['seconds']:>9.1f}")
    print(f"{'total':<12}{time.time() - t0:>9.1f}")
    problems = validate_manifest()
    if problems:
        print(f"MANIFEST validation FAILED ({len(problems)}):")
        for p in problems[:20]:
            print("  -", p)
        raise SystemExit(1)
    print("MANIFEST validation OK")


if __name__ == "__main__":
    main()
