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
        mock_sentinel_cls.assert_called_once()
        mock_instance.master_for.assert_called_once_with("mymaster")


def test_redis_cluster_client_init():
    cache = RedisExactCache(
        redis_url="redis://cluster-node1:6379",
        cluster_mode=True,
    )
    with patch("redis.asyncio.cluster.RedisCluster.from_url") as mock_cluster_cls:
        mock_cluster = MagicMock()
        mock_cluster_cls.return_value = mock_cluster

        client = cache._get_client()
        assert client == mock_cluster
        mock_cluster_cls.assert_called_once()
