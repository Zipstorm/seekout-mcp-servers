import pytest
from unittest.mock import AsyncMock

from fastmcp import FastMCP

from seekout_mcp_search.tools import register_tools


@pytest.fixture
def mcp_server(mock_seekout_api, query_builder, mock_cache_store):
    """Create a FastMCP server with all tools registered."""
    mcp = FastMCP("test-seekout")
    register_tools(
        mcp, query_builder, mock_seekout_api, mock_cache_store,
        query_store_endpoint="https://example.com/api/StoreQuery",
        query_store_api_key="test-key",
    )
    return mcp


@pytest.fixture
def mcp_server_minimal(mock_seekout_api, query_builder, mock_cache_store):
    """Create a FastMCP server without optional link tool."""
    mcp = FastMCP("test-seekout")
    register_tools(mcp, query_builder, mock_seekout_api, mock_cache_store)
    return mcp


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


class TestSeekoutPing:
    @pytest.mark.asyncio
    async def test_ping_success(self, mock_seekout_api, mock_cache_store):
        mock_seekout_api.ping.return_value = (200, 15.3)
        mcp = FastMCP("test")
        register_tools(mcp, AsyncMock(), mock_seekout_api, mock_cache_store)

        tools = {t.name: t for t in await mcp.list_tools()}
        assert "seekout_ping" in tools

    @pytest.mark.asyncio
    async def test_ping_error(self, mock_seekout_api, mock_cache_store):
        mock_seekout_api.ping.side_effect = Exception("Connection refused")
        mcp = FastMCP("test")
        register_tools(mcp, AsyncMock(), mock_seekout_api, mock_cache_store)

        tools = {t.name: t for t in await mcp.list_tools()}
        assert "seekout_ping" in tools


class TestToolRegistration:
    @pytest.mark.asyncio
    async def test_all_tools_registered(self, mcp_server):
        tools = {t.name: t for t in await mcp_server.list_tools()}
        for name in STATELESS_TOOLS + LINK_TOOLS:
            assert name in tools, f"Tool {name} not registered"
        assert len(tools) == 9

    @pytest.mark.asyncio
    async def test_only_stateless_tools_without_optional(self, mcp_server_minimal):
        tools = {t.name: t for t in await mcp_server_minimal.list_tools()}
        for name in STATELESS_TOOLS:
            assert name in tools, f"Tool {name} not registered"
        for name in LINK_TOOLS:
            assert name not in tools, f"Optional tool {name} should not be registered"
        assert len(tools) == 8

    @pytest.mark.asyncio
    async def test_all_tools_have_annotations(self, mcp_server):
        tools = await mcp_server.list_tools()
        for tool in tools:
            assert tool.annotations is not None, f"Tool {tool.name} missing annotations"


class TestToolAnnotations:
    @pytest.mark.asyncio
    async def test_search_tools_are_read_only(self, mcp_server):
        tools = {t.name: t for t in await mcp_server.list_tools()}
        read_only_tools = [
            "seekout_search_people", "seekout_count_results",
            "seekout_get_facets", "seekout_get_profile",
            "seekout_get_suggestions", "seekout_validate_query",
            "seekout_get_query", "seekout_ping",
        ]
        for name in read_only_tools:
            assert tools[name].annotations.readOnlyHint is True, (
                f"Tool {name} should be readOnly"
            )

    @pytest.mark.asyncio
    async def test_link_tool_is_not_read_only(self, mcp_server):
        tools = {t.name: t for t in await mcp_server.list_tools()}
        assert tools["seekout_get_link"].annotations.readOnlyHint is not True


class TestSummaryCandidates:
    @pytest.mark.asyncio
    async def test_search_returns_enriched_summaries(
        self, mock_seekout_api, query_builder, mock_cache_store,
    ):
        mock_seekout_api.search_people.return_value = (
            {
                "search_id": "test-id",
                "count": 1,
                "results": [{
                    "key": "abc",
                    "full_name": "Jane Smith",
                    "cur_title": "Engineer",
                    "cur_company": "Google",
                    "locations": ["Seattle"],
                    "li_urls": ["https://linkedin.com/in/jane"],
                    "grad_year": 2015,
                    "skills": ["Python", "Go", "K8s", "gRPC", "SQL", "Rust"],
                    "headlines": ["Building things"],
                }],
                "facets": {},
            },
            1,
        )

        mcp = FastMCP("test")
        register_tools(mcp, query_builder, mock_seekout_api, mock_cache_store)

        result = await mcp.call_tool("seekout_search_people", {"query": "test"})
        # Extract data from ToolResult content
        import json
        content = result.content if hasattr(result, 'content') else []
        text = content[0].text if content else "{}"
        data = json.loads(text)

        candidate = data["candidates"][0]
        assert candidate["linkedin_url"] == "https://linkedin.com/in/jane"
        assert candidate["years_of_experience"] is not None
        assert candidate["source_index"] == "NorthAmerica"
        assert len(candidate["skills"]) <= 5  # Capped at 5
        assert data["search_id"] == "test-id"
