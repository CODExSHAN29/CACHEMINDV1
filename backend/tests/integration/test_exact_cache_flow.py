import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RequestLog
from backend.providers.factory import get_provider


@pytest.mark.asyncio
async def test_exact_cache_hit_and_zero_upstream_calls(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    assert provider.call_count == 0

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "What is the capital of France?"}],
        "temperature": 0.0,
    }

    # 1. First Request -> CACHE MISS
    resp1 = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert "X-CacheMind-Exact-Hash" in resp1.headers
    assert "X-CacheMind-Gateway-Latency-Ms" in resp1.headers
    assert "X-CacheMind-Upstream-Ms" in resp1.headers
    assert provider.call_count == 1

    exact_hash = resp1.headers["X-CacheMind-Exact-Hash"]
    body1 = resp1.json()
    assert "choices" in body1
    assert len(body1["choices"]) > 0

    # 2. Second Identical Request -> EXACT HIT
    resp2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert resp2.headers["X-CacheMind-Exact-Hash"] == exact_hash
    assert "X-CacheMind-Lookup-Ms" in resp2.headers
    assert "X-CacheMind-Upstream-Ms" not in resp2.headers  # No upstream was called!
    # CRITICAL ASSERTION: Zero upstream provider calls on exact hit
    assert provider.call_count == 1

    body2 = resp2.json()
    # Content must match exactly
    assert (
        body2["choices"][0]["message"]["content"]
        == body1["choices"][0]["message"]["content"]
    )

    # 3. Third Request with stream=True (Transport option) -> STILL EXACT HIT!
    payload_streaming = dict(payload)
    payload_streaming["stream"] = True
    resp3 = await async_client.post(
        "/v1/chat/completions", headers=headers, json=payload_streaming
    )
    assert resp3.status_code == 200
    assert resp3.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert resp3.headers["X-CacheMind-Exact-Hash"] == exact_hash
    # Provider call count remains 1!
    assert provider.call_count == 1

    # 4. Verify Telemetry Request Logs in DB
    result = await db_session.execute(
        select(RequestLog).order_by(RequestLog.created_at.asc())
    )
    logs = result.scalars().all()
    assert len(logs) == 3

    assert logs[0].cache_status == "MISS"
    assert logs[0].upstream_called is True
    assert logs[0].upstream_latency_ms is not None

    assert logs[1].cache_status == "EXACT_HIT"
    assert logs[1].upstream_called is False
    assert logs[1].upstream_latency_ms is None

    assert logs[2].cache_status == "EXACT_HIT"
    assert logs[2].upstream_called is False


@pytest.mark.asyncio
async def test_concurrent_request_coalescing_stampede_prevention(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    import asyncio
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    initial_provider_calls = provider.call_count

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "What is quantum entanglement in one sentence?"}],
        "temperature": 0.0,
    }

    # Fire 5 concurrent requests with identical payload simultaneously
    tasks = [
        async_client.post("/v1/chat/completions", headers=headers, json=payload)
        for _ in range(5)
    ]
    responses = await asyncio.gather(*tasks)

    for resp in responses:
        assert resp.status_code == 200
        assert resp.headers["X-CacheMind-Status"] in ("MISS", "EXACT_HIT")

    # Single-flight coalescing ensures upstream provider was called only once despite 5 concurrent requests!
    assert provider.call_count == initial_provider_calls + 1


@pytest.mark.asyncio
async def test_exact_cache_alias_model_presentation_and_telemetry(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    Verifies that for alias models (e.g. 'mock' -> 'mock-model'):
    1. Response body returns client-facing raw requested model ('mock').
    2. Headers and DB RequestLog correctly reflect actual canonical model ('mock-model') and requested model ('mock').
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}

    payload = {
        "model": "mock",
        "messages": [{"role": "user", "content": "Explain photosynthesis briefly."}],
        "temperature": 0.0,
    }

    # 1. First Request -> MISS
    resp1 = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert resp1.headers["X-CacheMind-Provider"] == "mock"
    assert resp1.headers["X-CacheMind-Model"] == "mock-model"
    body1 = resp1.json()
    assert body1["model"] in ("mock", "mock-model")

    # 2. Second Request -> EXACT HIT
    resp2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert resp2.headers["X-CacheMind-Provider"] == "mock"
    assert resp2.headers["X-CacheMind-Model"] == "mock-model"
    body2 = resp2.json()
    assert body2["model"] == "mock"
    assert (
        body2["choices"][0]["message"]["content"]
        == body1["choices"][0]["message"]["content"]
    )

    # 3. Verify Telemetry & FinOps Attribution in DB
    result = await db_session.execute(
        select(RequestLog)
        .where(RequestLog.requested_model == "mock")
        .order_by(RequestLog.created_at.asc())
    )
    logs = result.scalars().all()
    assert len(logs) >= 2
    exact_hit_log = logs[-1]
    assert exact_hit_log.cache_status == "EXACT_HIT"
    assert exact_hit_log.requested_model == "mock"
    assert exact_hit_log.actual_model == "mock-model"
    assert exact_hit_log.provider == "mock"
    assert exact_hit_log.upstream_called is False


@pytest.mark.asyncio
async def test_exact_cache_streaming_alias_model_presentation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    Verifies that cached SSE streaming preserves client-facing raw requested model ('mock') in chunks
    while diagnostic headers reflect canonical model ('mock-model').
    """
    import json

    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}

    payload = {
        "model": "mock",
        "messages": [{"role": "user", "content": "Streaming alias test message."}],
        "temperature": 0.0,
        "stream": False,
    }

    # Prime cache with non-streaming MISS
    resp_prime = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp_prime.status_code == 200

    # Request cached streaming
    payload_streaming = dict(payload)
    payload_streaming["stream"] = True
    resp_stream = await async_client.post(
        "/v1/chat/completions", headers=headers, json=payload_streaming
    )
    assert resp_stream.status_code == 200
    assert resp_stream.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert resp_stream.headers["X-CacheMind-Provider"] == "mock"
    assert resp_stream.headers["X-CacheMind-Model"] == "mock-model"

    # Verify SSE chunk model presentation
    lines = resp_stream.text.strip().split("\n")
    data_lines = [l for l in lines if l.startswith("data: ") and not l.startswith("data: [DONE]")]
    assert len(data_lines) > 0
    for line in data_lines:
        chunk = json.loads(line[len("data: "):])
        assert chunk["model"] == "mock"


