# MCP Infrastructure Patterns for SPOT

**Date:** 2026-03-04
**Status:** Research
**Context:** Evaluating MCP infrastructure patterns for the SPOT recruiting platform's agent orchestration layer (`packages/agents/`), which uses Agno `Team(mode="route")` with mixed MCP + native tooling.

---

## Executive Summary

MCP (Model Context Protocol) is a JSON-RPC 2.0 based protocol that standardizes how AI agents discover and invoke tools exposed by external servers. For SPOT, MCP serves as the integration layer between Agno-based recruiting agents and external services (SeekOut search, candidate data, outreach platforms). This document covers transport selection, server architecture, Agno integration patterns, lifecycle management, and production deployment considerations.

**Key Recommendations (TL;DR):**

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| Transport | Streamable HTTP for remote servers, stdio for local dev/testing | Streamable HTTP is the current spec (2025-11-25), fits FastAPI natively |
| Build vs Consume | Build SPOT-specific MCP servers for SeekOut/recruiting APIs; consume third-party MCP servers for generic services (email, file, calendar) | Internal APIs have domain-specific schemas that benefit from custom MCP wrapping |
| Server granularity | One MCP server per domain (seekout-search, candidate-profiles, outreach) | Matches microservice boundaries, independent scaling and deployment |
| Agno integration | `MCPTools` with async context manager in agent lifecycle hooks | Align MCP connection lifecycle with agent `on_init`/`on_cleanup` |
| Deployment | Sidecar containers in the same pod/service mesh as recruiter-api | Low latency, shared auth context, simple networking |

---

## 1. MCP Protocol Fundamentals (Spec 2025-11-25)

### 1.1 Protocol Overview

MCP uses JSON-RPC 2.0 for all messages. The protocol defines a lifecycle:

1. **Initialization** -- Client sends `initialize` request with protocol version and capabilities. Server responds with its capabilities. Client confirms with `initialized` notification.
2. **Operation** -- Normal tool discovery (`tools/list`) and invocation (`tools/call`) using negotiated capabilities.
3. **Shutdown** -- Transport-level disconnection (close stdin for stdio, HTTP connection termination for Streamable HTTP).

Servers expose three capability types:
- **Tools** -- Functions the LLM can invoke (primary interest for SPOT)
- **Resources** -- Read-only data the client can fetch (useful for candidate profiles, JD templates)
- **Prompts** -- Reusable prompt templates (useful for outreach templates)

### 1.2 Transport Options

The current spec (2025-11-25) defines two standard transports. The older SSE transport from 2024-11-05 is deprecated but supported via backwards compatibility.

#### stdio

The client spawns the MCP server as a subprocess. Communication happens over stdin/stdout with newline-delimited JSON-RPC messages.

**Characteristics:**
- Client manages server process lifecycle (spawn, monitor, terminate)
- No network overhead -- direct IPC
- Server must never write non-MCP content to stdout (logging goes to stderr)
- Single client per server instance

**Best for:** Local development, CLI tools, testing, embedded servers that run alongside the client process.

**SPOT fit:** Useful for local development and testing. Not suitable for production where recruiter-api needs to share MCP servers across multiple concurrent requests.

#### Streamable HTTP (Replaces SSE)

The server is an independent HTTP service exposing a single MCP endpoint. The client sends JSON-RPC messages via HTTP POST. The server responds with either `application/json` (simple response) or `text/event-stream` (SSE stream for long-running operations).

**Characteristics:**
- Server is a standalone HTTP service (fits FastAPI perfectly)
- Multiple clients can connect simultaneously
- Session management via `MCP-Session-Id` header
- Supports SSE streaming for progress updates, notifications, and server-initiated messages
- Resumable streams via `Last-Event-ID` for reliability
- Protocol version header: `MCP-Protocol-Version: 2025-11-25`

**Security requirements (per spec):**
- MUST validate `Origin` header to prevent DNS rebinding attacks
- SHOULD bind to localhost when running locally
- SHOULD implement proper authentication
- MUST use HTTPS for production

**Best for:** Production deployments, service-to-service communication, multi-client access.

**SPOT fit:** This is the primary transport for production. FastAPI is a natural fit -- the MCP endpoint is just another route. Can be deployed as a sidecar or standalone service.

#### Deprecated: HTTP+SSE (2024-11-05)

The old transport used separate SSE and POST endpoints. Streamable HTTP replaces it with a single endpoint that optionally uses SSE. Clients wanting backwards compatibility can probe the server and fall back to the old transport.

**SPOT fit:** Do not build new servers with this transport. Only relevant if consuming legacy third-party MCP servers.

### 1.3 Transport Comparison for SPOT

