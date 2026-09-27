from backend.app.config import settings
from backend.caching.backend import ExactCacheBackend
from backend.caching.memory import InMemoryExactCache
from backend.caching.redis_backend import RedisExactCache

_cache_instance: ExactCacheBackend | None = None


def get_cache_backend() -> ExactCacheBackend:
    """Returns the singleton exact cache backend configured by application settings."""
    global _cache_instance
    if _cache_instance is None:
        if settings.CACHE_BACKEND == "redis":
            _cache_instance = RedisExactCache(
                redis_url=settings.REDIS_URL,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            )
        else:
            _cache_instance = InMemoryExactCache()
    return _cache_instance


def set_cache_backend(backend: ExactCacheBackend) -> None:
    """Explicitly sets or overrides cache backend instance (e.g., in test fixtures)."""
    global _cache_instance
    _cache_instance = backend
