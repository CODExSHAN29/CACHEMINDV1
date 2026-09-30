import pytest
from backend.caching.factory import get_cache_backend
from backend.caching.fingerprint import compute_exact_request_hash
from backend.caching.invalidation import CacheManagementService, CachePurgeRequest
from backend.caching.models import CachedResponse
from backend.caching.warmer import CacheWarmer, WarmItem
from backend.normalization.models import NormalizedInferenceRequest, NormalizedMessage
from backend.semantic.factory import get_semantic_cache_service


@pytest.mark.asyncio
async def test_cache_delete_exact_key():
    backend = get_cache_backend()
    project_id = "test_project_1"
    key_hash = "abc123hash"

    cached = CachedResponse(
        id="resp-1",
        model="gpt-4o",
        created=1700000000,
        content="Cached response text",
        created_at=1700000000.0,
        ttl_seconds=3600,
        exact_request_hash=key_hash,
    )
    await backend.set(project_id, key_hash, cached)

    # Check key exists
    ins = await CacheManagementService.inspect_key(project_id, key_hash)
    assert ins.exists is True
    assert ins.content_preview == "Cached response text"

    # Delete key
    deleted = await CacheManagementService.delete_exact_key(project_id, key_hash)
    assert deleted is True

    # Check key no longer exists
    ins_after = await CacheManagementService.inspect_key(project_id, key_hash)
    assert ins_after.exists is False


@pytest.mark.asyncio
async def test_cache_list_keys():
    backend = get_cache_backend()
    project_id = "test_project_list"

    for i in range(5):
        key = f"hash_{i}"
        cached = CachedResponse(
            id=f"resp-{i}",
            model="gpt-4o",
            created=1700000000,
            content=f"Response {i}",
            created_at=1700000000.0,
            ttl_seconds=3600,
            exact_request_hash=key,
        )
        await backend.set(project_id, key, cached)

    keys = await CacheManagementService.list_keys(project_id, limit=10)
    assert len(keys) == 5
    assert all(k.startswith("hash_") for k in keys)


@pytest.mark.asyncio
async def test_cache_purge():
    backend = get_cache_backend()
    project_id = "purge_project"

    for i in range(3):
        cached = CachedResponse(
            id=f"resp-purge-{i}",
            model="gpt-4o" if i < 2 else "claude-3-5-sonnet",
            created=1700000000,
            content=f"Purge Response {i}",
            created_at=1700000000.0,
            ttl_seconds=3600,
            exact_request_hash=f"purge_hash_{i}",
            tags=["finance"] if i == 0 else ["general"],
            namespace="v1" if i == 0 else "v2",
        )
        await backend.set(project_id, f"purge_hash_{i}", cached)

    # Scoped purge for model=gpt-4o
    result = await CacheManagementService.purge_cache(
        tenant_id="tenant_1",
        project_id=project_id,
        model="gpt-4o",
    )
    assert result.purged_l1 == 2

    # Verify only claude-3-5-sonnet remains
    remaining = await CacheManagementService.list_keys(project_id)
    assert len(remaining) == 1
    assert remaining[0] == "purge_hash_2"


@pytest.mark.asyncio
async def test_cache_warmer():
    tenant_id = "tenant_warm"
    project_id = "proj_warm"

    items = [
        WarmItem(
            prompt="What is Python?",
            response="Python is a high-level, interpreted programming language.",
            model="gpt-4o",
            tags=["programming", "docs"],
            namespace="knowledge_base",
        ),
        WarmItem(
            prompt="Explain binary search.",
            response="Binary search is an O(log n) search algorithm on sorted arrays.",
            model="gpt-4o",
        ),
    ]

    result = await CacheWarmer.warm_cache(tenant_id, project_id, items)
    assert result.total_items == 2
    assert result.exact_seeded == 2
    assert result.semantic_seeded == 2

    # Verify that exact cache now contains the items
    keys = await CacheManagementService.list_keys(project_id)
    assert len(keys) == 2
