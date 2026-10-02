import pytest
from httpx import AsyncClient

from backend.app.config import settings
from backend.caching.factory import get_cache_backend


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

    # Upstream mock response should reflect the masked content, not raw email/card
    data = resp.json()
    reply = data["choices"][0]["message"]["content"]
    assert "[REDACTED_EMAIL]" in reply
    assert "[REDACTED_CREDIT_CARD]" in reply
    assert "user.john@example.com" not in reply
    assert "4532015112830366" not in reply

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
async def test_pii_client_downgrade_to_passthrough_prevented(async_client: AsyncClient, tenant_a_fixtures: dict):
    """
    Verifies that when server policy is 'mask' (the default), a client cannot
    downgrade to 'passthrough' via X-CacheMind-PII-Mode header.
    The effective policy remains 'mask' and PII is redacted.
    """
    headers = {
        "Authorization": f"Bearer {tenant_a_fixtures['raw_key']}",
        "X-CacheMind-PII-Mode": "passthrough",
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Here is my private email: contact.ceo@company.org"}
        ],
        "temperature": 0.0,
    }

    resp = await async_client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    reply = data["choices"][0]["message"]["content"]
    assert "[REDACTED_EMAIL]" in reply
    assert "contact.ceo@company.org" not in reply


@pytest.mark.asyncio
async def test_invalid_pii_mode_rejected_with_400(async_client: AsyncClient, tenant_a_fixtures: dict):
    """
    Verifies that passing an unsupported or malformed PII mode returns HTTP 400 Bad Request.
    """
    headers = {
        "Authorization": f"Bearer {tenant_a_fixtures['raw_key']}",
        "X-CacheMind-PII-Mode": "disable_security_checks",
    }

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello world"}],
    }

    resp = await async_client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 400
    data = resp.json()
    assert "Invalid PII mode 'disable_security_checks'" in data.get("detail", "")


@pytest.mark.asyncio
async def test_structured_multipart_content_pii_masking(async_client: AsyncClient, tenant_a_fixtures: dict):
    """
    Verifies that multi-part content arrays ([{'type': 'text', 'text': '...'}]) have their
    text parts sanitized while non-text parts are preserved intact.
    """
    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Billing inquiry for SSN 123-45-6789 and account."},
                    {"type": "image_url", "image_url": {"url": "https://example.com/receipt.jpg"}},
                ],
            }
        ],
        "temperature": 0.0,
    }

    resp = await async_client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    reply = data["choices"][0]["message"]["content"]
    assert "[REDACTED_SSN]" in reply
    assert "123-45-6789" not in reply


@pytest.mark.asyncio
async def test_cache_warming_enforces_pii_sanitization(async_client: AsyncClient, tenant_a_fixtures: dict):
    """
    Verifies that cache pre-warming (/v1/cache/warm) sanitizes PII in prompts and responses
    so raw PII is never seeded into the cache.
    """
    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}

    warm_payload = {
        "items": [
            {
                "prompt": "Customer support for alice.smith@secure-bank.com",
                "completion": "Account verified for customer with SSN 456-78-1234.",
                "model": "gpt-4o",
            }
        ]
    }

    warm_res = await async_client.post("/v1/cache/warm", json=warm_payload, headers=headers)
    assert warm_res.status_code == 200
    assert warm_res.json()["seeded"] >= 1

    # Now query via chat completions with the same prompt: should hit L1 exact cache with sanitized content
    query_payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Customer support for alice.smith@secure-bank.com"}
        ],
        "temperature": 0.0,
    }

    chat_res = await async_client.post("/v1/chat/completions", json=query_payload, headers=headers)
    assert chat_res.status_code == 200
    assert chat_res.headers.get("X-CacheMind-Status") == "EXACT_HIT"
    reply = chat_res.json()["choices"][0]["message"]["content"]
    assert "[REDACTED_SSN]" in reply
    assert "456-78-1234" not in reply

