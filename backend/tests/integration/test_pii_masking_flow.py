import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_pii_masking_in_chat_completions(async_client: AsyncClient, tenant_a_fixtures: dict):
    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}

    # 1. Send prompt with email and credit card in default mask mode
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "My email is user.john@example.com and card number is 4532015112830366. Summarize this.",
            }
        ],
        "temperature": 0.0,
    }

    resp = await async_client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("X-CacheMind-Status") == "MISS"

    # 2. Re-send identical prompt -> should be an exact cache HIT
    resp2 = await async_client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp2.status_code == 200
    assert resp2.headers.get("X-CacheMind-Status") == "EXACT_HIT"


@pytest.mark.asyncio
async def test_pii_block_mode(async_client: AsyncClient, tenant_a_fixtures: dict):
    headers = {
        "Authorization": f"Bearer {tenant_a_fixtures['raw_key']}",
        "X-CacheMind-PII-Mode": "block",
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Here is my secret API key: sk-1234567890abcdef1234567890"}
        ],
    }

    resp = await async_client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
    assert "pii_blocked" in str(data) or "entities" in str(data)


@pytest.mark.asyncio
async def test_pii_passthrough_mode(async_client: AsyncClient, tenant_a_fixtures: dict):
    headers = {
        "Authorization": f"Bearer {tenant_a_fixtures['raw_key']}",
        "X-CacheMind-PII-Mode": "passthrough",
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Here is my email: contact@company.org"}
        ],
    }

    resp = await async_client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 200
