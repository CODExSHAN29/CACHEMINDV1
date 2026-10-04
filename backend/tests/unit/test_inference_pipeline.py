import ast
import os
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.auth.identity import AuthenticatedIdentity
from backend.caching.backend import ExactCacheBackend
from backend.caching.factory import get_cache_backend
from backend.caching.fingerprint import compute_exact_request_hash
from backend.caching.models import CachedResponse
from backend.inference.models import InferenceResult
from backend.inference.pipeline import InferencePipeline, get_inference_pipeline
from backend.normalization.models import NormalizedInferenceRequest, NormalizedMessage
from backend.providers.base import ProviderError
from backend.providers.mock_provider import MockProvider
from backend.providers.registry import ProviderRegistry, set_provider_registry
from backend.routing.engine import RoutingEngine, set_routing_engine
from backend.semantic.factory import SemanticCacheFactory, get_semantic_cache_service
from backend.db.models import RequestLog
from sqlalchemy import select


@pytest.fixture
def sample_identity() -> AuthenticatedIdentity:
    return AuthenticatedIdentity(
        tenant_id="tenant_alpha",
        project_id="proj_alpha_1",
        api_key_id="key_alpha_1",
        tenant_name="Alpha Corp",
        project_name="Alpha Main App",
        key_prefix="cm_live_alpha_",
        role="admin",
    )


@pytest.fixture
def sample_norm_req() -> NormalizedInferenceRequest:
    return NormalizedInferenceRequest(
        provider="mock",
        model="mock-gpt-4o",
        messages=[
            NormalizedMessage(role="system", content="You are a helpful assistant."),
            NormalizedMessage(role="user", content="Hello, what is the capital of France?"),
        ],
        temperature=0.0,
        stream=False,
    )


