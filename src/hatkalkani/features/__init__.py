"""Feature layer: per-segment raw risk factors as of a date (risk-model-spec section 2).

Importing the package registers every factor in ``FACTORS``.
"""

from hatkalkani.features import factors as _factors  # noqa: F401  (registers FACTORS)
from hatkalkani.features.asof import AsOf, TemporalLeakageError, parse_as_of
from hatkalkani.features.registry import FACTORS, FactorResult, FactorSpec, factor

__all__ = [
    "FACTORS",
    "AsOf",
    "FactorResult",
    "FactorSpec",
    "TemporalLeakageError",
    "factor",
    "parse_as_of",
]
