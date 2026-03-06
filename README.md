# seekout-mcp-servers

MCP servers exposing SeekOut functionality to AI agents and tools.

## Packages

### seekout-mcp-search

SeekOut people search exposed as MCP tools.

#### Quick Start

```bash
cd packages/search
uv sync --dev
uv run python -m seekout_mcp_search
```

Required environment variables (or `.env` file):

| Variable | Description | Default |
|---|---|---|
| `SPOT_ENV` | Environment (`local` for dev token auth) | `production` |
| `MCP_PORT` | Server port | `8001` |
| `SEEKOUT_RUNTIME_API_ENDPOINT` | Runtime API base URL | `http://localhost:9000` |
| `SEEKOUT_RUNTIME_API_KEY` | Runtime API key | |
| `SEEKOUT_JWKS_URI` | JWKS endpoint for JWT validation | |
| `SEEKOUT_OAUTH_ISSUER` | OAuth issuer URL | |
| `SEEKOUT_MCP_AUDIENCE` | JWT audience | `seekout-mcp-server` |
| `SEEKOUT_MCP_RESOURCE_URL` | Protected resource URL (RFC 9728) | |
| `MCP_INTERNAL_API_KEY` | API key for internal agents | |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `SESSION_TTL_SECONDS` | Session expiry | `3600` |
| `QUERY_STORE_ENDPOINT` | Query store URL (for app links) | |
| `QUERY_STORE_API_KEY` | Query store API key | |

#### Claude Desktop Config

```json
{
  "mcpServers": {
    "seekout": {
      "url": "http://localhost:8001/mcp",
      "headers": {
        "Authorization": "Bearer dev-token-123"
      }
    }
  }
}
```

#### Docker

```bash
docker build -t seekout-mcp-search --target dev packages/search/
docker run -p 8001:8001 --env-file packages/search/.env seekout-mcp-search
```

#### Available Tools

| Tool | Description |
|---|---|
| `seekout_ping` | Check connectivity to the SeekOut Runtime API |
| `seekout_search_people` | Search for candidates matching criteria |
| `seekout_count_results` | Get candidate count without returning profiles |
| `seekout_get_facets` | Get facet breakdowns for a search |
| `seekout_get_profile` | Get detailed profile for a candidate |
| `seekout_get_suggestions` | Autocomplete suggestions for entity names |
| `seekout_validate_query` | Validate a boolean search expression |
| `seekout_get_query` | Inspect the built PeopleSearchQuery |
| `seekout_get_link` | Generate a SeekOut app URL for a search |
| `session_create` | Create a new search session |
| `session_add_filter` | Add/replace a filter on a session |
| `session_remove_filter` | Remove a filter from a session |
| `session_run_search` | Execute search with session filters |
| `session_get` | Get current session state |
| `session_delete` | Delete a session |

#### Library Usage

```python
from seekout_mcp_search import create_server, Settings

settings = Settings()
mcp = create_server(settings)

# Mount in an existing ASGI app
app.mount("/mcp/seekout", mcp.streamable_http_app())
```

#### Development

```bash
cd packages/search
uv sync --dev
uv run pytest -v
uv run ruff check seekout_mcp_search/ tests/
```
