import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_billing_plans_endpoint(async_client: AsyncClient):
    response = await async_client.get("/v1/billing/plans")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert "starter" in data["plans"]
    assert "pro" in data["plans"]


@pytest.mark.asyncio
async def test_billing_usage_endpoint(async_client: AsyncClient, tenant_a_fixtures: dict):
    admin_headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    response = await async_client.get(
        "/v1/billing/usage?tenant_id=tenant_default&tier=pro",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "pro"
    assert "usage_pct_of_request_limit" in data
    assert "estimated_overage_cost_usd" in data


@pytest.mark.asyncio
async def test_billing_webhook_flow(async_client: AsyncClient):
    payload = {
        "id": "evt_test123",
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "customer": "cus_test123",
                "amount_paid": 19900,
                "status": "paid",
            }
        },
    }
    response = await async_client.post("/v1/billing/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert data["event_type"] == "invoice.payment_succeeded"
