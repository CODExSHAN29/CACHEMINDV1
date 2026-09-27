import time
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from backend.semantic.qdrant_backend import QdrantSemanticBackend
from backend.semantic.vector_index import SemanticCandidate


@pytest.mark.asyncio
async def test_qdrant_backend_operations():
    backend = QdrantSemanticBackend(
        url="http://mock-qdrant:6333",
        api_key="test-api-key",
        collection_name="test_collection",
        default_threshold=0.88,
        dimension=384,
    )

    req = httpx.Request("GET", "http://mock-qdrant:6333")

    # 1. Ping check
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(200, request=req, json={"status": "ok"})
        assert await backend.ping() is True

    # 2. Insert check
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
        mock_get.return_value = httpx.Response(200, request=req, json={"status": "ok"})
        mock_put.return_value = httpx.Response(200, request=req, json={"result": {"status": "completed"}})

        await backend.insert(
            scope_hash="scope_qdrant_1",
            exact_request_hash="req_qdrant_1",
            vector=[0.1] * 384,
            response_payload={"choices": [{"message": {"content": "Qdrant response"}}]},
            created_at=time.time(),
            tenant_id="tenant_qdrant",
            provider="anthropic",
            model="claude-3-5-sonnet",
        )
        assert mock_put.called

    # 3. Search check
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = httpx.Response(200, request=req, json={"status": "ok"})
        mock_post.return_value = httpx.Response(
            200,
            request=req,
            json={
                "result": [
                    {
                        "id": "mock-uuid",
                        "score": 0.95,
                        "payload": {
                            "exact_request_hash": "req_qdrant_1",
                            "scope_hash": "scope_qdrant_1",
                            "created_at": time.time(),
                            "response_payload": {"choices": [{"message": {"content": "Qdrant hit"}}]},
                        },
                    }
                ]
            },
        )

        candidates = await backend.search(
            query_vector=[0.1] * 384,
            scope_hash="scope_qdrant_1",
            top_k=3,
        )
        assert len(candidates) == 1
        assert isinstance(candidates[0], SemanticCandidate)
        assert candidates[0].exact_request_hash == "req_qdrant_1"
        assert candidates[0].similarity == 0.95

    # 4. Inspect key check
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(
            200,
            request=req,
            json={
                "result": {
                    "payload": {
                        "scope_hash": "scope_qdrant_1",
                        "tenant_id": "tenant_qdrant",
                        "provider": "anthropic",
                        "model": "claude-3-5-sonnet",
                        "created_at": time.time(),
                        "expires_at": time.time() + 3600,
                        "ttl_seconds": 3600,
                    },
                    "vector": [0.1] * 384,
                }
            },
        )
        info = await backend.inspect_key("req_qdrant_1")
        assert info is not None
        assert info["scope_hash"] == "scope_qdrant_1"
        assert info["tenant_id"] == "tenant_qdrant"
        assert info["has_embedding"] is True
        assert info["embedding_dimension"] == 384

    # 5. Delete check
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(200, request=req, json={"result": {"status": "completed"}})
        deleted = await backend.delete("req_qdrant_1")
        assert deleted is True

    # 6. Stats check
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(
            200,
            request=req,
            json={"result": {"status": "green", "points_count": 42, "vectors_count": 42}},
        )
        stats = await backend.get_stats()
        assert stats["backend"] == "qdrant"
        assert stats["total_entries"] == 42