@pytest.mark.asyncio
async def test_inference_pipeline_exact_cache_hit(
    db_session: AsyncSession,
    sample_identity: AuthenticatedIdentity,
    sample_norm_req: NormalizedInferenceRequest,
):
    """Verifies that L1 exact cache hit returns an InferenceResult without calling upstream routing."""
    pipeline = get_inference_pipeline()
    exact_hash = compute_exact_request_hash(
        tenant_id=sample_identity.tenant_id,
        project_id=sample_identity.project_id,
        provider=sample_norm_req.provider,
        model=sample_norm_req.model,
        request=sample_norm_req,
    )

    cached_payload = {
        "id": "chatcmpl-cached-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "mock-gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Paris is the capital of France."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }

    cache_backend = get_cache_backend()
    await cache_backend.set(
        project_id=sample_identity.project_id,
        exact_request_hash=exact_hash,
        payload=CachedResponse(
            exact_request_hash=exact_hash,
            response_payload=cached_payload,
            provider="mock",
            model="mock-gpt-4o",
            ttl_seconds=3600,
        ),
        ttl_seconds=3600,
    )

    result = await pipeline.execute(
        norm_req=sample_norm_req,
        identity=sample_identity,
        db=db_session,
        raw_requested_model="gpt-4o",
    )

    assert isinstance(result, InferenceResult)
    assert result.cache_status == "EXACT_HIT"
    assert result.is_stream is False
    assert result.provider == "mock"
    assert result.model == "mock-gpt-4o"
    assert result.exact_request_hash == exact_hash
    assert result.headers.get("X-CacheMind-Status") == "EXACT_HIT"
    assert result.headers.get("X-CacheMind-Cache") == "EXACT_HIT"
    assert result.headers.get("X-CacheMind-Provider") == "mock"
    assert result.headers.get("X-CacheMind-Model") == "mock-gpt-4o"
    assert result.response_body is not None
    assert result.response_body["choices"][0]["message"]["content"] == "Paris is the capital of France."

    # Verify telemetry
    logs = (await db_session.execute(select(RequestLog).where(RequestLog.request_id == result.request_id))).scalars().all()
    assert len(logs) == 1
    assert logs[0].cache_status == "EXACT_HIT"
    assert logs[0].requested_model == "gpt-4o"
    assert logs[0].actual_model == "mock-gpt-4o"
    assert logs[0].upstream_called is False


@pytest.mark.asyncio
async def test_inference_pipeline_semantic_cache_hit(
    db_session: AsyncSession,
    sample_identity: AuthenticatedIdentity,
):
    """Verifies that L2 semantic cache hit returns an InferenceResult with similarity headers."""
    pipeline = get_inference_pipeline()
    settings.SEMANTIC_CACHE_MODE = "safe"

    t1 = "What is the capital city of France?"
    t2 = "Tell me what the capital of France is."

    # Register similar embedding before priming
    semantic_service = get_semantic_cache_service()
    embed_engine = semantic_service.embedding_engine
    embed_engine.register_similar(t1, t2, similarity=0.96)

    # 1. Warm cache with prime query
    prime_req = NormalizedInferenceRequest(
        provider="mock",
        model="mock-gpt-4o",
        messages=[
            NormalizedMessage(role="system", content="You are a helpful assistant."),
            NormalizedMessage(role="user", content=t1),
        ],
        temperature=0.0,
        stream=False,
    )

    prime_res = await pipeline.execute(
        norm_req=prime_req,
        identity=sample_identity,
        db=db_session,
        raw_requested_model="gpt-4o",
    )
    assert prime_res.cache_status == "MISS"

    # 2. Query with semantically similar prompt
    sem_req = NormalizedInferenceRequest(
        provider="mock",
        model="mock-gpt-4o",
        messages=[
            NormalizedMessage(role="system", content="You are a helpful assistant."),
            NormalizedMessage(role="user", content=t2),
        ],
        temperature=0.0,
        stream=False,
    )

    sem_res = await pipeline.execute(
        norm_req=sem_req,
        identity=sample_identity,
        db=db_session,
        raw_requested_model="gpt-4o",
    )

    assert isinstance(sem_res, InferenceResult)
    assert sem_res.cache_status == "L2_HIT"
    assert sem_res.is_stream is False
    assert sem_res.similarity_score is not None
    assert sem_res.similarity_score >= 0.85
    assert sem_res.headers.get("X-CacheMind-Status") == "L2_HIT"
    assert sem_res.headers.get("X-CacheMind-Cache") == "L2_HIT"
    assert "X-CacheMind-Similarity" in sem_res.headers


@pytest.mark.asyncio
async def test_inference_pipeline_miss_and_dual_backfill(
    db_session: AsyncSession,
    sample_identity: AuthenticatedIdentity,
    sample_norm_req: NormalizedInferenceRequest,
):
    """Verifies that a cache miss calls upstream routing and backfills L1 and L2."""
    pipeline = get_inference_pipeline()
    settings.SEMANTIC_CACHE_MODE = "safe"

    result = await pipeline.execute(
        norm_req=sample_norm_req,
        identity=sample_identity,
        db=db_session,
        raw_requested_model="gpt-4o",
    )

    assert isinstance(result, InferenceResult)
    assert result.cache_status == "MISS"
    assert result.headers.get("X-CacheMind-Status") == "MISS"
    assert result.response_body is not None

    # Verify L1 backfill
    cache_backend = get_cache_backend()
    cached = await cache_backend.get(sample_identity.project_id, result.exact_request_hash)
    assert cached is not None

    # Verify telemetry
    logs = (await db_session.execute(select(RequestLog).where(RequestLog.request_id == result.request_id))).scalars().all()
    assert len(logs) == 1
    assert logs[0].cache_status == "MISS"
    assert logs[0].upstream_called is True


@pytest.mark.asyncio
async def test_inference_pipeline_streaming_miss(
    db_session: AsyncSession,
    sample_identity: AuthenticatedIdentity,
    sample_norm_req: NormalizedInferenceRequest,
):
    """Verifies streaming cache miss returns an InferenceResult with stream generator."""
    pipeline = get_inference_pipeline()
    sample_norm_req.stream = True

    result = await pipeline.execute(
        norm_req=sample_norm_req,
        identity=sample_identity,
        db=db_session,
        raw_requested_model="gpt-4o",
    )

    assert isinstance(result, InferenceResult)
    assert result.cache_status == "MISS"
    assert result.is_stream is True
    assert result.stream_generator is not None

    # Accumulate chunks
    chunks = []
    async for chunk in result.stream_generator:
        chunks.append(chunk)

    assert len(chunks) > 0
    assert any("data: " in c for c in chunks)
    assert any("[DONE]" in c for c in chunks)


@pytest.mark.asyncio
async def test_inference_pipeline_streaming_cache_hit(
    db_session: AsyncSession,
    sample_identity: AuthenticatedIdentity,
    sample_norm_req: NormalizedInferenceRequest,
):
    """Verifies streaming cache hit yields SSE formatted tokens."""
    pipeline = get_inference_pipeline()
    exact_hash = compute_exact_request_hash(
        tenant_id=sample_identity.tenant_id,
        project_id=sample_identity.project_id,
        provider=sample_norm_req.provider,
        model=sample_norm_req.model,
        request=sample_norm_req,
    )

    cached_payload = {
        "id": "chatcmpl-cached-streaming-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "mock-gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Streamed cached content."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9},
    }

    cache_backend = get_cache_backend()
    await cache_backend.set(
        project_id=sample_identity.project_id,
        exact_request_hash=exact_hash,
        payload=CachedResponse(
            exact_request_hash=exact_hash,
            response_payload=cached_payload,
            provider="mock",
            model="mock-gpt-4o",
            ttl_seconds=3600,
        ),
        ttl_seconds=3600,
    )

    sample_norm_req.stream = True
    result = await pipeline.execute(
        norm_req=sample_norm_req,
        identity=sample_identity,
        db=db_session,
        raw_requested_model="gpt-4o",
    )

    assert isinstance(result, InferenceResult)
    assert result.cache_status == "EXACT_HIT"
    assert result.is_stream is True
    assert result.stream_generator is not None

    chunks = []
    async for chunk in result.stream_generator:
        chunks.append(chunk)

    assert len(chunks) > 0
    full_stream = "".join(chunks)
    assert "Streamed cached content." in full_stream or any("Streamed" in c for c in chunks)


@pytest.mark.asyncio
async def test_inference_pipeline_fallback_isolation(
    db_session: AsyncSession,
    sample_identity: AuthenticatedIdentity,
):
    """Verifies fallback execution isolates backfill under the executed fallback target."""
    settings.ANTHROPIC_FALLBACK_MODEL = "claude-3-5-sonnet-20241022"
    reg = ProviderRegistry()
    primary_mock = MockProvider(error_mode="rate_limit", provider_name="openai")
    fallback_mock = MockProvider(provider_name="anthropic")
    reg.register("openai", primary_mock)
    reg.register("anthropic", fallback_mock)
    set_provider_registry(reg)

    routing_engine = RoutingEngine(provider_registry=reg)
    set_routing_engine(routing_engine)

    pipeline = InferencePipeline(routing_engine=routing_engine)

    norm_req = NormalizedInferenceRequest(
        provider="openai",
        model="gpt-4o",
        messages=[
            NormalizedMessage(role="user", content="Calculate square root of 144."),
        ],
        allow_provider_fallback=True,
    )

    result = await pipeline.execute(
        norm_req=norm_req,
        identity=sample_identity,
        db=db_session,
        raw_requested_model="gpt-4o",
    )

    assert isinstance(result, InferenceResult)
    assert result.cache_status == "MISS"
    assert result.provider == "anthropic"  # default fallback provider for gpt-4o
    assert result.fallback_hops == 1

    # Verify backfill exact hash is under anthropic/claude-3-5-sonnet-20241022, not openai/gpt-4o
    expected_fallback_hash = compute_exact_request_hash(
        tenant_id=sample_identity.tenant_id,
        project_id=sample_identity.project_id,
        provider=result.provider,
        model=result.model,
        request=norm_req.model_copy(update={"provider": result.provider, "model": result.model}),
    )
    assert result.exact_request_hash == expected_fallback_hash

    cache_backend = get_cache_backend()
    cached = await cache_backend.get(sample_identity.project_id, expected_fallback_hash)
    assert cached is not None
    assert cached.provider == result.provider
    assert cached.model == result.model


@pytest.mark.asyncio
async def test_inference_pipeline_provider_error_handling(
    db_session: AsyncSession,
    sample_identity: AuthenticatedIdentity,
    sample_norm_req: NormalizedInferenceRequest,
):
    """Verifies that ProviderError logs error telemetry and is re-raised."""
    reg = ProviderRegistry()
    error_mock = MockProvider(error_mode="auth_error_401", provider_name="mock")
    reg.register("mock", error_mock)
    set_provider_registry(reg)

    routing_engine = RoutingEngine(provider_registry=reg)
    set_routing_engine(routing_engine)

    pipeline = InferencePipeline(routing_engine=routing_engine)

    with pytest.raises(ProviderError):
        await pipeline.execute(
            norm_req=sample_norm_req,
            identity=sample_identity,
            db=db_session,
            raw_requested_model="mock-gpt-4o",
        )

    # Verify error logged in DB
    logs = (await db_session.execute(select(RequestLog).where(RequestLog.tenant_id == sample_identity.tenant_id))).scalars().all()
    assert len(logs) >= 1
    error_log = logs[-1]
    assert error_log.cache_status == "ERROR"
    assert error_log.upstream_called is True


def test_inference_pipeline_architectural_neutrality():
    """
    AST inspection verifying that backend.inference has 0 imports of HTTP frameworks (fastapi, starlette)
    and 0 imports of concrete providers (OpenAIProvider, AnthropicProvider, OllamaProvider).
    """
    inference_dir = os.path.join("backend", "inference")
    forbidden_http_modules = {"fastapi", "starlette"}
    forbidden_provider_classes = {"OpenAIProvider", "AnthropicProvider", "OllamaProvider"}

    for root, _, files in os.walk(inference_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=file_path)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            root_pkg = alias.name.split(".")[0]
                            assert root_pkg not in forbidden_http_modules, (
                                f"{file_path} illegally imports HTTP module '{alias.name}'"
                            )
                            assert alias.name not in forbidden_provider_classes, (
                                f"{file_path} illegally imports concrete provider '{alias.name}'"
                            )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            root_pkg = node.module.split(".")[0]
                            assert root_pkg not in forbidden_http_modules, (
                                f"{file_path} illegally imports from HTTP module '{node.module}'"
                            )
                        for alias in node.names:
                            assert alias.name not in forbidden_provider_classes, (
                                f"{file_path} illegally imports concrete provider '{alias.name}' from '{node.module}'"
                            )
