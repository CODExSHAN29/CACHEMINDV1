import asyncio
import httpx
import pytest

from backend.app.config import settings
from backend.normalization.models import ChatMessage, NormalizedInferenceRequest
from backend.providers.base import ProviderError, ProviderErrorKind
from backend.providers.mock_provider import MockProvider
from backend.providers.registry import ProviderRegistry
from backend.resilience.circuit_breaker import CircuitBreakerRegistry
from backend.routing.engine import (
    InvalidFallbackConfigurationError,
    RoutingEngine,
    is_plain_text_compatible,
)
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


def test_build_routing_plan_rejects_unknown_fallback_model(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_FALLBACK_MODEL", "nonexistent-model-xyz")
    engine = RoutingEngine()

    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="gpt-4o",
        allow_provider_fallback=True,
    )
    with pytest.raises(InvalidFallbackConfigurationError) as exc_info:
        engine.build_routing_plan(req)
    assert "could not be resolved in catalog" in str(exc_info.value)


def test_build_routing_plan_rejects_wrong_provider_fallback_model(monkeypatch):
    # ANTHROPIC_FALLBACK_MODEL configured to an OpenAI model
    monkeypatch.setattr(settings, "ANTHROPIC_FALLBACK_MODEL", "gpt-4o-mini")
    engine = RoutingEngine()

    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="gpt-4o",
        allow_provider_fallback=True,
    )
    with pytest.raises(InvalidFallbackConfigurationError) as exc_info:
        engine.build_routing_plan(req)
    assert "resolved to provider 'openai', expected 'anthropic'" in str(exc_info.value)


def test_build_routing_plan_rejects_empty_fallback_model(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_FALLBACK_MODEL", "")
    engine = RoutingEngine()

    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="gpt-4o",
        allow_provider_fallback=True,
    )
    with pytest.raises(InvalidFallbackConfigurationError) as exc_info:
        engine.build_routing_plan(req)
    assert "No fallback model configured for 'openai' primary provider" in str(exc_info.value)


def test_build_routing_plan_capability_gating_system_instructions(monkeypatch):
    # o1 does not support system instructions
    monkeypatch.setattr(settings, "OPENAI_FALLBACK_MODEL", "o1")
    engine = RoutingEngine()

    # Case 1: Request with system prompt targeting Anthropic primary -> o1 fallback should be rejected
    req_with_system = NormalizedInferenceRequest(
        messages=[
            ChatMessage(role="system", content="Act as helper"),
            ChatMessage(role="user", content="Hello"),
        ],
        model="claude-3-5-sonnet-20241022",
        allow_provider_fallback=True,
    )
    plan = engine.build_routing_plan(req_with_system)
    assert len(plan.fallbacks) == 0

    # Case 2: Request without system prompt -> o1 fallback allowed
    req_without_system = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Hello")],
        model="claude-3-5-sonnet-20241022",
        allow_provider_fallback=True,
    )
    plan_ok = engine.build_routing_plan(req_without_system)
    assert len(plan_ok.fallbacks) == 1
    assert plan_ok.fallbacks[0].model == "o1"


@pytest.mark.asyncio
async def test_circuit_breaker_failure_accounting():
    registry = ProviderRegistry()
    cb_registry = CircuitBreakerRegistry()
    engine = RoutingEngine(provider_registry=registry, circuit_registry=cb_registry)

    # 1. Client error (401 Auth) -> Should NOT record failure
    class AuthErrorProvider(MockProvider):
        async def chat_completion(self, request):
            raise ProviderError(
                provider="openai",
                kind=ProviderErrorKind.AUTHENTICATION_ERROR,
                status_code=401,
                retryable=False,
                safe_message="Authentication failed with openai upstream.",
            )

    registry.register("openai", AuthErrorProvider(provider_name="openai"))
    breaker = cb_registry.get_breaker("openai:gpt-4o")
    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Test")],
        model="gpt-4o",
    )

    with pytest.raises(ProviderError):
        await engine.execute(req)
    assert breaker.failure_count == 0

    # 2. Server error (500 Internal / 503 Unavailable) -> SHOULD record failure
    class UnavailableProvider(MockProvider):
        async def chat_completion(self, request):
            raise ProviderError(
                provider="openai",
                kind=ProviderErrorKind.UPSTREAM_UNAVAILABLE,
                status_code=503,
                retryable=True,
                safe_message="Openai upstream service is temporarily unavailable.",
            )

    registry.register("openai", UnavailableProvider(provider_name="openai"))
    registry.register("anthropic", MockProvider(provider_name="anthropic"))
    plan = RoutingPlan(
        primary=ProviderTarget(provider="openai", model="gpt-4o"),
        fallbacks=[ProviderTarget(provider="anthropic", model="claude-3-5-sonnet-20241022")],
    )

    result = await engine.execute(req, plan=plan)
    assert result.provider_used == "anthropic"
    assert breaker.failure_count == 1
    assert len(result.errors_encountered) == 1
    assert result.errors_encountered[0] == "openai:gpt-4o - Openai upstream service is temporarily unavailable."


@pytest.mark.asyncio
async def test_raw_transport_errors_do_not_trip_circuit_or_retry():
    registry = ProviderRegistry()
    cb_registry = CircuitBreakerRegistry()
    engine = RoutingEngine(provider_registry=registry, circuit_registry=cb_registry)

    class RawTransportErrorProvider(MockProvider):
        async def chat_completion(self, request):
            raise httpx.ConnectError("Connection refused")

    registry.register("openai", RawTransportErrorProvider(provider_name="openai"))
    registry.register("anthropic", MockProvider(provider_name="anthropic"))
    breaker = cb_registry.get_breaker("openai:gpt-4o")

    plan = RoutingPlan(
        primary=ProviderTarget(provider="openai", model="gpt-4o"),
        fallbacks=[ProviderTarget(provider="anthropic", model="claude-3-5-sonnet-20241022")],
    )
    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Test")],
        model="gpt-4o",
        allow_provider_fallback=True,
    )

    with pytest.raises(httpx.ConnectError):
        await engine.execute(req, plan=plan)

    # Breaker must NOT have recorded a failure because raw unhandled errors are not normalized ProviderErrors
    assert breaker.failure_count == 0

