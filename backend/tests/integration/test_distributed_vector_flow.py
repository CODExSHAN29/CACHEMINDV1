import pytest
import time
from backend.app.config import settings
from backend.semantic.factory import SemanticCacheFactory
from backend.semantic.pgvector_backend import PgVectorSemanticBackend
from backend.semantic.qdrant_backend import QdrantSemanticBackend
from backend.semantic.vector_index import VectorIndex


@pytest.mark.asyncio
async def test_semantic_factory_backend_selection(monkeypatch):
    # 1. Memory backend
    monkeypatch.setattr(settings, "VECTOR_BACKEND", "memory")
    mem_backend = SemanticCacheFactory.get_vector_backend()
    assert mem_backend is not None

    # 2. PgVector backend
    monkeypatch.setattr(settings, "VECTOR_BACKEND", "pgvector")
    pg_backend = SemanticCacheFactory.get_vector_backend()
    assert isinstance(pg_backend, PgVectorSemanticBackend)

    # 3. Qdrant backend
    monkeypatch.setattr(settings, "VECTOR_BACKEND", "qdrant")
    qdrant_backend = SemanticCacheFactory.get_vector_backend()
    assert isinstance(qdrant_backend, QdrantSemanticBackend)


@pytest.mark.asyncio
async def test_pgvector_end_to_end_insertion_and_search(db_session):
    backend = PgVectorSemanticBackend()
    await backend.clear()

    scope = "integration_test_scope_999"
    exact_hash = "integration_req_hash_999"
    embedding = [0.25] * 384
    resp = {"id": "chatcmpl-test", "choices": [{"message": {"role": "assistant", "content": "PGVector OK"}}]}

    # Insert into PostgreSQL/SQLite storage
    await backend.insert(
        scope_hash=scope,
        exact_request_hash=exact_hash,
        vector=embedding,
        response_payload=resp,
        created_at=time.time(),
        input_text="Testing pgvector integration flow",
        tenant_id="tenant_prod",
        project_id="proj_prod",
    )

    # Search
    hits = await backend.search(query_vector=embedding, scope_hash=scope, top_k=2)
    assert len(hits) == 1
    assert hits[0].exact_request_hash == exact_hash
    assert hits[0].response_payload["choices"][0]["message"]["content"] == "PGVector OK"

    # Clean up
    await backend.clear()
