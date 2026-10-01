"""
SemanticCacheBackend Protocol interface.

Mirrors ExactCacheBackend protocol, but designed for
vector-based search within scope namespaces (in-memory, pgvector, qdrant).
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from backend.semantic.models import SemanticCacheEntry
from backend.semantic.vector_index import SemanticCandidate


@runtime_checkable
class SemanticCacheBackend(Protocol):
    """
    Protocol defining the contract for L2 semantic cache backends.
    """

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
        """Stores a vector entry under scope_hash partition."""
        ...

    async def search(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
    ) -> List[SemanticCandidate]:
        """Returns candidate hits within scope partition with similarity >= threshold."""
        ...

    async def delete(self, exact_request_hash: str) -> bool:
        """Deletes entry by exact_request_hash."""
        ...

    async def delete_by_scope(self, scope_hash: str) -> int:
        """Deletes all entries within a specific scope hash."""
        ...

    async def delete_by_project(self, tenant_id: str, project_id: str) -> int:
        """Deletes all vector entries belonging to a specific project within a tenant."""
        ...

    async def delete_by_scope_filters(
        self,
        tenant_id: str,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Deletes vector entries matching specific tenant, project, and scope filters."""
        ...

    async def delete_by_tenant(self, tenant_id: str) -> int:
        """Deletes all vector entries belonging to a tenant."""
        ...

    async def inspect_key(self, exact_request_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves vector and metadata inspection for a single entry."""
        ...

    async def get_stats(self) -> Dict[str, Any]:
        """Returns backend vector storage statistics."""
        ...

    async def ping(self) -> bool:
        """Health check."""
        ...

    async def clear(self) -> None:
        """Clears all entries (test isolation)."""
        ...

