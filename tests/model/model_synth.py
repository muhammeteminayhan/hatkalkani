"""Synthetic feature frames and model configs for tests/model (helpers, not fixtures)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from hatkalkani.model.config import ModelConfig, model_config_from_dict
from hatkalkani.model.score import FactorMeta

LABELS = {
    "enc": ("Ağaç", "Trees"),
    "dry": ("Kuru", "Dry"),
    "fuel": ("Yakıt", "Fuel"),
    "wui": ("Yerleşim", "Buildings"),
    "asset": ("Tesis", "Asset"),
}


def factor_metas(extra: dict[str, FactorMeta] | None = None) -> dict[str, FactorMeta]:
    """Four small synthetic factors (2 ignition, 2 consequence) + one unavailable factor."""
    out = {
        "enc": FactorMeta("enc", "ignition", "higher", "static", *LABELS["enc"]),
        "dry": FactorMeta("dry", "ignition", "lower", "time_filtered", *LABELS["dry"]),
        "fuel": FactorMeta("fuel", "consequence", "higher", "static", *LABELS["fuel"]),
        "wui": FactorMeta("wui", "consequence", "higher", "static", *LABELS["wui"]),
        "asset": FactorMeta("asset", "consequence", "higher", "unavailable", *LABELS["asset"]),
    }
    out.update(extra or {})
    return out


def config_dict(**over) -> dict:
    cfg = {
        "version": "test",
        "normalization": "percentile",
        "combine": "geometric",
        "ignition": {"enc": 0.6, "dry": 0.4},
        "consequence": {"fuel": 0.7, "wui": 0.3, "asset": 0.0},
        "tiers": {"kritik": 0.95, "yuksek": 0.80, "orta": 0.50},
        "labels": {k: {"tr": v[0], "en": v[1]} for k, v in LABELS.items()},
    }
    cfg.update(over)
    return cfg


def make_config(**over) -> ModelConfig:
    return model_config_from_dict(config_dict(**over))


def feature_frame(n: int = 40, seed: int = 7) -> pd.DataFrame:
    """Random raw features with a few ties; one documented NaN of each kind."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "segment_id": [f"L{i // 10}_{i % 10 + 1:04d}" for i in range(n)],
        "line_id": [f"L{i // 10}" for i in range(n)],
        "as_of": "2025-05-31",
        "enc": np.where(rng.random(n) < 0.4, 0.0, rng.random(n)),  # many ties at 0
        "dry": rng.normal(0.1, 0.1, n),
        "fuel": rng.random(n),
        "wui": rng.integers(0, 5, n).astype(float),  # few distinct values
        "asset": np.nan,
    })
    df.loc[3, "dry"] = np.nan
    df.loc[11, "dry"] = np.nan
    df["nan_reasons"] = ""
    df.loc[3, "nan_reasons"] = "dry:all_water"
    df.loc[11, "nan_reasons"] = "dry:no_valid_ndmi_pixels"
    return df
