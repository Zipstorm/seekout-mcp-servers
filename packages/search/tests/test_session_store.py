import json

import pytest
from unittest.mock import AsyncMock

from seekout_mcp_search.session_store import SessionStore


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    r.delete = AsyncMock(return_value=1)
    return r


@pytest.fixture
def store(mock_redis):
    return SessionStore(mock_redis, ttl_seconds=3600)


class TestCreate:
    async def test_create_returns_session_with_id(self, store, mock_redis):
        session = await store.create(query="Python engineer")

        assert "session_id" in session
        assert session["query"] == "Python engineer"
        assert session["filters"] == {}
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args.kwargs["ex"] == 3600

    async def test_create_with_empty_query(self, store):
        session = await store.create()
        assert session["query"] == ""


class TestGet:
    async def test_get_returns_session(self, store, mock_redis):
        stored = {"session_id": "abc", "query": "", "filters": {}}
        mock_redis.get.return_value = json.dumps(stored)

        session = await store.get("abc")

        assert session == stored
        mock_redis.get.assert_called_once_with("mcp:search:abc")

    async def test_get_returns_none_for_missing(self, store, mock_redis):
        mock_redis.get.return_value = None
        assert await store.get("missing") is None


class TestAddFilter:
    async def _setup_session(self, mock_redis, filters=None):
        stored = {"session_id": "abc", "query": "", "filters": filters or {}}
        mock_redis.get.return_value = json.dumps(stored)

    async def test_add_titles_filter(self, store, mock_redis):
        await self._setup_session(mock_redis)
        session = await store.add_filter("abc", "titles", ["Engineer", "Manager"])

        assert session is not None
        assert session["filters"]["current_title"] == {"alt_names": ["Engineer", "Manager"]}

    async def test_add_companies_filter(self, store, mock_redis):
        await self._setup_session(mock_redis)
        session = await store.add_filter("abc", "companies", ["Google"])

        assert session["filters"]["current_company"] == {"alt_names": ["Google"]}

    async def test_add_locations_filter(self, store, mock_redis):
        await self._setup_session(mock_redis)
        session = await store.add_filter("abc", "locations", ["Seattle"])

        assert session["filters"]["location"] == {"alt_names": ["Seattle"]}

    async def test_add_skills_filter(self, store, mock_redis):
        await self._setup_session(mock_redis)
        session = await store.add_filter("abc", "skills", ["Python", "Go"])

        assert session["filters"]["_skill_names"] == ["Python", "Go"]

    async def test_add_years_min(self, store, mock_redis):
        await self._setup_session(mock_redis)
        session = await store.add_filter("abc", "years_experience_min", ["5"])

        assert session["filters"]["years_of_experience"]["min"] == 5

    async def test_add_years_max(self, store, mock_redis):
        await self._setup_session(mock_redis)
        session = await store.add_filter("abc", "years_experience_max", ["15"])

        assert session["filters"]["years_of_experience"]["max"] == 15

    async def test_add_query(self, store, mock_redis):
        await self._setup_session(mock_redis)
        session = await store.add_filter("abc", "query", ["Python AND Django"])

        assert session["query"] == "Python AND Django"

    async def test_add_filter_replaces_existing(self, store, mock_redis):
        await self._setup_session(mock_redis, {"current_company": {"alt_names": ["Google"]}})
        session = await store.add_filter("abc", "companies", ["Meta"])

        assert session["filters"]["current_company"] == {"alt_names": ["Meta"]}

    async def test_add_filter_missing_session(self, store, mock_redis):
        mock_redis.get.return_value = None
        result = await store.add_filter("missing", "titles", ["Eng"])
        assert result is None

    async def test_add_unknown_filter_type(self, store, mock_redis):
        await self._setup_session(mock_redis)
        result = await store.add_filter("abc", "unknown_type", ["value"])
        assert result is None


class TestRemoveFilter:
    async def _setup_session(self, mock_redis, filters):
        stored = {"session_id": "abc", "query": "test", "filters": filters}
        mock_redis.get.return_value = json.dumps(stored)

    async def test_remove_titles(self, store, mock_redis):
        await self._setup_session(mock_redis, {"current_title": {"alt_names": ["Eng"]}})
        session = await store.remove_filter("abc", "titles")

        assert "current_title" not in session["filters"]

    async def test_remove_query(self, store, mock_redis):
        await self._setup_session(mock_redis, {})
        session = await store.remove_filter("abc", "query")

        assert session["query"] == ""

    async def test_remove_years_min_keeps_max(self, store, mock_redis):
        await self._setup_session(mock_redis, {"years_of_experience": {"min": 3, "max": 10}})
        session = await store.remove_filter("abc", "years_experience_min")

        assert session["filters"]["years_of_experience"] == {"max": 10}

    async def test_remove_years_max_removes_whole_filter(self, store, mock_redis):
        await self._setup_session(mock_redis, {"years_of_experience": {"max": 10}})
        session = await store.remove_filter("abc", "years_experience_max")

        assert "years_of_experience" not in session["filters"]

    async def test_remove_missing_session(self, store, mock_redis):
        mock_redis.get.return_value = None
        result = await store.remove_filter("missing", "titles")
        assert result is None


class TestDelete:
    async def test_delete_existing(self, store, mock_redis):
        mock_redis.delete.return_value = 1
        assert await store.delete("abc") is True

    async def test_delete_missing(self, store, mock_redis):
        mock_redis.delete.return_value = 0
        assert await store.delete("missing") is False
