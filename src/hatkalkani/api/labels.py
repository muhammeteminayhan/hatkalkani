"""Single factor-name mapping (Turkish / English) used by the API.

The risk stage writes the same mapping into ``risk_<as_of>.meta.json`` (``labels``); the API
prefers that copy and falls back to this table only if it is missing. Nothing else in the
API hard-codes factor names.
"""

from __future__ import annotations

from collections.abc import Mapping

FACTOR_LABELS: dict[str, dict[str, str]] = {
    "vegetation_encroachment": {"tr": "Hatta yakın yüksek ağaç", "en": "Tall vegetation near line"},
    "strike_trees": {"tr": "Hatta devrilebilecek ağaç", "en": "Potential strike trees"},
    "fuel_dryness": {"tr": "Kuru bitki örtüsü", "en": "Dry vegetation"},
    "wind_exposure": {"tr": "Rüzgâra açıklık", "en": "Wind exposure"},
    "fuel_continuity": {"tr": "Kesintisiz orman/maki", "en": "Continuous forest/shrub fuel"},
    "wui_exposure": {"tr": "Yerleşime yakınlık", "en": "Proximity to buildings"},
    "slope": {"tr": "Dik yamaç", "en": "Steep slope"},
    "fire_history": {"tr": "Geçmiş yangın yoğunluğu", "en": "Past fire density"},
    "asset_condition": {"tr": "Tesis durumu", "en": "Asset condition"},
}


def merged_labels(from_meta: Mapping[str, Mapping[str, str]] | None) -> dict[str, dict[str, str]]:
    """Fallback table overlaid with whatever the risk meta file provides."""
    out = {k: dict(v) for k, v in FACTOR_LABELS.items()}
    for key, lab in (from_meta or {}).items():
        out.setdefault(key, {}).update({k: str(v) for k, v in lab.items()})
    return out
