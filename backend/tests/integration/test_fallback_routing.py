import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.normalization.models import NormalizedInferenceRequest, ChatMessage
from backend.providers.factory import set_provider
from backend.providers.mock_provider import MockProvider
from backend.providers.registry import get_provider_registry
from backend.resilience.circuit_breaker import get_circuit_breaker_registry
from backend.routing.engine import RoutingEngine, get_routing_engine
from backend.routing.models import ProviderTarget, RoutingPlan


class FailingMockProvider(MockProvider):
    async def chat_completion(self, request: NormalizedInferenceRequest):
        from backend.providers.base import ProviderError, ProviderErrorKind
        raise ProviderError(
            provider=self.provider_name,
            kind=ProviderErrorKind.UPSTREAM_UNAVAILABLE,
            status_code=500,
            retryable=True,
            safe_message=f"{self.provider_name} upstream is temporarily unavailable.",
        )


@pytest.mark.asyncio
async def test_fallback_routing_on_primary_failure(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}

    registry = get_provider_registry()
    # Register failing provider as primary and working mock as fallback
    registry.register("failing_primary", FailingMockProvider(provider_name="failing_primary"))
    registry.register("working_fallback", MockProvider(provider_name="working_fallback"))

    engine = get_routing_engine()
    custom_plan = RoutingPlan(
        primary=ProviderTarget(provider="failing_primary", model="primary-model"),
        fallbacks=[ProviderTarget(provider="working_fallback", model="fallback-model")],
    )

    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Test fallback")],
        model="primary-model",
    )

    result = await engine.execute(req, plan=custom_plan)
    assert result.provider_used == "working_fallback"
    assert result.fallback_hops == 1
    assert result.model_used == "fallback-model"


@pytest.mark.asyncio
async def test_circuit_breaker_fast_fail_skips_open_provider():
    registry = get_provider_registry()
    cb_registry = get_circuit_breaker_registry()

    registry.register("broken", FailingMockProvider(provider_name="broken"))
    registry.register("healthy", MockProvider(provider_name="healthy"))

    breaker = cb_registry.get_breaker("broken:m1")
    for _ in range(3):
        await breaker.record_failure()
    assert await breaker.can_execute() is False

    engine = RoutingEngine(provider_registry=registry, circuit_registry=cb_registry)
    plan = RoutingPlan(
        primary=ProviderTarget(provider="broken", model="m1"),
        fallbacks=[ProviderTarget(provider="healthy", model="m2")],
    )

    req = NormalizedInferenceRequest(
        messages=[ChatMessage(role="user", content="Test fast-fail")],
        model="m1",
    )

    result = await engine.execute(req, plan=plan)
    assert result.provider_used == "healthy"
    assert result.fallback_hops == 1


@pytest.mark.asyncio
async def test_endpoint_diagnostic_routing_headers(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Diagnostic routing headers test"}],
        "temperature": 0.0,
    }

    # 1. Miss Request
    resp1 = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert "X-CacheMind-Provider" in resp1.headers
    assert "X-CacheMind-Model" in resp1.headers
    assert resp1.headers["X-CacheMind-Fallback-Hops"] == "0"

    # 2. Exact Hit Request
    resp2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert "X-CacheMind-Provider" in resp2.headers
    assert resp2.headers["X-CacheMind-Model"] == "gpt-4o-mini"
    assert resp2.headers["X-CacheMind-Fallback-Hops"] == "0"

