import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.caching.fingerprint import (
    EXACT_CACHE_IDENTITY_VERSION,
    SEMANTIC_POLICY_VERSION,
    compute_exact_request_hash,
    compute_scope_hash,
)
from backend.normalization.models import (
    NormalizedInferenceRequest,
    NormalizedMessage,
)
from backend.routing.model_catalog import resolve_model, UnknownModelError


def test_exact_cache_hash_binds_provider_and_canonical_model():
    req_openai = NormalizedInferenceRequest(
        provider="openai",
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Hello CacheMind")],
    )
    req_anthropic = NormalizedInferenceRequest(
        provider="anthropic",
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Hello CacheMind")],
    )
    req_diff_model = NormalizedInferenceRequest(
        provider="openai",
        model="gpt-4o-mini",
        messages=[NormalizedMessage(role="user", content="Hello CacheMind")],
    )

    hash_openai = compute_exact_request_hash(
        tenant_id="tenant_1",
        project_id="proj_1",
        provider="openai",
        model="gpt-4o",
        request=req_openai,
    )
    hash_anthropic = compute_exact_request_hash(
        tenant_id="tenant_1",
        project_id="proj_1",
        provider="anthropic",
        model="gpt-4o",
        request=req_anthropic,
    )
    hash_diff_model = compute_exact_request_hash(
        tenant_id="tenant_1",
        project_id="proj_1",
        provider="openai",
        model="gpt-4o-mini",
        request=req_diff_model,
    )

    # Hashes must be distinct across providers and models
    assert hash_openai != hash_anthropic
    assert hash_openai != hash_diff_model
    assert EXACT_CACHE_IDENTITY_VERSION == "v2"


def test_exact_cache_hash_rejects_contradictory_identity():
    req = NormalizedInferenceRequest(
        provider="openai",
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Hello CacheMind")],
    )

    # Provider mismatch must raise ValueError
    with pytest.raises(ValueError, match="Contradictory provider"):
        compute_exact_request_hash(
            tenant_id="tenant_1",
            project_id="proj_1",
            provider="anthropic",
            model="gpt-4o",
            request=req,
        )

    # Model mismatch must raise ValueError
    with pytest.raises(ValueError, match="Contradictory model"):
        compute_exact_request_hash(
            tenant_id="tenant_1",
            project_id="proj_1",
            provider="openai",
            model="gpt-4o-mini",
            request=req,
        )


def test_semantic_scope_hash_binds_provider_and_canonical_model():
    hash_openai = compute_scope_hash(
        tenant_id="tenant_1",
        project_id="proj_1",
        provider="openai",
        model="gpt-4o",
        system_prompt=None,
        temperature=0.0,
    )
    hash_anthropic = compute_scope_hash(
        tenant_id="tenant_1",
        project_id="proj_1",
        provider="anthropic",
        model="gpt-4o",
        system_prompt=None,
        temperature=0.0,
    )
    hash_diff_model = compute_scope_hash(
        tenant_id="tenant_1",
        project_id="proj_1",
        provider="openai",
        model="gpt-4o-mini",
        system_prompt=None,
        temperature=0.0,
    )

    assert hash_openai != hash_anthropic
    assert hash_openai != hash_diff_model
    assert SEMANTIC_POLICY_VERSION == "v3"


