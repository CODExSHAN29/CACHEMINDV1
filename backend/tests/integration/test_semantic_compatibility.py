import pytest
from httpx import AsyncClient

from backend.app.config import settings
from backend.normalization.models import NormalizedInferenceRequest, NormalizedMessage
from backend.providers.factory import get_provider
from backend.semantic.factory import SemanticCacheFactory
from backend.semantic.policy import evaluate_semantic_eligibility, SemanticPolicyReason


@pytest.mark.asyncio
async def test_multi_turn_policy_rejection():
    # 1. Multiple user turns
    req1 = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[
            NormalizedMessage(role="user", content="Q1"),
            NormalizedMessage(role="user", content="Q2"),
        ],
    )
    res1 = evaluate_semantic_eligibility(req1)
    assert res1.eligible is False
    assert res1.reason == SemanticPolicyReason.MULTIPLE_USER_MESSAGES

    # 2. Assistant message present
    req2 = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[
            NormalizedMessage(role="user", content="Q1"),
            NormalizedMessage(role="assistant", content="A1"),
        ],
    )
    res2 = evaluate_semantic_eligibility(req2)
    assert res2.eligible is False
    assert res2.reason == SemanticPolicyReason.ASSISTANT_MESSAGE_PRESENT


@pytest.mark.asyncio
async def test_structured_output_policy_rejection():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Return JSON")],
        response_format={"type": "json_object"},
    )
    res = evaluate_semantic_eligibility(req)
    assert res.eligible is False
    assert res.reason == SemanticPolicyReason.STRUCTURED_OUTPUT_SCHEMA


@pytest.mark.asyncio
async def test_generation_parameters_policy_rejection():
    req_temp = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Creative poem")],
        temperature=0.7,
    )
    assert evaluate_semantic_eligibility(req_temp).eligible is False
    assert evaluate_semantic_eligibility(req_temp).reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS

    req_tokens = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Summarize")],
        max_tokens=100,
    )
    assert evaluate_semantic_eligibility(req_tokens).eligible is False
    assert evaluate_semantic_eligibility(req_tokens).reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS


@pytest.mark.asyncio
async def test_multi_turn_request_bypasses_l2_in_flow(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Ensures multi-turn requests never hit or seed L2 semantic cache.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "What is Python?"
    t2 = "Explain Python"
    embed_engine.register_similar(t1, t2, similarity=0.97)

    # 1. Seed single-turn query t1 -> MISS and seeded into L1 and L2
    resp1 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": t1}], "temperature": 0.0},
    )
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # 2. Multi-turn query containing t2 -> Even though t2 is semantically similar to t1,
    # multi-turn requests MUST bypass L2 and call upstream!
    multi_turn_payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": t2},
        ],
        "temperature": 0.0,
    }
    resp2 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json=multi_turn_payload,
    )
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_structured_output_bypasses_l2_in_flow(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Requests with structured JSON output response_format must bypass L2 semantic cache.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "List 3 colors in JSON format"
    t2 = "Give 3 colors in JSON"
    embed_engine.register_similar(t1, t2, similarity=0.98)

    # 1. Single-turn with response_format
    resp1 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": t1}],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        },
    )
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # 2. Similar query t2 with response_format -> must bypass L2 and call upstream
    resp2 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": t2}],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        },
    )
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_exact_only_mode_disables_l2(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    When SEMANTIC_CACHE_MODE is set to 'exact_only', L2 lookup and insertion are disabled.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    provider = get_provider()

    # Set mode to exact_only
    original_mode = settings.SEMANTIC_CACHE_MODE
    try:
        settings.SEMANTIC_CACHE_MODE = "exact_only"

        embed_engine = SemanticCacheFactory.get_embedding_engine()
        t1 = "Explain photosynthesis"
        t2 = "Describe photosynthesis"
        embed_engine.register_similar(t1, t2, similarity=0.98)

        # 1. First query -> MISS
        resp1 = await async_client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": t1}], "temperature": 0.0},
        )
        assert resp1.status_code == 200
        assert resp1.headers["X-CacheMind-Status"] == "MISS"
        assert provider.call_count == 1

        # 2. Exact match -> EXACT_HIT (L1 works)
        resp_exact = await async_client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": t1}], "temperature": 0.0},
        )
        assert resp_exact.status_code == 200
        assert resp_exact.headers["X-CacheMind-Status"] == "EXACT_HIT"
        assert provider.call_count == 1

        # 3. Semantically similar query -> In exact_only mode, L2 is bypassed -> MISS!
        resp_sim = await async_client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": t2}], "temperature": 0.0},
        )
        assert resp_sim.status_code == 200
        assert resp_sim.headers["X-CacheMind-Status"] == "MISS"
        assert provider.call_count == 2

    finally:
        settings.SEMANTIC_CACHE_MODE = original_mode
