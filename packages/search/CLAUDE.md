# CLAUDE.md (seekout-mcp-search)

## Purpose

Package-level guidance for `packages/search/` — the SeekOut people search MCP server.

## Inheritance

- Root `AGENTS.md` and `CLAUDE.md` still apply as baseline policy.
- This file adds package-specific skill routing and conventions.

## Skill Allowlist

Use these skills first for work in this package:

- `python-code-style`
- `python-design-patterns`
- `python-error-handling`
- `python-type-safety`
- `python-testing-patterns`
- `python-observability`
- `python-resilience`
- `python-resource-management`
- `python-configuration`
- `async-python-patterns`
- `python-anti-patterns`
- `python-performance-optimization`
- `uv-package-manager`

## Routing Rules

- If editing files under `packages/search/`, select skills from the allowlist above.
- Use only the minimal number of skills required by the task.
- If a required capability is missing from the allowlist, use a directly relevant shared skill and call out why.

## Stack

- **Framework:** FastMCP 3.0 (PrefectHQ/fastmcp) with `stateless_http=True`
- **Python:** >=3.12
- **Config:** pydantic-settings (`config.py`)
- **HTTP client:** httpx async (`seekout_api.py`)
- **Auth:** CompositeVerifier — API key + JWT/JWKS (`auth.py`)
- **Sessions:** Redis-backed with sliding TTL (`session_store.py`)
- **Entity resolution:** In-process TTLCache, 1h (`entity_resolver.py`)
- **Testing:** pytest, pytest-asyncio

## Package Layout

```
seekout_mcp_search/
├── __init__.py           # exports create_server(), Settings
├── __main__.py           # python -m seekout_mcp_search
├── server.py             # create_server() factory
├── config.py             # pydantic-settings
├── auth.py               # CompositeVerifier (API key + JWT)
├── seekout_api.py        # httpx client for Runtime API
├── entity_resolver.py    # name -> ID resolution with TTLCache
├── query_builder.py      # Filters dict -> PeopleSearchQuery
├── session_store.py      # Redis-backed sessions
└── tools.py              # 15 MCP tools (register_tools function)
```

## Key Patterns

- **Public API:** `create_server(Settings)` factory — used for standalone, library import, and ASGI mount
- **Tool registration:** `register_tools(mcp, api, resolver, builder, session_store)` — conditional registration based on available services
- **Query builder:** Accepts `Filters` dict internally; `flat_params_to_filters()` adapter for stateless tools
- **Auth dispatch:** `CompositeVerifier` tries API key first, falls back to JWT

## Do's and Don'ts

### Do
- Use the `create_server()` factory for all consumption modes
- Add new tools in `tools.py` via `register_tools()`
- Use `Filters` dict as the internal query representation
- Write tests for every new tool (see `tests/test_tools.py` pattern)
- Use `SeekOutAPI` for all Runtime API calls (never raw httpx)

### Don't
- Do not instantiate FastMCP directly outside `server.py`
- Do not add module-level state — all state flows through `create_server()`
- Do not bypass `CompositeVerifier` for auth
- Do not use synchronous HTTP calls
