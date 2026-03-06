# Research: SeekOut MCP Server Deployment in spot-v2 with SeekOut OAuth Authentication

**Date**: 2026-03-05
**Depth**: deep dive
**Question**: How do we deploy a Python-based SeekOut MCP server (FastMCP 3.0) in spot-v2 that authenticates via SeekOut's OAuth 2.1, handles stateful search workflows, and can be tested locally?

## Executive Summary

- **FastMCP 3.0 + JWTVerifier is the right stack**: FastMCP 3.0's `JWTVerifier` can validate RS256 JWTs issued by recruit-api's new OAuth 2.1 server (PR #5335). The MCP server validates tokens via the JWKS endpoint at `{issuer}/api/oauth/jwks` — no custom auth code needed. (confidence: high)
- **recruit-api PR #5335 provides the full auth server**: The PR adds OAuth 2.1 Authorization Code + PKCE flow with RS256 JWT signing, JWKS endpoint, refresh token rotation, and RFC 8414 discovery. MCP clients (Claude Desktop, VS Code) can auto-discover and authenticate against SeekOut. (confidence: high)
- **Server-side state IS necessary for token efficiency**: The `Filters` class has 60+ properties, `PeopleSearchQuery` has 30+ more. Option D (stateless with full JSON echo) would cost ~2,000-4,000 tokens per 5-step search just on filter round-tripping. Stateful `add_filter`/`run_search` tools cost ~150-300 tokens for the same workflow — 10-15x cheaper. (confidence: high)
- **Start simple, prove the concept first**: Port the current C# MCP server's 7 stateless tools as-is to Python — don't rebuild the QueryBuilder architecture. The existing tools work. Focus on proving: deployment, auth via SeekOut OAuth, local testing with Claude Desktop. Advanced stateful tools come in iteration 2. (confidence: high)
- **Local testing is achievable with StaticTokenVerifier**: FastMCP 3.0 provides `StaticTokenVerifier` for dev/test, plus the MCP Inspector CLI for protocol-level testing. Full end-to-end testing with Claude Desktop requires the OAuth flow running locally. (confidence: high)
- **Bottom line**: Build a FastMCP 3.0 server in `apps/mcp-seekout/` in spot-v2, validate JWTs from recruit-api's OAuth server via JWKS. Iteration 1: port the current 7 C# tools as-is. Iteration 2: add stateful session tools (`add_filter`/`run_search`) for token-efficient iterative search.

## Sub-question Findings

### 1. How does authentication work end-to-end?

**Finding**: recruit-api acts as the OAuth 2.1 Authorization Server; the MCP server is a Resource Server that validates JWTs via JWKS.
**Confidence**: high

**The auth flow (from PR #5335):**

```
MCP Client (Claude Desktop, VS Code, Cursor)
    │
    ├─1─► MCP Server (seekout-mcp) → 401 + resource_metadata
    │     pointing to /.well-known/oauth-protected-resource
    │
    ├─2─► recruit-api: GET /.well-known/oauth-authorization-server
    │     Returns: authorization_endpoint, token_endpoint, jwks_uri
    │
    ├─3─► recruit-api: GET /api/oauth/authorize
    │     → Redirects to SeekOut login (email/password, Microsoft, Google, SAML)
    │     → After login: returns auth code with PKCE challenge
    │
    ├─4─► recruit-api: POST /api/oauth/token
    │     {grant_type: "authorization_code", code, code_verifier, redirect_uri, client_id}
    │     → Returns: {access_token (RS256 JWT), refresh_token, expires_in: 3600}
    │
    └─5─► MCP Server: POST /mcp (with Authorization: Bearer <JWT>)
          → JWTVerifier validates via JWKS at {issuer}/api/oauth/jwks
          → Extracts sub, email, name, scope from JWT claims
          → Tool executes with user context
```

**JWT claims issued by recruit-api:**
- `sub`: SeekOut user ID
- `email`: User's primary email
- `name`: User's display name
- `scope`: "mcp:tools"
- `iss`: e.g., "https://app.seekout.io"
- `aud`: "seekout-mcp-server" (configurable via `OAUTH_MCP_AUDIENCE`)
- `exp`: 1 hour from issuance
- Signed with RS256, key ID in `kid` header

**FastMCP 3.0 server-side setup (three auth modes):**

The MCP server supports three auth modes depending on the caller:
1. **StaticTokenVerifier** — local dev (`SPOT_ENV=local`), hardcoded dev tokens
2. **API key** — internal spot-v2 agents in the same cluster, shared secret via `MCP_INTERNAL_API_KEY` env var
3. **JWTVerifier** — external MCP clients (Claude Desktop, Cursor), validates RS256 JWTs via JWKS

```python
import os
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier, StaticTokenVerifier

def create_auth_verifier():
    env = os.environ.get("SPOT_ENV", "production")

    if env == "local":
        # Dev mode: static tokens for local testing
        return StaticTokenVerifier(
            tokens={"dev-token-123": {"client_id": "dev@seekout.io", "scopes": ["mcp:tools"]}}
        )

    # Production/staging: composite auth
    # - API key for internal agents (spot-v2 Python services)
    # - JWT for external clients (Claude Desktop, Cursor)
    #
    # Implementation: custom verifier that checks for X-API-Key header first,
    # falls back to JWT validation via JWKS
    internal_api_key = os.environ.get("MCP_INTERNAL_API_KEY")
    jwt_verifier = JWTVerifier(
        jwks_uri=os.environ["SEEKOUT_JWKS_URI"],
        issuer=os.environ["SEEKOUT_OAUTH_ISSUER"],
        audience=os.environ.get("SEEKOUT_MCP_AUDIENCE", "seekout-mcp-server"),
    )
    return CompositeVerifier(internal_api_key=internal_api_key, jwt_verifier=jwt_verifier)

mcp = FastMCP("seekout-search", auth=create_auth_verifier(), stateless_http=True)
```

**Internal agent usage (no OAuth, just API key):**
```python
# From a spot-v2 Python agent (e.g., market-insights-agent)
from fastmcp import Client

client = Client(
    "http://mcp-seekout:8001/mcp",
    headers={"X-API-Key": os.environ["MCP_SEEKOUT_API_KEY"]},
)
```

**The MCP server also needs to expose protected resource metadata** so clients can discover the auth server:

```python
@mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
async def protected_resource_metadata(request):
    return JSONResponse({
        "resource": os.environ["SEEKOUT_MCP_RESOURCE_URL"],
        "authorization_servers": [os.environ["SEEKOUT_OAUTH_ISSUER"]],
        "scopes_supported": ["mcp:tools"],
        "bearer_methods_supported": ["header"],
    })
```

### 2. How do we port the C# tools to Python?

**Finding**: Port the existing 7 C# tools as-is. Don't rebuild the QueryBuilder architecture — the current flat-param approach works for proving the concept.
**Confidence**: high

**C# tools to port (from `Spot.Mcp.Servers.SeekOut`):**

| C# Tool | Python equivalent | Parameters |
|---------|------------------|------------|
| `SearchPeopleTool` | `seekout_search_people` | query, titles, companies, locations, skills, years_experience_min/max, max_results, skip |
| `CountResultsTool` | `seekout_count_results` | same filter params, returns count only |
| `GetFacetsTool` | `seekout_get_facets` | same filter params, returns facet breakdowns |
| `GetProfileTool` | `seekout_get_profile` | profile_key, index |
| `GetSuggestionsTool` | `seekout_get_suggestions` | entity_type, query |
| `ValidateQueryTool` | `seekout_validate_query` | boolean query string |
| `PingTool` | `seekout_ping` | none |

**The Python port is a thin layer:**

```python
# 1. Same flat string params as C# (comma-separated titles, companies, etc.)
# 2. Same entity resolution: call /api/Search/Get to resolve names → IDs
# 3. Same Runtime API: POST /api/PeopleSearch/SearchPeople
# 4. httpx replaces IHttpClientFactory
# 5. cachetools.TTLCache replaces IMemoryCache for entity resolution caching
```

**What we're NOT doing in iteration 1:**
- No full `PeopleSearchQuery` Pydantic model (60+ filter properties = unnecessary complexity)
- No structured JSON filters (token-expensive for the LLM to reconstruct)
- No server-side session state (that's iteration 2)
- No custom QueryBuilder architecture — just the same flat-param → query conversion the C# version does

**What we ARE proving:**
- FastMCP 3.0 server running in Python
- JWT auth via SeekOut OAuth (JWKS validation)
- SeekOut Runtime API integration via httpx
- Local dev with StaticTokenVerifier
- Claude Desktop end-to-end

### 3. Where does this live in spot-v2?

**Finding**: New `apps/mcp-seekout/` directory, following the existing FastAPI app pattern.
**Confidence**: high

The spot-v2 repo is a pnpm monorepo with Python apps in `apps/`. There's no `packages/` directory. Each app is self-contained with its own Dockerfile and `pyproject.toml`.

**Proposed structure (iteration 1 — keep it simple):**

```
apps/mcp-seekout/
├── pyproject.toml              # uv-managed: fastmcp, httpx, pydantic, cachetools
├── Dockerfile
├── main.py                     # FastMCP server: auth setup, tool registration, run()
├── config.py                   # pydantic-settings: SEEKOUT_RUNTIME_API_*, OAUTH_*
├── seekout_api.py              # httpx client for SeekOut Runtime API (SearchPeople, GetProfile, SearchEntities, etc.)
├── query_builder.py            # Flat params → PeopleSearchQuery dict (port of C# QueryBuilder)
├── entity_resolver.py          # Resolve names → IDs via /api/Search/Get (with TTL cache)
├── tools.py                    # All 7 MCP tools in one file (same interface as C# tools)
├── tests/
│   ├── conftest.py
│   ├── test_query_builder.py
│   ├── test_entity_resolver.py
│   └── test_tools.py
└── CLAUDE.md
```

This is intentionally flat — no `models/`, `services/`, `core/` subdirectories. We can refactor when complexity warrants it. The C# version has more structure because it has the Orchestrator, Skills, and QueryGeneration systems layered on top — we're only porting the SeekOut tools layer.

**docker-compose addition:**

```yaml
  mcp-seekout:
    container_name: spot-mcp-seekout
    build:
      context: apps/mcp-seekout
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      - SEEKOUT_RUNTIME_API_ENDPOINT=${SEEKOUT_RUNTIME_API_ENDPOINT}
      - SEEKOUT_RUNTIME_API_KEY=${SEEKOUT_RUNTIME_API_KEY}
      - SEEKOUT_JWKS_URI=${SEEKOUT_JWKS_URI:-http://host.docker.internal:3000/api/oauth/jwks}
      - SEEKOUT_OAUTH_ISSUER=${SEEKOUT_OAUTH_ISSUER:-http://localhost:3000}
      - SEEKOUT_MCP_AUDIENCE=${SEEKOUT_MCP_AUDIENCE:-seekout-mcp-server}
      - FASTMCP_STATELESS_HTTP=true
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped
```

### 4. How do we handle state for iterative search workflows?

**Finding**: Server-side state is necessary. The `Filters` class has 60+ properties — round-tripping that as JSON on every call is 10-15x more expensive on tokens than stateful tools. But this is iteration 2, not iteration 1.
**Confidence**: high

**Why the prior Option D conclusion was wrong:**

The 2026-02-25 research recommended Option D (stateless with structured JSON filters). But that analysis underestimated the token cost because it didn't account for the actual `Filters` schema size:

| Dimension | Count |
|-----------|-------|
| `Filters` class properties | 60+ (EntityFilter, LocationFilter, IntegerFilter, StringFilter, etc.) |
| `PeopleSearchQuery` properties | 30+ (search, index, facets, power_filters, etc.) |
| Nested filter types | PositionFilter, EducationFilter, AlumniFilter, CustomFilter, DynamicFilter... |
| Entity types needing ID resolution | Company, Title, Location, Skill, School, Major, Degree, Industry, Certification |

**Token cost comparison for a 5-step iterative search:**

| Approach | Tokens per step (filter state) | 5-step total | Notes |
|----------|-------------------------------|-------------|-------|
| Option D (stateless JSON echo) | 400-800 tokens | 2,000-4,000 | LLM must reconstruct full JSON each call |
| Stateful (`add_filter`/`run_search`) | 30-60 tokens | 150-300 | LLM sends only the delta |
| Current C# tools (flat params) | 100-200 tokens | 500-1,000 | LLM must repeat all params |

**Iteration plan:**

**Iteration 1 (prove the concept):** Port the current 7 C# tools as-is. Flat string params (query, titles, companies, etc.). The LLM repeats all params on each call — acceptable for the ~8 dimensions the current tools expose. Focus: auth, deployment, local testing.

**Iteration 2 (token-efficient state):** Add stateful session tools:
- `seekout_add_filter(field, value)` — accumulate filters server-side
- `seekout_remove_filter(field)` — remove a filter
- `seekout_run_search(top, skip)` — execute with accumulated filters, return results + facets
- `seekout_get_filters()` — inspect current filter state
- `seekout_clear_search()` — reset session

Session storage: Redis (already in docker-compose) or in-memory with `Mcp-Session-Id` tracking. FastMCP 3.0 supports both `stateless_http=True` (iteration 1) and session-aware mode (iteration 2).

### 5. How do we test locally?

**Finding**: Three testing tiers — unit tests, MCP Inspector, and end-to-end with Claude Desktop.
**Confidence**: high

**Tier 1: Unit tests (no MCP protocol)**

```python
# tests/test_query_builder.py
import pytest
from services.query_builder import QueryBuilder
from models.filters import SearchFilters, EntityFilter

@pytest.mark.asyncio
async def test_builds_query_with_company_filter():
    # Mock entity resolver
    builder = QueryBuilder(mock_entity_resolver, mock_search_api)
    filters = SearchFilters(
        current_company=EntityFilter(alt_names=["Google"]),
        years_of_experience=IntegerFilter(min=5),
    )
    query = await builder.build(query="Python", filters=filters, top=10, skip=0, index="NorthAmerica")
    assert query.filters.current_company.ids == [60]  # Resolved "Google" → ID 60
    assert query.filters.years_of_experience.min == 5
```

**Tier 2: MCP Inspector (protocol-level)**

FastMCP 3.0 includes CLI tools:

```bash
# List available tools
fastmcp list apps/mcp-seekout/main.py

# Call a tool directly
fastmcp call apps/mcp-seekout/main.py seekout_search_people \
  --arg query="Python engineer" \
  --arg filters='{"location": {"ids": [3]}}'

# Interactive MCP inspector
fastmcp dev apps/mcp-seekout/main.py
```

For testing with auth, use `StaticTokenVerifier` in dev mode:

```python
# main.py — dev mode
if os.environ.get("SPOT_ENV") == "local":
    from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
    verifier = StaticTokenVerifier(
        tokens={
            "dev-token-123": {
                "client_id": "dev@seekout.io",
                "scopes": ["mcp:tools"],
            }
        }
    )
else:
    verifier = JWTVerifier(
        jwks_uri=os.environ["SEEKOUT_JWKS_URI"],
        issuer=os.environ["SEEKOUT_OAUTH_ISSUER"],
        audience=os.environ.get("SEEKOUT_MCP_AUDIENCE", "seekout-mcp-server"),
    )

mcp = FastMCP("seekout-search", auth=verifier, stateless_http=True)
```

**Tier 3: Claude Desktop end-to-end**

Claude Desktop config (`claude_desktop_config.json`):

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

For full OAuth testing (after recruit-api PR #5335 is merged and running locally):

```json
{
  "mcpServers": {
    "seekout": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

Claude Desktop will:
1. Hit `http://localhost:8001/mcp` → get 401 with resource metadata
2. Discover auth server via `/.well-known/oauth-authorization-server`
3. Open browser for SeekOut login
4. Exchange auth code for JWT
5. Use JWT for all subsequent MCP calls

### 6. What are the risks and counter-evidence?

**Finding**: Three main risks — FastMCP 3.0 maturity, entity resolution latency, and OAuth flow complexity for local dev.
**Confidence**: medium

**Risk 1: FastMCP 3.0 is new (released Jan 19, 2026)**
FastMCP 3.0 is a major rewrite. The `JWTVerifier` and `stateless_http` features are new. There may be edge cases or bugs. Mitigation: Pin the version, have integration tests, and the fallback is implementing JWT validation manually with `python-jose` (trivial).

**Risk 2: Entity resolution on every call (Option D overhead)**
Without server-side session state, entity resolution (name → ID) happens on every search call. The C# version caches with `IMemoryCache`. Python equivalent: `cachetools.TTLCache` or Redis. Expected overhead: ~100-200ms per unresolved entity, cached after first resolution.

**Risk 3: OAuth flow complexity for local development**
Full OAuth testing requires recruit-api running locally with the RSA key configured. This is a multi-service setup. Mitigation: `StaticTokenVerifier` for day-to-day dev, full OAuth only for integration testing.

**Risk 4: FastMCP vs official MCP SDK**
FastMCP (by Prefect/jlowin) is a community library, not the official `mcp` package from Anthropic. The official SDK also has `FastMCP` (confusingly). The community FastMCP 3.0 has better auth primitives and deployment features. The official SDK's `FastMCP` is simpler but lacks `JWTVerifier`, `stateless_http`, etc.

**Clarification needed**: Which FastMCP do we mean?
- **Official `mcp` package** (from `modelcontextprotocol/python-sdk`): Includes a basic `FastMCP` class. Used in the existing mcp-infrastructure-patterns.md research.
- **Community `fastmcp` package** (from `PrefectHQ/fastmcp`, previously `jlowin/fastmcp`): FastMCP 3.0 with advanced auth, stateless HTTP, providers, transforms.

**Recommendation**: Use the **community FastMCP 3.0** (`pip install fastmcp`) for its superior auth and deployment features. The official SDK can be used as a fallback.

## Internal Context

**What we already know/have:**
- **Spot MCP C# server** (`AI-1099/MCP/Spot.Mcp.Servers.SeekOut`): 7 stateless tools, deployed on AKS, no OAuth — uses API key auth to SeekOut Runtime API. Tools: `seekout_search_people`, `seekout_count_results`, `seekout_get_facets`, `seekout_get_profile`, `seekout_get_suggestions`, `seekout_validate_query`, `seekout_ping`.
- **C# QueryBuilder**: Converts flat string params → `PeopleSearchQuery` with parallel entity resolution. Handles titles, companies, locations, skills, years of experience.
- **C# PeopleSearchQueryFilterBuilder**: Fluent builder with typed filter builders for Company, Title, Location, String, Integer, Date, Application filters. Covers ~20 filter dimensions. Enums for filter subtypes (Current/Previous/Past/Any for companies and titles).
- **recruit-api PR #5335**: Full OAuth 2.1 server with Authorization Code + PKCE, RS256 JWT signing, JWKS endpoint, refresh token rotation, RFC 8414 discovery. Uses `jose` library, Cosmos DB for token storage, Redis for rate limiting.
- **Prior state management research** (2026-02-25): Concluded Option D (improved stateless) is the recommended approach. Stateful (Helix) is a fallback if Option D proves insufficient.
- **spot-v2 repo**: FastAPI-based Python monorepo. `apps/recruiter-api/` uses FastAPI + SQLAlchemy + Pydantic + Redis. Auth currently uses header-based identity (`X-User-Email`), designed to swap to JWT.

**Gaps in internal knowledge:**
- No decision on community FastMCP vs official MCP SDK for the Python server
- No benchmarks on entity resolution latency when called repeatedly (Option D concern)
- recruit-api PR #5335 is not yet merged — the OAuth server doesn't exist in production yet
- No clarity on whether the MCP server should be in spot-v2 or the AI-1099 repo

## Synthesis

The pieces fit together cleanly. recruit-api's OAuth 2.1 server (PR #5335) issues RS256 JWTs that FastMCP 3.0's `JWTVerifier` can validate via the JWKS endpoint. The MCP server doesn't need to know anything about SeekOut's login system — it just validates JWTs. This is the standard Resource Server pattern.

The Python port of the C# tools is straightforward because the SeekOut Runtime API is plain HTTP. The `QueryBuilder` pattern (parse filters → resolve entities → build query → POST to Runtime API) maps 1:1 to Python with Pydantic models replacing C# DTOs and httpx replacing `IHttpClientFactory`.

**The key architectural decision (updated after sounding board analysis)**: Iteration 1 ports the C# tools as stateless flat-param tools with two additions: facet return and a `seekout_get_query` introspection tool. Iteration 2 introduces stateful session tools (`add_filter`/`run_search`) backed by Redis, at which point the flat-param search tools are deprecated. This phasing decouples platform risk (FastMCP, auth, deployment) from interaction model risk (stateful sessions).

The prior Option D recommendation (Feb 25 — pure stateless with structured JSON) is rejected for the iterative workflow. The token cost math is decisive: 2,000-4,000 tokens for stateless JSON echo vs 150-300 for stateful over a 5-step search. Iteration 1's facet return serves as an empirical test of whether LLMs use facets for refinement before committing to the full stateful build.

For local testing, the three-tier approach (unit tests → MCP Inspector → Claude Desktop) provides coverage at each layer. `StaticTokenVerifier` covers local dev; PR #5335 is landing imminently for full OAuth testing.

## Implications

> **Note**: The iteration plan, open questions, risk matrix, and action items have been updated in the **Sounding Board Assessment** section below. The original plan is superseded.

**If not pursuing:**
- Continue using the C# MCP server in AI-1099 repo
- Python agents in spot-v2 would consume the C# server via `MCPTools` or direct HTTP
- The C# server would need its own OAuth integration (currently uses API key)

## Sounding Board Assessment (2026-03-04)

> **Classification**: Architecture decisions (implementation phasing, auth, state management)
> **Reversibility**: Type 2 (two-way door) — Python service in a monorepo, can be refactored
> **Intensity**: Stress test — this sets the foundation for external MCP access to SeekOut

### Decisions Locked In (Not Challenged)

- Community FastMCP 3.0 (PrefectHQ/fastmcp) — not the official mcp SDK
- Lives in spot-v2 repo at `apps/mcp-seekout/` — not AI-1099
- Redis for session state in iteration 2 — already in docker-compose, needed for horizontal scaling

### Decision 1: Iteration 1 (Stateless) → Iteration 2 (Stateful) — CONFIRMED CORRECT

**Steelman**: This phasing decouples proving the **platform** (FastMCP 3.0, auth, deployment, SeekOut Runtime API integration) from proving the **interaction model** (stateful sessions). The 7 C# tools are a known-working interface. Porting them as-is reduces variables. If anything breaks, you know it's the platform, not the design.

**Challenges tested:**

**1. Iteration 1 is partially throwaway work — but less than it looks.**

Of the 7 tools:
- `seekout_ping`, `seekout_validate_query`, `seekout_get_suggestions`, `seekout_get_profile` — **survive unchanged** into iteration 2 (inherently stateless)
- `seekout_search_people`, `seekout_count_results`, `seekout_get_facets` — **get deprecated** when stateful tools ship in iteration 2

So 4/7 tools persist. The "throwaway" is `query_builder.py` and `entity_resolver.py` as currently designed (flat params → query). But even those get reused — iteration 2's `run_search` still needs to build a `PeopleSearchQuery` from accumulated filters, and entity resolution still happens (just at `add_filter` time instead of `run_search` time). The plumbing survives; the call sites change. Throwaway ratio: ~30% of iteration 1 code, not 100%.

**2. The Option D argument from Feb 25 research deserves a clear kill decision.**

The March 5 report reversed the Feb 25 recommendation (Option D stateless with structured JSON → Option B stateful). The reasoning is the token cost math: 2,000-4,000 tokens for Option D vs 150-300 for stateful over a 5-step search. But this only matters for **iterative multi-step searches**. For one-shot searches ("find me Python engineers at Google in Seattle"), Option D and stateful are equivalent.

The real question: **what % of MCP searches will be iterative (3+ refinement steps)?** The recruiter workflow strongly implies iteration — recruiters rarely nail a search on the first try, and the SeekOut UI is designed around iterative refinement. Estimated >60% iterative, making the stateful investment worthwhile.

**Kill decision on Option D**: Option D (pure stateless with structured JSON) is rejected for the iterative workflow. The token cost math is decisive for multi-step searches. However, iteration 1 effectively IS Option D-lite (flat params + facet return) — it serves as the empirical test of whether LLMs use facets for refinement.

**3. Pre-mortem: How the iter 1 → 2 transition fails.**

*It's September 2026. Iteration 1 shipped in April. Three internal agents and two team members' Claude Desktop configs depend on the flat-param tools. Iteration 2 design is ready but keeps getting deprioritized because "the current tools work." The stateful tools finally ship in October but the flat-param tools can't be removed. Now you maintain two tool surfaces with subtly different entity resolution behavior.*

**Mitigation (decided)**: Flat-param search tools (seekout_search_people, seekout_count_results, seekout_get_facets) get **deprecated when iteration 2 ships**. Set a concrete deprecation timeline before iteration 1 ships. The 4 stateless tools (ping, validate_query, get_suggestions, get_profile) persist.

**Design recommendation**: Build `query_builder.py` to accept a `Filters`-like dict/Pydantic model internally (not flat strings), with the flat-param tools as a thin adapter on top. Iteration 2's `run_search` calls the same builder. Minimizes throwaway code.

### Decision 2: Auth Architecture — CONFIRMED CORRECT, EXPANDED TO THREE MODES

**Steelman**: recruit-api as OAuth 2.1 Authorization Server, Python MCP server as Resource Server validating via JWKS — textbook RFC 6749/9068. Clean separation. FastMCP 3.0's `JWTVerifier` handles validation automatically.

**Addition: Internal agents use API key auth, not OAuth.** Python agents in spot-v2 (e.g., market-insights-agent) are trusted internal services in the same cluster. They don't need the OAuth dance — a shared API key via `MCP_INTERNAL_API_KEY` / `X-API-Key` header is sufficient.

**Three auth modes:**

| Mode | When | Mechanism | User context |
|------|------|-----------|-------------|
| StaticTokenVerifier | `SPOT_ENV=local` | Hardcoded dev tokens | Dev identity from token config |
| API key | Internal spot-v2 agents | `X-API-Key` header, shared secret | Service identity (agent name) — no per-user context |
| JWTVerifier | External clients (Claude Desktop, Cursor) | `Authorization: Bearer <JWT>`, validated via JWKS | Full user context from JWT claims (sub, email, name, scope) |

**Implementation**: A `CompositeVerifier` checks for `X-API-Key` header first; if not present, falls back to JWT validation. Single server endpoint (`/mcp`) serves both internal and external callers.

**Design note for internal API key mode**: Internal agents calling via API key have **no user context** — there's no JWT `sub` claim. Tools that need user identity (e.g., iteration 2's session key `mcp:search:{user_id}`) must either:
- Require the agent to pass a `user_id` parameter explicitly, or
- Reject stateful session tools when called via API key (stateful tools are for external clients with user identity)

Recommendation: Iteration 1 tools are stateless and don't need user identity — API key mode works as-is. For iteration 2, require internal agents to pass `user_id` explicitly if they want sessions.

**Challenges tested:**

**1. PR #5335 dependency → RESOLVED**: PR #5335 is already merged / landing within <2 weeks. No fallback needed. StaticTokenVerifier covers local dev until OAuth is testable end-to-end.

**2. JWKS availability is a runtime dependency.** If recruit-api is down or slow, the MCP server can't validate tokens. FastMCP 3.0's `JWTVerifier` likely caches JWKS keys (standard for `PyJWKClient`), but the cache TTL and cold-start fallback behavior need verification.

**Action item**: Verify FastMCP 3.0's JWKS caching behavior before shipping. If it doesn't cache, wrap with `PyJWKClient(lifespan=...)`.

**3. Token refresh is the client's problem.** Claude Desktop, Cursor, and VS Code handle refresh token rotation per OAuth spec. PR #5335 rotates refresh tokens on use. If a client doesn't implement rotation correctly, users get logged out after 1 hour. This is outside our control — document as a known limitation.

### Decision 3: Stateful Session Design (Iteration 2)

#### 3a. Out-of-order Tool Calls — PERMISSIVE DESIGN

**Problem**: LLMs will call `run_search` before `add_filter`. Apple's ToolSandbox (NAACL 2025) shows state dependency between tools is one of the hardest challenges even for SOTA LLMs.

**Decision**: Every tool returns a useful result regardless of what was called before. No tool fails due to sequencing.

- `run_search` with no filters → executes broad search, returns results + facets + `"active_filters": {}` + `"hint": "Use add_filter to narrow results"`
- `add_filter` after `run_search` → filter accumulates; LLM calls `run_search` again when ready
- `get_filters` with empty session → returns `"filters": {}` (not an error)

#### 3b. Session Expiry — SLIDING WINDOW WITH HARD CAP

**Problem**: 30-minute fixed TTL is too short for recruiting workflows. A recruiter opens a search, reads 3-4 profiles in detail (5-10 min each), then refines. That's 30-40 minutes of "idle" search session.

**Decision**: Sliding window TTL of **2 hours**, reset on every `add_filter`/`run_search`/`get_filters` call. Hard cap at **8 hours**.

**Graceful degradation on expiry**: When a session is gone, `run_search` and `get_filters` return `"session_expired": true, "message": "Previous filters have expired. Start a new search."` — not a 500 or cryptic error. The LLM can recover by re-adding filters.

#### 3c. Session Key Design — ONE PER USER, EVOLVING TO MULTI-SESSION

**Iteration 2 (ship now)**:
```
Redis key: mcp:search:{user_id}
```
- `user_id` from JWT `sub` claim (stable across reconnections)
- LLM never mentions a session ID — it's implicit
- `clear_search` resets; `add_filter` auto-creates
- **Accepted risk**: Two MCP clients for the same user clobber each other's sessions

**Future evolution (iteration 3+) — multi-session per user**:
```
Redis key: mcp:search:{user_id}:{session_id}
```

Multi-session adds real complexity:

1. **Session discovery**: Need a `list_sessions` tool. The LLM must choose the right session or create a new one — a meta-workflow on top of the search workflow.
2. **Session context**: When the user says "go back to my Google search," the LLM must map natural language to a session ID. Requires session metadata (name/description) and LLM reasoning about which session matches.
3. **Tool parameter pollution**: Every stateful tool (`add_filter`, `run_search`, `get_filters`, `clear_search`) needs an optional `session_id` parameter. If omitted, needs a "current/last-active session" concept — reintroducing implicit state.
4. **LLM reliability**: LLMs already struggle with one ID to track. Multiple IDs = cross-session contamination risk (adding a filter to the wrong search).
5. **Redis complexity**: TTL management per session, max sessions per user (memory cap), session listing queries.

**Migration path is clean**: Single-session is a degenerate case of multi-session where `session_id` defaults to `"default"`. When multi-session ships, existing tools get an optional `session_id` param that defaults to last-active. New tools added: `list_sessions`, `create_session(name)`, `switch_session(session_id)`. No breaking change to existing tools.

### Iteration 1 Additions (Decided)

Two additions beyond the straight C# port:

**1. Facet return in search responses.** The Runtime API already returns facets. Include top facets in `seekout_search_people` and `seekout_count_results` responses. This tests whether LLMs use facets for refinement — the key signal for whether iteration 2's stateful tools deliver real value.

**2. New tool: `seekout_get_query`** — returns the full `PeopleSearchQuery` object that was built from the flat params. This gives the LLM (and developers) visibility into entity resolution results (did "Google" resolve to ID 60?), how skills were appended to the boolean search, and exactly what was sent to the Runtime API. Useful for debugging and for informing the iteration 2 filter design.

### Updated Iteration Plan

**Iteration 1 — Prove the platform + test facet hypothesis:**
1. Create `apps/mcp-seekout/` in spot-v2 — flat structure, minimal files
2. Port the 7 C# tools as-is — same flat string params, same tool descriptions
3. **Add facet return** to `seekout_search_people` and `seekout_count_results` responses
4. **Add `seekout_get_query` tool** — returns the full PeopleSearchQuery built from flat params
5. Port QueryBuilder + EntityResolver — design `query_builder.py` to accept a `Filters`-like dict internally (not flat strings), with flat-param tools as a thin adapter
6. Auth: three modes — StaticTokenVerifier (dev), API key via `X-API-Key` header (internal spot-v2 agents), JWTVerifier via JWKS (external clients). CompositeVerifier dispatches.
7. Docker-compose: add `mcp-seekout` service on port 8001
8. Test with Claude Desktop — dev token first, then full OAuth
9. Basic pytest for QueryBuilder + EntityResolver

**Iteration 2 — Stateful session tools + deprecate flat-param search:**
1. Add stateful session tools: `add_filter(field, value)`, `remove_filter(field)`, `run_search(top, skip)`, `get_filters()`, `clear_search()`
2. Redis-backed session storage: key `mcp:search:{user_id}`, sliding 2h TTL, 8h hard cap
3. Permissive tool ordering — every tool returns useful results regardless of call sequence
4. Facet return on every `run_search` to guide iterative refinement
5. Graceful session expiry with recovery guidance
6. **Deprecate** flat-param search tools (`seekout_search_people`, `seekout_count_results`, `seekout_get_facets`)
7. Keep stateless tools: `seekout_ping`, `seekout_validate_query`, `seekout_get_suggestions`, `seekout_get_profile`, `seekout_get_query`

**Iteration 3 (future) — Multi-session per user:**
1. Add `session_id` optional param to all stateful tools (defaults to last-active)
2. Add meta-tools: `list_sessions`, `create_session(name)`, `switch_session(session_id)`
3. Redis key: `mcp:search:{user_id}:{session_id}`, max sessions per user cap
4. Session metadata: name, created_at, last_accessed, filter summary

### Updated Risk Matrix

| Risk | Severity | Likelihood | Mitigation | Residual |
|------|----------|-----------|------------|----------|
| FastMCP 3.0 JWTVerifier has edge cases | Medium | Medium | Pin version; fallback to manual `python-jose` validation | Low |
| JWKS cache staleness on key rotation | Medium | Low | Verify FastMCP caching behavior; wrap with `PyJWKClient(lifespan=...)` if needed | Low |
| Flat-param tools become permanent (not deprecated) | Medium | Medium | Set deprecation timeline before iter 1 ships; deprecate on iter 2 launch | Low |
| LLMs call stateful tools out of order | Low | High | Permissive design; every tool returns useful results | Negligible |
| Session expiry during profile reading | Medium | High | Sliding window TTL (2h) with hard cap (8h); graceful expiry message | Low |
| Two clients clobber single-user session | Low | Low | Accept for iter 2; multi-session in iter 3 | Low |
| Entity resolution latency on every add_filter | Low | Medium | TTLCache per user in iter 1; Redis cache in iter 2 | Low |
| LLMs don't use facets for refinement | Medium | Low | Iter 1 facet return tests the hypothesis cheaply | Low |

### Resolved Open Questions

1. ~~Should the MCP server live in spot-v2 or AI-1099?~~ → **spot-v2** at `apps/mcp-seekout/` (locked in)
2. ~~Which FastMCP? Community 3.0 vs official SDK?~~ → **Community FastMCP 3.0** (locked in)
3. ~~Does the C# MCP server continue to exist?~~ → Still needs team decision (not addressed here)
4. ~~What SeekOut Runtime API credentials?~~ → Still needs team decision
5. ~~RBAC beyond "authenticated SeekOut user"?~~ → Still needs team decision
6. ~~Stateful vs stateless tool design?~~ → **Stateful (iteration 2)**, with flat-param tools deprecated on iter 2 ship
7. ~~Session key design?~~ → **One per user** (`mcp:search:{user_id}`) in iter 2, multi-session in iter 3
8. ~~Session expiry strategy?~~ → **Sliding 2h TTL, 8h hard cap**, graceful degradation
9. ~~Out-of-order tool calls?~~ → **Permissive design**, no sequencing failures

### Action Items

- [ ] Verify FastMCP 3.0 JWKS caching behavior (check `JWTVerifier` source)
- [ ] Design `query_builder.py` with `Filters`-like dict input (not flat strings) so iter 2 reuse is clean
- [ ] Add facet return to iter 1 search/count tools (Runtime API already returns them)
- [ ] Build `seekout_get_query` tool for iter 1 (returns full PeopleSearchQuery)
- [ ] Set explicit deprecation plan for flat-param search tools before iter 1 ships
- [ ] For iter 2: prototype Redis session with `mcp:search:{user_id}` key and sliding TTL
- [ ] Decide: does the C# MCP server continue to exist alongside the Python one?
- [ ] Decide: what Runtime API credentials does the Python server use?

## Sources

| # | Source | Type | Quality | Key Takeaway |
|---|--------|------|---------|-------------|
| 1 | recruit-api PR #5335 | internal | high | OAuth 2.1 Authorization Code + PKCE, RS256 JWT, JWKS, RFC 8414 discovery |
| 2 | Spot.Mcp.Servers.SeekOut (C#) | internal | high | 7 stateless tools, QueryBuilder with entity resolution, SeekOut Runtime API HTTP client |
| 3 | PeopleSearchQueryBuilder.cs | internal | high | Fluent builder pattern for filters: Company, Title, Location, String, Integer, Date, Application |
| 4 | PeopleSearchQueryFilterBuilder.cs | internal | high | 20+ filter dimensions with typed builders and enums |
| 5 | mcp-infrastructure-patterns.md | internal | high | Transport decisions (Streamable HTTP), Agno integration, deployment patterns (sidecar) |
| 6 | 2026-02-25-mcp-client-state-management.md | internal | high | Option D recommended: structured JSON filters + facet return, stateless, no Redis |
| 7 | spot-v2 repo structure | internal | high | FastAPI monorepo, apps/ pattern, docker-compose, uv/pydantic stack |
| 8 | [FastMCP 3.0 Release Notes](https://gofastmcp.com/updates) | external | high | Component versioning, JWTVerifier, stateless_http, BearerAuthProvider |
| 9 | [FastMCP Token Verification](https://gofastmcp.com/servers/auth/token-verification) | external | high | JWTVerifier with JWKS, StaticTokenVerifier for dev, IntrospectionTokenVerifier |
| 10 | [FastMCP HTTP Deployment](https://gofastmcp.com/deployment/http) | external | high | stateless_http mode, FastAPI mount, nginx config, health checks |
| 11 | [FastMCP Bearer Auth (Client)](https://gofastmcp.com/clients/auth/bearer) | external | medium | Client-side bearer token configuration |
| 12 | [FastMCP Auth Blog (gelembjuk)](https://gelembjuk.com/blog/post/authentication-remote-mcp-server-python/) | external | medium | Middleware pattern, context.set_state for user info |
| 13 | [FastMCP Auth Demo (gbaeke)](https://github.com/gbaeke/fastmcp-auth) | external | medium | BearerAuthProvider with Azure JWKS, scope validation |

## Research Quality

- **Depth**: deep dive + sounding board stress test (2026-03-04)
- **Internal sources found**: 7 (C# codebase x4, PR #5335, prior research x2)
- **External sources consulted**: 6 (FastMCP docs x4, blog x1, GitHub x1) + sounding board references (Apple ToolSandbox, MCP-Bench)
- **Confidence distribution**: 5 high, 1 medium; sounding board raised confidence on phasing and session design
- **Known gaps**: No benchmarks on FastMCP 3.0 `JWTVerifier` performance under load; JWKS caching behavior unverified; no filter complexity distribution data from SeekOut UI analytics
- **Decisions resolved by sounding board**: FastMCP 3.0 (locked in), spot-v2 (locked in), Redis (locked in), iteration phasing (confirmed), auth split (confirmed), session key design (one-per-user → multi-session evolution), tool deprecation strategy (flat-param search tools deprecated on iter 2 ship)
- **Staleness risk**: Medium — FastMCP 3.0 is new and may have breaking changes in minor versions. Pin the version.
