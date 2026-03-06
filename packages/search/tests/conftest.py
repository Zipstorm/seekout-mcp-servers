from unittest.mock import AsyncMock

import pytest

from seekout_mcp_search.entity_resolver import EntityResolver
from seekout_mcp_search.query_builder import QueryBuilder
from seekout_mcp_search.seekout_api import SeekOutAPI


@pytest.fixture
def mock_seekout_api():
    api = AsyncMock(spec=SeekOutAPI)
    api.search_entities = AsyncMock(return_value=[])
    api.search_people = AsyncMock(return_value=({}, 0))
    api.get_profile = AsyncMock(return_value=None)
    api.validate_boolean = AsyncMock(return_value=(True, None))
    api.ping = AsyncMock(return_value=(200, 15.0))
    return api


@pytest.fixture
def entity_resolver(mock_seekout_api):
    return EntityResolver(mock_seekout_api)


@pytest.fixture
def query_builder(entity_resolver):
    return QueryBuilder(entity_resolver)
