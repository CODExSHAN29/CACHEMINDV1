import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RequestLog
from backend.providers.factory import get_provider
from backend.semantic.factory import SemanticCacheFactory


@pytest.mark.asyncio
async def test_semantic_l2_cache_hit_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    Validates end-to-end L1 miss -> upstream response -> dual backfill ->
    subsequent semantically equivalent query hits L2 semantic cache with zero upstream calls.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    # Configure mock embedding engine similarity for the test
    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "What is the capital of France?"
    t2 = "Tell me the capital of France"
    embed_engine.register_similar(t1, t2, similarity=0.96)

    payload_1 = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": t1}],
        "temperature": 0.0,
    }

    # 1. First Request -> MISS
    resp1 = await async_client.post("/v1/chat/completions", headers=headers, json=payload_1)
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1
    content1 = resp1.json()["choices"][0]["message"]["content"]

    # 2. Exact Query -> EXACT_HIT
    resp_exact = await async_client.post("/v1/chat/completions", headers=headers, json=payload_1)
    assert resp_exact.status_code == 200
    assert resp_exact.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert provider.call_count == 1

    # 3. Semantically Similar Query -> L2_HIT
    payload_2 = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": t2}],
        "temperature": 0.0,
    }
    resp2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload_2)
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "L2_HIT"
    assert "X-CacheMind-Similarity" in resp2.headers
    sim_score = float(resp2.headers["X-CacheMind-Similarity"])
    assert sim_score >= 0.90
    assert "X-CacheMind-Lookup-Ms" in resp2.headers
    assert "X-CacheMind-Upstream-Ms" not in resp2.headers
    # Zero upstream provider calls on semantic L2 hit
    assert provider.call_count == 1

    content2 = resp2.json()["choices"][0]["message"]["content"]
    assert content2 == content1

    # 4. Check DB Request Logs
    result = await db_session.execute(
        select(RequestLog).order_by(RequestLog.created_at.asc())
    )
    logs = result.scalars().all()
    assert len(logs) == 3

    assert logs[0].cache_status == "MISS"
    assert logs[0].upstream_called is True

    assert logs[1].cache_status == "EXACT_HIT"
    assert logs[1].upstream_called is False

    assert logs[2].cache_status == "L2_HIT"
    assert logs[2].upstream_called is False


@pytest.mark.asyncio
async def test_semantic_guardrail_rejection_falls_back_to_upstream(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    If a semantically similar candidate fails safety guardrails (e.g. opposing actions),
    the gateway must reject the candidate and fall through to the upstream LLM.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "Cancel my subscription"
    t2 = "Renew my subscription"
    embed_engine.register_similar(t1, t2, similarity=0.96)

    # 1. Prime cache with "Cancel my subscription"
    resp1 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": t1}]},
    )
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # 2. Query with "Renew my subscription" -> High similarity, but Arbiter rejects opposing action
    resp2 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": t2}]},
    )
    assert resp2.status_code == 200
    # Must NOT be L2_HIT; must be MISS and call upstream
    assert resp2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_semantic_numeric_mismatch_guardrail_rejection(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Candidate with numerical differences (e.g. $50 vs $500) must be rejected by Arbiter.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "Transfer $50 to my savings account"
    t2 = "Transfer $500 to my savings account"
    embed_engine.register_similar(t1, t2, similarity=0.98)

    # 1. Cache $50 request
    resp1 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": t1}]},
    )
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # 2. Request with $500 -> rejected by numeric guardrail -> Upstream called
    resp2 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": t2}]},
    )
    assert resp2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_volatility_ttl_assigned_in_flow(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Verifies that volatile and evergreen queries pass through gateway successfully.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    # Volatile prompt
    resp_v = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "What is the stock price of TSLA?"}]},
    )
    assert resp_v.status_code == 200
    assert resp_v.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # Evergreen prompt
    resp_e = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "How to sort an array in Python tutorial"}]},
    )
    assert resp_e.status_code == 200
    assert resp_e.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_semantic_hit_model_attribution_and_preservation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
    monkeypatch,
):
    """
    Validates that on an L2 semantic cache hit:
    1. Client response body preserves the client-requested model.
    2. Response headers X-CacheMind-Provider and X-CacheMind-Model reflect norm_req.provider and norm_req.model.
    3. Telemetry records requested_model (raw client model) and actual_model (norm_req.model).
    4. MetricsCollector.record_request receives norm_req.provider and norm_req.model.
    """
    from backend.metrics.collector import get_metrics_collector

    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}

    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "Explain quantum computing simply"
    t2 = "Explain quantum physics and computing in simple terms"
    embed_engine.register_similar(t1, t2, similarity=0.95)

    metrics_collector = get_metrics_collector()
    recorded_metrics = []
    original_record_request = metrics_collector.record_request

    def spy_record_request(*args, **kwargs):
        recorded_metrics.append((args, kwargs))
        return original_record_request(*args, **kwargs)

    monkeypatch.setattr(metrics_collector, "record_request", spy_record_request)

    # 1. Seed L2 cache via MISS
    payload_1 = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": t1}],
        "temperature": 0.0,
    }
    resp1 = await async_client.post("/v1/chat/completions", headers=headers, json=payload_1)
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"

    recorded_metrics.clear()

    # 2. Query with semantically similar prompt -> L2_HIT
    payload_2 = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": t2}],
        "temperature": 0.0,
    }
    resp2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload_2)
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "L2_HIT"

    # Verify diagnostic headers use norm_req.provider and norm_req.model
    assert resp2.headers["X-CacheMind-Provider"] == "openai"
    assert resp2.headers["X-CacheMind-Model"] == "gpt-4o-mini"

    # Verify response body preserves client-requested model
    data2 = resp2.json()
    assert data2["model"] == "gpt-4o-mini"

    # Verify MetricsCollector was called with norm_req.provider and norm_req.model
    assert len(recorded_metrics) == 1
    call_kwargs = recorded_metrics[0][1]
    assert call_kwargs["provider"] == "openai"
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["cache_status"] == "L2_HIT"

    # Verify Telemetry log has requested_model and actual_model
    result = await db_session.execute(
        select(RequestLog).where(RequestLog.cache_status == "L2_HIT").order_by(RequestLog.created_at.desc())
    )
    log = result.scalars().first()
    assert log is not None
    assert log.requested_model == "gpt-4o-mini"
    assert log.actual_model == "gpt-4o-mini"
    assert log.provider == "openai"

