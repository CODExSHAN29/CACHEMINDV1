import json
import logging
from typing import Optional
import redis.asyncio as redis
from redis.exceptions import RedisError

from backend.caching.backend import ExactCacheBackend
from backend.caching.models import CachedResponse

logger = logging.getLogger(__name__)


class RedisExactCache(ExactCacheBackend):
    """
    Production Redis-backed exact cache implementation with automatic serialization,
    TTL enforcement, and graceful degradation (fail-open) on Redis connectivity issues.
    """

    def __init__(self, redis_url: str, socket_timeout: float = 2.0) -> None:
        self.redis_url = redis_url
        self.socket_timeout = socket_timeout
        self._client: Optional[redis.Redis] = None

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.socket_timeout,
                decode_responses=True,
            )
        return self._client

    def _make_key(self, project_id: str, exact_request_hash: str) -> str:
        return f"cm:v1:exact:{project_id}:{exact_request_hash}"

    async def get(
        self, project_id: str, exact_request_hash: str
    ) -> Optional[CachedResponse]:
        key = self._make_key(project_id, exact_request_hash)
        try:
            client = self._get_client()
            raw_data = await client.get(key)
            if not raw_data:
                return None
            data_dict = json.loads(raw_data)
            return CachedResponse(**data_dict)
        except (RedisError, ConnectionError, TimeoutError, json.JSONDecodeError) as err:
            logger.warning("Redis cache get error (graceful fail-open): %s", err)
            return None

    async def set(
        self,
        project_id: str,
        exact_request_hash: str,
        payload: CachedResponse,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        key = self._make_key(project_id, exact_request_hash)
        ttl = ttl_seconds if ttl_seconds is not None else payload.ttl_seconds
        try:
            client = self._get_client()
            raw_json = payload.model_dump_json()
            await client.set(key, raw_json, ex=ttl)
        except (RedisError, ConnectionError, TimeoutError) as err:
            logger.warning("Redis cache set error (graceful bypass): %s", err)

    async def delete(self, project_id: str, exact_request_hash: str) -> bool:
        key = self._make_key(project_id, exact_request_hash)
        try:
            client = self._get_client()
            deleted_count = await client.delete(key)
            return bool(deleted_count > 0)
        except (RedisError, ConnectionError, TimeoutError) as err:
            logger.warning("Redis cache delete error: %s", err)
            return False

    async def increment_hit(
        self, project_id: str, exact_request_hash: str
    ) -> int:
        key = self._make_key(project_id, exact_request_hash)
        try:
            client = self._get_client()
            # If entry exists, we can store hit counts or increment in a separate key or in payload
            # For simplicity and Redis atomic safety, use a subkey counter
            counter_key = f"{key}:hits"
            hits = await client.incr(counter_key)
            return hits
        except (RedisError, ConnectionError, TimeoutError) as err:
            logger.warning("Redis cache increment_hit error: %s", err)
            return 0

    async def ping(self) -> bool:
        try:
            client = self._get_client()
            return bool(await client.ping())
        except Exception:
            return False

    async def purge_project(self, project_id: str) -> int:
        prefix = f"cm:v1:exact:{project_id}:*"
        deleted_count = 0
        try:
            client = self._get_client()
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor=cursor, match=prefix, count=100)
                if keys:
                    del_res = await client.delete(*keys)
                    deleted_count += del_res
                if cursor == 0:
                    break
            return deleted_count
        except (RedisError, ConnectionError, TimeoutError) as err:
            logger.warning("Redis cache purge_project error: %s", err)
            return 0

    async def list_keys(self, project_id: str, limit: int = 100) -> list[str]:
        prefix = f"cm:v1:exact:{project_id}:"
        try:
            client = self._get_client()
            cursor = 0
            matching_keys: list[str] = []
            while len(matching_keys) < limit:
                cursor, keys = await client.scan(cursor=cursor, match=f"{prefix}*", count=100)
                for k in keys:
                    if not k.endswith(":hits"):
                        matching_keys.append(k[len(prefix):])
                if cursor == 0:
                    break
            return matching_keys[:limit]
        except (RedisError, ConnectionError, TimeoutError) as err:
            logger.warning("Redis cache list_keys error: %s", err)
            return []

    async def clear(self) -> None:
        try:
            client = self._get_client()
            await client.flushdb()
        except (RedisError, ConnectionError, TimeoutError) as err:
            logger.warning("Redis cache clear error: %s", err)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