| Factor | stdio | Streamable HTTP |
|--------|-------|-----------------|
| Production viability | No (single-client, subprocess) | Yes (multi-client, standalone) |
| FastAPI integration | Poor (subprocess model) | Native (HTTP routes) |
| Network latency | ~0ms (IPC) | ~1-5ms (localhost HTTP) |
| Concurrent clients | 1 | Unlimited |
| Scaling | Not possible | Standard HTTP scaling |
| Dev/test simplicity | High (just run script) | Medium (need HTTP server) |
| Auth integration | Environment variables | HTTP headers (Bearer tokens) |

**Decision: Use Streamable HTTP for all production MCP servers. Use stdio only for local development/testing with third-party MCP servers.**

---

## 2. Building MCP Servers for SPOT

### 2.1 Build vs Consume Decision Matrix

| Service | Build Custom MCP Server? | Rationale |
|---------|--------------------------|-----------|
| SeekOut candidate search | YES | Custom domain, complex query DSL, internal API, no public MCP server exists |
| Candidate profile data | YES | Internal DB/API, domain-specific schema, auth tied to recruiter identity |
| Outreach/messaging | YES (wrapper) | Internal templates + external email APIs, domain logic in composition |
| Email (SendGrid/SES) | MAYBE | Generic MCP servers may exist; build if custom domain logic needed |
| Calendar/scheduling | CONSUME | Generic service, third-party MCP servers available |
| File system access | CONSUME | Standard MCP server (`@modelcontextprotocol/server-filesystem`) |
| Web search | CONSUME or NATIVE | Agno has built-in web search tools; MCP adds overhead here |

**Rule of thumb:** Build MCP servers when the domain logic is SPOT-specific and you control the underlying API. Consume existing MCP servers for generic capabilities.

### 2.2 FastMCP -- Python MCP Server SDK

The official Python MCP SDK (`mcp` package, v1.2.0+) includes `FastMCP`, a high-level API for building MCP servers using Python decorators and type hints.

```python
# packages/mcp-servers/seekout-search/server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("seekout-search")


@mcp.tool()
async def search_candidates(
    query: str,
    skills: list[str] | None = None,
    location: str | None = None,
    experience_years_min: int | None = None,
    experience_years_max: int | None = None,
    limit: int = 20,
) -> str:
    """Search SeekOut for candidates matching criteria.

    Args:
        query: Natural language search query or boolean string.
        skills: Required skills to filter by.
        location: Geographic location filter.
        experience_years_min: Minimum years of experience.
        experience_years_max: Maximum years of experience.
        limit: Maximum number of results to return.
    """
    # Internal SeekOut API call
    results = await seekout_client.search(
        query=query,
        skills=skills,
        location=location,
        experience_range=(experience_years_min, experience_years_max),
        limit=limit,
    )
    return format_candidate_results(results)


@mcp.tool()
async def get_candidate_profile(candidate_id: str) -> str:
    """Get detailed profile for a specific candidate.

    Args:
        candidate_id: The SeekOut candidate identifier.
    """
    profile = await seekout_client.get_profile(candidate_id)
    return format_profile(profile)


@mcp.resource("seekout://search-history/{recruiter_id}")
async def get_search_history(recruiter_id: str) -> str:
    """Get recent search history for a recruiter."""
    history = await db.get_search_history(recruiter_id)
    return json.dumps(history)
```

### 2.3 Running FastMCP with Streamable HTTP

FastMCP supports multiple transports. For production with FastAPI:

```python
# Option 1: Standalone server (recommended for sidecar deployment)
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)


# Option 2: Mount into existing FastAPI app (for in-process deployment)
from starlette.applications import Starlette
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("seekout-search")
# ... register tools ...

# Get the Starlette/ASGI app from FastMCP
mcp_app = mcp.streamable_http_app()

# Mount in FastAPI
from fastapi import FastAPI
app = FastAPI()
app.mount("/mcp/seekout", mcp_app)
```

### 2.4 Proposed MCP Server Architecture for SPOT

```
packages/mcp-servers/
├── seekout-search/           # SeekOut candidate search + profiles
│   ├── pyproject.toml
│   ├── server.py             # FastMCP server with search/profile tools
│   ├── client.py             # Internal SeekOut API client
│   └── Dockerfile
├── recruiting-data/          # SPOT DB: pipelines, JDs, analytics
│   ├── pyproject.toml
│   ├── server.py             # FastMCP server with data query tools
│   ├── queries.py            # SQLAlchemy query layer
│   └── Dockerfile
├── outreach/                 # Email/messaging composition
│   ├── pyproject.toml
│   ├── server.py             # FastMCP server with outreach tools
│   ├── templates.py          # Template engine
│   └── Dockerfile
└── shared/                   # Shared utilities
    ├── auth.py               # MCP auth middleware
    ├── observability.py      # Logging/tracing helpers
    └── errors.py             # Standard error formatting
```

