"""Shared helpers for the ingest stage: AOI config, paths, hashing, MANIFEST, Overpass."""

from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_COLUMNS = ["kaynak", "url", "yerel_yol", "bayt", "sha256", "tarih", "lisans"]
USER_AGENT = "HatKalkani/0.1 (research prototype; contact: github.com/muhammeteminayhan/hatkalkani)"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
ODBL = "ODbL 1.0; (c) OpenStreetMap contributors"


@dataclass(frozen=True)
class AoiConfig:
    """Subset of config/aoi.yaml needed by ingest."""

    aoi_id: str
    il: str
    ilce: str
    storage_crs: str
    metric_crs: str
    segment_length_m: float
    min_last_segment_m: float


def load_aoi(aoi_id: str, config_path: Path | None = None) -> AoiConfig:
    path = config_path or ROOT / "config" / "aoi.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    for cand in cfg.get("candidates", []):
        if cand["id"] == aoi_id:
            seg = cfg["segmentation"]
            return AoiConfig(
                aoi_id=aoi_id,
                il=cand["il"],
                ilce=cand["ilce"],
                storage_crs=cfg["storage_crs"],
                metric_crs=cfg["metric_crs"],
                segment_length_m=float(seg["segment_length_m"]),
                min_last_segment_m=float(seg["min_last_segment_m"]),
            )
    raise KeyError(f"AOI not found in config: {aoi_id}")


def raw_dir(aoi_id: str, root: Path = ROOT) -> Path:
    return root / "data" / "raw" / aoi_id


def processed_dir(aoi_id: str, root: Path = ROOT) -> Path:
    return root / "data" / "processed" / aoi_id


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ MANIFEST
def manifest_path(root: Path = ROOT) -> Path:
    return root / "data" / "raw" / "MANIFEST.csv"


def read_manifest(root: Path = ROOT) -> list[dict[str, str]]:
    p = manifest_path(root)
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def manifest_remove(yerel_yol: str, root: Path = ROOT) -> None:
    """Drop the row keyed by `yerel_yol` (no-op when absent)."""
    rows = read_manifest(root)
    kept = [r for r in rows if r["yerel_yol"] != yerel_yol]
    if len(kept) == len(rows):
        return
    with manifest_path(root).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        w.writerows(kept)


def manifest_upsert(row: dict[str, str], root: Path = ROOT) -> None:
    """Insert or replace the row keyed by `yerel_yol`."""
    rows = [r for r in read_manifest(root) if r["yerel_yol"] != row["yerel_yol"]]
    rows.append({k: str(row[k]) for k in MANIFEST_COLUMNS})
    p = manifest_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def is_cached(path: Path, root: Path = ROOT) -> bool:
    """True when the file exists and its sha256 equals the MANIFEST entry."""
    if not path.exists():
        return False
    rel = path.relative_to(root).as_posix()
    for r in read_manifest(root):
        if r["yerel_yol"] == rel:
            return r["sha256"] == sha256_file(path)
    return False


def register(path: Path, source: str, url: str, license_: str, root: Path = ROOT) -> dict[str, str]:
    row = {
        "kaynak": source,
        "url": url,
        "yerel_yol": path.relative_to(root).as_posix(),
        "bayt": str(path.stat().st_size),
        "sha256": sha256_file(path),
        "tarih": date.today().isoformat(),
        "lisans": license_,
    }
    manifest_upsert(row, root)
    return row


# ------------------------------------------------------------------ Overpass
def fetch_overpass(
    query: str,
    dest: Path,
    source: str,
    license_: str = ODBL,
    root: Path = ROOT,
    endpoints: list[str] | None = None,
    timeout: int = 240,
) -> Path:
    """POST an Overpass query; skip when `dest` is cached (sha256 matches MANIFEST).

    Three rounds over the endpoint list with exponential back-off between rounds.
    """
    if is_cached(dest, root):
        return dest
    eps = endpoints or OVERPASS_ENDPOINTS
    last: Exception | None = None
    for attempt in range(3):
        for url in eps:
            try:
                r = requests.post(
                    url, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=timeout
                )
                r.raise_for_status()
                data = r.json()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(data), encoding="utf-8")
                register(dest, source, f"{url}?data={' '.join(query.split())}", license_, root)
                return dest
            except (requests.RequestException, ValueError) as exc:
                last = exc
        time.sleep(5 * 2**attempt)
    raise RuntimeError(f"Overpass failed after retries: {last}")
