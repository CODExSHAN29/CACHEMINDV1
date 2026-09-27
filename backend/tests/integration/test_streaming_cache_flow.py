import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RequestLog
from backend.providers.factory import get_provider
from backend.semantic.factory import SemanticCacheFactory


def parse_sse_events(raw_stream_text: str) -> list:
    """Parses raw SSE response text into a list of JSON dicts and ignores [DONE]."""
    events = []
    lines = raw_stream_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data_str = line[len("data:"):].strip()
        if not data_str or data_str == "[DONE]":
            continue
        events.append(json.loads(data_str))
    return events


@pytest.mark.asyncio
async def test_streaming_miss_and_exact_hit_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    1. First streaming request misses upstream, yields SSE tokens, and dual-backfills cache.
    2. Subsequent streaming request hits L1 Exact Cache and streams with 0 upstream calls.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Explain asynchronous programming in Python"}],
        "stream": True,
        "temperature": 0.0,
    }

    # 1. First Request -> Stream MISS
    resp1 = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert "text/event-stream" in resp1.headers["content-type"]
    assert provider.call_count == 1

    events1 = parse_sse_events(resp1.text)
    assert len(events1) >= 2
    full_text_1 = "".join(e["choices"][0]["delta"].get("content", "") for e in events1)
    assert "Mock response" in full_text_1

    # 2. Second Request -> Stream EXACT_HIT
    resp2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert "text/event-stream" in resp2.headers["content-type"]
    # Zero upstream calls!
    assert provider.call_count == 1

    events2 = parse_sse_events(resp2.text)
    full_text_2 = "".join(e["choices"][0]["delta"].get("content", "") for e in events2)
    assert full_text_2 == full_text_1

    # 3. Check DB logs
    res = await db_session.execute(select(RequestLog).order_by(RequestLog.created_at.asc()))
    logs = res.scalars().all()
    assert len(logs) == 2
    assert logs[0].cache_status == "MISS"
    assert logs[0].upstream_called is True
    assert logs[1].cache_status == "EXACT_HIT"
    assert logs[1].upstream_called is False


@pytest.mark.asyncio
async def test_streaming_l2_semantic_hit_flow(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Verifies that a streaming request hitting L2 semantic cache replays tokens via SSE
    with zero upstream provider calls.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "How does photosynthesis work?"
    t2 = "Explain the process of photosynthesis"
    embed_engine.register_similar(t1, t2, similarity=0.97)

    payload_1 = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": t1}],
        "stream": True,
        "temperature": 0.0,
    }

    # 1. Miss and populate cache
    resp1 = await async_client.post("/v1/chat/completions", headers=headers, json=payload_1)
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1
    events1 = parse_sse_events(resp1.text)
    full_text_1 = "".join(e["choices"][0]["delta"].get("content", "") for e in events1)

    # 2. Similar query with streaming -> L2_HIT
    payload_2 = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": t2}],
        "stream": True,
        "temperature": 0.0,
    }
    resp2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload_2)
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "L2_HIT"
    assert "X-CacheMind-Similarity" in resp2.headers
    assert float(resp2.headers["X-CacheMind-Similarity"]) >= 0.90
    assert provider.call_count == 1

    events2 = parse_sse_events(resp2.text)
    full_text_2 = "".join(e["choices"][0]["delta"].get("content", "") for e in events2)
    assert full_text_2 == full_text_1


@pytest.mark.asyncio
async def test_bidirectional_cache_cross_streaming(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    1. Priming cache with non-streaming request -> Hit with streaming request.
    2. Priming cache with streaming request -> Hit with non-streaming request.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    # Case 1: Non-stream Prime -> Stream Hit
    payload_non_stream = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Tell me three tips for learning Rust"}],
        "stream": False,
        "temperature": 0.0,
    }
    resp_ns = await async_client.post("/v1/chat/completions", headers=headers, json=payload_non_stream)
    assert resp_ns.status_code == 200
    assert resp_ns.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1
    ns_content = resp_ns.json()["choices"][0]["message"]["content"]

    payload_stream = dict(payload_non_stream)
    payload_stream["stream"] = True

    resp_s = await async_client.post("/v1/chat/completions", headers=headers, json=payload_stream)
    assert resp_s.status_code == 200
    assert resp_s.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert provider.call_count == 1
    events = parse_sse_events(resp_s.text)
    stream_content = "".join(e["choices"][0]["delta"].get("content", "") for e in events)
    assert stream_content == ns_content

    # Case 2: Stream Prime -> Non-stream Hit
    payload_stream_2 = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "What are the SOLID principles?"}],
        "stream": True,
        "temperature": 0.0,
    }
    resp_s2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload_stream_2)
    assert resp_s2.status_code == 200
    assert resp_s2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2
    events2 = parse_sse_events(resp_s2.text)
    stream_content_2 = "".join(e["choices"][0]["delta"].get("content", "") for e in events2)

    payload_non_stream_2 = dict(payload_stream_2)
    payload_non_stream_2["stream"] = False

    resp_ns2 = await async_client.post("/v1/chat/completions", headers=headers, json=payload_non_stream_2)
    assert resp_ns2.status_code == 200
    assert resp_ns2.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert provider.call_count == 2
    ns_content_2 = resp_ns2.json()["choices"][0]["message"]["content"]
    assert ns_content_2 == stream_content_2
