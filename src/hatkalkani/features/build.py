"""Build per-segment raw features as of a date (risk-model-spec section 2).

CLI::

    uv run python -m hatkalkani.features.build --aoi izmir_menderes --as-of 2025-05-31
    uv run python -m hatkalkani.features.build --aoi izmir_menderes --as-of backtest current

Writes ``data/processed/<aoi>/features_<as_of>.parquet`` (one row per segment, metadata
embedded under ``hatkalkani_features``) and a readable ``.meta.json`` sidecar.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from hatkalkani.features import factors as _factors  # noqa: F401  (registers FACTORS)
from hatkalkani.features.asof import AsOf, assert_before_cutoff, parse_as_of
from hatkalkani.features.context import FeatureContext
from hatkalkani.features.registry import (
    FACTORS,
    FactorResult,
    FactorSpec,
    check_against_config,
)
from hatkalkani.ingest import common

log = logging.getLogger("hatkalkani.features")

SCHEMA_VERSION = "features-0.1"
META_KEY = b"hatkalkani_features"
BASE_COLUMNS = ["segment_id", "line_id", "voltage_level", "length_m"]


class FeatureBuildError(RuntimeError):
    """A factor returned values that violate the feature contract."""


def _jsonable(obj: Any) -> Any:
    """Recursively convert numpy / pandas scalars so json.dumps works without defaults."""
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating | float):
        v = float(obj)
        return None if math.isnan(v) else v
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def validate_result(name: str, spec: FactorSpec, res: FactorResult, ids: pd.Index) -> None:
    """Enforce the contract: one finite value or a NaN with a reason per segment."""
    for label, s in (("values", res.values), ("nan_reason", res.nan_reason)):
        if not isinstance(s, pd.Series) or not s.index.equals(ids):
            raise FeatureBuildError(f"{name}: {label} must be a Series indexed by segment_id")
    vals = pd.to_numeric(res.values, errors="raise").astype("float64")
    if np.isinf(vals.to_numpy()).any():
        raise FeatureBuildError(f"{name}: infinite values")
    is_nan = vals.isna().to_numpy()
    has_reason = res.nan_reason.fillna("").astype(str).str.len().to_numpy() > 0
    if (is_nan & ~has_reason).any():
        bad = list(ids[is_nan & ~has_reason][:5])
        raise FeatureBuildError(f"{name}: NaN without a documented reason, e.g. {bad}")
    if (~is_nan & has_reason).any():
        raise FeatureBuildError(f"{name}: reason given for a finite value")
    if spec.temporal == "unavailable" and not is_nan.all():
        raise FeatureBuildError(f"{name}: declared unavailable but returned values")
    if spec.temporal == "time_filtered" and "max_time_used_utc" not in res.provenance:
        raise FeatureBuildError(f"{name}: time-filtered factor must report max_time_used_utc")
    if not res.aux.empty:
        if not res.aux.index.equals(ids):
            raise FeatureBuildError(f"{name}: aux must be indexed by segment_id")
        bad_cols = [c for c in res.aux.columns if not str(c).startswith("aux_")]
        if bad_cols:
            raise FeatureBuildError(f"{name}: aux columns need the aux_ prefix: {bad_cols}")
        for c in res.aux.columns:
            col = res.aux[c]
            if col.dtype.kind == "f" and (col.isna().to_numpy() & ~is_nan).any():
                raise FeatureBuildError(f"{name}: {c} is NaN where the factor is finite")


def build_features(
    ctx: FeatureContext,
    *,
    as_of: AsOf | date | str,
    registry: Mapping[str, FactorSpec] | None = None,
    strict_config: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, float]]:
    """Compute every registered factor. Returns (frame, metadata, seconds per factor)."""
    as_of = parse_as_of(as_of)
    reg = FACTORS if registry is None else registry
    problems = check_against_config(ctx.cfg.weights, reg)
    if strict_config and problems:
        raise FeatureBuildError("registry and risk_weights.yaml disagree: " + "; ".join(problems))
    out = ctx.segments[BASE_COLUMNS].copy().reset_index(drop=True)
    out["segment_id"] = out["segment_id"].astype(str)
    out["as_of"] = as_of.isoformat()
    reasons: dict[str, pd.Series] = {}
    aux_frames: list[pd.DataFrame] = []
    provenance: dict[str, Any] = {}
    nan_counts: dict[str, dict[str, int]] = {}
    seconds: dict[str, float] = {}
    for name, spec in reg.items():
        t0 = time.perf_counter()
        res = spec.func(ctx, as_of=as_of)
        validate_result(name, spec, res, ctx.ids)
        assert_before_cutoff(res.provenance.get("max_time_used_utc"), as_of, name)
        values = res.values.astype("float64").to_numpy()
        out[name] = values
        reasons[name] = res.nan_reason.fillna("").astype(str)
        if not res.aux.empty:
            aux_frames.append(res.aux.reset_index(drop=True))
        provenance[name] = res.provenance
        counts = reasons[name][np.isnan(values)].value_counts()
        nan_counts[name] = {str(k): int(v) for k, v in counts.items()}
        seconds[name] = time.perf_counter() - t0
    documented = [n for n, s in reg.items() if s.temporal != "unavailable"]
    rs = pd.DataFrame({n: reasons[n].to_numpy() for n in documented})
    out["nan_reasons"] = [
        ";".join(f"{n}:{r}" for n, r in zip(documented, row, strict=True) if r)
        for row in rs.itertuples(index=False, name=None)
    ]
    aux = pd.concat(aux_frames, axis=1) if aux_frames else pd.DataFrame(index=out.index)
    dup = list(aux.columns[aux.columns.duplicated()])
    if dup:
        raise FeatureBuildError(f"duplicate aux columns: {dup}")
    out = pd.concat([out, aux], axis=1)
    meta = {
        "schema_version": SCHEMA_VERSION,
        "aoi": ctx.cfg.aoi_id,
        "as_of": as_of.isoformat(),
        "cutoff_local_exclusive": as_of.cutoff_local.isoformat(),
        "cutoff_utc_exclusive": as_of.cutoff_utc.isoformat(),
        "day_boundary": (
            f"local calendar day in {as_of.tz}: only data stamped before the start of the "
            "next local day are used (ADR-009)"
        ),
        "n_segments": int(len(out)),
        "columns": {
            "base": [*BASE_COLUMNS, "as_of"],
            "factors": list(reg),
            "nan_reasons": "nan_reasons",
            "aux": [str(c) for c in aux.columns],
        },
        "factors": [s.describe() for s in reg.values()],
        "unavailable_factors": [n for n, s in reg.items() if s.temporal == "unavailable"],
        "nan_counts": nan_counts,
        "provenance": provenance,
        "inputs_sha256": {
            p.relative_to(ctx.root).as_posix(): common.sha256_file(p) for p in ctx.used_files()
        },
        "config": {
            "metric_crs": ctx.cfg.metric_crs,
            "buffers_m": ctx.cfg.buffers_m,
            "parameters": ctx.cfg.parameters,
            "periods": ctx.cfg.periods,
        },
        "registry_config_problems": problems,
    }
    return out, _jsonable(meta), seconds


def output_path(ctx: FeatureContext, as_of: AsOf, out_dir: Path | None = None) -> Path:
    return (out_dir or ctx.processed) / f"features_{as_of.isoformat()}.parquet"


def write_features(df: pd.DataFrame, meta: dict[str, Any], path: Path) -> Path:
    """Atomic parquet write with metadata, plus a pretty JSON sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(meta, ensure_ascii=False, sort_keys=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.replace_schema_metadata({**(table.schema.metadata or {}),
                                          META_KEY: payload.encode("utf-8")})
    tmp = path.with_name(path.name + ".tmp")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)
    path.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
    )
    return path


