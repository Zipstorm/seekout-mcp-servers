# SeekOut MCP Server — Auth & Deployment

This spec covers the three authentication modes, configuration management, Dockerfile, and docker-compose integration. It is one of two specs that form the mcp-seekout plan. Start with [plan.md](./plan.md) for the full picture.

---

## 1. Authentication

The MCP server supports three auth modes dispatched by a single `CompositeVerifier`. All modes funnel through one endpoint: `POST /mcp`.

### 1.1 Auth Mode Selection

```
Incoming request to /mcp
    │
    ├─ SPOT_ENV=local?
    │   └─ Yes → StaticTokenVerifier (dev tokens)
    │
    └─ No (production/staging) → CompositeVerifier:
        │
        ├─ X-API-Key header present?
        │   └─ Yes → validate against MCP_INTERNAL_API_KEY
        │       ├─ Match → authenticated (service identity)
        │       └─ No match → 401
        │
        └─ No X-API-Key → JWTVerifier
            └─ Authorization: Bearer <token>
                ├─ Valid JWT (RS256, JWKS) → authenticated (user identity)
                └─ Invalid/missing → 401
```

### 1.2 Implementation

```python
# In main.py

from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.providers.jwt import JWTVerifier, StaticTokenVerifier

class CompositeVerifier(TokenVerifier):
    """Dispatches auth based on request headers.

    Checks X-API-Key first (internal agents), falls back to JWT (external clients).
    """

    def __init__(self, internal_api_key: str, jwt_verifier: JWTVerifier):
        self._api_key = internal_api_key
        self._jwt = jwt_verifier

    async def verify_token(self, token: str, **kwargs) -> dict:
        # FastMCP passes the Bearer token from Authorization header.
        # For API key auth, we need to check if the original request
        # had X-API-Key instead.
        #
        # Implementation note: FastMCP 3.0's auth flow extracts the
        # Bearer token and passes it to verify_token(). For X-API-Key,
        # we may need to use middleware or check kwargs for headers.
        # This needs verification against FastMCP 3.0 source.
        #
        # Fallback approach: if FastMCP doesn't expose headers,
        # treat the token as either an API key or JWT based on format.
        # API keys are opaque strings; JWTs have 3 dot-separated parts.

        if "." not in token:
            # Opaque token — check as API key
            if token == self._api_key:
                return {"client_id": "internal-agent", "scopes": ["mcp:tools"]}
            raise ValueError("Invalid API key")

        # JWT — delegate to JWTVerifier
        return await self._jwt.verify_token(token, **kwargs)


def create_auth_verifier(settings) -> TokenVerifier:
    if settings.spot_env == "local":
        return StaticTokenVerifier(
            tokens={
                "dev-token-123": {
                    "client_id": "dev@seekout.io",
                    "scopes": ["mcp:tools"],
                }
            }
        )

    jwt_verifier = JWTVerifier(
        jwks_uri=settings.seekout_jwks_uri,
        issuer=settings.seekout_oauth_issuer,
        audience=settings.seekout_mcp_audience,
    )
    return CompositeVerifier(
        internal_api_key=settings.mcp_internal_api_key,
        jwt_verifier=jwt_verifier,
    )
```

**Internal agent usage:**

```python
# From a spot-v2 agent (e.g., market-insights-agent)
from fastmcp import Client

client = Client(
    "http://mcp-seekout:8001/mcp",
    headers={"Authorization": f"Bearer {os.environ['MCP_SEEKOUT_API_KEY']}"},
)
async with client:
    result = await client.call_tool("seekout_search_people", {
        "query": "Python engineer",
        "locations": "Seattle",
    })
```

### 1.3 Protected Resource Metadata

External MCP clients (Claude Desktop, Cursor) need to discover the OAuth authorization server. The MCP server exposes this via RFC 9728:

```python
# In main.py — custom route or Starlette middleware

@mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
async def protected_resource_metadata(request):
    from starlette.responses import JSONResponse
    return JSONResponse({
        "resource": settings.seekout_mcp_resource_url,
        "authorization_servers": [settings.seekout_oauth_issuer],
        "scopes_supported": ["mcp:tools"],
        "bearer_methods_supported": ["header"],
    })
```

**Open question:** Verify that `@mcp.custom_route()` works in `stateless_http=True` mode. If not, mount on the underlying Starlette/ASGI app directly.

---

## 2. Configuration

All configuration via environment variables, managed by pydantic-settings.

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False}

    # Server
    spot_env: str = "production"
    mcp_port: int = 8001

    # SeekOut Runtime API
    seekout_runtime_api_endpoint: str
    seekout_runtime_api_key: str

    # Auth — JWT (external clients)
    seekout_jwks_uri: str = ""
    seekout_oauth_issuer: str = ""
    seekout_mcp_audience: str = "seekout-mcp-server"
    seekout_mcp_resource_url: str = ""

    # Auth — API key (internal agents)
    mcp_internal_api_key: str = ""
