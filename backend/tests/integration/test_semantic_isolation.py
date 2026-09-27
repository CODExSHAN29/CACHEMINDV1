import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.keys import generate_api_key
from backend.db.models import APIKey, Project
from backend.providers.factory import get_provider
from backend.semantic.factory import SemanticCacheFactory


@pytest.mark.asyncio
async def test_cross_tenant_semantic_isolation(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
    tenant_b_fixtures: dict,
):
    """
    CRITICAL SECURITY INVARIANT:
    Tenant B MUST NEVER hit Tenant A's semantic cache, even for semantically identical queries.
    """
    provider = get_provider()
    embed_engine = SemanticCacheFactory.get_embedding_engine()

    t1 = "Explain quantum computing fundamentals"
    t2 = "Explain the basics of quantum computing"
    embed_engine.register_similar(t1, t2, similarity=0.97)

    payload_a = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": t1}],
    }

    # 1. Tenant A queries -> MISS -> Upstream count: 1 (stored in Tenant A's scope)
    headers_a = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    resp_a1 = await async_client.post("/v1/chat/completions", headers=headers_a, json=payload_a)
    assert resp_a1.status_code == 200
    assert resp_a1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # 2. Tenant A queries similar prompt -> L2_HIT -> Upstream count: 1
    payload_a_similar = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": t2}],
    }
    resp_a2 = await async_client.post("/v1/chat/completions", headers=headers_a, json=payload_a_similar)
    assert resp_a2.status_code == 200
    assert resp_a2.headers["X-CacheMind-Status"] == "L2_HIT"
    assert provider.call_count == 1

    # 3. Tenant B queries the exact same similar prompt -> MUST MISS & Call Upstream!
    headers_b = {"Authorization": f"Bearer {tenant_b_fixtures['raw_key']}"}
    resp_b = await async_client.post("/v1/chat/completions", headers=headers_b, json=payload_a_similar)
    assert resp_b.status_code == 200
    assert resp_b.headers["X-CacheMind-Status"] == "MISS"
    # Upstream MUST have been called for Tenant B
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_cross_project_semantic_isolation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    Projects within the same tenant must have strictly isolated semantic caches.
    """
    tenant_id = tenant_a_fixtures["tenant_id"]
    provider = get_provider()

    # Create Project A2
    proj2 = Project(id="proj_alpha_semantic_2", tenant_id=tenant_id, name="Alpha App 2", is_active=True)
    db_session.add(proj2)
    await db_session.commit()

    raw_key2, prefix2, hash2 = generate_api_key("cm_live_alpha_sem2_")
    key2 = APIKey(
        id="key_alpha_sem2",
        project_id=proj2.id,
        key_prefix=prefix2,
        key_hash=hash2,
        name="Alpha Key Sem 2",
        is_active=True,
    )
    db_session.add(key2)
    await db_session.commit()

    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "Design a scalable microservices architecture"
    t2 = "How to architect scalable microservices"
    embed_engine.register_similar(t1, t2, similarity=0.96)

    # Project 1 queries
    headers_1 = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    resp1 = await async_client.post(
        "/v1/chat/completions",
        headers=headers_1,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": t1}]},
    )
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # Project 2 queries similar prompt -> MUST MISS (isolated by project_id in scope_hash)
    headers_2 = {"Authorization": f"Bearer {raw_key2}"}
    resp2 = await async_client.post(
        "/v1/chat/completions",
        headers=headers_2,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": t2}]},
    )
    assert resp2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_system_prompt_semantic_isolation(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Queries with differing system prompts must be partitioned in the semantic cache.
    """
    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    provider = get_provider()

    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "Explain gravity"
    t2 = "Explain how gravity works"
    embed_engine.register_similar(t1, t2, similarity=0.98)

    # 1. Query with System Prompt A
    resp1 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a university physics professor."},
                {"role": "user", "content": t1},
            ],
        },
    )
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # 2. Query with System Prompt B -> MUST MISS because system prompt differs in scope_hash
    resp2 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are explaining to a 5 year old."},
                {"role": "user", "content": t2},
            ],
        },
    )
    assert resp2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_model_semantic_isolation(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Semantic hits must only occur within the exact same model.
    """
    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    provider = get_provider()

    embed_engine = SemanticCacheFactory.get_embedding_engine()
    t1 = "Tell me a joke"
    t2 = "Say something funny"
    embed_engine.register_similar(t1, t2, similarity=0.96)

    # 1. Query on gpt-4o
    resp1 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": t1}]},
    )
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # 2. Query similar prompt on gpt-4o-mini -> MUST MISS
    resp2 = await async_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": t2}]},
    )
    assert resp2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2