def read_features(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Features frame plus the embedded metadata."""
    table = pq.read_table(path)
    raw = (table.schema.metadata or {}).get(META_KEY)
    if raw is None:
        raise ValueError(f"{path} has no {META_KEY.decode()} metadata")
    return table.to_pandas(), json.loads(raw.decode("utf-8"))


def resolve_as_of(token: str, periods: Mapping[str, Any]) -> date:
    """'backtest' / 'current' map to config periods; anything else must be YYYY-MM-DD."""
    key = {"backtest": "backtest_asof", "current": "current_asof"}.get(token.strip().lower())
    if key is not None:
        value = periods.get(key)
        if not value:
            raise SystemExit(f"config periods.{key} is empty; pass an explicit date")
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    return date.fromisoformat(token.strip())


def peak_memory_mb() -> float | None:
    """Peak resident memory of this process (best effort, no extra dependency)."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            k32 = ctypes.WinDLL("kernel32")
            psapi = ctypes.WinDLL("psapi")
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD
            ]
            c = Counters()
            c.cb = ctypes.sizeof(Counters)
            if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return c.PeakWorkingSetSize / 2**20
            return None
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return rss / 2**20 if sys.platform == "darwin" else rss / 1024
    except Exception:  # noqa: BLE001 - diagnostics only
        return None


def summarize(df: pd.DataFrame, factor_names: list[str]) -> str:
    """One-line median / NaN summary per factor for the CLI log."""
    parts = []
    for n in factor_names:
        s = df[n]
        n_nan = int(s.isna().sum())
        if n_nan == len(s):
            parts.append(f"{n}: all-NaN")
            continue
        text = f"{n}: med={s.median():.3g}"
        parts.append(text + (f" nan={n_nan}" if n_nan else ""))
    return "; ".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--as-of", required=True, nargs="+", metavar="DATE",
                    help="YYYY-MM-DD, or 'backtest' / 'current' (config/aoi.yaml periods)")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="default: data/processed/<aoi>/")
    ap.add_argument("--root", type=Path, default=common.ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    t_all = time.perf_counter()
    ctx = FeatureContext(args.aoi, args.root)
    dates = [resolve_as_of(tok, ctx.cfg.periods) for tok in args.as_of]
    for d in dict.fromkeys(dates):
        t0 = time.perf_counter()
        df, meta, secs = build_features(ctx, as_of=d)
        path = write_features(df, meta, output_path(ctx, parse_as_of(d), args.out_dir))
        top = sorted(secs.items(), key=lambda kv: -kv[1])[:3]
        slow = ", ".join(f"{k} {v:.1f}s" for k, v in top)
        shown = path.relative_to(ctx.root).as_posix() if path.is_relative_to(ctx.root) else path
        log.info("%s rows=%d %.1fs (slowest: %s)", shown, len(df), time.perf_counter() - t0, slow)
        log.info("  %s", summarize(df, meta["columns"]["factors"]))
    peak = peak_memory_mb()
    log.info("features done in %.1fs; peak memory %s", time.perf_counter() - t_all,
             f"{peak:.0f} MB" if peak else "n/a")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
