import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.keys import generate_api_key
from backend.db.models import APIKey, Project, Tenant
from backend.providers.factory import get_provider


@pytest.mark.asyncio
async def test_cross_tenant_isolation(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
    tenant_b_fixtures: dict,
):
    """
    CRITICAL SECURITY INVARIANT:
    Tenant B MUST NEVER hit Tenant A's cache even for identical prompts.
    """
    provider = get_provider()
    prompt = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Company confidential prompt"}],
    }

    # Tenant A executes prompt -> MISS (upstream count: 1)
    headers_a = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    resp_a1 = await async_client.post("/v1/chat/completions", headers=headers_a, json=prompt)
    assert resp_a1.status_code == 200
    assert resp_a1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1
    hash_a = resp_a1.headers["X-CacheMind-Exact-Hash"]

    # Tenant A repeats prompt -> EXACT_HIT (upstream count: 1)
    resp_a2 = await async_client.post("/v1/chat/completions", headers=headers_a, json=prompt)
    assert resp_a2.status_code == 200
    assert resp_a2.headers["X-CacheMind-Status"] == "EXACT_HIT"
    assert provider.call_count == 1

    # Tenant B executes EXACT SAME prompt -> MUST MISS & Trigger Upstream (upstream count: 2)
    headers_b = {"Authorization": f"Bearer {tenant_b_fixtures['raw_key']}"}
    resp_b1 = await async_client.post("/v1/chat/completions", headers=headers_b, json=prompt)
    assert resp_b1.status_code == 200
    assert resp_b1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2
    hash_b = resp_b1.headers["X-CacheMind-Exact-Hash"]

    # The exact hashes MUST be completely different due to tenant binding
    assert hash_a != hash_b


@pytest.mark.asyncio
async def test_cross_project_isolation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    Projects within the same tenant must have partitioned caches.
    """
    tenant_id = tenant_a_fixtures["tenant_id"]
    provider = get_provider()

    # Create Project A2 under Tenant A
    proj2 = Project(id="proj_alpha_2", tenant_id=tenant_id, name="Alpha Second App", is_active=True)
    db_session.add(proj2)
    await db_session.commit()

    raw_key2, prefix2, hash2 = generate_api_key("cm_live_alpha2_")
    key2 = APIKey(
        id="key_alpha_2",
        project_id=proj2.id,
        key_prefix=prefix2,
        key_hash=hash2,
        name="Alpha Key 2",
        is_active=True,
    )
    db_session.add(key2)
    await db_session.commit()

    prompt = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Project isolation test"}],
    }

    # Request with Key 1 (Project A1) -> MISS
    resp1 = await async_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"},
        json=prompt,
    )
    assert resp1.status_code == 200
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # Request with Key 2 (Project A2) -> MISS (Project isolated!)
    resp2 = await async_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_key2}"},
        json=prompt,
    )
    assert resp2.status_code == 200
    assert resp2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_spoofed_headers_ignored(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
    tenant_b_fixtures: dict,
):
    """
    Client-supplied headers attempting to override tenant or project must be ignored.
    """
    headers = {
        "Authorization": f"Bearer {tenant_a_fixtures['raw_key']}",
        "X-Tenant-ID": tenant_b_fixtures["tenant_id"],
        "X-Project-ID": tenant_b_fixtures["project_id"],
        "X-Org-ID": "malicious_org",
    }
    prompt = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Spoofing test prompt"}],
    }

    resp = await async_client.post("/v1/chat/completions", headers=headers, json=prompt)
    assert resp.status_code == 200

    # Repeating with clean Tenant A headers MUST HIT (proving it was cached under Tenant A, not B)
    clean_headers_a = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    resp_repeat = await async_client.post(
        "/v1/chat/completions", headers=clean_headers_a, json=prompt
    )
    assert resp_repeat.status_code == 200
    assert resp_repeat.headers["X-CacheMind-Status"] == "EXACT_HIT"


@pytest.mark.asyncio
async def test_inactive_auth_credentials_rejected(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    # 1. Non-existent key
    resp = await async_client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer cm_live_nonexistent_key_12345"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401

    # 2. Inactive API Key
    tenant = Tenant(id="tenant_inactive", name="Inactive Corp", is_active=True)
    proj = Project(id="proj_inactive", tenant_id=tenant.id, name="Proj", is_active=True)
    raw_key, pfx, hsh = generate_api_key()
    api_key = APIKey(
        id="key_inactive",
        project_id=proj.id,
        key_prefix=pfx,
        key_hash=hsh,
        name="Key",
        is_active=False,  # Inactive Key
    )
    db_session.add_all([tenant, proj, api_key])
    await db_session.commit()

    resp = await async_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401

    # 3. Inactive Project
    proj.is_active = False
    api_key.is_active = True
    await db_session.commit()

    resp = await async_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401

    # 4. Inactive Tenant
    proj.is_active = True
    tenant.is_active = False
    await db_session.commit()

    resp = await async_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_parameter_variation_cache_isolation(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Different generation parameters, models, or system prompts MUST produce distinct cache entries.
    """
    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    provider = get_provider()

    base_req = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.0,
    }
    resp1 = await async_client.post("/v1/chat/completions", headers=headers, json=base_req)
    assert resp1.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 1

    # Different temperature
    diff_temp = dict(base_req, temperature=0.7)
    resp2 = await async_client.post("/v1/chat/completions", headers=headers, json=diff_temp)
    assert resp2.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 2

    # Different model
    diff_model = dict(base_req, model="gpt-4o-mini")
    resp3 = await async_client.post("/v1/chat/completions", headers=headers, json=diff_model)
    assert resp3.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 3

    # Additional system prompt
    with_sys = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Hello"},
        ],
        "temperature": 0.0,
    }
    resp4 = await async_client.post("/v1/chat/completions", headers=headers, json=with_sys)
    assert resp4.headers["X-CacheMind-Status"] == "MISS"
    assert provider.call_count == 4
