import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cache_warm_and_inspect_api(async_client: AsyncClient, tenant_a_fixtures: dict):
    headers = {"Authorization": f"Bearer {tenant_a_fixtures['raw_key']}"}

    # 1. Warm cache with 2 Q&A pairs
    warm_payload = {
        "project_id": tenant_a_fixtures["project_id"],
        "items": [
            {
                "prompt": "What is CacheMind?",
                "response": "CacheMind is a production-grade AI caching and security gateway.",
                "model": "gpt-4o",
                "tags": ["gateway", "overview"],
                "namespace": "docs",
            },
            {
                "prompt": "What is Python asyncio?",
                "response": "Asyncio is a library to write concurrent code using async/await syntax.",
                "model": "gpt-4o",
            },
        ],
    }

    warm_resp = await async_client.post("/v1/cache/warm", json=warm_payload, headers=headers)
    assert warm_resp.status_code == 200
    warm_data = warm_resp.json()
    assert warm_data["total_items"] == 2
    assert warm_data["exact_seeded"] == 2
    assert warm_data["semantic_seeded"] == 2

    # 2. List cache keys
    keys_resp = await async_client.get("/v1/cache/keys", headers=headers)
    assert keys_resp.status_code == 200
    keys_data = keys_resp.json()
    assert keys_data["count"] == 2
    seeded_key = keys_data["keys"][0]

    # 3. Inspect the seeded key
    inspect_resp = await async_client.get(f"/v1/cache/inspect/{seeded_key}", headers=headers)
    assert inspect_resp.status_code == 200
    inspect_data = inspect_resp.json()
    assert inspect_data["exists"] is True
    assert inspect_data["model"] == "gpt-4o"

    # 4. Send exact chat completion request matching seeded prompt -> Should be EXACT_HIT
    chat_payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "What is CacheMind?"}],
        "temperature": 0.0,
    }
    chat_headers = {
        **headers,
        "X-CacheMind-Namespace": "docs",
        "X-CacheMind-Tags": "gateway,overview",
    }
    chat_resp = await async_client.post("/v1/chat/completions", json=chat_payload, headers=chat_headers)
    assert chat_resp.status_code == 200
    assert chat_resp.headers.get("X-CacheMind-Status") == "EXACT_HIT"
    chat_data = chat_resp.json()
    assert "CacheMind is a production-grade" in chat_data["choices"][0]["message"]["content"]

    # 5. Delete the key surgically
    del_resp = await async_client.delete(f"/v1/cache/keys/{seeded_key}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # 6. Purge remaining cache entries
    purge_payload = {"project_id": tenant_a_fixtures["project_id"]}
    purge_resp = await async_client.post("/v1/cache/purge", json=purge_payload, headers=headers)
    assert purge_resp.status_code == 200
    assert purge_resp.json()["success"] is True

    # 7. Check that keys list is now empty
    keys_after = await async_client.get("/v1/cache/keys", headers=headers)
    assert keys_after.json()["count"] == 0
