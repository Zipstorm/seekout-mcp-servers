import pytest
from unittest.mock import AsyncMock

from fastmcp import FastMCP

from seekout_mcp_search.session_store import SessionStore
from seekout_mcp_search.tools import register_tools


@pytest.fixture
def mock_session_store():
    return AsyncMock(spec=SessionStore)


@pytest.fixture
def mcp_server(mock_seekout_api, query_builder, mock_session_store):
    """Create a FastMCP server with all tools registered."""
    mcp = FastMCP("test-seekout")
    register_tools(
        mcp, query_builder, mock_seekout_api, mock_session_store,
        query_store_endpoint="https://example.com/api/StoreQuery",
        query_store_api_key="test-key",
    )
    return mcp


@pytest.fixture
def mcp_server_no_sessions(mock_seekout_api, query_builder):
    """Create a FastMCP server without session or link tools."""
    mcp = FastMCP("test-seekout")
    register_tools(mcp, query_builder, mock_seekout_api, session_store=None)
    return mcp


class TestSeekoutPing:
    @pytest.mark.asyncio
    async def test_ping_success(self, mock_seekout_api):
        mock_seekout_api.ping.return_value = (200, 15.3)
        mcp = FastMCP("test")
        register_tools(mcp, AsyncMock(), mock_seekout_api)

        tools = {t.name: t for t in await mcp.list_tools()}
        assert "seekout_ping" in tools

    @pytest.mark.asyncio
    async def test_ping_error(self, mock_seekout_api):
        mock_seekout_api.ping.side_effect = Exception("Connection refused")
        mcp = FastMCP("test")
        register_tools(mcp, AsyncMock(), mock_seekout_api)

        tools = {t.name: t for t in await mcp.list_tools()}
        assert "seekout_ping" in tools


STATELESS_TOOLS = [
    "seekout_ping",
    "seekout_search_people",
    "seekout_count_results",
    "seekout_get_facets",
    "seekout_get_profile",
    "seekout_get_suggestions",
    "seekout_validate_query",
    "seekout_get_query",
]

LINK_TOOLS = [
    "seekout_get_link",
]

SESSION_TOOLS = [
    "session_create",
    "session_add_filter",
    "session_remove_filter",
    "session_run_search",
    "session_get",
    "session_delete",
]


class TestToolRegistration:
    @pytest.mark.asyncio
    async def test_all_tools_registered(self, mcp_server):
        tools = {t.name: t for t in await mcp_server.list_tools()}
        for name in STATELESS_TOOLS + LINK_TOOLS + SESSION_TOOLS:
            assert name in tools, f"Tool {name} not registered"
        assert len(tools) == 15

    @pytest.mark.asyncio
    async def test_only_stateless_tools_without_optional(self, mcp_server_no_sessions):
        tools = {t.name: t for t in await mcp_server_no_sessions.list_tools()}
        for name in STATELESS_TOOLS:
            assert name in tools, f"Tool {name} not registered"
        for name in SESSION_TOOLS + LINK_TOOLS:
            assert name not in tools, f"Optional tool {name} should not be registered"
        assert len(tools) == 8
