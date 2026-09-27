"""
SemanticCacheBackend Protocol interface.

Mirrors ExactCacheBackend protocol from Phase 1, but designed for
vector-based search within scope namespaces.
"""

from typing import List, Optional, Protocol, runtime_checkable

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
    ) -> None:
        """Stores a vector entry under scope_hash partition."""
        ...

    async def search(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int = 5,
    ) -> List[SemanticCandidate]:
        """Returns candidate hits within scope partition with similarity >= threshold."""
        ...

    async def delete(self, exact_request_hash: str) -> bool:
        """Deletes entry by exact_request_hash."""
        ...

    async def ping(self) -> bool:
        """Health check."""
        ...

    async def clear(self) -> None:
        """Clears all entries (test isolation)."""
        ...
