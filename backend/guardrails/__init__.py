"""
Guardrail Arbiter Package for CacheMind Phase 2.

Prevents dangerous false-positive semantic cache hits by validating:
1. Negations (cancel != renew, delete != create)
2. Numbers ($50 != $500)
3. Dates (2020 != 2024)
4. System Prompts (must match exactly)
5. Dynamic TTL via Volatility classification
"""

from backend.guardrails.arbiter import (
    GuardrailArbiter,
    GuardrailDecision,
    get_guardrail_arbiter,
    set_guardrail_arbiter,
)
from backend.guardrails.volatility import (
    VolatilityClassification,
    VolatilityEngine,
    get_volatility_engine,
    set_volatility_engine,
)

__all__ = [
    # Arbiter
    "GuardrailArbiter",
    "GuardrailDecision",
    "get_guardrail_arbiter",
    "set_guardrail_arbiter",
    # Volatility
    "VolatilityClassification",
    "VolatilityEngine",
    "get_volatility_engine",
    "set_volatility_engine",
]