Each MCP server is:
- A standalone Python package managed by `uv`
- Deployable as a Docker container (sidecar or standalone)
- Exposes Streamable HTTP on its own port
- Shares auth middleware from `shared/`

---

## 3. Agno MCP Integration

### 3.1 MCPTools -- Agno's MCP Client

Agno provides `MCPTools` for consuming MCP servers. It works as an async context manager that handles the MCP client lifecycle (connect, initialize, discover tools, cleanup).

```python
from agno.tools.mcp import MCPTools

# stdio transport (local/dev)
async with MCPTools(command="uv run packages/mcp-servers/seekout-search/server.py") as tools:
    agent = Agent(tools=[tools])
    result = await agent.arun("Find senior Python engineers in Seattle")

# SSE transport (existing servers -- legacy)
async with MCPTools(url="http://localhost:8001/sse") as tools:
    agent = Agent(tools=[tools])

# Streamable HTTP transport
# Note: As of the prior research (2026-02-28), Agno's MCPTools supports stdio and SSE.
# Streamable HTTP support was a pending feature request (Issue #3143).
# Check current Agno version for status.
async with MCPTools(url="http://localhost:8001/mcp") as tools:
    agent = Agent(tools=[tools])
```

### 3.2 MultiMCPTools -- Multiple MCP Servers

When an agent needs tools from multiple MCP servers:

```python
from agno.tools.mcp import MultiMCPTools

async with MultiMCPTools(
    # stdio servers
    commands=[
        "uv run packages/mcp-servers/seekout-search/server.py",
    ],
    # HTTP/SSE servers
    urls=[
        "http://localhost:8002/sse",  # recruiting-data
        "http://localhost:8003/sse",  # outreach
    ],
) as mcp_tools:
    agent = Agent(
        name="Sourcing",
        model=OpenAIChat(id="gpt-4.1-mini"),
        tools=[mcp_tools, CandidateScoringToolkit()],  # MCP + native mix
    )
```

### 3.3 Known Gotchas and Limitations

