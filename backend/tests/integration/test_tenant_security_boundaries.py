import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.auth.keys import generate_api_key
from backend.db.models import APIKey, Project, Tenant, TenantMembership, User
from backend.auth.session import hash_session_token, calculate_session_expiry
from backend.db.models import Session as UserSession


@pytest.mark.asyncio
async def test_tenant_api_key_cannot_access_system_admin_endpoints(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    DEFECT F01 VERIFICATION:
    A tenant-issued API key with role='admin' must NEVER have access to
    cluster-level /v1/admin/* management endpoints.
    """
    # Create an API key with role="admin" under Tenant A
    raw_key, key_prefix, key_hash = generate_api_key("cm_live_admin_")
    admin_key = APIKey(
        id="key_admin_tenant_a",
        project_id=tenant_a_fixtures["project_id"],
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="Tenant Admin Key",
        role="admin",
        is_active=True,
    )
    db_session.add(admin_key)
    await db_session.commit()

    # Attempt to access cluster administration endpoints
    headers = {"Authorization": f"Bearer {raw_key}"}
    resp = await async_client.get("/v1/admin/tenants", headers=headers)
    assert resp.status_code == 403
    assert "System administration privileges required" in resp.json()["detail"]

    # Attempt to create a tenant via admin API
    resp_create = await async_client.post(
        "/v1/admin/tenants",
        headers=headers,
        json={"name": "Attacker Tenant"},
    )
    assert resp_create.status_code == 403


@pytest.mark.asyncio
async def test_master_admin_key_can_access_system_admin_endpoints(
    async_client: AsyncClient,
):
    """
    Verifies that the configured ADMIN_MASTER_KEY can access system administration endpoints.
    """
    master_key = settings.ADMIN_MASTER_KEY or "cm_master_admin_key_super_secret"
    settings.ADMIN_MASTER_KEY = master_key

    headers = {"Authorization": f"Bearer {master_key}"}
    resp = await async_client.get("/v1/admin/tenants", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_cross_tenant_cache_purge_blocked(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
    tenant_b_fixtures: dict,
):
    """
    DEFECT F02 VERIFICATION:
    Tenant A must NOT be able to purge Tenant B's cache or specify Tenant B's tenant/project ID.
    """
    headers_a = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}

    # Tenant A attempts to purge specifying foreign tenant_id
    resp_foreign_tenant = await async_client.post(
        "/v1/cache/purge",
        headers=headers_a,
        json={"tenant_id": tenant_b_fixtures["tenant_id"]},
    )
    assert resp_foreign_tenant.status_code == 403
    assert "foreign tenant" in resp_foreign_tenant.json()["detail"].lower()

    # Tenant A attempts to purge specifying foreign project_id
    resp_foreign_proj = await async_client.post(
        "/v1/cache/purge",
        headers=headers_a,
        json={"project_id": tenant_b_fixtures["project_id"]},
    )
    assert resp_foreign_proj.status_code == 403
    assert "outside your workspace" in resp_foreign_proj.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cross_tenant_cache_warm_blocked(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
    tenant_b_fixtures: dict,
):
    """
    Tenant A must NOT be able to warm cache for Tenant B's project or tenant.
    """
    headers_a = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    warm_payload = {
        "tenant_id": tenant_b_fixtures["tenant_id"],
        "items": [{"prompt": "Hello", "completion": "World"}],
    }
    resp = await async_client.post("/v1/cache/warm", headers=headers_a, json=warm_payload)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_role_based_permissions(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    Verifies granular roles:
    - 'read_only': cannot infer, cannot write cache (purge/warm/delete), can inspect/list
    - 'inference': can infer, cannot write cache (purge/warm/delete), can inspect/list
    - 'cache_write': can infer, can write cache (purge/warm/delete), can inspect/list
    """
    project_id = tenant_a_fixtures["project_id"]

    # 1. Create read_only key
    raw_ro, p_ro, h_ro = generate_api_key("cm_ro_")
    key_ro = APIKey(
        id="key_read_only",
        project_id=project_id,
        key_prefix=p_ro,
        key_hash=h_ro,
        name="Read Only Key",
        role="read_only",
        is_active=True,
    )
    db_session.add(key_ro)

    # 2. Create inference key
    raw_inf, p_inf, h_inf = generate_api_key("cm_inf_")
    key_inf = APIKey(
        id="key_inference",
        project_id=project_id,
        key_prefix=p_inf,
        key_hash=h_inf,
        name="Inference Key",
        role="inference",
        is_active=True,
    )
    db_session.add(key_inf)

    # 3. Create cache_write key
    raw_cw, p_cw, h_cw = generate_api_key("cm_cw_")
    key_cw = APIKey(
        id="key_cache_write",
        project_id=project_id,
        key_prefix=p_cw,
        key_hash=h_cw,
        name="Cache Write Key",
        role="cache_write",
        is_active=True,
    )
    db_session.add(key_cw)
    await db_session.commit()

    prompt_payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Security role test"}],
    }

    # --- Test read_only key ---
    headers_ro = {"Authorization": f"Bearer {raw_ro}"}
    # Cannot infer
    resp_ro_chat = await async_client.post("/v1/chat/completions", headers=headers_ro, json=prompt_payload)
    assert resp_ro_chat.status_code == 403
    assert "inference operations" in resp_ro_chat.json()["detail"].lower()
    # Cannot purge
    resp_ro_purge = await async_client.post("/v1/cache/purge", headers=headers_ro, json={})
    assert resp_ro_purge.status_code == 403
    # Cannot warm
    resp_ro_warm = await async_client.post("/v1/cache/warm", headers=headers_ro, json={"items": [{"prompt": "A", "completion": "B"}]})
    assert resp_ro_warm.status_code == 403
    # Cannot delete key
    resp_ro_del = await async_client.delete("/v1/cache/keys/fakehash", headers=headers_ro)
    assert resp_ro_del.status_code == 403
    # Can list keys
    resp_ro_list = await async_client.get("/v1/cache/keys", headers=headers_ro)
    assert resp_ro_list.status_code == 200

    # --- Test inference key ---
    headers_inf = {"Authorization": f"Bearer {raw_inf}"}
    # Can infer
    resp_inf_chat = await async_client.post("/v1/chat/completions", headers=headers_inf, json=prompt_payload)
    assert resp_inf_chat.status_code == 200
    # Cannot purge
    resp_inf_purge = await async_client.post("/v1/cache/purge", headers=headers_inf, json={})
    assert resp_inf_purge.status_code == 403
    # Cannot warm
    resp_inf_warm = await async_client.post("/v1/cache/warm", headers=headers_inf, json={"items": [{"prompt": "A", "completion": "B"}]})
    assert resp_inf_warm.status_code == 403
    # Cannot delete key
    resp_inf_del = await async_client.delete("/v1/cache/keys/fakehash", headers=headers_inf)
    assert resp_inf_del.status_code == 403

    # --- Test cache_write key ---
    headers_cw = {"Authorization": f"Bearer {raw_cw}"}
    # Can infer
    resp_cw_chat = await async_client.post("/v1/chat/completions", headers=headers_cw, json=prompt_payload)
    assert resp_cw_chat.status_code == 200
    # Can purge
    resp_cw_purge = await async_client.post("/v1/cache/purge", headers=headers_cw, json={})
    assert resp_cw_purge.status_code == 200
    # Can warm
    resp_cw_warm = await async_client.post("/v1/cache/warm", headers=headers_cw, json={"items": [{"prompt": "A", "completion": "B"}]})
    assert resp_cw_warm.status_code == 200
    # Can delete key
    resp_cw_del = await async_client.delete("/v1/cache/keys/fakehash", headers=headers_cw)
    assert resp_cw_del.status_code == 200


@pytest.mark.asyncio
async def test_inactive_resource_hierarchy(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    DEFECT F04 VERIFICATION:
    Inactive tenant, project, or API key must fail closed with HTTP 401.
    """
    # 1. Inactive Tenant
    t_inact = Tenant(id="tenant_inactive", name="Inactive Corp", is_active=False)
    p_for_t = Project(id="proj_for_inact_tenant", tenant_id=t_inact.id, name="P1", is_active=True)
    raw_k1, pref1, hash1 = generate_api_key("cm_k1_")
    k_for_t = APIKey(id="key_inact_tenant", project_id=p_for_t.id, key_prefix=pref1, key_hash=hash1, is_active=True)
    db_session.add_all([t_inact, p_for_t, k_for_t])

    # 2. Inactive Project
    t_act = Tenant(id="tenant_active_for_p", name="Active Corp", is_active=True)
    p_inact = Project(id="proj_inactive", tenant_id=t_act.id, name="P2", is_active=False)
    raw_k2, pref2, hash2 = generate_api_key("cm_k2_")
    k_for_p = APIKey(id="key_inact_proj", project_id=p_inact.id, key_prefix=pref2, key_hash=hash2, is_active=True)
    db_session.add_all([t_act, p_inact, k_for_p])

    # 3. Inactive Key
    p_act = Project(id="proj_active_for_k", tenant_id=t_act.id, name="P3", is_active=True)
    raw_k3, pref3, hash3 = generate_api_key("cm_k3_")
    k_inact = APIKey(id="key_inactive", project_id=p_act.id, key_prefix=pref3, key_hash=hash3, is_active=False)
    db_session.add_all([p_act, k_inact])
    await db_session.commit()

    prompt = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Test"}]}

    # Inactive tenant -> 401
    r1 = await async_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_k1}"}, json=prompt)
    assert r1.status_code == 401

    # Inactive project -> 401
    r2 = await async_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_k2}"}, json=prompt)
    assert r2.status_code == 401

    # Inactive key -> 401
    r3 = await async_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_k3}"}, json=prompt)
    assert r3.status_code == 401


@pytest.mark.asyncio
async def test_no_synthetic_project_id_fail_closed(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    DEFECT F04 VERIFICATION:
    If a session user belongs to a workspace with 0 active projects,
    auth resolution must FAIL CLOSED with HTTP 400 instead of creating a synthetic project string.
    """
    user = User(id="user_empty_ws", email="empty_ws@cachemind.io", password_hash="dummy", is_active=True)
    tenant = Tenant(id="tenant_no_proj", name="Empty Workspace", is_active=True)
    membership = TenantMembership(id="mem_empty", user_id=user.id, tenant_id=tenant.id, role="owner")
    db_session.add_all([user, tenant, membership])

    token = "session_token_empty_workspace_123"
    sess = UserSession(
        id="sess_empty",
        session_token_hash=hash_session_token(token),
        user_id=user.id,
        active_tenant_id=tenant.id,
        expires_at=calculate_session_expiry(),
    )
    db_session.add(sess)
    await db_session.commit()

    prompt = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Test"}]}
    resp = await async_client.post(
        "/v1/chat/completions",
        cookies={settings.SESSION_COOKIE_NAME: token},
        json=prompt,
    )
    assert resp.status_code == 400
    assert "No active projects found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_response_omits_session_token(
    async_client: AsyncClient,
):
    """
    DEFECT F05 VERIFICATION:
    Signup & login response payloads MUST NOT leak raw session_token in the JSON response.
    """
    # Signup
    signup_res = await async_client.post(
        "/v1/auth/signup",
        json={
            "email": "cookie.test@cachemind.io",
            "password": "Password12345!",
            "full_name": "Cookie Tester",
        },
    )
    assert signup_res.status_code == 201
    data = signup_res.json()
    assert "session_token" not in data
    assert settings.SESSION_COOKIE_NAME in signup_res.cookies

    # Login
    login_res = await async_client.post(
        "/v1/auth/login",
        json={
            "email": "cookie.test@cachemind.io",
            "password": "Password12345!",
        },
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "session_token" not in login_data
    assert settings.SESSION_COOKIE_NAME in login_res.cookies


@pytest.mark.asyncio
async def test_inactive_selected_tenant_fails_closed_without_switching(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    FAIL-CLOSED SESSION RESOLUTION VERIFICATION:
    When a session has an explicit active_tenant_id and that tenant becomes inactive,
    the session MUST fail closed (HTTP 403) instead of silently falling back to
    another active tenant the user belongs to.
    """
    user = User(id="user_multi_tenant", email="multi@cachemind.io", password_hash="dummy", is_active=True)
    tenant_inactive = Tenant(id="tenant_inact_sel", name="Inactive Primary", is_active=False)
    tenant_active = Tenant(id="tenant_act_sec", name="Active Secondary", is_active=True)
    proj_active = Project(id="proj_act_sec", tenant_id=tenant_active.id, name="Active Secondary Project", is_active=True)

    mem_inact = TenantMembership(id="mem_1", user_id=user.id, tenant_id=tenant_inactive.id, role="owner")
    mem_act = TenantMembership(id="mem_2", user_id=user.id, tenant_id=tenant_active.id, role="owner")

    token = "session_token_multi_tenant_inactive_sel"
    sess = UserSession(
        id="sess_multi_inact",
        session_token_hash=hash_session_token(token),
        user_id=user.id,
        active_tenant_id=tenant_inactive.id,
        expires_at=calculate_session_expiry(),
    )
    db_session.add_all([user, tenant_inactive, tenant_active, proj_active, mem_inact, mem_act, sess])
    await db_session.commit()

    # 1. /v1/chat/completions with cookie must fail closed (403)
    prompt = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}
    chat_res = await async_client.post(
        "/v1/chat/completions",
        cookies={settings.SESSION_COOKIE_NAME: token},
        json=prompt,
    )
    assert chat_res.status_code == 403
    assert "Selected workspace is inactive or inaccessible." in chat_res.json()["detail"]

    # 2. /v1/auth/me with cookie must fail closed (403)
    me_res = await async_client.get(
        "/v1/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: token},
    )
    assert me_res.status_code == 403
    assert "Selected workspace is inactive or disabled." in me_res.json()["detail"]


@pytest.mark.asyncio
async def test_uninitialized_session_falls_back_to_active_workspace(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    When session.active_tenant_id is None (uninitialized/legacy session),
    it resolves to the first active workspace membership.
    """
    user = User(id="user_uninit_sess", email="uninit@cachemind.io", password_hash="dummy", is_active=True)
    tenant_active = Tenant(id="tenant_uninit_target", name="Target Workspace", is_active=True)
    proj_active = Project(id="proj_uninit_target", tenant_id=tenant_active.id, name="Target Project", is_active=True)
    mem = TenantMembership(id="mem_uninit", user_id=user.id, tenant_id=tenant_active.id, role="owner")

    token = "session_token_uninit_active_tenant"
    sess = UserSession(
        id="sess_uninit",
        session_token_hash=hash_session_token(token),
        user_id=user.id,
        active_tenant_id=None,
        expires_at=calculate_session_expiry(),
    )
    db_session.add_all([user, tenant_active, proj_active, mem, sess])
    await db_session.commit()

    # /v1/auth/me should succeed and resolve Target Workspace
    me_res = await async_client.get(
        "/v1/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: token},
    )
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["active_tenant"]["id"] == tenant_active.id


@pytest.mark.asyncio
async def test_default_api_key_role_is_inference(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    Verifies that creating an API key without specifying role defaults to 'inference' (least-privilege).
    """
    user = User(id="user_key_tester", email="keytest@cachemind.io", password_hash="dummy", is_active=True)
    tenant = Tenant(id="tenant_key_tester", name="Key Workspace", is_active=True)
    proj = Project(id="proj_key_tester", tenant_id=tenant.id, name="Key Project", is_active=True)
    mem = TenantMembership(id="mem_key_tester", user_id=user.id, tenant_id=tenant.id, role="owner")

    token = "session_token_key_tester"
    sess = UserSession(
        id="sess_key_tester",
        session_token_hash=hash_session_token(token),
        user_id=user.id,
        active_tenant_id=tenant.id,
        expires_at=calculate_session_expiry(),
    )
    db_session.add_all([user, tenant, proj, mem, sess])
    await db_session.commit()

    resp = await async_client.post(
        "/v1/auth/keys",
        cookies={settings.SESSION_COOKIE_NAME: token},
        json={"project_id": proj.id, "name": "Least Privilege Key"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "inference"

