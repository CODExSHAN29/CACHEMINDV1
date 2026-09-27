"""
Factory module for CacheMind guardrails.

Provides singleton instances of GuardrailArbiter and VolatilityEngine.
Enables dependency injection for testing and ensures consistent configuration.
"""

from typing import List, Optional
from .arbiter import GuardrailArbiter, GuardrailDecision
from .volatility import VolatilityEngine, VolatilityClassification, VolatilityTier

_default_arbiter: Optional[GuardrailArbiter] = None
_default_volatility_engine: Optional[VolatilityEngine] = None


def get_guardrail_arbiter() -> GuardrailArbiter:
    """Returns the singleton GuardrailArbiter instance."""
    global _default_arbiter
    if _default_arbiter is None:
        _default_arbiter = GuardrailArbiter(
            strict_numbers=True,
            strict_dates=True,
            strict_negations=True,
            strict_system_prompt=True,
        )
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


def get_guardrail_arbiter_instance() -> GuardrailArbiter:
    return get_guardrail_arbiter()


def get_volatility_engine_instance() -> VolatilityEngine:
    return get_volatility_engine()


def create_guardrail_arbiter(
    strict_numbers: bool = True,
    strict_dates: bool = True,
    strict_negations: bool = True,
    strict_system_prompt: bool = True,
) -> GuardrailArbiter:
    """Factory function to create a new GuardrailArbiter instance."""
    return GuardrailArbiter(
        strict_numbers=strict_numbers,
        strict_dates=strict_dates,
        strict_negations=strict_negations,
        strict_system_prompt=strict_system_prompt,
    )


def create_volatility_engine(
    volatile_keywords: Optional[List[str]] = None,
    semi_static_keywords: Optional[List[str]] = None,
    evergreen_keywords: Optional[List[str]] = None,
    default_tier: str = "semi-static",
) -> VolatilityEngine:
    """Factory function to create a new VolatilityEngine instance."""
    return VolatilityEngine(
        volatile_keywords=volatile_keywords,
        semi_static_keywords=semi_static_keywords,
        evergreen_keywords=evergreen_keywords,
        default_tier=VolatilityTier(default_tier),
    )


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
    "create_guardrail_arbiter",
    "create_volatility_engine",
]
