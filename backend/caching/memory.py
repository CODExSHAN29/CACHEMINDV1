import asyncio
import copy
import time
from typing import Dict, Optional, Tuple

from backend.caching.backend import ExactCacheBackend
from backend.caching.models import CachedResponse


class InMemoryExactCache(ExactCacheBackend):
    """
    In-memory asyncio-safe exact cache implementation for tests and local development.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[CachedResponse, float]] = {}  # key -> (payload, expire_at)
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        """Lazy lock creation ensures binding to the current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _make_key(self, project_id: str, exact_request_hash: str) -> str:
        return f"cm:v1:exact:{project_id}:{exact_request_hash}"

    async def get(
        self, project_id: str, exact_request_hash: str
    ) -> Optional[CachedResponse]:
        key = self._make_key(project_id, exact_request_hash)
        async with self.lock:
            entry = self._store.get(key)
            if not entry:
                return None
            cached_resp, expire_at = entry
            if time.time() > expire_at:
                del self._store[key]
                return None
            # Return deepcopy to ensure isolation
            return copy.deepcopy(cached_resp)

    async def set(
        self,
        project_id: str,
        exact_request_hash: str,
        payload: CachedResponse,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        key = self._make_key(project_id, exact_request_hash)
        ttl = ttl_seconds if ttl_seconds is not None else payload.ttl_seconds
        expire_at = time.time() + ttl

        async with self.lock:
            self._store[key] = (copy.deepcopy(payload), expire_at)

    async def delete(self, project_id: str, exact_request_hash: str) -> bool:
        key = self._make_key(project_id, exact_request_hash)
        async with self.lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def increment_hit(
        self, project_id: str, exact_request_hash: str
    ) -> int:
        key = self._make_key(project_id, exact_request_hash)
        async with self.lock:
            if key in self._store:
                cached_resp, expire_at = self._store[key]
                cached_resp.hit_count += 1
                return cached_resp.hit_count
            return 0

    async def ping(self) -> bool:
        return True

    async def purge_project(self, project_id: str) -> int:
        prefix = f"cm:v1:exact:{project_id}:"
        deleted_count = 0
        async with self.lock:
            keys_to_delete = [k for k in self._store.keys() if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._store[k]
                deleted_count += 1
        return deleted_count

    async def list_keys(self, project_id: str, limit: int = 100) -> list[str]:
        prefix = f"cm:v1:exact:{project_id}:"
        async with self.lock:
            keys = [
                k[len(prefix):] for k in self._store.keys() if k.startswith(prefix)
            ]
            return keys[:limit]

    async def clear(self) -> None:
        async with self.lock:
            self._store.clear()
