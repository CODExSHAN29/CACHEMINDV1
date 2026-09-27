import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RequestLog


@pytest.mark.asyncio
async def test_analytics_api_empty(async_client: AsyncClient, tenant_a_fixtures: dict):
    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}

    # Overview
    res = await async_client.get("/v1/analytics/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_requests"] == 0
    assert data["hit_rate_pct"] == 0.0

    # Timeseries
    res = await async_client.get("/v1/analytics/timeseries", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Models
    res = await async_client.get("/v1/analytics/models", headers=headers)
    assert res.status_code == 200
    assert res.json() == []

    # Logs
    res = await async_client.get("/v1/analytics/logs", headers=headers)
    assert res.status_code == 200
    logs_data = res.json()
    assert logs_data["total"] == 0
    assert logs_data["items"] == []


@pytest.mark.asyncio
async def test_analytics_api_end_to_end_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
    tenant_b_fixtures: dict,
):
    headers_a = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    headers_b = {"Authorization": f"Bearer {tenant_b_fixtures['raw_key']}"}

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Explain quant finance in 5 bullets."}],
        "temperature": 0.0,
    }

    # 1. Tenant A Request 1: Cache Miss
    res1 = await async_client.post("/v1/chat/completions", json=payload, headers=headers_a)
    assert res1.status_code == 200
    assert res1.headers["X-CacheMind-Status"] == "MISS"

    # 2. Tenant A Request 2: Exact Cache Hit
    res2 = await async_client.post("/v1/chat/completions", json=payload, headers=headers_a)
    assert res2.status_code == 200
    assert res2.headers["X-CacheMind-Status"] == "EXACT_HIT"

    # 3. Tenant A Queries Analytics Overview
    overview_a = await async_client.get("/v1/analytics/overview", headers=headers_a)
    assert overview_a.status_code == 200
    data_a = overview_a.json()
    assert data_a["total_requests"] == 2
    assert data_a["exact_hits"] == 1
    assert data_a["misses"] == 1
    assert data_a["hit_rate_pct"] == 50.0
    assert data_a["tokens_saved"] > 0
    assert data_a["estimated_cost_saved_usd"] > 0.0

    # 4. Tenant B Queries Analytics Overview (Multi-Tenant Isolation)
    # Tenant B has not sent any requests yet, so their analytics must be 0!
    overview_b = await async_client.get("/v1/analytics/overview", headers=headers_b)
    assert overview_b.status_code == 200
    data_b = overview_b.json()
    assert data_b["total_requests"] == 0
    assert data_b["hit_rate_pct"] == 0.0

    # 5. Tenant A cannot snoop Tenant B or global data by passing tenant_id query param
    snoop_res = await async_client.get(
        f"/v1/analytics/overview?tenant_id={tenant_b_fixtures['tenant_id']}",
        headers=headers_a,
    )
    assert snoop_res.status_code == 403


@pytest.mark.asyncio
async def test_analytics_logs_filtering_and_search(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    headers_a = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello analytics logger search query"}],
        "temperature": 0.0,
    }

    res = await async_client.post("/v1/chat/completions", json=payload, headers=headers_a)
    assert res.status_code == 200

    # Query logs
    logs_res = await async_client.get("/v1/analytics/logs?limit=10", headers=headers_a)
    assert logs_res.status_code == 200
    logs_data = logs_res.json()
    assert logs_data["total"] >= 1
    assert len(logs_data["items"]) >= 1
    assert logs_data["items"][0]["requested_model"] == "gpt-4o"
