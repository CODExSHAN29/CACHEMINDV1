import asyncio
import pytest
from backend.caching.memory import InMemoryExactCache
from backend.caching.models import CachedResponse
from backend.caching.redis_backend import RedisExactCache


@pytest.mark.asyncio
async def test_in_memory_cache_get_set_delete():
    cache = InMemoryExactCache()
    proj_id = "proj_123"
    req_hash = "hash_abc"

    # Initial state
    assert await cache.get(proj_id, req_hash) is None

    # Store entry
    payload = CachedResponse(
        exact_request_hash=req_hash,
        response_payload={"choices": [{"message": {"content": "Test reply"}}]},
        provider="openai",
        model="gpt-4o",
        ttl_seconds=3600,
    )
    await cache.set(proj_id, req_hash, payload)

    # Retrieve
    retrieved = await cache.get(proj_id, req_hash)
    assert retrieved is not None
    assert retrieved.response_payload["choices"][0]["message"]["content"] == "Test reply"

    # Increment hit
    hits = await cache.increment_hit(proj_id, req_hash)
    assert hits == 1

    # Delete
    assert await cache.delete(proj_id, req_hash) is True
    assert await cache.get(proj_id, req_hash) is None


@pytest.mark.asyncio
async def test_in_memory_cache_ttl_expiration():
    cache = InMemoryExactCache()
    proj_id = "proj_ttl"
    req_hash = "hash_ttl"

    payload = CachedResponse(
        exact_request_hash=req_hash,
        response_payload={"choices": []},
        provider="openai",
        model="gpt-4o",
        ttl_seconds=1,  # 1 second TTL
    )
    # Set with 0 second TTL for instant expiration simulation
    await cache.set(proj_id, req_hash, payload, ttl_seconds=0)
    await asyncio.sleep(0.01)

    # Should be expired immediately
    assert await cache.get(proj_id, req_hash) is None


@pytest.mark.asyncio
async def test_redis_graceful_fail_open_on_unreachable_server():
    # Point to nonexistent port to trigger connection error
    redis_cache = RedisExactCache(redis_url="redis://127.0.0.1:59999/0", socket_timeout=0.1)

    # Should not raise exception, should return None / fail open gracefully
    res = await redis_cache.get("proj_fail", "hash_fail")
    assert res is None

    payload = CachedResponse(
        exact_request_hash="hash_fail",
        response_payload={},
        provider="openai",
        model="gpt-4o",
    )
    # Set should log warning and not crash
    await redis_cache.set("proj_fail", "hash_fail", payload)

    # Ping should return False
    assert await redis_cache.ping() is False
