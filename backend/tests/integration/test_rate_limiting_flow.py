import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.ratelimit.limiter import get_rate_limiter


@pytest.mark.asyncio
async def test_rate_limiting_gateway_ingress_rejection(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}"}
    limiter = get_rate_limiter()

    # Pre-exhaust the tenant's bucket
    tenant_id = tenant_a_fixtures["tenant_id"]
    project_id = tenant_a_fixtures["project_id"]
    bucket = await limiter.get_or_create_bucket(tenant_id, project_id, rpm_limit=2, tpm_limit=500)
    await bucket.consume(requested_tokens=2, estimated_llm_tokens=100)

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Will I be rate limited?"}],
    }

    response = await async_client.post("/v1/chat/completions", headers=headers, json=payload)
    assert response.status_code == 429
    assert response.headers.get("X-RateLimit-Remaining-Requests") == "0"
    assert "Retry-After" in response.headers
    body = response.json()
    assert body["error"]["code"] == "rate_limit_exceeded"
