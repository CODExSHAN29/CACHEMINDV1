from typing import Optional, Protocol, runtime_checkable

from backend.caching.models import CachedResponse


@runtime_checkable
class ExactCacheBackend(Protocol):
    """
    Protocol defining the authoritative exact cache storage contract.
    """

    async def get(
        self, project_id: str, exact_request_hash: str
    ) -> Optional[CachedResponse]:
        """Retrieves a cached response if present and not expired, else None."""
        ...

    async def set(
        self,
        project_id: str,
        exact_request_hash: str,
        payload: CachedResponse,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Stores a cached response under project and exact request hash with TTL."""
        ...

    async def delete(self, project_id: str, exact_request_hash: str) -> bool:
        """Removes a cached response."""
        ...

    async def increment_hit(
        self, project_id: str, exact_request_hash: str
    ) -> int:
        """Increments and returns the hit count for telemetry."""
        ...

    async def ping(self) -> bool:
        """Health-checks the cache backend connectivity."""
        ...

    async def purge_project(self, project_id: str) -> int:
        """Purges all cached entries belonging to a project."""
        ...

    async def list_keys(self, project_id: str, limit: int = 100) -> list[str]:
        """Lists cached exact request hashes under a project."""
        ...

    async def clear(self) -> None:
        """Clears all entries (used primarily in test suites)."""
        ...
