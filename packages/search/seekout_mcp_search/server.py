from pathlib import Path

import redis.asyncio as redis
from fastmcp import FastMCP
from fastmcp.experimental.transforms.code_mode import CodeMode
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.providers.skills import SkillsDirectoryProvider

from seekout_mcp_search.auth import CompositeVerifier
from seekout_mcp_search.cache_store import CacheStore
from seekout_mcp_search.config import Settings
from seekout_mcp_search.instructions import SEARCH_INSTRUCTIONS
from seekout_mcp_search.seekout_api import SeekOutAPI
from seekout_mcp_search.entity_resolver import EntityResolver
from seekout_mcp_search.query_builder import QueryBuilder
from seekout_mcp_search.tools import register_tools

_SKILLS_DIR = Path(__file__).parent / "skills"


def create_auth_verifier(settings: Settings):
    """Create the appropriate auth verifier based on environment."""
    if settings.spot_env == "local":
        return StaticTokenVerifier(
            tokens={
                "dev-token-123": {
                    "client_id": "dev@seekout.io",
                    "scope": "mcp:tools",
                }
            }
        )

    return CompositeVerifier(
        internal_api_key=settings.mcp_internal_api_key or None,
        jwks_uri=settings.seekout_jwks_uri,
        issuer=settings.seekout_oauth_issuer,
        audience=settings.seekout_mcp_audience,
        resource_url=settings.seekout_mcp_resource_url,
        authorization_server=settings.seekout_oauth_issuer,
    )


def create_server(settings: Settings | None = None) -> FastMCP:
    """Build a fully configured SeekOut MCP search server.

    Uses Code Mode transform: LLM discovers tools via search + get_schema,
    then executes them via Python code blocks. This collapses the tool surface
    from N tools to 3 meta-tools (search, get_schema, execute).

    Usage:
      Standalone:  python -m seekout_mcp_search
      Library:     from seekout_mcp_search import create_server, Settings
                   mcp = create_server(Settings())
      In-process:  app.mount("/mcp/seekout", create_server(settings).streamable_http_app())
    """
    settings = settings or Settings()

    verifier = create_auth_verifier(settings)
    mcp = FastMCP(
        "seekout-search",
        instructions=SEARCH_INSTRUCTIONS,
        auth=verifier,
        transforms=[CodeMode()],
    )

    seekout_api = SeekOutAPI(
        base_url=settings.seekout_runtime_api_endpoint,
        api_key=settings.seekout_runtime_api_key,
    )
    entity_resolver = EntityResolver(seekout_api)
    query_builder = QueryBuilder(entity_resolver)

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    cache_store = CacheStore(redis_client, ttl_seconds=settings.cache_ttl_seconds)

    register_tools(
        mcp,
        query_builder,
        seekout_api,
        cache_store,
        query_store_endpoint=settings.query_store_endpoint,
        query_store_api_key=settings.query_store_api_key,
    )

    # Expose recruiter workflow skills as MCP resources
    mcp.add_provider(SkillsDirectoryProvider(roots=_SKILLS_DIR))

    return mcp
