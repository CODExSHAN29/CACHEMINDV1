import time
import pytest
from sqlalchemy import select
from backend.db.models import SemanticVectorEntry
from backend.db.session import AsyncSessionLocal
from backend.semantic.pgvector_backend import PgVectorSemanticBackend
from backend.semantic.vector_index import SemanticCandidate


@pytest.mark.asyncio
async def test_pgvector_backend_insert_and_search(db_session):
    backend = PgVectorSemanticBackend(session_factory=AsyncSessionLocal, default_threshold=0.85)

    # 1. Clear any prior test entries
    await backend.clear()

    scope = "scope_test_123"
    exact_hash = "exact_req_test_123"
    vec = [0.5] * 384
    payload = {"choices": [{"message": {"content": "Hello distributed cache!"}}]}
    now = time.time()

    # 2. Insert vector entry
    await backend.insert(
        scope_hash=scope,
        exact_request_hash=exact_hash,
        vector=vec,
        response_payload=payload,
        created_at=now,
        input_text="What is distributed caching?",
        provider="openai",
        model="gpt-4o",
        ttl_seconds=3600,
        tenant_id="test_tenant",
        project_id="test_project",
    )

    # 3. Search within scope with identical vector
    hits = await backend.search(query_vector=vec, scope_hash=scope, top_k=5)
    assert len(hits) == 1
    assert isinstance(hits[0], SemanticCandidate)
    assert hits[0].exact_request_hash == exact_hash
    assert hits[0].similarity >= 0.99
    assert hits[0].response_payload["choices"][0]["message"]["content"] == "Hello distributed cache!"

    # 4. Search within different scope yields 0 hits (namespace isolation)
    wrong_scope_hits = await backend.search(query_vector=vec, scope_hash="different_scope", top_k=5)
    assert len(wrong_scope_hits) == 0

    # 5. Inspect key
    inspection = await backend.inspect_key(exact_hash)
    assert inspection is not None
    assert inspection["exact_request_hash"] == exact_hash
    assert inspection["tenant_id"] == "test_tenant"
    assert inspection["provider"] == "openai"
    assert inspection["has_embedding"] is True
    assert inspection["embedding_dimension"] == 384

    # 6. Stats check
    stats = await backend.get_stats()
    assert stats["total_entries"] >= 1
    assert stats["backend"] == "pgvector"

    # 7. Ping check
    is_alive = await backend.ping()
    assert is_alive is True

    # 8. Delete by exact hash
    deleted = await backend.delete(exact_hash)
    assert deleted is True

    # 9. Verify deleted
    hits_after = await backend.search(query_vector=vec, scope_hash=scope, top_k=5)
    assert len(hits_after) == 0


@pytest.mark.asyncio
async def test_pgvector_backend_ttl_expiry(db_session):
    backend = PgVectorSemanticBackend(session_factory=AsyncSessionLocal, default_threshold=0.85)
    await backend.clear()

    scope = "scope_expired_test"
    exact_hash = "exact_expired_1"
    vec = [0.1] * 384
    payload = {"choices": [{"message": {"content": "Old response"}}]}

    # Insert entry with TTL = 1 second, created 10 seconds ago
    past_time = time.time() - 10.0
    await backend.insert(
        scope_hash=scope,
        exact_request_hash=exact_hash,
        vector=vec,
        response_payload=payload,
        created_at=past_time,
        ttl_seconds=1,
    )

    # Search should ignore expired entry
    hits = await backend.search(query_vector=vec, scope_hash=scope, top_k=5)
    assert len(hits) == 0

    await backend.clear()
