import pytest
from httpx import AsyncClient

from backend.app.config import settings
from backend.caching.factory import get_cache_backend
from backend.providers.factory import get_provider
from backend.semantic.factory import get_semantic_cache_service


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


@pytest.mark.asyncio
async def test_pii_server_block_client_passthrough_blocked_with_no_side_effects(
    async_client: AsyncClient, tenant_a_fixtures: dict, monkeypatch: pytest.MonkeyPatch
):
    """
    Verifies that when server PII policy is 'block', a client passing 'passthrough'
    cannot downgrade the policy. A prompt containing PII is rejected with HTTP 400,
    with zero upstream provider calls, no L1 exact cache entries, and no L2 semantic entries.
    """
    monkeypatch.setattr(settings, "PII_MASKING_MODE", "block")

    cache_backend = get_cache_backend()
    semantic_service = get_semantic_cache_service()
    provider = get_provider("openai")
    provider.reset()

    headers = {
        "Authorization": f"Bearer {tenant_a_fixtures['raw_key']}",
        "X-CacheMind-PII-Mode": "passthrough",
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "My private secret key is sk-1234567890abcdef1234567890"}
        ],
        "temperature": 0.0,
    }

    resp = await async_client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 400
    data = resp.json()
    assert "pii_blocked" in str(data) or "entities" in str(data) or "PII" in str(data)

    # Zero side-effects assertions
    assert provider.call_count == 0
    assert len(cache_backend._store) == 0
    assert len(semantic_service.backend._entries_by_scope) == 0


@pytest.mark.asyncio
async def test_cache_warming_under_block_policy_records_safe_failure(
    async_client: AsyncClient, tenant_a_fixtures: dict, monkeypatch: pytest.MonkeyPatch
):
    """
    Verifies that when server policy is 'block', cache pre-warming with PII items
    records a failure safely without leaking sensitive entity values into error messages.
    """
    monkeypatch.setattr(settings, "PII_MASKING_MODE", "block")

    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}
    sensitive_token = "sk-1234567890abcdef1234567890"

    warm_payload = {
        "items": [
            {
                "prompt": f"Secret prompt containing key {sensitive_token}",
                "completion": "Secret completion text",
                "model": "gpt-4o",
            }
        ]
    }

    res = await async_client.post("/v1/cache/warm", json=warm_payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["failed_count"] == 1
    assert data["exact_seeded"] == 0
    assert data["semantic_seeded"] == 0
    assert len(data["errors"]) == 1
    err = data["errors"][0]
    assert "PII detected and blocked by policy" in err
    assert sensitive_token not in err


@pytest.mark.asyncio
async def test_session_authenticated_pii_masking_flow(async_client: AsyncClient):
    """
    Verifies that user session authentication (via session cookie) enforces
    PII sanitization just like API key authentication.
    """
    # 1. Sign up to create session
    signup_payload = {
        "email": "pii.session.user@cachemind.io",
        "password": "SecurePassword123!",
        "full_name": "PII Session Tester",
        "workspace_name": "PII Session Lab",
    }
    signup_res = await async_client.post("/v1/auth/signup", json=signup_payload)
    assert signup_res.status_code == 201

    # 2. Query chat completions using the active session cookie
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "Confidential contact: support.vip@enterprise.com and API key sk-9876543210abcdef9876543210",
            }
        ],
        "temperature": 0.0,
    }

    resp = await async_client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    reply = data["choices"][0]["message"]["content"]
    assert "[REDACTED_EMAIL]" in reply
    assert "[REDACTED_SECRET]" in reply
    assert "support.vip@enterprise.com" not in reply
    assert "sk-9876543210abcdef9876543210" not in reply


