import pytest
import time
from backend.caching.factory import get_cache_backend
from backend.caching.invalidation import CacheManagementService
from backend.caching.models import CachedResponse
from backend.caching.warmer import CacheWarmer, WarmItem
from backend.semantic.factory import get_semantic_cache_service
from backend.semantic.vector_index import VectorIndex


@pytest.mark.asyncio
async def test_in_memory_vector_index_scoped_deletion():
    index = VectorIndex(dim=4, threshold=0.8)

    # Insert entries for Tenant 1 - Project A
    await index.insert(
        scope_hash="scope_1",
        exact_request_hash="hash_1a",
        vector=[1.0, 0.0, 0.0, 0.0],
        response_payload={"answer": "1a"},
        created_at=time.time(),
        tenant_id="tenant_1",
        project_id="proj_a",
        model="gpt-4o",
        namespace="prod",
        tags=["tag1", "tag2"],
    )
    await index.insert(
        scope_hash="scope_1",
        exact_request_hash="hash_1b",
        vector=[0.0, 1.0, 0.0, 0.0],
        response_payload={"answer": "1b"},
        created_at=time.time(),
        tenant_id="tenant_1",
        project_id="proj_a",
        model="claude-3-5-sonnet",
        namespace="dev",
        tags=["tag1"],
    )
    # Insert entry for Tenant 1 - Project B (same scope)
    await index.insert(
        scope_hash="scope_1",
        exact_request_hash="hash_1c",
        vector=[0.0, 0.0, 1.0, 0.0],
        response_payload={"answer": "1c"},
        created_at=time.time(),
        tenant_id="tenant_1",
        project_id="proj_b",
        model="gpt-4o",
        namespace="prod",
    )
    # Insert entry for Tenant 2 - Project C (same scope)
    await index.insert(
        scope_hash="scope_1",
        exact_request_hash="hash_2a",
        vector=[0.0, 0.0, 0.0, 1.0],
        response_payload={"answer": "2a"},
        created_at=time.time(),
        tenant_id="tenant_2",
        project_id="proj_c",
        model="gpt-4o",
    )

    # 1. Delete by scope filters: Tenant 1, Project A, model="gpt-4o"
    del_count = await index.delete_by_scope_filters(
        tenant_id="tenant_1",
        project_id="proj_a",
        model="gpt-4o",
    )
    assert del_count == 1
    assert await index.inspect_key("hash_1a") is None
    assert await index.inspect_key("hash_1b") is not None
    assert await index.inspect_key("hash_1c") is not None
    assert await index.inspect_key("hash_2a") is not None

    # 2. Delete by project: Tenant 1, Project A
    del_count_proj = await index.delete_by_project(
        tenant_id="tenant_1",
        project_id="proj_a",
    )
    assert del_count_proj == 1  # remaining hash_1b deleted
    assert await index.inspect_key("hash_1b") is None
    # Tenant 1 Project B and Tenant 2 Project C remain untouched
    assert await index.inspect_key("hash_1c") is not None
    assert await index.inspect_key("hash_2a") is not None


@pytest.mark.asyncio
async def test_cache_purge_project_isolation():
    cache_backend = get_cache_backend()
    semantic_service = get_semantic_cache_service()

    # Pre-warm Project A
    items_a = [
        WarmItem(
            prompt="Hello from Project A",
            response="Answer for Project A",
            model="gpt-4o",
        )
    ]
    await CacheWarmer.warm_cache(
        tenant_id="t_shared",
        project_id="proj_alpha",
        items=items_a,
    )

    # Pre-warm Project B
    items_b = [
        WarmItem(
            prompt="Hello from Project B",
            response="Answer for Project B",
            model="gpt-4o",
        )
    ]
    await CacheWarmer.warm_cache(
        tenant_id="t_shared",
        project_id="proj_beta",
        items=items_b,
    )

    keys_a = await CacheManagementService.list_keys("proj_alpha")
    keys_b = await CacheManagementService.list_keys("proj_beta")
    assert len(keys_a) == 1
    assert len(keys_b) == 1

    # Purge only Project A
    purge_res = await CacheManagementService.purge_cache(
        tenant_id="t_shared",
        project_id="proj_alpha",
    )
    assert purge_res.purged_l1 == 1
    assert purge_res.purged_l2 >= 1

    # Verify Project A is empty
    assert len(await CacheManagementService.list_keys("proj_alpha")) == 0
    # Verify Project B is intact
    assert len(await CacheManagementService.list_keys("proj_beta")) == 1
    ins_b = await CacheManagementService.inspect_key("proj_beta", keys_b[0])
    assert ins_b.exists is True


@pytest.mark.asyncio
async def test_cross_project_key_authorization():
    cache_backend = get_cache_backend()

    key_hash = "secret_key_123"
    cached = CachedResponse(
        id="resp-secret",
        model="gpt-4o",
        created=1700000000,
        content="Project 1 secret data",
        created_at=1700000000.0,
        ttl_seconds=3600,
        exact_request_hash=key_hash,
    )
    await cache_backend.set("project_owner", key_hash, cached)

    # Foreign project inspection fails
    foreign_ins = await CacheManagementService.inspect_key("project_attacker", key_hash)
    assert foreign_ins.exists is False

    # Foreign project deletion fails to delete owner key
    deleted = await CacheManagementService.delete_exact_key("project_attacker", key_hash)
    assert deleted is False

    # Key still exists in owner project
    owner_ins = await CacheManagementService.inspect_key("project_owner", key_hash)
    assert owner_ins.exists is True

    # Owner project deletion succeeds
    owner_del = await CacheManagementService.delete_exact_key("project_owner", key_hash)
    assert owner_del is True
    assert (await CacheManagementService.inspect_key("project_owner", key_hash)).exists is False
