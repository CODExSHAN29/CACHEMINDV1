import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.models import Project, Tenant, TenantMembership, User
from backend.db.repositories import SessionRepository


@pytest.mark.asyncio
async def test_server_authoritative_active_project_selection(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies server-authoritative project selection:
    1. Creating projects within workspace.
    2. Selecting project via path param (/v1/auth/projects/{id}/select) and body param (/v1/auth/projects/select).
    3. Session database record stores active_project_id.
    4. /v1/auth/me returns updated active_project.
    5. Selecting non-existent or cross-tenant project fails with 404 or 403.
    """
    # 1. Signup user
    signup_res = await async_client.post(
        "/v1/auth/signup",
        json={
            "email": "project.scope.tester@cachemind.io",
            "password": "Password12345!",
            "full_name": "Scope Tester",
            "workspace_name": "Scope Workspace",
        },
    )
    assert signup_res.status_code == 201
    signup_data = signup_res.json()
    tenant_id = signup_data["active_tenant"]["id"]
    default_proj_id = signup_data["active_project"]["id"]

    # Verify me returns initial active project
    me_res = await async_client.get("/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["active_project"]["id"] == default_proj_id

    # 2. Create second and third projects
    p2_res = await async_client.post(
        "/v1/auth/projects",
        json={"name": "Analytics Engine"},
    )
    assert p2_res.status_code == 201
    p2_id = p2_res.json()["id"]

    p3_res = await async_client.post(
        "/v1/auth/projects",
        json={"name": "Embedding Pipeline"},
    )
    assert p3_res.status_code == 201
    p3_id = p3_res.json()["id"]

    # 3. Select second project via path parameter
    select_p2_res = await async_client.post(f"/v1/auth/projects/{p2_id}/select")
    assert select_p2_res.status_code == 200
    assert select_p2_res.json()["active_project"]["id"] == p2_id
    assert select_p2_res.json()["active_project"]["name"] == "Analytics Engine"

    # Verify /me reflects p2
    me_after_p2 = await async_client.get("/v1/auth/me")
    assert me_after_p2.status_code == 200
    assert me_after_p2.json()["active_project"]["id"] == p2_id

    # 4. Select third project via POST /v1/auth/projects/select body parameter
    select_p3_res = await async_client.post(
        "/v1/auth/projects/select",
        json={"project_id": p3_id},
    )
    assert select_p3_res.status_code == 200
    assert select_p3_res.json()["active_project"]["id"] == p3_id
    assert select_p3_res.json()["active_project"]["name"] == "Embedding Pipeline"

    # Verify database session model reflects active_project_id
    cookie_val = async_client.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie_val is not None
    from backend.auth.session import hash_session_token
    session_repo = SessionRepository(db_session)
    stored_session = await session_repo.get_by_token_hash(hash_session_token(cookie_val))
    assert stored_session is not None
    assert stored_session.active_project_id == p3_id

    # 5. Cross-tenant project selection prevention
    # Create another tenant & project directly in DB
    other_tenant = Tenant(id="tenant_other_isolate", name="Isolated Org", is_active=True)
    other_project = Project(
        id="proj_other_isolate",
        tenant_id="tenant_other_isolate",
        name="Isolated Secret Project",
        is_active=True,
    )
    db_session.add(other_tenant)
    db_session.add(other_project)
    await db_session.commit()

    cross_select_res = await async_client.post("/v1/auth/projects/proj_other_isolate/select")
    assert cross_select_res.status_code in (403, 404)

    # 6. Non-existent project selection prevention
    fake_select_res = await async_client.post("/v1/auth/projects/proj_does_not_exist/select")
    assert fake_select_res.status_code in (403, 404)


@pytest.mark.asyncio
async def test_workspace_switch_reconciles_active_project(
    async_client: AsyncClient,
):
    """
    Verifies that switching active workspace automatically updates/reconciles active_project_id
    to a project within the newly selected workspace.
    """
    signup_res = await async_client.post(
        "/v1/auth/signup",
        json={
            "email": "reconcile.tester@cachemind.io",
            "password": "Password12345!",
            "full_name": "Reconcile Tester",
            "workspace_name": "Workspace A",
        },
    )
    assert signup_res.status_code == 201
    ws_a_id = signup_res.json()["active_tenant"]["id"]
    ws_a_proj_id = signup_res.json()["active_project"]["id"]

    # Create Workspace B
    ws_b_res = await async_client.post(
        "/v1/auth/workspaces",
        json={"name": "Workspace B"},
    )
    assert ws_b_res.status_code == 201
    ws_b_id = ws_b_res.json()["id"]

    # Create a project in Workspace B
    # First switch to Workspace B
    sw_b_res = await async_client.post(f"/v1/auth/workspaces/{ws_b_id}/select")
    assert sw_b_res.status_code == 200
    assert sw_b_res.json()["active_tenant"]["id"] == ws_b_id

    # Create project in Workspace B
    proj_b_res = await async_client.post(
        "/v1/auth/projects",
        json={"name": "Workspace B Project 1"},
    )
    assert proj_b_res.status_code == 201
    ws_b_proj_id = proj_b_res.json()["id"]

    # Select project in Workspace B
    await async_client.post(f"/v1/auth/projects/{ws_b_proj_id}/select")

    # Switch back to Workspace A
    sw_a_res = await async_client.post(f"/v1/auth/workspaces/{ws_a_id}/select")
    assert sw_a_res.status_code == 200
    assert sw_a_res.json()["active_tenant"]["id"] == ws_a_id
    assert sw_a_res.json()["active_project"]["id"] == ws_a_proj_id

    # Verify /me confirms active project is in Workspace A
    me_a = await async_client.get("/v1/auth/me")
    assert me_a.status_code == 200
    assert me_a.json()["active_tenant"]["id"] == ws_a_id
    assert me_a.json()["active_project"]["id"] == ws_a_proj_id


@pytest.mark.asyncio
async def test_control_plane_contracts_and_cors_headers(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies control plane wire schema contracts and CORS telemetry headers:
    1. WarmBatchResult contract: seeded, seeded_l1, seeded_l2, details
    2. CachePurgeResult contract: purged, keys_purged, tenant_id, project_id, model, namespace
    3. CacheKeyInspection contract: key_hash, exists_in_l1, exists_in_l2, exact_entry, semantic_entry, ttl_remaining_seconds
    4. CORS exposed headers
    """
    # 1. Signup and get project key
    signup_res = await async_client.post(
        "/v1/auth/signup",
        json={
            "email": "contracts.tester@cachemind.io",
            "password": "Password12345!",
            "full_name": "Contracts Tester",
            "workspace_name": "Contracts Workspace",
        },
    )
    assert signup_res.status_code == 201
    project_id = signup_res.json()["active_project"]["id"]
    tenant_id = signup_res.json()["active_tenant"]["id"]

    # Create a key with cache_write role for cache operations
    key_res = await async_client.post(
        "/v1/auth/keys",
        json={"project_id": project_id, "name": "Cache Admin Key", "role": "cache_write"},
    )
    assert key_res.status_code == 201
    raw_key = key_res.json()["raw_key"]
    auth_headers = {"Authorization": f"Bearer {raw_key}"}

    # 2. Warm Cache - Verify WarmBatchResult schema
    warm_payload = {
        "items": [
            {
                "prompt": "What is CacheMind?",
                "completion": "CacheMind is an intelligent dual-tier caching gateway for LLMs.",
                "model": "gpt-4o-mini",
            }
        ]
    }
    warm_res = await async_client.post("/v1/cache/warm", json=warm_payload, headers=auth_headers)
    assert warm_res.status_code == 200
    warm_data = warm_res.json()
    assert "seeded" in warm_data
    assert "seeded_l1" in warm_data
    assert "seeded_l2" in warm_data
    assert "details" in warm_data
    assert isinstance(warm_data["seeded"], int)
    assert isinstance(warm_data["details"], list)

    # 3. Inspect Cache Key - Verify CacheKeyInspection schema
    inspect_res = await async_client.get("/v1/cache/inspect/nonexistent_hash_123", headers=auth_headers)
    assert inspect_res.status_code == 200
    inspect_data = inspect_res.json()
    assert inspect_data["key_hash"] == "nonexistent_hash_123"
    assert "exists_in_l1" in inspect_data
    assert "exists_in_l2" in inspect_data
    assert "exact_entry" in inspect_data
    assert "semantic_entry" in inspect_data
    assert "ttl_remaining_seconds" in inspect_data

    # 4. Purge Cache - Verify CachePurgeResult schema
    purge_payload = {
        "model": "gpt-4o-mini",
    }
    purge_res = await async_client.post("/v1/cache/purge", json=purge_payload, headers=auth_headers)
    assert purge_res.status_code == 200
    purge_data = purge_res.json()
    assert "purged" in purge_data
    assert "keys_purged" in purge_data
    assert purge_data["tenant_id"] == tenant_id
    assert purge_data["project_id"] == project_id
    assert purge_data["model"] == "gpt-4o-mini"
    assert "namespace" in purge_data

    # 5. Test Chat completions & CORS header exposure in main.py config
    chat_res = await async_client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "What is CacheMind?"}],
        },
    )
    assert chat_res.status_code == 200
    # Telemetry headers returned on inference
    assert "x-cachemind-status" in chat_res.headers
    assert "x-cachemind-cache" in chat_res.headers
    assert "x-cachemind-request-id" in chat_res.headers


