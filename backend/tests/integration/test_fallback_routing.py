import time
import uuid
from typing import Any, Dict

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.caching.fingerprint import compute_exact_request_hash
from backend.normalization.models import NormalizedInferenceRequest, ChatMessage
from backend.providers.base import ProviderError, ProviderErrorKind, ProviderResponse
from backend.providers.mock_provider import MockProvider
from backend.providers.registry import get_provider_registry
from backend.resilience.circuit_breaker import get_circuit_breaker_registry
from backend.routing.engine import RoutingEngine, get_routing_engine
from backend.routing.models import ProviderTarget, RoutingPlan


class FailingMockProvider(MockProvider):
    async def chat_completion(self, request: NormalizedInferenceRequest):
        raise ProviderError(
            provider=self.provider_name,
            kind=ProviderErrorKind.UPSTREAM_UNAVAILABLE,
            status_code=500,
            retryable=True,
            safe_message=f"{self.provider_name} upstream is temporarily unavailable.",
        )


class WorkingMockProvider(MockProvider):
    """Provider that works correctly for cache validation tests."""

    async def chat_completion(self, request: NormalizedInferenceRequest) -> ProviderResponse:
        import hashlib
        from backend.normalization.canonicalizer import canonicalize_request

        self.call_count += 1
        self.history.append(request)

        # Synthesize deterministic response based on input hash
        req_hash = hashlib.sha256(canonicalize_request(request).encode("utf-8")).hexdigest()[:12]

        reply_content = f"Test response from {request.provider} for {request.model}"

        prompt_tokens = 10
        completion_tokens = 15

        raw_response: Dict[str, Any] = {
            "id": f"test-{request.provider}-{request.model}-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": reply_content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

        return ProviderResponse(
            raw_response=raw_response,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            model=request.model,
            provider_latency_ms=1.0,
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


@pytest.mark.asyncio
async def test_unknown_model_fails_fast_with_400(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}

    payload = {
        "model": "non-existent-unregistered-model-12345",
        "messages": [{"role": "user", "content": "This should fail fast"}],
    }

    resp = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
    assert "Unknown model identifier" in data["detail"]


@pytest.mark.asyncio
async def test_fallback_routing_cache_isolation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Test that when a request for provider A fails over to provider B:
    1. Provider A exact hash is NOT populated in cache.
    2. Provider B exact hash IS populated in cache.
    3. Subsequent identical requests for provider A fail over or miss cleanly.
    4. Direct requests for provider B hit the cache (EXACT_HIT).
    """
    from backend.app.config import settings
    from backend.caching.factory import get_cache_backend
    from backend.normalization.models import NormalizedMessage

    fallback_model = "claude-3-5-sonnet-20241022"
    monkeypatch.setattr(settings, "ANTHROPIC_FALLBACK_MODEL", fallback_model)

    raw_key = tenant_a_fixtures["raw_key"]
    headers = {
        "Authorization": f"Bearer {raw_key}",
        "X-CacheMind-Allow-Fallback": "true",
    }

    registry = get_provider_registry()
    # Provider A (failing primary) - will fail
    registry.register("openai", FailingMockProvider(provider_name="openai"))
    # Provider B (working fallback) - will succeed
    registry.register("anthropic", WorkingMockProvider(provider_name="anthropic"))

    cache_backend = get_cache_backend()

    fallback_model = settings.ANTHROPIC_FALLBACK_MODEL or "claude-3-5-sonnet-20241022"

    # Request for gpt-4o (should fallback to anthropic fallback_model)
    payload_a = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Test request that will fallback"}],
        "temperature": 0.0,
    }

    resp_a = await async_client.post("/v1/chat/completions", headers=headers, json=payload_a)
    assert resp_a.status_code == 200
    assert resp_a.headers["X-CacheMind-Status"] == "MISS"
    assert resp_a.headers["X-CacheMind-Provider"] == "anthropic"
    assert resp_a.headers["X-CacheMind-Model"] == fallback_model
    assert resp_a.headers["X-CacheMind-Fallback-Hops"] == "1"

    # Compute the exact hashes for both providers
    req_primary = NormalizedInferenceRequest(
        provider="openai",
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Test request that will fallback")],
        temperature=0.0,
        stream=False,
    )
    req_fallback = NormalizedInferenceRequest(
        provider="anthropic",
        model=fallback_model,
        messages=[NormalizedMessage(role="user", content="Test request that will fallback")],
        temperature=0.0,
        stream=False,
    )

    primary_exact_hash = compute_exact_request_hash(
        tenant_id=tenant_a_fixtures["tenant_id"],
        project_id=tenant_a_fixtures["project_id"],
        provider="openai",
        model="gpt-4o",
        request=req_primary,
    )
    fallback_exact_hash = compute_exact_request_hash(
        tenant_id=tenant_a_fixtures["tenant_id"],
        project_id=tenant_a_fixtures["project_id"],
        provider="anthropic",
        model=fallback_model,
        request=req_fallback,
    )

    # Verify 1: Provider A exact hash is NOT populated in cache
    primary_cached = await cache_backend.get(tenant_a_fixtures["project_id"], primary_exact_hash)
    assert (
        primary_cached is None
    ), f"Primary provider A cache entry should not exist, but found: {primary_cached}"

    # Verify 2: Provider B exact hash IS populated in cache
    fallback_cached = await cache_backend.get(tenant_a_fixtures["project_id"], fallback_exact_hash)
    assert (
        fallback_cached is not None
    ), f"Fallback provider B cache entry should exist, but not found for hash: {fallback_exact_hash}"
    assert fallback_cached.provider == "anthropic"
    assert fallback_cached.model == fallback_model

    # Request 3: Subsequent identical request for provider A should still fail over
    resp_a_2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload_a)
    assert resp_a_2.status_code == 200
    assert resp_a_2.headers["X-CacheMind-Status"] == "MISS"  # Should be MISS again since A is still failing
    assert resp_a_2.headers["X-CacheMind-Provider"] == "anthropic"
    assert resp_a_2.headers["X-CacheMind-Model"] == fallback_model

    # Request 4: Direct request for provider B should hit cache (EXACT_HIT)
    payload_b = {
        "model": fallback_model,
        "messages": [{"role": "user", "content": "Test request that will fallback"}],
        "temperature": 0.0,
    }

    resp_b = await async_client.post("/v1/chat/completions", headers=headers, json=payload_b)
    assert resp_b.status_code == 200
    # Should hit exact cache since we just populated it under provider B
    assert resp_b.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert resp_b.headers["X-CacheMind-Provider"] == "anthropic"
    assert resp_b.headers["X-CacheMind-Model"] == fallback_model

    # Verify cache consistency: check that the cached entry matches our expectations
    final_cache_check = await cache_backend.get(tenant_a_fixtures["project_id"], fallback_exact_hash)
    assert final_cache_check is not None
    assert final_cache_check.provider == "anthropic"
    assert final_cache_check.model == fallback_model


@pytest.mark.asyncio
async def test_fallback_routing_metrics_finops_attribution(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
    monkeypatch,
):
    """
    Validates that on fallback execution, MetricsCollector receives the executed fallback
    provider and model for accurate Prometheus metrics labels and FinOps pricing calculations,
    and TelemetryService records both raw requested_model and actual_model.
    """
    from backend.app.config import settings
    from backend.metrics.collector import get_metrics_collector
    from backend.db.models import RequestLog
    from sqlalchemy import select

    fallback_model = "claude-3-5-sonnet-20241022"
    monkeypatch.setattr(settings, "ANTHROPIC_FALLBACK_MODEL", fallback_model)

    raw_key = tenant_a_fixtures["raw_key"]
    headers = {
        "Authorization": f"Bearer {raw_key}",
        "X-CacheMind-Allow-Fallback": "true",
    }

    registry = get_provider_registry()
    registry.register("openai", FailingMockProvider(provider_name="openai"))
    registry.register("anthropic", WorkingMockProvider(provider_name="anthropic"))

    metrics_collector = get_metrics_collector()
    recorded_metrics = []
    original_record_request = metrics_collector.record_request

    def spy_record_request(*args, **kwargs):
        recorded_metrics.append((args, kwargs))
        return original_record_request(*args, **kwargs)

    monkeypatch.setattr(metrics_collector, "record_request", spy_record_request)

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "FinOps fallback test"}],
        "temperature": 0.0,
    }

    resp = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp.status_code == 200
    assert resp.headers["X-CacheMind-Status"] == "MISS"
    assert resp.headers["X-CacheMind-Provider"] == "anthropic"
    assert resp.headers["X-CacheMind-Model"] == fallback_model

    # Verify MetricsCollector was called with the executed fallback target
    assert len(recorded_metrics) == 1
    call_kwargs = recorded_metrics[0][1]
    assert call_kwargs["provider"] == "anthropic"
    assert call_kwargs["model"] == fallback_model
    assert call_kwargs["cache_status"] == "MISS"

    # Verify DB RequestLog contains requested_model vs actual_model separation
    result = await db_session.execute(
        select(RequestLog).where(RequestLog.tenant_id == tenant_a_fixtures["tenant_id"]).order_by(RequestLog.created_at.desc())
    )
    log = result.scalars().first()
    assert log is not None
    assert log.requested_model == "gpt-4o"
    assert log.actual_model == fallback_model
    assert log.provider == "anthropic"