@pytest.mark.asyncio
async def test_warmer_provider_model_validation_and_parity():
    from backend.caching.warmer import CacheWarmer, WarmItem

    # 1. Mismatch between explicit provider and resolved model provider fails
    item_mismatch = WarmItem(
        prompt="Test mismatch",
        response="Mismatch response",
        model="gpt-4o-mini",
        provider="anthropic",
    )
    res_mismatch = await CacheWarmer.warm_cache(
        tenant_id="t_warm",
        project_id="p_warm",
        items=[item_mismatch],
    )
    assert res_mismatch.failed_count == 1
    assert any("Provider mismatch" in err for err in res_mismatch.errors)

    # 2. Matching provider succeeds and matches live request exact hash
    item_valid = WarmItem(
        prompt="Parity prompt",
        response="Parity response",
        model="gpt-4o-mini",
        provider="openai",
    )
    res_valid = await CacheWarmer.warm_cache(
        tenant_id="t_warm",
        project_id="p_warm",
        items=[item_valid],
    )
    assert res_valid.exact_seeded == 1
    assert len(res_valid.exact_hashes) == 1

    # Live request hash computation must produce identical hash
    target = resolve_model("gpt-4o-mini")
    live_norm_req = NormalizedInferenceRequest(
        provider=target.provider,
        model=target.canonical_model,
        messages=[NormalizedMessage(role="user", content="Parity prompt")],
        temperature=0.0,
        stream=False,
    )
    live_hash = compute_exact_request_hash(
        tenant_id="t_warm",
        project_id="p_warm",
        provider=target.provider,
        model=target.canonical_model,
        request=live_norm_req,
    )
    assert res_valid.exact_hashes[0] == live_hash


@pytest.mark.asyncio
async def test_stream_accumulator_fallback_isolation():
    from backend.auth.identity import AuthenticatedIdentity
    from backend.streaming.accumulator import StreamAccumulator

    identity = AuthenticatedIdentity(
        tenant_id="tenant_stream",
        project_id="proj_stream",
        api_key_id="key_1",
        tenant_name="Tenant Stream",
        project_name="Proj Stream",
        key_prefix="cm_live_test",
        role="inference",
    )
    norm_req = NormalizedInferenceRequest(
        provider="openai",
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Stream query")],
    )

    exact_hash_primary = compute_exact_request_hash(
        tenant_id="tenant_stream",
        project_id="proj_stream",
        provider="openai",
        model="gpt-4o",
        request=norm_req,
    )
    scope_hash_primary = compute_scope_hash(
        tenant_id="tenant_stream",
        project_id="proj_stream",
        provider="openai",
        model="gpt-4o",
        system_prompt=None,
    )

    async def mock_upstream_stream():
        yield 'data: {"choices": [{"delta": {"role": "assistant", "content": "Hello"}}]}\n\n'
        yield 'data: {"choices": [{"delta": {"content": " world"}}]}\n\n'
        yield 'data: [DONE]\n\n'

    db_mock = MagicMock()
    db_mock.commit = AsyncMock()
    db_mock.rollback = AsyncMock()

    accumulator = StreamAccumulator(
        upstream_stream=mock_upstream_stream(),
        request_id="req_stream_1",
        identity=identity,
        norm_req=norm_req,
        exact_request_hash=exact_hash_primary,
        scope_hash=scope_hash_primary,
        last_user_text="Stream query",
        system_prompt=None,
        gateway_start_ns=0,
        exact_cache_lookup_ms=1.5,
        db=db_mock,
        provider_used="anthropic",
        model_used="claude-3-5-sonnet-20241022",
        raw_requested_model="gpt-4o",
        fallback_hops=1,
    )

    chunks = []
    async for chunk in accumulator:
        chunks.append(chunk)

    assert len(chunks) == 3
    assert "".join(accumulator.accumulated_chunks) == "Hello world"
    assert accumulator.provider_used == "anthropic"
    assert accumulator.model_used == "claude-3-5-sonnet-20241022"
    assert accumulator.raw_requested_model == "gpt-4o"

    # Verify that cache entry was saved under the executed fallback target and not primary
    from backend.caching.factory import get_cache_backend
    cache_backend = get_cache_backend()

    # Primary hash must NOT exist
    primary_cached = await cache_backend.get(identity.project_id, exact_hash_primary)
    assert primary_cached is None

    # Fallback hash MUST exist and have executed model & provider
    backfill_req = norm_req.model_copy(update={"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"})
    expected_fallback_hash = compute_exact_request_hash(
        tenant_id="tenant_stream",
        project_id="proj_stream",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        request=backfill_req,
    )
    fallback_cached = await cache_backend.get(identity.project_id, expected_fallback_hash)
    assert fallback_cached is not None
    assert fallback_cached.provider == "anthropic"
    assert fallback_cached.model == "claude-3-5-sonnet-20241022"
