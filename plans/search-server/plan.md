# SeekOut MCP Search Server — Plan

**Date:** 2026-03-04 (ported 2026-03-06)
**Status:** Implemented (Phases 1-4 complete, ported from spot-v2)
**Package:** `packages/search/` → `seekout-mcp-search`

---

## Vision

A Python MCP server exposing SeekOut people search as MCP tools, callable by Claude Desktop, Cursor, and internal agents. Built on community FastMCP 3.0 (PrefectHQ/fastmcp) with three auth modes (dev token, API key, JWT), entity resolution, facet return, and Redis-backed stateful search sessions.

```
                        External MCP Clients
                     (Claude Desktop, Cursor)
                              │
                              │ Bearer JWT (RS256)
                              ▼
┌─────────────────────────────────────────────────┐
│           seekout-mcp-search (port 8001)        │
│  ┌───────────────────────────────────────────┐  │
│  │          CompositeVerifier                │  │
│  │  StaticToken │ API Key │ JWTVerifier      │  │
│  └───────────────────────────────────────────┘  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ tools.py │─▶│query_builder │─▶│seekout_api│ │
│  │ 15 tools │  │  .py         │  │  .py      │ │
│  └──────────┘  └──────┬───────┘  └─────┬─────┘ │
│                       │                │        │
│                ┌──────▼───────┐        │        │
│                │entity_resolver│       │        │
│                │  .py (cache) │        │        │
│                └──────────────┘        │        │
└────────────────────────────────────────┼────────┘
                                         │ httpx
              Internal agents            │
              (X-API-Key header)         ▼
                              ┌──────────────────┐
                              │ SeekOut Runtime   │
                              │ API (HTTP)        │
                              └──────────────────┘
```

---

## Package Structure

```
packages/search/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── seekout_mcp_search/
│   ├── __init__.py             # exports create_server(), Settings
│   ├── __main__.py             # python -m seekout_mcp_search
│   ├── server.py               # create_server() factory
│   ├── config.py               # pydantic-settings
│   ├── auth.py                 # CompositeVerifier
│   ├── seekout_api.py          # httpx client for Runtime API
│   ├── entity_resolver.py      # name → ID resolution with TTLCache
│   ├── query_builder.py        # Filters dict → PeopleSearchQuery
│   ├── session_store.py        # Redis-backed sessions
│   └── tools.py                # 15 MCP tools
└── tests/
```

---

## Tools

| Tool | Type | Description |
|------|------|-------------|
| `seekout_ping` | Stateless | Connectivity check |
| `seekout_search_people` | Stateless | Search with flat params, returns candidates + facets |
| `seekout_count_results` | Stateless | Count only + facets |
| `seekout_get_facets` | Stateless | Facet breakdowns |
| `seekout_get_profile` | Stateless | Detailed candidate profile |
| `seekout_get_suggestions` | Stateless | Entity autocomplete |
| `seekout_validate_query` | Stateless | Boolean query validation |
| `seekout_get_query` | Stateless | Inspect built PeopleSearchQuery |
| `seekout_get_link` | Stateless | Generate SeekOut app URL |
| `session_create` | Stateful | Create search session |
| `session_add_filter` | Stateful | Add/replace filter on session |
| `session_remove_filter` | Stateful | Remove filter from session |
| `session_run_search` | Stateful | Execute search with accumulated filters |
| `session_get` | Stateful | Inspect session state |
| `session_delete` | Stateful | Delete session |

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Library | Community FastMCP 3.0 (PrefectHQ/fastmcp) | Superior auth (JWTVerifier, StaticTokenVerifier), stateless_http mode |
| Transport | `stateless_http=True` (single `/mcp` endpoint) | Stateless HTTP; session state lives in Redis, not MCP transport |
| Query builder internal API | Accepts `Filters` dict, not flat strings | Flat-param tools are thin adapter; session tools reuse same builder |
| Skills handling | Appended to boolean search string | Matches C# behavior; `skill:ID` or `"name"` format |
| Entity resolution cache | `cachetools.TTLCache`, 1h TTL, in-process | Simple, no external dependency |
| Auth dispatch | `CompositeVerifier`: API key first, falls back to JWT | Single `/mcp` endpoint serves internal agents and external clients |
| Session storage | Redis with sliding TTL | Horizontal scaling, 1h default TTL |
| Public API | `create_server(Settings)` factory | Works for standalone, library import, and ASGI mount |

---

## Spec Index

| # | Spec | What It Covers |
|---|------|----------------|
| **01** | [Tools & Query Builder](./01-tools-and-query-builder.md) | All tools, query builder, entity resolver, Runtime API surface |
| **02** | [Auth & Deployment](./02-auth-and-deployment.md) | Three auth modes, CompositeVerifier, config, Docker |
| **Research** | [Deployment Research](./research.md) | Full research + sounding board: auth flow, iteration decisions, risk matrix |

---

## Deployment

- **Standalone:** `python -m seekout_mcp_search`
- **Docker:** `docker build -t seekout-mcp-search --target dev packages/search/`
- **AKS:** Helm values at `deploy/mcp-search/values.yaml`
- **Library:** `from seekout_mcp_search import create_server, Settings`

---

## Future Work

- **Additional filter dimensions:** School, major, degree, industry, company size, seniority
- **Multi-session per user:** `mcp:search:{user_id}:{session_id}` with session listing
- **Full OAuth end-to-end testing:** Requires recruit-api OAuth server
- **New MCP servers:** outreach, recruiting-data (separate packages in this repo)
