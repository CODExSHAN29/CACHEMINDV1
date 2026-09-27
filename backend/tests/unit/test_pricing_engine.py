import pytest
from backend.analytics.pricing import PricingEngine


def test_pricing_engine_known_models():
    # gpt-4o: $2.50 / 1M prompt, $10.00 / 1M completion
    cost_spent = PricingEngine.calculate_cost("gpt-4o", input_tokens=1_000_000, output_tokens=1_000_000)
    assert pytest.approx(cost_spent, rel=1e-3) == 12.50

    cost_saved = PricingEngine.calculate_savings("gpt-4o", input_tokens=500_000, output_tokens=500_000)
    assert pytest.approx(cost_saved, rel=1e-3) == 6.25


def test_pricing_engine_mini_models():
    # gpt-4o-mini: $0.15 / 1M prompt, $0.60 / 1M completion
    cost = PricingEngine.calculate_cost("gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000)
    assert pytest.approx(cost, rel=1e-3) == 0.75


def test_pricing_engine_anthropic_models():
    # claude-3-5-sonnet: $3.00 / 1M prompt, $15.00 / 1M completion
    cost = PricingEngine.calculate_cost("claude-3-5-sonnet-20241022", input_tokens=1_000_000, output_tokens=1_000_000)
    assert pytest.approx(cost, rel=1e-3) == 18.00


def test_pricing_engine_fallback_for_unknown_model():
    # Unknown model should fall back gracefully without error
    cost = PricingEngine.calculate_cost("unknown-custom-llm-v1", input_tokens=1000, output_tokens=1000)
    assert cost > 0


def test_pricing_engine_zero_tokens():
    assert PricingEngine.calculate_cost("gpt-4o", 0, 0) == 0.0
    assert PricingEngine.calculate_savings("gpt-4o", 0, 0) == 0.0


def test_register_custom_model_pricing():
    PricingEngine.register_pricing("my-enterprise-llm", input_per_1m=1.0, output_per_1m=2.0)
    cost = PricingEngine.calculate_cost("my-enterprise-llm", 1_000_000, 1_000_000)
    assert pytest.approx(cost, rel=1e-3) == 3.0
