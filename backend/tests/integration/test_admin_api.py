import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_api_end_to_end_provisioning(async_client: AsyncClient, tenant_a_fixtures: dict):
    admin_headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}

    # 1. Create Tenant
    t_resp = await async_client.post(
        "/v1/admin/tenants",
        json={"name": "Enterprise Test Org"},
        headers=admin_headers,
    )
    assert t_resp.status_code == 201
    tenant = t_resp.json()
    assert tenant["name"] == "Enterprise Test Org"
    tenant_id = tenant["id"]

    # 2. List Tenants
    t_list_resp = await async_client.get("/v1/admin/tenants", headers=admin_headers)
    assert t_list_resp.status_code == 200
    assert any(t["id"] == tenant_id for t in t_list_resp.json())

    # 3. Create Project
    p_resp = await async_client.post(
        "/v1/admin/projects",
        json={"tenant_id": tenant_id, "name": "Production Bot App"},
        headers=admin_headers,
    )
    assert p_resp.status_code == 201
    project = p_resp.json()
    assert project["name"] == "Production Bot App"
    project_id = project["id"]

    # 4. List Projects
    p_list_resp = await async_client.get(
        f"/v1/admin/projects?tenant_id={tenant_id}", headers=admin_headers
    )
    assert p_list_resp.status_code == 200
    assert len(p_list_resp.json()) == 1

    # 5. Generate New API Key
    k_resp = await async_client.post(
        "/v1/admin/keys",
        json={"project_id": project_id, "name": "Prod Ingest Key", "role": "inference"},
        headers=admin_headers,
    )
    assert k_resp.status_code == 201
    key_data = k_resp.json()
    assert "raw_api_key" in key_data
    raw_key = key_data["raw_api_key"]
    key_id = key_data["id"]

    # 6. Test Inference with newly generated API key
    new_headers = {"Authorization": f"Bearer {raw_key}"}
    chat_resp = await async_client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello new key!"}]},
        headers=new_headers,
    )
    assert chat_resp.status_code == 200

    # 7. Revoke API Key
    del_k_resp = await async_client.delete(f"/v1/admin/keys/{key_id}", headers=admin_headers)
    assert del_k_resp.status_code == 200
    assert del_k_resp.json()["revoked"] is True

    # 8. Attempt inference with revoked key -> Must fail 401 Unauthorized
    chat_revoked_resp = await async_client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Should fail"}]},
        headers=new_headers,
    )
    assert chat_revoked_resp.status_code == 401

    # 9. Get Cluster Stats
    stats_resp = await async_client.get("/v1/admin/stats", headers=admin_headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_tenants"] >= 2  # tenant_a + newly created
    assert stats["total_projects"] >= 2
    assert stats["total_api_keys"] >= 2