Based on the prior ADK vs Agno research and project experience:

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **Agno is MCP client-only** (cannot act as MCP server) | Cannot expose SPOT agents as MCP tools to external consumers | Use A2A protocol for agent-to-agent exposure instead |
| **Streamable HTTP support pending** (Issue #3143) | May need SSE transport as fallback | SSE is functionally equivalent for current needs; monitor issue for resolution |
| **MCPTools is async context manager** | Connection lifecycle tied to `async with` scope | Must manage scope carefully in long-lived FastAPI services (see Section 4) |
| **Tool name collisions** across MCP servers | Multiple servers might expose tools with same name | Use `MultiMCPTools` which namespaces or deduplicate; alternatively prefix tool names in server definitions |
| **No built-in retry/circuit breaker** | MCP tool call failures propagate directly to agent | Implement retry logic in the `MCPToolProvider` wrapper (see Section 4.3) |
| **Thread safety with session state** (Agno Issue #4663) | Concurrent requests sharing MCPTools instance may conflict | Per-request `build_agent()` pattern already addresses this (see 02-agent-runtime.md) |

### 3.4 Integration with SPOT's Agent Architecture

The existing plan in `02-agent-runtime.md` defines `MCPToolProvider` as a wrapper around `MCPTools`. Here is the refined version that handles lifecycle properly:

```python
from agno.tools.mcp import MCPTools
from spot_agents.base import ToolProvider


class MCPToolProvider(ToolProvider):
    """Provides tools from a remote MCP server via Streamable HTTP.

    Manages connection lifecycle: connect on init, cleanup on shutdown.
    Handles reconnection on failure.
    """

    def __init__(
        self,
        url: str | None = None,
        command: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        self.url = url
        self.command = command
        self.headers = headers or {}
        self.timeout = timeout
        self._mcp_tools: MCPTools | None = None
        self._connected = False

    async def connect(self) -> None:
        """Establish MCP connection. Called during agent on_init."""
        if self.url:
            self._mcp_tools = MCPTools(url=self.url)
        elif self.command:
            self._mcp_tools = MCPTools(command=self.command)
        else:
            raise ValueError("Either url or command must be provided")

        await self._mcp_tools.__aenter__()
        self._connected = True

    async def get_tools(self) -> list:
        """Return the MCP tools for agent construction."""
        if not self._connected:
            await self.connect()
        return [self._mcp_tools]

    async def cleanup(self) -> None:
        """Close MCP connection. Called during agent on_cleanup."""
        if self._mcp_tools and self._connected:
            await self._mcp_tools.__aexit__(None, None, None)
            self._connected = False

    async def reconnect(self) -> None:
        """Force reconnection (e.g., after error)."""
        await self.cleanup()
        await self.connect()
```

Usage in an agent:

```python
class SourcingAgent(AgentBase):
    def __init__(self, seekout_mcp_url: str, db_pool):
        super().__init__()
        self._seekout = MCPToolProvider(url=seekout_mcp_url)
        self._scoring = NativeToolProvider(CandidateScoringToolkit(db_pool))

    async def on_init(self) -> None:
        """Connect to MCP servers on agent registration."""
        await self._seekout.connect()

    async def on_cleanup(self) -> None:
        """Disconnect from MCP servers on shutdown."""
        await self._seekout.cleanup()

    def build_agent(self) -> Agent:
        """Build per-request agent with pre-connected MCP tools."""
        return Agent(
            name="Sourcing",
            model=OpenAIChat(id="gpt-4.1-mini"),
            tools=[
                *self._seekout.get_tools_sync(),  # MCP tools (already connected)
                self._scoring.toolkit,              # Native toolkit
                UserFeedbackTools(),
            ],
            instructions="Search for candidates matching requirements...",
        )
```

---

## 4. MCP Architecture Patterns

### 4.1 Server Granularity: Per-Domain vs Monolithic

| Pattern | Pros | Cons |
|---------|------|------|
| **One MCP server per domain** | Independent deployment, scaling, and failure isolation. Clear ownership. Easier to test. | More moving parts, more connections to manage. |
| **Monolithic MCP server** | Single connection, simpler setup. | Blast radius of failures is larger. Coupling between unrelated tools. Harder to scale selectively. |
| **Hybrid (domain clusters)** | Group related tools (e.g., search + profiles in one server). Balance between isolation and complexity. | Requires judgment on grouping boundaries. |

**Recommendation for SPOT:** Per-domain servers aligned with service boundaries:

```
seekout-search     → search_candidates, get_candidate_profile, get_search_history
recruiting-data    → get_pipeline_stats, get_jd_details, get_analytics
outreach           → draft_email, send_outreach, get_templates, track_opens
```

This matches the agent architecture where each specialist agent (sourcing, outreach, analytics) primarily uses tools from one domain, with occasional cross-domain access handled by the Team leader's hub-and-spoke delegation.

### 4.2 MCP Server Registry and Discovery

For SPOT's scale (3-5 MCP servers), a simple configuration-based registry is sufficient:

```python
# packages/agents/src/spot_agents/config.py
from pydantic_settings import BaseSettings


class MCPServerConfig(BaseSettings):
    """MCP server URLs, loaded from environment."""

    seekout_search_url: str = "http://localhost:8001/mcp"
    recruiting_data_url: str = "http://localhost:8002/mcp"
    outreach_url: str = "http://localhost:8003/mcp"

    class Config:
        env_prefix = "MCP_"
```

For larger deployments, consider a service registry pattern:

```python
class MCPRegistry:
    """Dynamic MCP server discovery."""

    def __init__(self):
        self._servers: dict[str, MCPServerInfo] = {}

    def register(self, name: str, url: str, health_url: str | None = None):
        self._servers[name] = MCPServerInfo(name=name, url=url, health_url=health_url)

    async def discover(self, capability: str) -> list[MCPServerInfo]:
        """Find servers that expose a specific tool/resource."""
        # Could query each server's tools/list or maintain a local cache
        ...

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all registered MCP servers."""
        ...
```

### 4.3 Error Handling and Retry Patterns

MCP defines two error categories:
1. **Protocol errors** -- JSON-RPC errors (unknown tool, malformed request). These indicate client bugs and should not be retried.
2. **Tool execution errors** -- Returned in tool results with `isError: true`. These are actionable and should be fed back to the LLM for self-correction.

```python
import asyncio
from dataclasses import dataclass


@dataclass
class MCPCallResult:
    content: str
    is_error: bool = False
    retryable: bool = False


class ResilientMCPToolProvider(MCPToolProvider):
    """MCPToolProvider with retry logic and circuit breaking."""

    def __init__(
        self,
        url: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        circuit_break_threshold: int = 5,
        circuit_break_reset: float = 60.0,
    ):
        super().__init__(url=url)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_break_threshold = circuit_break_threshold
        self._circuit_break_reset = circuit_break_reset

    async def call_tool_with_retry(
        self, tool_name: str, arguments: dict
    ) -> MCPCallResult:
        """Call an MCP tool with retry logic.

        Note: This is a conceptual pattern. In practice, Agno's MCPTools
        handles tool calls internally. This pattern applies if building
        a custom MCP client layer or wrapping tool calls in agent hooks.
        """
        if self._circuit_open:
            return MCPCallResult(
                content=f"MCP server {self.url} is temporarily unavailable.",
                is_error=True,
                retryable=False,
            )

        for attempt in range(self.max_retries):
            try:
                # Agno MCPTools handles the actual JSON-RPC call
                result = await self._execute_tool(tool_name, arguments)
                self._consecutive_failures = 0
                return result
            except ConnectionError:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._circuit_break_threshold:
                    self._circuit_open = True
                    asyncio.get_event_loop().call_later(
                        self._circuit_break_reset,
                        self._reset_circuit,
                    )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))

        return MCPCallResult(
            content=f"Failed to call {tool_name} after {self.max_retries} attempts.",
            is_error=True,
        )

    def _reset_circuit(self):
        self._circuit_open = False
        self._consecutive_failures = 0
```

### 4.4 Caching MCP Tool Results

MCP itself does not define caching. Implement caching at the application layer:

```python
import hashlib
import json
from datetime import timedelta

from core.redis import get_redis


class CachedMCPToolProvider(MCPToolProvider):
    """Wraps MCP tool calls with Redis caching."""

    def __init__(self, url: str, cache_ttl: timedelta = timedelta(minutes=5)):
        super().__init__(url=url)
        self.cache_ttl = cache_ttl

    @staticmethod
    def _cache_key(tool_name: str, arguments: dict) -> str:
        args_hash = hashlib.sha256(
            json.dumps(arguments, sort_keys=True).encode()
        ).hexdigest()[:16]
        return f"mcp:tool:{tool_name}:{args_hash}"

    async def call_tool_cached(self, tool_name: str, arguments: dict) -> str:
        """Check cache before calling MCP tool."""
        redis = get_redis()
        key = self._cache_key(tool_name, arguments)

        cached = await redis.get(key)
        if cached:
            return cached.decode()

        result = await self._execute_tool(tool_name, arguments)
        await redis.setex(key, int(self.cache_ttl.total_seconds()), result.content)
        return result.content
```

**When to cache:**
- Candidate search results (TTL: 5-15 minutes) -- data changes slowly
- Profile data (TTL: 1 hour) -- rarely changes within a session
- Analytics/pipeline stats (TTL: 30 minutes)

**When NOT to cache:**
- Outreach sends (side-effecting operations)
- Real-time availability data
- Any write operations

### 4.5 Auth and Security

The MCP spec (2025-11-25) defines OAuth 2.1 as the authorization framework for HTTP transports. For SPOT's internal MCP servers, a simpler approach is appropriate:

#### Internal MCP Servers (service-to-service)

```python
# packages/mcp-servers/shared/auth.py
from functools import wraps
from starlette.requests import Request


async def validate_internal_token(request: Request) -> dict:
    """Validate internal service token from recruiter-api.

    For internal MCP servers, we forward the recruiter's auth context
    so tools can enforce per-user access control.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid authorization")

    token = auth_header.split(" ", 1)[1]
    # Validate against same auth system as recruiter-api
    user_context = await verify_token(token)
    return user_context


# In MCP tool implementation:
@mcp.tool()
async def search_candidates(query: str, ctx: Context) -> str:
    """Search candidates with recruiter's permissions."""
    # Access user context from request headers
    user = ctx.request_context.get("user")
    results = await seekout_client.search(
        query=query,
        org_id=user["org_id"],  # Scope to recruiter's org
    )
    return format_results(results)
```

#### External MCP Servers

For consuming third-party MCP servers that require OAuth:

```python
# The MCP spec requires:
# 1. Bearer token in Authorization header on every request
# 2. Token audience validation (RFC 8707)
# 3. PKCE for authorization code flow

async with MCPTools(
    url="https://external-service.com/mcp",
    # Agno MCPTools may accept headers parameter (check current version)
    # Otherwise, configure auth at the HTTP client level
) as tools:
    agent = Agent(tools=[tools])
```

**Header forwarding pattern** for passing recruiter context through MCP:

```python
class AuthenticatedMCPToolProvider(MCPToolProvider):
    """Forwards recruiter auth headers to MCP servers."""

    def __init__(self, url: str, auth_token_factory):
        super().__init__(url=url)
        self._get_token = auth_token_factory

    async def connect(self) -> None:
        token = await self._get_token()
        self.headers = {"Authorization": f"Bearer {token}"}
        await super().connect()
```

---

## 5. MCP Server Lifecycle in FastAPI

### 5.1 Startup and Shutdown

MCP server connections should be managed via FastAPI's lifespan context manager:

```python
# apps/recruiter-api/main.py
from contextlib import asynccontextmanager
from spot_agents.registry import AgentRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    await init_redis()

    # Initialize MCP connections for all agents
    registry: AgentRegistry = app.state.agent_registry
    for agent in registry.all_agents():
        await agent.on_init()  # Connects MCP servers

    yield

    # --- Shutdown ---
    for agent in registry.all_agents():
        await agent.on_cleanup()  # Disconnects MCP servers

    await close_redis()
    engine.dispose()
```

### 5.2 Connection Pooling

For Streamable HTTP transport, MCP connections are essentially HTTP connections. Use connection pooling at the HTTP client level:

```python
import httpx

# Shared HTTP client with connection pooling
_http_client = httpx.AsyncClient(
    timeout=30.0,
    limits=httpx.Limits(
        max_connections=100,       # Total connections across all MCP servers
        max_keepalive_connections=20,  # Keep-alive connections per server
    ),
)
```

For stdio transport, each `MCPTools` instance manages its own subprocess. There is no pooling -- each connection is a separate process.

### 5.3 Health Checks

MCP defines a `ping` utility that can be used for health checks:

```python
# Health check for MCP servers
@health_router.get("/health/mcp")
async def mcp_health():
    """Check connectivity to all MCP servers."""
    results = {}
    for name, provider in mcp_providers.items():
        try:
            # MCP ping is a JSON-RPC request with method "ping"
            await provider.ping(timeout=5.0)
            results[name] = "healthy"
        except Exception as e:
            results[name] = f"unhealthy: {e}"

    all_healthy = all(v == "healthy" for v in results.values())
    status_code = 200 if all_healthy else 503
    return JSONResponse(content=results, status_code=status_code)
```

---

## 6. Production Considerations

### 6.1 Deployment Patterns

#### Sidecar (Recommended for SPOT)

MCP servers run as sidecar containers alongside recruiter-api in the same pod (Kubernetes) or task definition (ECS).

```yaml
# docker-compose.yml (development)
services:
  recruiter-api:
    build: ./apps/recruiter-api
    ports: ["8000:8000"]
    environment:
      MCP_SEEKOUT_SEARCH_URL: http://seekout-mcp:8001/mcp
      MCP_RECRUITING_DATA_URL: http://recruiting-data-mcp:8002/mcp

  seekout-mcp:
    build: ./packages/mcp-servers/seekout-search
    ports: ["8001:8001"]
    environment:
      SEEKOUT_API_KEY: ${SEEKOUT_API_KEY}

  recruiting-data-mcp:
    build: ./packages/mcp-servers/recruiting-data
    ports: ["8002:8002"]
    environment:
      DATABASE_URL: ${DATABASE_URL}
```

**Advantages:**
- Localhost networking (fast, no TLS needed internally)
- Shared resource limits and scaling
- Simple service discovery (fixed hostnames)
- Recruiter-api controls MCP server lifecycle

#### Standalone Service

MCP servers as independent deployments behind a load balancer.

**When to use:** When MCP servers need independent scaling (e.g., SeekOut search is CPU-intensive and needs more replicas than recruiter-api).

#### In-Process (Mount in FastAPI)

MCP server runs inside the recruiter-api process via ASGI mount.

```python
# Mount MCP server directly in recruiter-api
from packages.mcp_servers.seekout_search.server import mcp as seekout_mcp

app.mount("/mcp/seekout", seekout_mcp.streamable_http_app())
```

**Advantages:** Zero network overhead, simplest deployment.
**Disadvantages:** Shared process resources, no independent scaling, failure in MCP server affects recruiter-api.

**Use for:** Small/simple MCP servers (recruiting-data reads from same DB), or during early prototyping.

### 6.2 Monitoring and Observability

#### Structured Logging

```python
import structlog

logger = structlog.get_logger()


# In MCP server tool implementations:
@mcp.tool()
async def search_candidates(query: str) -> str:
    logger.info(
        "mcp.tool.call",
        tool="search_candidates",
        query=query,
        server="seekout-search",
    )
    t0 = time.monotonic()
    try:
        result = await seekout_client.search(query)
        logger.info(
            "mcp.tool.success",
            tool="search_candidates",
            duration_ms=round((time.monotonic() - t0) * 1000),
            result_count=len(result),
        )
        return format_results(result)
    except Exception as e:
        logger.error(
            "mcp.tool.error",
            tool="search_candidates",
            error=str(e),
            duration_ms=round((time.monotonic() - t0) * 1000),
        )
        raise
```

#### Langfuse Integration

Since SPOT already plans to use Langfuse (Phase 5), MCP tool calls should be traced as spans:

```python
from langfuse import Langfuse

langfuse = Langfuse()


class TracedMCPToolProvider(MCPToolProvider):
    """Adds Langfuse tracing to MCP tool calls."""

    async def call_tool(self, tool_name: str, arguments: dict, trace_id: str):
        span = langfuse.span(
            trace_id=trace_id,
            name=f"mcp.{self._server_name}.{tool_name}",
            input=arguments,
        )
        try:
            result = await super()._execute_tool(tool_name, arguments)
            span.end(output={"content": result.content[:500], "is_error": result.is_error})
            return result
        except Exception as e:
            span.end(level="ERROR", status_message=str(e))
            raise
```

#### Key Metrics to Track

| Metric | Source | Alert Threshold |
|--------|--------|----------------|
| MCP tool call latency (p50, p95, p99) | Application | p99 > 5s |
| MCP tool call error rate | Application | > 5% over 5min window |
| MCP server health check failures | Health endpoint | Any failure |
| MCP connection count (active) | HTTP client pool | > 80% of pool limit |
| Tool calls per agent per request | Langfuse trace | > 10 (may indicate agent loop) |

### 6.3 Rate Limiting and Cost Control

#### Server-Side Rate Limiting

```python
# packages/mcp-servers/shared/rate_limit.py
from datetime import timedelta
from core.redis import get_redis


class MCPRateLimiter:
    """Rate limit MCP tool calls per user/org."""

    def __init__(self, max_calls: int, window: timedelta):
        self.max_calls = max_calls
        self.window = window

    async def check(self, user_id: str, tool_name: str) -> bool:
        redis = get_redis()
        key = f"mcp:ratelimit:{user_id}:{tool_name}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, int(self.window.total_seconds()))
        return count <= self.max_calls


# Usage in MCP tool:
rate_limiter = MCPRateLimiter(max_calls=100, window=timedelta(hours=1))

@mcp.tool()
async def search_candidates(query: str, ctx: Context) -> str:
    user_id = ctx.request_context.get("user_id")
    if not await rate_limiter.check(user_id, "search_candidates"):
        return "Rate limit exceeded. Please wait before searching again."
    # ... actual search logic
```

#### Agent-Side Guard Rails

Prevent agents from making excessive MCP calls in a single run:

```python
class ToolCallBudget:
    """Limit total MCP tool calls per agent run."""

    def __init__(self, max_calls: int = 15):
        self.max_calls = max_calls
        self._call_count = 0

    def increment(self) -> bool:
        self._call_count += 1
        return self._call_count <= self.max_calls

    @property
    def exhausted(self) -> bool:
        return self._call_count >= self.max_calls
```

### 6.4 Testing MCP Servers and Integrations

#### Unit Testing MCP Tools

Test tool functions directly without the MCP transport layer:

```python
# packages/mcp-servers/seekout-search/tests/test_tools.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_search_candidates_returns_formatted_results():
    mock_results = [
        {"name": "Jane Doe", "title": "Senior SRE", "location": "Seattle"},
    ]
    with patch("server.seekout_client.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results
        result = await search_candidates(query="SRE Seattle", skills=["kubernetes"])
        assert "Jane Doe" in result
        mock_search.assert_called_once()
```

#### Integration Testing with MCP Client

Test the full MCP protocol round-trip:

```python
# packages/mcp-servers/seekout-search/tests/test_integration.py
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@pytest.mark.asyncio
async def test_mcp_server_tools_list():
    """Verify MCP server exposes expected tools."""
    async with streamable_http_client("http://localhost:8001/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            assert "search_candidates" in tool_names
            assert "get_candidate_profile" in tool_names


@pytest.mark.asyncio
async def test_mcp_tool_call():
    """Test actual tool invocation via MCP protocol."""
    async with streamable_http_client("http://localhost:8001/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_candidates",
                arguments={"query": "python engineer", "limit": 5},
            )
            assert not result.isError
            assert len(result.content) > 0
```

#### Testing Agno Agent + MCP Integration

```python
# packages/agents/tests/integration/test_sourcing_agent.py
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_sourcing_agent_uses_mcp_tools(mock_mcp_server):
    """Test that the sourcing agent correctly invokes MCP tools."""
    agent = SourcingAgent(seekout_mcp_url=mock_mcp_server.url, db_pool=None)
    await agent.on_init()

    try:
        result = await agent.run("Find 5 senior Python engineers in Seattle")
        assert "candidates" in result.content.lower()
    finally:
        await agent.on_cleanup()


@pytest.fixture
async def mock_mcp_server():
    """Spin up a test MCP server with mock data."""
    from mcp.server.fastmcp import FastMCP

    test_mcp = FastMCP("test-seekout")

    @test_mcp.tool()
    async def search_candidates(query: str, limit: int = 20) -> str:
        return '{"candidates": [{"name": "Test Candidate", "title": "Senior Python Engineer"}]}'

    # Run as in-process server for testing
    server = test_mcp.streamable_http_app()
    # ... start with httpx test client or uvicorn
    yield server
```

---

## 7. Recommendations for SPOT

### 7.1 Implementation Roadmap

| Phase | What | When |
|-------|------|------|
| **Phase 1** (Agent Scaffold) | Use `MCPToolProvider` abstraction with mock MCP servers. Validate lifecycle management. | Aligns with orchestrator Phase 1 |
| **Phase 2** (First Real MCP Server) | Build `seekout-search` MCP server with FastMCP + Streamable HTTP. Wire into sourcing agent. | After orchestrator Phase 2 |
| **Phase 3** (Production Hardening) | Add auth forwarding, caching, rate limiting, Langfuse tracing. Deploy as sidecars. | Aligns with orchestrator Phase 5 |
| **Phase 4** (Expand) | Build `recruiting-data` and `outreach` MCP servers. Consume third-party MCP servers for generic capabilities. | Post-MVP |

### 7.2 Key Architecture Decisions

1. **Transport: Streamable HTTP** -- It is the current MCP spec standard, maps directly to FastAPI routes, supports multi-client access, and provides session management. If Agno's `MCPTools` does not yet support Streamable HTTP (Issue #3143), use SSE as a bridge and contribute/monitor the issue.

2. **Build custom MCP servers for internal APIs** -- SeekOut search, candidate profiles, and recruiting data are domain-specific with complex schemas. Custom MCP servers give full control over tool definitions, auth, and error handling. Use FastMCP for rapid development.

3. **One MCP server per domain** -- Aligns with microservice boundaries and the per-agent tool ownership model. Each specialist agent primarily consumes tools from one MCP server.

4. **Lifecycle via agent hooks** -- Connect MCP in `on_init()`, disconnect in `on_cleanup()`. The per-request `build_agent()` pattern (already in the plan) avoids thread-safety issues with shared MCP connections.

5. **Sidecar deployment** -- Start with docker-compose sidecars for development, deploy as sidecar containers in production. Consider in-process mounting for read-only data tools that share the same database.

6. **Cache aggressively, trace everything** -- Redis caching for search results and profiles (5-15 min TTL). Langfuse spans for every MCP tool call. Rate limit per user per tool.

### 7.3 What NOT to Do

- **Do not expose SPOT agents as MCP servers.** Agno is client-only for MCP. Use A2A protocol for agent-to-agent communication instead.
- **Do not use stdio transport in production.** It is single-client and requires subprocess management.
- **Do not build a monolithic MCP server** with all tools in one process. It creates coupling and blast radius problems.
- **Do not cache write operations** (outreach sends, profile updates). Only cache idempotent read operations.
- **Do not skip auth on internal MCP servers.** Even service-to-service calls should forward the recruiter's identity for per-user access control and audit logging.

### 7.4 Open Questions

1. **Agno Streamable HTTP status** -- Check if `MCPTools` now supports Streamable HTTP (Issue #3143 was pending as of 2026-02-28). If not, SSE works as a fallback, but Streamable HTTP is preferred.

2. **MCP session affinity** -- For stateful MCP servers (e.g., maintaining search cursor state), how does session affinity work when recruiter-api scales horizontally? May need sticky sessions or stateless MCP servers.

3. **Tool result size limits** -- MCP has no built-in pagination for tool results. For large result sets (e.g., 100+ candidates), should the MCP server paginate internally, or should the agent request pages?

4. **Cross-agent tool sharing** -- If the sourcing agent and analytics agent both need `get_pipeline_stats`, should they share an MCP connection or each maintain their own? (Recommendation: separate connections for isolation, share the MCP server instance.)

---

## References

- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) -- Current protocol spec
- [MCP Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) -- stdio and Streamable HTTP details
- [MCP Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) -- OAuth 2.1 auth spec
- [MCP Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) -- Tool definition and invocation spec
- [MCP Python SDK (FastMCP)](https://modelcontextprotocol.io/quickstart/server) -- Server quickstart
- [Agno MCP Docs](https://docs.agno.com/tools/mcp) -- MCPTools usage
- [Agno GitHub Issue #3143](https://github.com/agno-agi/agno/issues/3143) -- Streamable HTTP support
- [SPOT Agent Orchestrator Plan](../../apps/plans/agent-orchestrator/plan.md) -- System design
- [SPOT Agent Runtime Spec](../../apps/plans/agent-orchestrator/02-agent-runtime.md) -- Tool system, MCPToolProvider
- [ADK vs Agno Research](./agent-orchestration-adk-vs-agno.md) -- Framework comparison with MCP analysis
