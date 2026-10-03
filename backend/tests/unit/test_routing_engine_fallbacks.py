import pytest

from backend.app.config import settings
from backend.normalization.models import ChatMessage, NormalizedInferenceRequest
from backend.providers.base import ProviderError, ProviderErrorKind
from backend.providers.mock_provider import MockProvider
from backend.providers.registry import ProviderRegistry
from backend.resilience.circuit_breaker import CircuitBreakerRegistry
from backend.routing.engine import RoutingEngine, is_plain_text_compatible
from backend.routing.models import ProviderTarget, RoutingPlan


def test_is_plain_text_compatible_valid():
    req = NormalizedInferenceRequest(
        messages=[
            ChatMessage(role="system", content="You are an assistant"),
            ChatMessage(role="user", content="Hello world"),
        ],
        model="gpt-4o",
    )
    assert is_plain_text_compatible(req) is True


def test_is_plain_text_compatible_invalid_tools():
    req_tools = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="gpt-4o",
        tools=[{"type": "function", "function": {"name": "get_weather"}}],
    )
    assert is_plain_text_compatible(req_tools) is False


def test_is_plain_text_compatible_invalid_tool_choice():
    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="gpt-4o",
        tool_choice="auto",
    )
    assert is_plain_text_compatible(req) is False


def test_is_plain_text_compatible_invalid_response_format():
    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="gpt-4o",
        response_format={"type": "json_object"},
    )
    assert is_plain_text_compatible(req) is False


def test_is_plain_text_compatible_invalid_multimodal():
    req = NormalizedInferenceRequest(
        messages=[
            ChatMessage(
                role="user",
                content=[
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/pic.png"}},
                ],
            )
        ],
        model="gpt-4o",
    )
    assert is_plain_text_compatible(req) is False


def test_build_routing_plan_no_fallback_by_default(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_FALLBACK_MODEL", "claude-3-5-sonnet-20241022")
    engine = RoutingEngine()

    # allow_provider_fallback is False by default
    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="gpt-4o",
        allow_provider_fallback=False,
    )
    plan = engine.build_routing_plan(req)
    assert plan.primary.provider == "openai"
    assert plan.primary.model == "gpt-4o"
    assert len(plan.fallbacks) == 0


def test_build_routing_plan_with_fallback_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_FALLBACK_MODEL", "claude-3-5-sonnet-20241022")
    monkeypatch.setattr(settings, "OPENAI_FALLBACK_MODEL", "gpt-4o-mini")
    engine = RoutingEngine()

    req_openai = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="gpt-4o",
        allow_provider_fallback=True,
    )
    plan_openai = engine.build_routing_plan(req_openai)
    assert plan_openai.primary.provider == "openai"
    assert len(plan_openai.fallbacks) == 1
    assert plan_openai.fallbacks[0].provider == "anthropic"
    assert plan_openai.fallbacks[0].model == "claude-3-5-sonnet-20241022"

    req_anthropic = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="claude-3-5-sonnet-20241022",
        allow_provider_fallback=True,
    )
    plan_anthropic = engine.build_routing_plan(req_anthropic)
    assert plan_anthropic.primary.provider == "anthropic"
    assert len(plan_anthropic.fallbacks) == 1
    assert plan_anthropic.fallbacks[0].provider == "openai"
    assert plan_anthropic.fallbacks[0].model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_routing_engine_failover_on_retryable_provider_error():
    registry = ProviderRegistry()
    cb_registry = CircuitBreakerRegistry()

    failing_provider = MockProvider(provider_name="openai", error_mode="rate_limit_429")
    fallback_provider = MockProvider(provider_name="anthropic")

    registry.register("openai", failing_provider)
    registry.register("anthropic", fallback_provider)

    engine = RoutingEngine(provider_registry=registry, circuit_registry=cb_registry)

    plan = RoutingPlan(
        primary=ProviderTarget(provider="openai", model="gpt-4o"),
        fallbacks=[ProviderTarget(provider="anthropic", model="claude-3-5-sonnet-20241022")],
    )

    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="gpt-4o",
        allow_provider_fallback=True,
    )

    result = await engine.execute(req, plan=plan)
    assert result.provider_used == "anthropic"
    assert result.model_used == "claude-3-5-sonnet-20241022"
    assert result.fallback_hops == 1
    assert len(result.errors_encountered) == 1


@pytest.mark.asyncio
async def test_provider_registry_close_all():
    registry = ProviderRegistry()
    p1 = MockProvider(provider_name="p1")
    p2 = MockProvider(provider_name="p2")
    registry.register("p1", p1)
    registry.register("p2", p2)

    await registry.close_all()
    assert registry.get("p1") is None
    assert registry.get("p2") is None
