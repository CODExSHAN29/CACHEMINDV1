import json
import logging
from typing import Any, List, Optional, Tuple
import redis.asyncio as redis
from redis.exceptions import RedisError

from backend.app.config import settings
from backend.caching.backend import ExactCacheBackend
from backend.caching.models import CachedResponse

logger = logging.getLogger(__name__)


class RedisExactCache(ExactCacheBackend):
    """
    Production Redis-backed exact cache implementation with automatic serialization,
    TTL enforcement, and graceful degradation (fail-open) on Redis connectivity issues.
    Supports Standalone Redis, Redis Cluster, and Redis Sentinel high-availability.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        socket_timeout: Optional[float] = None,
        cluster_mode: Optional[bool] = None,
        sentinel_hosts: Optional[str] = None,
        sentinel_master: Optional[str] = None,
        password: Optional[str] = None,
        ssl: Optional[bool] = None,
        max_connections: Optional[int] = None,
    ) -> None:
        self.redis_url = redis_url or settings.REDIS_URL
        self.socket_timeout = socket_timeout if socket_timeout is not None else settings.REDIS_SOCKET_TIMEOUT
        self.cluster_mode = cluster_mode if cluster_mode is not None else settings.REDIS_CLUSTER_MODE
        self.sentinel_hosts = sentinel_hosts if sentinel_hosts is not None else settings.REDIS_SENTINEL_HOSTS
        self.sentinel_master = sentinel_master or settings.REDIS_SENTINEL_MASTER
        self.password = password or settings.REDIS_PASSWORD
        self.ssl = ssl if ssl is not None else settings.REDIS_SSL
        self.max_connections = max_connections or settings.REDIS_MAX_CONNECTIONS
        self._client: Any = None

    def _parse_sentinel_hosts(self, hosts_str: str) -> List[Tuple[str, int]]:
        hosts = []
        for part in hosts_str.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                h, p = part.split(":", 1)
                hosts.append((h.strip(), int(p.strip())))
            else:
                hosts.append((part, 26379))
        return hosts

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        if self.sentinel_hosts:
            try:
                from redis.asyncio.sentinel import Sentinel
                hosts = self._parse_sentinel_hosts(self.sentinel_hosts)
                sentinel_kwargs: dict[str, Any] = {
                    "socket_timeout": self.socket_timeout,
                    "decode_responses": True,
                }
                if self.password:
                    sentinel_kwargs["password"] = self.password
                if self.ssl:
                    sentinel_kwargs["ssl"] = True
                sentinel = Sentinel(
                    hosts,
                    **sentinel_kwargs,
                )
                self._client = sentinel.master_for(self.sentinel_master)
                logger.info("Initialized Redis Sentinel client for master '%s'", self.sentinel_master)
                return self._client
            except Exception as exc:
                logger.warning("Failed to initialize Redis Sentinel: %s, falling back to standalone URL", exc)

        if self.cluster_mode:
            try:
                from redis.asyncio.cluster import RedisCluster
                cluster_kwargs: dict[str, Any] = {
                    "socket_timeout": self.socket_timeout,
                    "decode_responses": True,
                }
                if self.max_connections:
                    cluster_kwargs["max_connections"] = self.max_connections
                if self.password:
                    cluster_kwargs["password"] = self.password
                if self.ssl:
                    cluster_kwargs["ssl"] = True
                self._client = RedisCluster.from_url(
                    self.redis_url,
                    **cluster_kwargs,
                )
                logger.info("Initialized Redis Cluster client")
                return self._client
            except Exception as exc:
                logger.warning("Failed to initialize Redis Cluster: %s, falling back to standalone", exc)

        client_kwargs: dict[str, Any] = {
            "socket_timeout": self.socket_timeout,
            "socket_connect_timeout": self.socket_timeout,
            "decode_responses": True,
        }
        if self.max_connections:
            client_kwargs["max_connections"] = self.max_connections
        if self.password:
            client_kwargs["password"] = self.password
        if self.ssl:
            client_kwargs["ssl"] = True

        self._client = redis.from_url(
            self.redis_url,
            **client_kwargs,
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
        except Exception as err:
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
        except (RedisError, ConnectionError, TimeoutError, IndexError, OSError, Exception) as err:
            logger.warning("Redis cache set error (graceful bypass): %s", err)

    async def delete(self, project_id: str, exact_request_hash: str) -> bool:
        key = self._make_key(project_id, exact_request_hash)
        try:
            client = self._get_client()
            deleted_count = await client.delete(key)
            return bool(deleted_count > 0)
        except (RedisError, ConnectionError, TimeoutError, IndexError, OSError, Exception) as err:
            logger.warning("Redis cache delete error: %s", err)
            return False

    async def increment_hit(
        self, project_id: str, exact_request_hash: str
    ) -> int:
        key = self._make_key(project_id, exact_request_hash)
        try:
            client = self._get_client()
            counter_key = f"{key}:hits"
            hits = await client.incr(counter_key)
            return hits
        except (RedisError, ConnectionError, TimeoutError, IndexError, OSError, Exception) as err:
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
        except (RedisError, ConnectionError, TimeoutError, IndexError, OSError, Exception) as err:
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
        except (RedisError, ConnectionError, TimeoutError, IndexError, OSError, Exception) as err:
            logger.warning("Redis cache list_keys error: %s", err)
            return []

    async def clear(self) -> None:
        try:
            client = self._get_client()
            await client.flushdb()
        except (RedisError, ConnectionError, TimeoutError, IndexError, OSError, Exception) as err:
            logger.warning("Redis cache clear error: %s", err)

    async def close(self) -> None:
        if self._client is not None:
            if hasattr(self._client, "aclose"):
                await self._client.aclose()
            elif hasattr(self._client, "close"):
                res = self._client.close()
                if hasattr(res, "__await__"):
                    await res
            self._client = None
