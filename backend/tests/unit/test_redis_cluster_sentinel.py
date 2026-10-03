import pytest
from unittest.mock import MagicMock, patch
from backend.caching.redis_backend import RedisExactCache


def test_redis_sentinel_host_parsing():
    cache = RedisExactCache()
    hosts = cache._parse_sentinel_hosts("sentinel1:26379, sentinel2:26380, 10.0.0.1")
    assert len(hosts) == 3
    assert hosts[0] == ("sentinel1", 26379)
    assert hosts[1] == ("sentinel2", 26380)
    assert hosts[2] == ("10.0.0.1", 26379)


def test_redis_sentinel_client_init():
    cache = RedisExactCache(
        sentinel_hosts="localhost:26379,localhost:26380",
        sentinel_master="mymaster",
        password="secretpassword",
        ssl=False,
    )
    with patch("redis.asyncio.sentinel.Sentinel") as mock_sentinel_cls:
        mock_instance = MagicMock()
        mock_master = MagicMock()
        mock_instance.master_for.return_value = mock_master
        mock_sentinel_cls.return_value = mock_instance

        client = cache._get_client()
        assert client == mock_master
        mock_sentinel_cls.assert_called_once_with(
            [("localhost", 26379), ("localhost", 26380)],
            socket_timeout=cache.socket_timeout,
            decode_responses=True,
            password="secretpassword",
        )
        mock_instance.master_for.assert_called_once_with("mymaster")


def test_redis_sentinel_client_init_with_ssl():
    cache = RedisExactCache(
        sentinel_hosts="localhost:26379",
        sentinel_master="mymaster",
        password=None,
        ssl=True,
    )
    with patch("redis.asyncio.sentinel.Sentinel") as mock_sentinel_cls:
        mock_instance = MagicMock()
        mock_master = MagicMock()
        mock_instance.master_for.return_value = mock_master
        mock_sentinel_cls.return_value = mock_instance

        client = cache._get_client()
        assert client == mock_master
        mock_sentinel_cls.assert_called_once_with(
            [("localhost", 26379)],
            socket_timeout=cache.socket_timeout,
            decode_responses=True,
            ssl=True,
        )


def test_redis_cluster_client_init():
    cache = RedisExactCache(
        redis_url="redis://cluster-node1:6379",
        cluster_mode=True,
        password="cluster_secret",
        max_connections=75,
        ssl=False,
    )
    with patch("redis.asyncio.cluster.RedisCluster.from_url") as mock_cluster_cls:
        mock_cluster = MagicMock()
        mock_cluster_cls.return_value = mock_cluster

        client = cache._get_client()
        assert client == mock_cluster
        mock_cluster_cls.assert_called_once_with(
            "redis://cluster-node1:6379",
            socket_timeout=cache.socket_timeout,
            decode_responses=True,
            max_connections=75,
            password="cluster_secret",
        )
        # Ensure ssl is NOT passed in kwargs
        _, kwargs = mock_cluster_cls.call_args
        assert "ssl" not in kwargs


def test_redis_cluster_client_init_with_ssl():
    cache = RedisExactCache(
        redis_url="redis://cluster-node1:6379",
        cluster_mode=True,
        ssl=True,
        max_connections=60,
    )
    with patch("redis.asyncio.cluster.RedisCluster.from_url") as mock_cluster_cls:
        mock_cluster = MagicMock()
        mock_cluster_cls.return_value = mock_cluster

        client = cache._get_client()
        assert client == mock_cluster
        mock_cluster_cls.assert_called_once_with(
            "rediss://cluster-node1:6379",
            socket_timeout=cache.socket_timeout,
            decode_responses=True,
            max_connections=60,
        )
        _, kwargs = mock_cluster_cls.call_args
        assert "ssl" not in kwargs


def test_redis_standalone_url_normalization():
    # A. REDIS_SSL=false, redis:// URL
    cache_plain = RedisExactCache(redis_url="redis://localhost:6379/0", ssl=False)
    assert cache_plain._normalize_redis_url(cache_plain.redis_url) == "redis://localhost:6379/0"

    # B. REDIS_SSL=true, redis:// URL -> rediss://
    cache_tls = RedisExactCache(redis_url="redis://localhost:6379/0", ssl=True)
    assert cache_tls._normalize_redis_url(cache_tls.redis_url) == "rediss://localhost:6379/0"

    # C. rediss:// URL preserved with ssl=False or ssl=True
    cache_already_tls_false = RedisExactCache(redis_url="rediss://localhost:6380/0", ssl=False)
    assert cache_already_tls_false._normalize_redis_url(cache_already_tls_false.redis_url) == "rediss://localhost:6380/0"

    cache_already_tls_true = RedisExactCache(redis_url="rediss://localhost:6380/0", ssl=True)
    assert cache_already_tls_true._normalize_redis_url(cache_already_tls_true.redis_url) == "rediss://localhost:6380/0"


def test_redis_standalone_connection_construction_plain():
    # A. REDIS_SSL=false, redis:// URL does NOT pass ssl kwarg, password=None omitted, max_connections preserved
    cache = RedisExactCache(
        redis_url="redis://localhost:6379/0",
        ssl=False,
        password=None,
        max_connections=50,
    )
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client

        client = cache._get_client()
        assert client == mock_client
        mock_from_url.assert_called_once_with(
            "redis://localhost:6379/0",
            socket_timeout=cache.socket_timeout,
            socket_connect_timeout=cache.socket_timeout,
            decode_responses=True,
            max_connections=50,
        )
        _, kwargs = mock_from_url.call_args
        assert "ssl" not in kwargs
        assert "password" not in kwargs
        assert kwargs["max_connections"] == 50


def test_redis_standalone_connection_construction_tls():
    # B. REDIS_SSL=true, redis:// URL uses rediss://, configured password & max_connections preserved
    cache = RedisExactCache(
        redis_url="redis://redis.internal:6379/0",
        ssl=True,
        password="my_redis_password",
        max_connections=100,
    )
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client

        client = cache._get_client()
        assert client == mock_client
        mock_from_url.assert_called_once_with(
            "rediss://redis.internal:6379/0",
            socket_timeout=cache.socket_timeout,
            socket_connect_timeout=cache.socket_timeout,
            decode_responses=True,
            max_connections=100,
            password="my_redis_password",
        )
        _, kwargs = mock_from_url.call_args
        assert "ssl" not in kwargs
        assert kwargs["password"] == "my_redis_password"
        assert kwargs["max_connections"] == 100


def test_redis_standalone_connection_construction_rediss_scheme():
    # C. rediss:// URL is preserved and connects without ssl kwarg
    cache = RedisExactCache(
        redis_url="rediss://default:token@tls-redis.host.com:6380/0",
        ssl=False,
        password=None,
        max_connections=30,
    )
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client

        client = cache._get_client()
        assert client == mock_client
        mock_from_url.assert_called_once_with(
            "rediss://default:token@tls-redis.host.com:6380/0",
            socket_timeout=cache.socket_timeout,
            socket_connect_timeout=cache.socket_timeout,
            decode_responses=True,
            max_connections=30,
        )
        _, kwargs = mock_from_url.call_args
        assert "ssl" not in kwargs
        assert "password" not in kwargs
        assert kwargs["max_connections"] == 30
