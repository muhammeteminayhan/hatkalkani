"""Run the HatKalkani pipeline stages.

Usage: ``uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage ingest``
       ``uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage features``
       ``uv run python scripts/run_pipeline.py --aoi izmir_menderes --stage score``
       (``--stage all`` = ingest, MANIFEST check, features, then score)
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
# Feature stage (risk-modeler): one process builds every as_of date of config periods.
FEATURE_MODULE = "hatkalkani.features.build"
FEATURE_INPUTS = [PROC + "segments.parquet", PROC + "boundary.parquet"] + [
    INTERIM + n for n in (
        "chm_corridor.tif", "s2_meta.json", "worldcover.tif", "dem_slope.tif", "dem_tpi.tif",
        "buildings.parquet", "firms.parquet", "wind_hourly.parquet")
]


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


def feature_dates(root: Path | None = None) -> list[str]:
    """as_of dates of the feature stage: periods.backtest_asof and periods.current_asof."""
    import yaml

    cfg = yaml.safe_load(((root or ROOT) / "config" / "aoi.yaml").read_text(encoding="utf-8"))
    p = cfg["periods"]
    dates = [str(p["backtest_asof"])]
    if p.get("current_asof"):
        dates.append(str(p["current_asof"]))
    return list(dict.fromkeys(dates))


def features_command(aoi: str, dates: list[str]) -> list[str]:
    return [sys.executable, "-m", FEATURE_MODULE, "--aoi", aoi, "--as-of", *dates]


def missing_feature_inputs(aoi: str, root: Path | None = None) -> list[Path]:
    base = root or ROOT
    return [base / f.format(aoi=aoi) for f in FEATURE_INPUTS
            if not (base / f.format(aoi=aoi)).exists()]


def run_features(
    aoi: str,
    runner: Callable[[list[str]], int] | None = None,
    log: Callable[[str], None] = print,
    root: Path | None = None,
) -> list[dict]:
    base = root or ROOT
    missing = missing_feature_inputs(aoi, base)
    if missing:
        shown = ", ".join(p.relative_to(base).as_posix() for p in missing)
        raise SystemExit(f"missing ingest outputs: {shown}; run --stage ingest first")
    dates = feature_dates(base)
    t0 = time.time()
    rc = (runner or _subprocess_runner)(features_command(aoi, dates))
    dt = time.time() - t0
    outs = [base / PROC.format(aoi=aoi) / f"features_{d}.parquet" for d in dates]
    log(f"[features] rc={rc} {dt:.1f}s -> "
        + ", ".join(o.relative_to(base).as_posix() for o in outs))
    if rc != 0:
        raise SystemExit(f"stage 'features' failed (rc={rc})")
    return [{"module": "features", "seconds": dt, "rc": rc, "outputs": outs}]


# Score stage (risk-modeler): scores, tiers, top factors, work orders and exports from the
# cached feature files; never rebuilds features.
SCORE_MODULE = "hatkalkani.model.run"


def score_command(aoi: str, dates: list[str]) -> list[str]:
    return [sys.executable, "-m", SCORE_MODULE, "--aoi", aoi, "--as-of", *dates]


def run_score(
    aoi: str,
    runner: Callable[[list[str]], int] | None = None,
    log: Callable[[str], None] = print,
    root: Path | None = None,
) -> list[dict]:
    base = root or ROOT
    dates = feature_dates(base)
    proc = base / PROC.format(aoi=aoi)
    missing = [proc / f"features_{d}.parquet" for d in dates
               if not (proc / f"features_{d}.parquet").exists()]
    if missing:
        shown = ", ".join(p.relative_to(base).as_posix() for p in missing)
        raise SystemExit(f"missing feature files: {shown}; run --stage features first")
    t0 = time.time()
    rc = (runner or _subprocess_runner)(score_command(aoi, dates))
    dt = time.time() - t0
    outs = [proc / f"risk_{d}.parquet" for d in dates]
    log(f"[score] rc={rc} {dt:.1f}s -> "
        + ", ".join(o.relative_to(base).as_posix() for o in outs) + " (+ geojson, workorders)")
    if rc != 0:
        raise SystemExit(f"stage 'score' failed (rc={rc})")
    return [{"module": "score", "seconds": dt, "rc": rc, "outputs": outs}]


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


def _print_table(results: list[dict], t0: float) -> None:
    print(f"{'module':<12}{'seconds':>9}")
    for r in results:
        print(f"{r['module']:<12}{r['seconds']:>9.1f}")
    print(f"{'total':<12}{time.time() - t0:>9.1f}")


def _check_manifest() -> None:
    problems = validate_manifest()
    if problems:
        print(f"MANIFEST validation FAILED ({len(problems)}):")
        for p in problems[:20]:
            print("  -", p)
        raise SystemExit(1)
    print("MANIFEST validation OK")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--stage", default="ingest",
                    choices=["ingest", "features", "score", "all"])
    ap.add_argument("--only", nargs="+", metavar="MODULE", help=f"subset of {MODULES}")
    ap.add_argument("--force", action="store_true", help="delete stage outputs and recompute")
    args = ap.parse_args(argv)
    t0 = time.time()
    if args.stage == "ingest":
        results = run_ingest(args.aoi, args.only, args.force)
        _print_table(results, t0)
        _check_manifest()
        return
    if args.stage in ("features", "score") and (args.only or args.force):
        raise SystemExit("--only/--force apply to the ingest stage only")
    results = []
    if args.stage == "all":
        results += run_ingest(args.aoi, args.only, args.force)
        _check_manifest()
    if args.stage in ("features", "all"):
        results += run_features(args.aoi)
    if args.stage in ("score", "all"):
        results += run_score(args.aoi)
    _print_table(results, t0)


if __name__ == "__main__":
    main()