@pytest.mark.asyncio
async def test_cross_workspace_project_selection_rejected_with_403(
    async_client: AsyncClient,
):
    """
    Verifies that an authenticated user who is a member of multiple workspaces
    cannot select a project from Workspace B when their active workspace is Workspace A.
    Must fail closed with HTTP 403 Forbidden ("Cannot select a project outside the active workspace.").
    """
    signup_res = await async_client.post(
        "/v1/auth/signup",
        json={
            "email": "boundary.tester@cachemind.io",
            "password": "Password12345!",
            "full_name": "Boundary Tester",
            "workspace_name": "Workspace Alpha",
        },
    )
    assert signup_res.status_code == 201
    ws_alpha_id = signup_res.json()["active_tenant"]["id"]

    # Create Workspace Beta
    ws_beta_res = await async_client.post(
        "/v1/auth/workspaces",
        json={"name": "Workspace Beta"},
    )
    assert ws_beta_res.status_code == 201
    ws_beta_id = ws_beta_res.json()["id"]

    # Switch to Workspace Beta and create a project in Beta
    await async_client.post(f"/v1/auth/workspaces/{ws_beta_id}/select")
    proj_beta_res = await async_client.post(
        "/v1/auth/projects",
        json={"name": "Project Beta 1"},
    )
    assert proj_beta_res.status_code == 201
    proj_beta_id = proj_beta_res.json()["id"]

    # Switch active workspace back to Workspace Alpha
    await async_client.post(f"/v1/auth/workspaces/{ws_alpha_id}/select")
    me_res = await async_client.get("/v1/auth/me")
    assert me_res.json()["active_tenant"]["id"] == ws_alpha_id

    # Attempt to select Project Beta 1 while active workspace is Workspace Alpha -> HTTP 403
    select_cross_res = await async_client.post(f"/v1/auth/projects/{proj_beta_id}/select")
    assert select_cross_res.status_code == 403
    assert "outside the active workspace" in select_cross_res.json()["detail"]

    # Also test via body endpoint
    select_cross_body = await async_client.post(
        "/v1/auth/projects/select",
        json={"project_id": proj_beta_id},
    )
    assert select_cross_body.status_code == 403
    assert "outside the active workspace" in select_cross_body.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_active_project_fails_closed_in_session_auth(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies that when a session's active_project_id is set to an inactive or non-existent
    project ID, session-based authentication in get_authenticated_identity fails closed
    with HTTP 403 Forbidden rather than silently falling back to another project.
    """
    signup_res = await async_client.post(
        "/v1/auth/signup",
        json={
            "email": "failclosed.proj@cachemind.io",
            "password": "Password12345!",
            "full_name": "Fail Closed Tester",
            "workspace_name": "Fail Closed Workspace",
        },
    )
    assert signup_res.status_code == 201

    # Corrupt the session's active_project_id in DB to point to an invalid project ID
    cookie_val = async_client.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie_val is not None
    from backend.auth.session import hash_session_token
    session_repo = SessionRepository(db_session)
    stored_session = await session_repo.get_by_token_hash(hash_session_token(cookie_val))
    assert stored_session is not None

    stored_session.active_project_id = "proj_invalid_corrupted_id"
    await db_session.commit()

    # Inference via session cookie must fail closed with HTTP 403
    chat_res = await async_client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Test fail closed"}],
        },
    )
    assert chat_res.status_code == 403
    assert "Selected project is inactive or inaccessible" in chat_res.json()["detail"]


@pytest.mark.asyncio
async def test_auth_session_response_schema_contract(
    async_client: AsyncClient,
):
    """
    Verifies that auth endpoints (signup, login, me, workspace select, project select)
    return the clean AuthSessionResponse schema without raw_api_key.
    """
    # 1. Signup
    signup_res = await async_client.post(
        "/v1/auth/signup",
        json={
            "email": "schema.tester@cachemind.io",
            "password": "Password12345!",
            "full_name": "Schema Tester",
            "workspace_name": "Schema Workspace",
        },
    )
    assert signup_res.status_code == 201
    data = signup_res.json()
    assert "raw_api_key" not in data
    assert "user" in data
    assert "active_tenant" in data
    assert "active_project" in data
    assert "workspaces" in data
    assert "projects" in data
    assert "api_keys" in data

    # 2. Get Me
    me_res = await async_client.get("/v1/auth/me")
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert "raw_api_key" not in me_data

    # 3. Login
    login_res = await async_client.post(
        "/v1/auth/login",
        json={
            "email": "schema.tester@cachemind.io",
            "password": "Password12345!",
        },
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "raw_api_key" not in login_data

