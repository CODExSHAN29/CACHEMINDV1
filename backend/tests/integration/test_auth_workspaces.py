import pytest
from httpx import AsyncClient
from backend.app.config import settings


@pytest.mark.asyncio
async def test_signup_flow(async_client: AsyncClient):
    # 1. Successful signup
    signup_payload = {
        "email": "developer@cachemind.io",
        "password": "SuperSecretPassword123!",
        "full_name": "Jane Developer",
        "workspace_name": "Jane's AI Lab",
    }
    res = await async_client.post("/v1/auth/signup", json=signup_payload)
    assert res.status_code == 201, res.text
    data = res.json()

    assert data["user"]["email"] == "developer@cachemind.io"
    assert data["user"]["full_name"] == "Jane Developer"
    assert data["active_tenant"]["name"] == "Jane's AI Lab"
    assert data["active_tenant"]["role"] == "owner"
    assert data["active_project"]["name"] == "Default Project"
    assert len(data["api_keys"]) >= 1
    assert data["raw_api_key"] is not None
    assert data["raw_api_key"].startswith("cm_live_")
    assert data["session_token"] is not None

    # Verify session cookie was set
    assert settings.SESSION_COOKIE_NAME in res.cookies

    # 2. Duplicate signup fails with 409
    dup_res = await async_client.post("/v1/auth/signup", json=signup_payload)
    assert dup_res.status_code == 409

    # 3. Short password fails with 400 or 422
    short_res = await async_client.post(
        "/v1/auth/signup",
        json={"email": "other@cachemind.io", "password": "short"},
    )
    assert short_res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_login_and_logout_flow(async_client: AsyncClient):
    # Create user
    await async_client.post(
        "/v1/auth/signup",
        json={
            "email": "user.login@cachemind.io",
            "password": "Password12345!",
            "full_name": "Login Tester",
        },
    )

    # 1. Failed login with wrong password
    fail_res = await async_client.post(
        "/v1/auth/login",
        json={"email": "user.login@cachemind.io", "password": "WrongPassword!"},
    )
    assert fail_res.status_code == 401

    # 2. Successful login
    login_res = await async_client.post(
        "/v1/auth/login",
        json={"email": "user.login@cachemind.io", "password": "Password12345!"},
    )
    assert login_res.status_code == 200
    assert settings.SESSION_COOKIE_NAME in login_res.cookies

    # 3. Get /me with cookie
    me_res = await async_client.get("/v1/auth/me")
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user"]["email"] == "user.login@cachemind.io"

    # 4. Logout
    logout_res = await async_client.post("/v1/auth/logout")
    assert logout_res.status_code == 200

    # 5. Subsequent /me fails
    me_after_logout = await async_client.get("/v1/auth/me")
    assert me_after_logout.status_code == 401


@pytest.mark.asyncio
async def test_workspace_and_project_provisioning(async_client: AsyncClient):
    # Signup
    signup_res = await async_client.post(
        "/v1/auth/signup",
        json={
            "email": "workspace.owner@cachemind.io",
            "password": "WorkspacePassword123!",
            "full_name": "Workspace Owner",
        },
    )
    assert signup_res.status_code == 201

    # 1. Create a second workspace
    ws_res = await async_client.post(
        "/v1/auth/workspaces",
        json={"name": "Second Enterprise Org"},
    )
    assert ws_res.status_code == 201
    ws_data = ws_res.json()
    assert ws_data["name"] == "Second Enterprise Org"
    assert ws_data["role"] == "owner"
    second_tenant_id = ws_data["id"]

    # 2. List workspaces
    list_ws = await async_client.get("/v1/auth/workspaces")
    assert list_ws.status_code == 200
    workspaces = list_ws.json()
    assert len(workspaces) >= 2

    # 3. Switch active workspace
    select_res = await async_client.post(f"/v1/auth/workspaces/{second_tenant_id}/select")
    assert select_res.status_code == 200
    assert select_res.json()["active_tenant"]["id"] == second_tenant_id

    # 4. Create new project in second workspace
    proj_res = await async_client.post(
        "/v1/auth/projects",
        json={"name": "Inference Microservice"},
    )
    assert proj_res.status_code == 201
    proj_data = proj_res.json()
    assert proj_data["name"] == "Primary Project Key"
    assert proj_data["raw_key"].startswith("cm_live_")
    new_project_id = proj_data["project_id"]
    issued_key = proj_data["raw_key"]
    key_id = proj_data["id"]

    # 5. List projects
    projects_res = await async_client.get("/v1/auth/projects")
    assert projects_res.status_code == 200
    proj_names = [p["name"] for p in projects_res.json()]
    assert "Inference Microservice" in proj_names

    # 6. Issue an additional API key
    key_res = await async_client.post(
        "/v1/auth/keys",
        json={"project_id": new_project_id, "name": "CI/CD Deployment Key"},
    )
    assert key_res.status_code == 201
    second_raw_key = key_res.json()["raw_key"]
    assert second_raw_key.startswith("cm_live_")

    # 7. List keys for project
    keys_list = await async_client.get(f"/v1/auth/keys?project_id={new_project_id}")
    assert keys_list.status_code == 200
    assert len(keys_list.json()) == 2

    # 8. Use newly provisioned API key on data plane (/v1/chat/completions)
    chat_res = await async_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {issued_key}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hello auth test"}],
        },
    )
    assert chat_res.status_code == 200
    assert "choices" in chat_res.json()

    # 9. Revoke key and verify data plane fails
    revoke_res = await async_client.delete(f"/v1/auth/keys/{key_id}")
    assert revoke_res.status_code == 200

    revoked_chat_res = await async_client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {issued_key}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hello after revoke"}],
        },
    )
    assert revoked_chat_res.status_code == 401
