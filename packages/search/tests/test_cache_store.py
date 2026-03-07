import json

import pytest
from unittest.mock import AsyncMock

from seekout_mcp_search.cache_store import CacheStore


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    return r


@pytest.fixture
def store(mock_redis):
    return CacheStore(mock_redis, ttl_seconds=3600)


class TestCacheSearch:
    async def test_cache_stores_query_and_results(self, store, mock_redis):
        query = {"search": "python", "top": 10}
        results = {"search_id": "abc", "count": 5, "results": []}

        await store.cache_search("abc", query, results)

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "mcp:cache:abc"
        stored = json.loads(call_args[0][1])
        assert stored["query"] == query
        assert stored["results"] == results
        assert call_args.kwargs["ex"] == 3600


class TestGetCached:
    async def test_returns_cached_data(self, store, mock_redis):
        payload = {"query": {"search": "python"}, "results": {"count": 5}}
        mock_redis.get.return_value = json.dumps(payload)

        cached = await store.get_cached("abc")

        assert cached == payload
        mock_redis.get.assert_called_once_with("mcp:cache:abc")

    async def test_returns_none_for_missing(self, store, mock_redis):
        mock_redis.get.return_value = None
        assert await store.get_cached("missing") is None
