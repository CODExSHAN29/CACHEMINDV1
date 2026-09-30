"""
Factory module for CacheMind guardrails.

Provides singleton instances of GuardrailArbiter and VolatilityEngine.
Enables dependency injection for testing and ensures consistent configuration.
"""

from typing import Optional
from .arbiter import GuardrailArbiter, GuardrailDecision
from .volatility import VolatilityEngine, VolatilityClassification, VolatilityTier

_default_arbiter: Optional[GuardrailArbiter] = None
_default_volatility_engine: Optional[VolatilityEngine] = None


def get_guardrail_arbiter() -> GuardrailArbiter:
    """Returns the singleton GuardrailArbiter instance."""
    global _default_arbiter
    if _default_arbiter is None:
        _default_arbiter = GuardrailArbiter()
    return _default_arbiter


def set_guardrail_arbiter(arbiter: Optional[GuardrailArbiter]) -> None:
    """Explicitly sets or overrides guardrail arbiter (for tests)."""
    global _default_arbiter
    _default_arbiter = arbiter


def get_volatility_engine() -> VolatilityEngine:
    """Returns the singleton VolatilityEngine instance."""
    global _default_volatility_engine
    if _default_volatility_engine is None:
        _default_volatility_engine = VolatilityEngine()
    return _default_volatility_engine


def set_volatility_engine(engine: Optional[VolatilityEngine]) -> None:
    """Explicitly sets or overrides volatility engine (for tests)."""
    global _default_volatility_engine
    _default_volatility_engine = engine


__all__ = [
    "GuardrailArbiter",
    "GuardrailDecision",
    "get_guardrail_arbiter",
    "set_guardrail_arbiter",
    "VolatilityEngine",
    "VolatilityClassification",
    "VolatilityTier",
    "get_volatility_engine",
    "set_volatility_engine",
]