```

**Environment variable reference:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SPOT_ENV` | No | `production` | `local` for dev mode (StaticTokenVerifier) |
| `MCP_PORT` | No | `8001` | Server listen port |
| `SEEKOUT_RUNTIME_API_ENDPOINT` | Yes | — | Base URL for SeekOut Runtime API |
| `SEEKOUT_RUNTIME_API_KEY` | Yes | — | API key for Runtime API (same as C# server) |
| `SEEKOUT_JWKS_URI` | Prod | — | JWKS endpoint URL (e.g., `https://app.seekout.io/api/oauth/jwks`) |
| `SEEKOUT_OAUTH_ISSUER` | Prod | — | OAuth issuer URL (e.g., `https://app.seekout.io`) |
| `SEEKOUT_MCP_AUDIENCE` | No | `seekout-mcp-server` | Expected JWT audience claim |
| `SEEKOUT_MCP_RESOURCE_URL` | Prod | — | This server's public URL (for resource metadata) |
| `MCP_INTERNAL_API_KEY` | Prod | — | Shared secret for internal agent auth |

---

## 3. Dockerfile

Multi-stage build using `uv` for fast dependency installation, following the pattern from recruiter-api.

```dockerfile
# ── Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml .
RUN uv sync --no-dev --frozen

COPY . .

# ── Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

CMD ["python", "main.py"]
```

**Notes:**
- No `dev` target needed for iteration 1 — local dev uses `uv run python main.py` directly
- `uv sync --no-dev --frozen` installs only production dependencies
- If hot-reload is needed, add a `dev` target with `fastmcp dev main.py`

---

## 4. Docker-Compose

Add to `docker-compose.yml`:

```yaml
  # ── MCP SeekOut ──────────────────────────────────────────────────────
  mcp-seekout:
    container_name: spot-mcp-seekout
    build:
      context: apps/mcp-seekout
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      - SPOT_ENV=${SPOT_ENV:-local}
      - MCP_PORT=8001
      - SEEKOUT_RUNTIME_API_ENDPOINT=${SEEKOUT_RUNTIME_API_ENDPOINT}
      - SEEKOUT_RUNTIME_API_KEY=${SEEKOUT_RUNTIME_API_KEY}
      - SEEKOUT_JWKS_URI=${SEEKOUT_JWKS_URI:-http://host.docker.internal:3000/api/oauth/jwks}
      - SEEKOUT_OAUTH_ISSUER=${SEEKOUT_OAUTH_ISSUER:-http://localhost:3000}
      - SEEKOUT_MCP_AUDIENCE=${SEEKOUT_MCP_AUDIENCE:-seekout-mcp-server}
      - MCP_INTERNAL_API_KEY=${MCP_INTERNAL_API_KEY:-dev-internal-key}
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped
```

Update the `ready` service banner to include:

```
echo "  MCP:     http://localhost:8001/mcp"
```

---

## 5. main.py Skeleton

```python
# main.py
import os
from fastmcp import FastMCP
from config import Settings
from seekout_api import SeekOutAPI
from entity_resolver import EntityResolver
from query_builder import QueryBuilder

settings = Settings()

# Auth
verifier = create_auth_verifier(settings)

# FastMCP server
mcp = FastMCP(
    "seekout-search",
    auth=verifier,
    stateless_http=True,
    port=settings.mcp_port,
)

# Dependencies
seekout_api = SeekOutAPI(
    base_url=settings.seekout_runtime_api_endpoint,
    api_key=settings.seekout_runtime_api_key,
)
entity_resolver = EntityResolver(seekout_api)
query_builder = QueryBuilder(entity_resolver, seekout_api)

# Register tools (imported from tools.py, which uses the module-level instances)
from tools import register_tools
register_tools(mcp, query_builder, seekout_api)

# Protected resource metadata
@mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
async def protected_resource_metadata(request):
    from starlette.responses import JSONResponse
    return JSONResponse({
        "resource": settings.seekout_mcp_resource_url,
        "authorization_servers": [settings.seekout_oauth_issuer],
        "scopes_supported": ["mcp:tools"],
        "bearer_methods_supported": ["header"],
    })

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

---

## 6. Claude Desktop Configuration

For local testing with dev token:

```json
{
  "mcpServers": {
    "seekout": {
      "url": "http://localhost:8001/mcp",
      "auth": {
        "type": "bearer",
        "token": "dev-token-123"
      }
    }
  }
}
```

For full OAuth testing (after recruit-api PR #5335):

```json
{
  "mcpServers": {
    "seekout": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

---

## Related Specs

- [plan.md](./plan.md) — Master plan and phase overview
- [01-tools-and-query-builder.md](./01-tools-and-query-builder.md) — All 8 tools, query builder, entity resolver, Runtime API surface
