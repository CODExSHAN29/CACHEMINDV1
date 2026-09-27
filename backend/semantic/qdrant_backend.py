"""
Qdrant Distributed Vector Semantic Cache Backend.

Provides high-throughput distributed vector indexing and search via Qdrant's
REST API with multi-tenant filtering on scope_hash and tenant_id.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from backend.app.config import settings
from backend.semantic.backend import SemanticCacheBackend
from backend.semantic.vector_index import SemanticCandidate

logger = logging.getLogger("cachemind.semantic.qdrant")


class QdrantSemanticBackend(SemanticCacheBackend):
    """
    Distributed L2 semantic cache backend communicating with Qdrant vector database.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
        default_threshold: float = 0.92,
        dimension: int = 384,
    ) -> None:
        self.url = (url or settings.QDRANT_URL or "http://localhost:6333").rstrip("/")
        self.api_key = api_key or settings.QDRANT_API_KEY
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self.default_threshold = default_threshold
        self.dimension = dimension
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    async def _ensure_collection(self, client: httpx.AsyncClient) -> None:
        if self._initialized:
            return
        try:
            resp = await client.get(f"{self.url}/collections/{self.collection_name}", headers=self._get_headers())
            if resp.status_code == 404:
                # Create collection
                create_payload = {
                    "vectors": {
                        "size": self.dimension,
                        "distance": "Cosine",
                    }
                }
                await client.put(
                    f"{self.url}/collections/{self.collection_name}",
                    json=create_payload,
                    headers=self._get_headers(),
                )
                logger.info("Created Qdrant collection '%s'", self.collection_name)
            self._initialized = True
        except Exception as exc:
            logger.warning("Failed to initialize Qdrant collection: %s", exc)

    async def insert(
        self,
        scope_hash: str,
        exact_request_hash: str,
        vector: List[float],
        response_payload: dict,
        created_at: float,
        input_text: str = "",
        system_prompt: Optional[str] = None,
        provider: str = "unknown",
        model: str = "unknown",
        ttl_seconds: Optional[int] = None,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        import uuid
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, exact_request_hash))
        payload = {
            "exact_request_hash": exact_request_hash,
            "scope_hash": scope_hash,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "provider": provider,
            "model": model,
            "system_prompt": system_prompt,
            "input_text": input_text,
            "namespace": namespace,
            "tags": tags or [],
            "response_payload": response_payload,
            "created_at": created_at,
            "ttl_seconds": ttl_seconds,
            "expires_at": created_at + (ttl_seconds or settings.DEFAULT_CACHE_TTL_SECONDS),
        }

        point = {
            "id": point_id,
            "vector": vector,
            "payload": payload,
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            await self._ensure_collection(client)
            resp = await client.put(
                f"{self.url}/collections/{self.collection_name}/points",
                json={"points": [point]},
                headers=self._get_headers(),
            )
            resp.raise_for_status()

    async def search(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
    ) -> List[SemanticCandidate]:
        threshold = similarity_threshold if similarity_threshold is not None else self.default_threshold
        now_ts = time.time()

        search_payload = {
            "vector": query_vector,
            "limit": top_k,
            "score_threshold": threshold,
            "filter": {
                "must": [
                    {"key": "scope_hash", "match": {"value": scope_hash}},
                    {"key": "expires_at", "range": {"gt": now_ts}},
                ]
            },
            "with_payload": True,
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            await self._ensure_collection(client)
            resp = await client.post(
                f"{self.url}/collections/{self.collection_name}/points/search",
                json=search_payload,
                headers=self._get_headers(),
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            hits = data.get("result", [])

            candidates = []
            for hit in hits:
                payload = hit.get("payload", {})
                candidates.append(
                    SemanticCandidate(
                        exact_request_hash=payload.get("exact_request_hash", ""),
                        scope_hash=payload.get("scope_hash", scope_hash),
                        similarity=float(hit.get("score", 0.0)),
                        response_payload=payload.get("response_payload", {}),
                        created_at=float(payload.get("created_at", 0.0)),
                    )
                )
            return candidates

    async def delete(self, exact_request_hash: str) -> bool:
        import uuid
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, exact_request_hash))
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{self.url}/collections/{self.collection_name}/points/delete",
                json={"points": [point_id]},
                headers=self._get_headers(),
            )
            return resp.status_code == 200

    async def delete_by_scope(self, scope_hash: str) -> int:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{self.url}/collections/{self.collection_name}/points/delete",
                json={"filter": {"must": [{"key": "scope_hash", "match": {"value": scope_hash}}]}},
                headers=self._get_headers(),
            )
            return 1 if resp.status_code == 200 else 0

    async def delete_by_tenant(self, tenant_id: str) -> int:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{self.url}/collections/{self.collection_name}/points/delete",
                json={"filter": {"must": [{"key": "tenant_id", "match": {"value": tenant_id}}]}},
                headers=self._get_headers(),
            )
            return 1 if resp.status_code == 200 else 0

    async def inspect_key(self, exact_request_hash: str) -> Optional[Dict[str, Any]]:
        import uuid
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, exact_request_hash))
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{self.url}/collections/{self.collection_name}/points/{point_id}",
                headers=self._get_headers(),
            )
            if resp.status_code != 200:
                return None
            result = resp.json().get("result")
            if not result:
                return None
            payload = result.get("payload", {})
            now = time.time()
            expires_at = payload.get("expires_at", 0.0)
            return {
                "id": point_id,
                "exact_request_hash": exact_request_hash,
                "scope_hash": payload.get("scope_hash"),
                "tenant_id": payload.get("tenant_id"),
                "project_id": payload.get("project_id"),
                "provider": payload.get("provider"),
                "model": payload.get("model"),
                "system_prompt": payload.get("system_prompt"),
                "input_text": payload.get("input_text"),
                "namespace": payload.get("namespace"),
                "tags": payload.get("tags"),
                "created_at": datetime.fromtimestamp(payload.get("created_at", now), tz=timezone.utc).isoformat(),
                "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat() if expires_at else None,
                "ttl_seconds": payload.get("ttl_seconds"),
                "ttl_remaining_seconds": max(0, int(expires_at - now)) if expires_at else None,
                "has_embedding": bool(result.get("vector")),
                "embedding_dimension": len(result.get("vector")) if result.get("vector") else 0,
            }

    async def get_stats(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{self.url}/collections/{self.collection_name}",
                headers=self._get_headers(),
            )
            if resp.status_code == 200:
                data = resp.json().get("result", {})
                return {
                    "backend": "qdrant",
                    "status": data.get("status"),
                    "total_entries": data.get("points_count", 0),
                    "vectors_count": data.get("vectors_count", 0),
                }
            return {"backend": "qdrant", "total_entries": 0, "status": "unknown"}

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.url}/healthz")
                return resp.status_code == 200
        except Exception:
            return False

    async def clear(self) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.delete(f"{self.url}/collections/{self.collection_name}", headers=self._get_headers())
            self._initialized = False
