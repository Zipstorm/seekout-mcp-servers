# SeekOut MCP Server — Tools & Query Builder

This spec covers the 8 MCP tools, the query builder, entity resolver, and the SeekOut Runtime API client surface. It is one of two specs that form the mcp-seekout plan. Start with [plan.md](./plan.md) for the full picture.

---

## 1. SeekOut Runtime API Surface

The MCP server calls the SeekOut Runtime API via httpx. All requests use the same base URL (`SEEKOUT_RUNTIME_API_ENDPOINT`) and API key (`SEEKOUT_RUNTIME_API_KEY` passed as a header or query param, matching the C# server's pattern).

### 1.1 Endpoint Inventory

| Method | Endpoint | Purpose | Used By |
|--------|----------|---------|---------|
| POST | `/api/PeopleSearch/SearchPeople` | Search for people, returns profiles + facets + total count | `seekout_search_people`, `seekout_count_results`, `seekout_get_facets` |
| GET | `/api/PeopleSearch/GetProfile` | Get a single profile by key | `seekout_get_profile` |
| GET | `/api/Search/Get` | Search entities (company, title, skill, location, school, industry) | `entity_resolver.py` |
| GET | `/api/Search/CheckBooleanExpression` | Validate a boolean search expression | `seekout_validate_query` |
| GET | `/api/Search/CheckBooleanExpression` | Connectivity check (reused) | `seekout_ping` |

### 1.2 Request/Response Shapes

**POST `/api/PeopleSearch/SearchPeople`**

```python
# Request body (PeopleSearchQuery)
{
    "Search": "Python AND (Django OR Flask)",
    "Top": 10,
    "Skip": 0,
    "Index": "NorthAmerica",  # enum: NorthAmerica, Europe, AsiaPacific, etc.
    "Filters": {
        "current_company": {"ids": [60, 492], "alt_names": ["Startup XYZ"]},
        "current_title": {"ids": [1234], "alt_names": []},
        "location": {"ids": [3], "alt_names": [], "radius": 25},
        "years_of_experience": {"min": 5, "max": 15}
    },
    "FacetQueries": [
        {"FieldName": "cur_company_id", "Top": 10},
        {"FieldName": "cur_title_id", "Top": 10},
        {"FieldName": "location_ids", "Top": 10},
        {"FieldName": "skills", "Top": 10}
    ]
}

# Response
{
    "WholePersonResults": [
        {
            "Key": "abc123",
            "Index": "NorthAmerica",
            "Name": "Jane Doe",
            "CurrentTitle": "Staff Engineer",
            "CurrentCompany": "Google",
            "Location": "Seattle, WA",
            "Skills": ["Python", "AWS", "Kubernetes"],
            "Headline": "...",
            "ProfileUrl": "..."
            # ... more fields
        }
    ],
    "TotalCount": 4523,
    "Facets": {
        "cur_company_id": [
            {"Name": "Google", "Id": 60, "Count": 1200},
            {"Name": "Meta", "Id": 492, "Count": 800}
        ],
        "cur_title_id": [...],
        "location_ids": [...]
    }
}
```

**GET `/api/PeopleSearch/GetProfile?key={key}&index={index}`**

```python
# Response: WholePersonProfile
{
    "Key": "abc123",
    "Name": "Jane Doe",
    "CurrentTitle": "Staff Engineer",
    "CurrentCompany": "Google",
    "Location": "Seattle, WA",
    "Headline": "...",
    "Summary": "...",
    "Skills": ["Python", "AWS", "Kubernetes", ...],
    "Certifications": ["AWS Solutions Architect"],
    "Positions": [
        {
            "Title": "Staff Engineer",
            "Company": "Google",
            "StartDate": "2020-01",
            "EndDate": null,
            "Description": "..."
        }
    ],
    "Education": [
        {
            "School": "MIT",
            "Degree": "MS",
            "Major": "Computer Science",
            "StartDate": "2014",
            "EndDate": "2016"
        }
    ],
    "Languages": ["English", "Spanish"]
}
```

**GET `/api/Search/Get?entityType={type}&query={query}&maxResults={n}`**

```python
# Response: list of EntitySearchResult
[
    {"Text": "Google", "Id": 60, "Count": 150000},
    {"Text": "Google Cloud", "Id": 8842, "Count": 12000},
    {"Text": "Google DeepMind", "Id": 45021, "Count": 3000}
]
```

**GET `/api/Search/CheckBooleanExpression?query={query}`**

```python
# Response
{
    "IsValid": true,
    "Error": null
}
# or
{
    "IsValid": false,
    "Error": "Unmatched parenthesis at position 15"
}
```

### 1.3 Python Client Class

```python
# seekout_api.py
class SeekOutAPI:
    """httpx-based client for SeekOut Runtime API."""

    def __init__(self, base_url: str, api_key: str):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def search_people(
        self, query: dict, facet_queries: list[dict] | None = None
    ) -> tuple[dict, int]:
        """POST /api/PeopleSearch/SearchPeople. Returns (results, total_count)."""
        ...

    async def get_count(self, query: dict) -> int:
        """Same endpoint with Top=0, returns count only."""
        ...

    async def get_profile(self, key: str, index: str = "NorthAmerica") -> dict | None:
        """GET /api/PeopleSearch/GetProfile."""
        ...

    async def search_entities(
        self, entity_type: str, query: str, max_results: int = 5
    ) -> list[dict]:
        """GET /api/Search/Get. Returns list of {Text, Id, Count}."""
        ...

    async def validate_boolean(self, query: str) -> tuple[bool, str | None]:
        """GET /api/Search/CheckBooleanExpression. Returns (is_valid, error)."""
        ...

    async def ping(self) -> tuple[int, float]:
        """GET /api/Search/CheckBooleanExpression?query=test. Returns (status_code, elapsed_ms)."""
        ...

    async def close(self):
        await self._client.aclose()
```

---

## 2. Query Builder

The query builder converts parameters into a `PeopleSearchQuery` dict. It accepts a `Filters`-like dict internally — the flat-param tools are a thin adapter layer.

### 2.1 Architecture

```
Flat string params (from tools.py)
    │
    ▼
┌──────────────────────────┐
│  flat_params_to_filters  │  Thin adapter: parses comma-separated
│  (in query_builder.py)   │  strings into Filters dict structure
└────────────┬─────────────┘
             │ Filters dict
             ▼
┌──────────────────────────┐
│     QueryBuilder.build   │  Core builder: entity resolution,
│                          │  skill → search string, assembles
│                          │  PeopleSearchQuery dict
└──────────────────────────┘
             │
             ▼
        PeopleSearchQuery dict
        (ready for seekout_api)
```

### 2.2 Filters Dict Schema

The internal representation mirrors the C# `Filters` class structure. Iteration 1 supports only the ~8 dimensions the flat-param tools expose. The dict schema is designed to grow in iteration 2 without breaking changes.

```python
# Internal Filters dict — not a Pydantic model, just a typed dict pattern.
# Using TypedDict for documentation; actual code can use plain dicts.

from typing import TypedDict, NotRequired

class EntityFilterDict(TypedDict, total=False):
    ids: list[int]
    alt_names: list[str]

class LocationFilterDict(TypedDict, total=False):
    ids: list[int]
    alt_names: list[str]
    radius: int  # miles

class IntegerFilterDict(TypedDict, total=False):
    min: int
    max: int

class FiltersDict(TypedDict, total=False):
    current_company: EntityFilterDict
    current_title: EntityFilterDict
    location: LocationFilterDict
    years_of_experience: IntegerFilterDict
    # Iteration 2 will add: prev_company, prev_title, school, major,
    # degree, industry, company_size, seniority, etc.
```

### 2.3 Skills Handling

Skills are NOT a filter — they're appended to the boolean search string. This matches the C# behavior exactly.

```python
# C# behavior (from QueryBuilder.cs AppendSkillsToSearch):
# Resolved skills: skill:ID
# Unresolved skills: "name" (quoted)
# Multiple: (skill:123 OR skill:456 OR "data science")
# Appended: {existing_search} AND (skill:123 OR "data science")

async def _append_skills_to_search(
    self, search: str, skill_names: list[str]
) -> str:
    resolved = await self._entity_resolver.resolve("Skill", skill_names)
    terms = []
    for r in resolved:
        if r["resolved"] and r["id"] is not None:
            terms.append(f"skill:{r['id']}")
        else:
            terms.append(f'"{r["name"]}"')

    if not terms:
        return search

    skill_expr = terms[0] if len(terms) == 1 else f"({' OR '.join(terms)})"
    return f"{search} AND {skill_expr}" if search.strip() else skill_expr
```

### 2.4 QueryBuilder Class

```python
# query_builder.py

class QueryBuilder:
    """Converts Filters dict → PeopleSearchQuery dict.

    Flat-param tools call flat_params_to_filters() first, then build().
    Iteration 2's stateful tools will call build() directly with a
    Filters dict accumulated from add_filter calls.
    """

    def __init__(self, entity_resolver: EntityResolver, seekout_api: SeekOutAPI):
        self._entity_resolver = entity_resolver
        self._api = seekout_api

    async def build(
        self,
        query: str = "",
        filters: dict | None = None,
        top: int = 10,
        skip: int = 0,
        index: str = "NorthAmerica",
        facet_fields: list[str] | None = None,
    ) -> dict:
        """Build a PeopleSearchQuery dict from a Filters dict.

        Entity resolution runs in parallel for all entity filters.
        Skills are appended to the search string, not added as a filter.
        """
        filters = filters or {}
        search = query

        # Collect entity resolution tasks
        resolution_tasks = {}
        for field, entity_type in [
            ("current_title", "Title"),
            ("current_company", "Company"),
            ("location", "Location"),
        ]:
            if field in filters and "alt_names" in filters[field]:
                resolution_tasks[field] = self._entity_resolver.resolve(
                    entity_type, filters[field]["alt_names"]
                )

        # Skills resolution (separate — goes to search string)
        skill_names = filters.pop("_skill_names", [])
        if skill_names:
            resolution_tasks["_skills"] = self._entity_resolver.resolve(
                "Skill", skill_names
            )

        # Await all resolutions in parallel
        if resolution_tasks:
            import asyncio
            results = dict(
                zip(resolution_tasks.keys(),
                    await asyncio.gather(*resolution_tasks.values()))
            )

            # Merge resolved IDs into filters
            for field in ["current_title", "current_company", "location"]:
                if field in results:
                    resolved = results[field]
                    ids = [r["id"] for r in resolved if r["resolved"]]
                    alt_names = [r["name"] for r in resolved if not r["resolved"]]
                    filters[field] = {
                        **({"ids": ids} if ids else {}),
                        **({"alt_names": alt_names} if alt_names else {}),
                    }

            # Append skills to search string
            if "_skills" in results:
                search = self._build_skill_search(search, results["_skills"])

        # Build PeopleSearchQuery dict
        pq = {
            "Search": search,
            "Top": min(top, 25),
            "Skip": max(skip, 0),
            "Index": index,
        }

        if filters:
            pq["Filters"] = self._serialize_filters(filters)

        if facet_fields:
            pq["FacetQueries"] = [
                {"FieldName": f, "Top": 10} for f in facet_fields
            ]

        return pq


def flat_params_to_filters(
    titles: str | None = None,
    companies: str | None = None,
    locations: str | None = None,
    skills: str | None = None,
    years_experience_min: int | None = None,
    years_experience_max: int | None = None,
) -> dict:
    """Convert flat comma-separated string params to a Filters dict.

    This is the thin adapter layer between the flat-param tools and
    the QueryBuilder. Iteration 2 bypasses this entirely.
    """
    filters = {}

    if titles:
        names = [t.strip() for t in titles.split(",") if t.strip()]
        if names:
            filters["current_title"] = {"alt_names": names}

    if companies:
        names = [c.strip() for c in companies.split(",") if c.strip()]
        if names:
            filters["current_company"] = {"alt_names": names}

    if locations:
        names = [l.strip() for l in locations.split(",") if l.strip()]
        if names:
            filters["location"] = {"alt_names": names}

    if skills:
        names = [s.strip() for s in skills.split(",") if s.strip()]
        if names:
            filters["_skill_names"] = names  # Handled specially by QueryBuilder

    if years_experience_min is not None or years_experience_max is not None:
        yoe = {}
        if years_experience_min is not None:
            yoe["min"] = years_experience_min
        if years_experience_max is not None:
            yoe["max"] = years_experience_max
        filters["years_of_experience"] = yoe

    return filters
```

---

## 3. Entity Resolver

Port of the C# `EntityResolver`. Resolves entity names (e.g., "Google") to IDs via the Runtime API, with confidence-based matching and TTL caching.

### 3.1 Confidence Matching Logic

Ported directly from C# `SelectBestMatch`:

```
Input: "Google" → API returns:
  [{"Text": "Google", "Id": 60, "Count": 150000},
   {"Text": "Google Cloud", "Id": 8842, "Count": 12000},
   {"Text": "Google DeepMind", "Id": 45021, "Count": 3000}]

Rules (in order):
1. Exact match (case-insensitive) → resolve immediately
   "Google" == "Google" → resolved, id=60

2. Clear winner (top count > 2x second) → resolve top
   150000 > 2 * 12000 → resolved, id=60

3. Single result → always resolve

4. Ambiguous → unresolved (falls back to alt_names in filter)
```

### 3.2 Implementation

```python
# entity_resolver.py
from cachetools import TTLCache

class EntityResolver:
    """Resolves entity names to IDs via SeekOut Runtime API.

    Results are cached in-process with a 1-hour TTL.
    """

    def __init__(self, seekout_api: SeekOutAPI):
        self._api = seekout_api
        self._cache: TTLCache = TTLCache(maxsize=1024, ttl=3600)

    async def resolve(
        self, entity_type: str, names: list[str]
    ) -> list[dict]:
        """Resolve a list of names in parallel.

        Returns list of {"name": str, "id": int | None, "resolved": bool}.
        """
        import asyncio
        tasks = [self._resolve_one(entity_type, name) for name in names]
        return await asyncio.gather(*tasks)

    async def _resolve_one(self, entity_type: str, name: str) -> dict:
        cache_key = f"entity:{entity_type}:{name.lower()}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            results = await self._api.search_entities(entity_type, name, max_results=5)
            result = self._select_best_match(results, name)
            self._cache[cache_key] = result
            return result
        except Exception:
            return {"name": name, "id": None, "resolved": False}

    @staticmethod
    def _select_best_match(results: list[dict], input_name: str) -> dict:
        if not results:
            return {"name": input_name, "id": None, "resolved": False}

        # Rule 1: exact match
        for r in results:
            if r["Text"].lower() == input_name.lower():
                return {"name": input_name, "id": r["Id"], "resolved": True}

        # Rule 2: clear winner (top > 2x second)
        if len(results) >= 2:
            if results[0]["Count"] > 2 * results[1]["Count"]:
                return {"name": input_name, "id": results[0]["Id"], "resolved": True}

        # Rule 3: single result
        if len(results) == 1:
            return {"name": input_name, "id": results[0]["Id"], "resolved": True}

        # Rule 4: ambiguous
        return {"name": input_name, "id": None, "resolved": False}
```

### 3.3 Test Cases

```python
# tests/test_entity_resolver.py — key scenarios

# Exact match wins even when not highest count
# Input: "AWS", results: [{"Text": "AWS", "Id": 100, "Count": 5000},
#                          {"Text": "Amazon Web Services", "Id": 101, "Count": 50000}]
# Expected: resolved=True, id=100

# Clear winner when no exact match
# Input: "MSFT", results: [{"Text": "Microsoft", "Id": 1, "Count": 200000},
#                           {"Text": "Microsoft Azure", "Id": 2, "Count": 30000}]
# Expected: resolved=True, id=1 (200000 > 2 * 30000)

# Ambiguous — no clear winner
# Input: "Apple", results: [{"Text": "Apple Inc", "Id": 10, "Count": 100000},
#                            {"Text": "Apple Leisure Group", "Id": 11, "Count": 80000}]
# Expected: resolved=False (100000 < 2 * 80000)

# Cache hit returns same result without API call
# API error returns unresolved (not exception)
```

---

## 4. Tool Inventory

All 8 tools are defined in `tools.py`. Each tool is registered on the FastMCP server instance.

### 4.1 `seekout_search_people`

```python
@mcp.tool(
    name="seekout_search_people",
    description=(
        "Search for candidates matching specific criteria. "
        "Returns summarized profiles with name, title, company, location, skills, "
        "and a profile_key for detailed lookup.\n\n"
        "WHEN TO USE: After getting a count with seekout_count_results, "
        "or when you need to see actual candidate profiles.\n"
        "WHEN NOT TO USE: If you just need a count, use seekout_count_results instead (faster).\n\n"
        "PAGINATION: Use skip parameter to page through results. First call: skip=0. Next page: skip=10.\n\n"
        "WORKFLOW: seekout_count_results -> seekout_search_people -> seekout_get_profile"
    ),
)
async def seekout_search_people(
    query: str | None = None,
    titles: str | None = None,
    companies: str | None = None,
    locations: str | None = None,
    skills: str | None = None,
    years_experience_min: int | None = None,
    years_experience_max: int | None = None,
    max_results: int = 10,
    skip: int = 0,
) -> dict:
    filters = flat_params_to_filters(
        titles, companies, locations, skills,
        years_experience_min, years_experience_max,
    )
    search_query = await query_builder.build(
        query=query or "",
        filters=filters,
        top=max(1, min(max_results, 25)),
        skip=max(skip, 0),
        facet_fields=DEFAULT_FACET_FIELDS,  # Always include facets
    )
    results, total_count = await seekout_api.search_people(search_query)

    return {
        "total_count": total_count,
        "returned": len(results.get("WholePersonResults", [])),
        "skip": skip,
        "candidates": _summarize_candidates(results),
        "facets": _extract_facets(results),  # NEW: facet return
    }
```

**Facet return format:**
```python
{
    "facets": {
        "companies": [{"name": "Google", "count": 1200}, {"name": "Meta", "count": 800}],
        "titles": [{"name": "Staff Engineer", "count": 500}],
        "locations": [{"name": "Seattle, WA", "count": 900}],
        "skills": [{"name": "Python", "count": 3000}]
    }
}
```

### 4.2 `seekout_count_results`

Same filter params as `seekout_search_people` (no `max_results`, `skip`). Calls Runtime API with `Top=0`. Returns `total_count` + facets.

### 4.3 `seekout_get_facets`

Same filter params + `facet_types` (comma-separated, default: `"titles,companies,locations,skills"`). Returns `total_count` + facets only, no candidate profiles.

### 4.4 `seekout_get_profile`

```python
@mcp.tool(name="seekout_get_profile")
async def seekout_get_profile(
    profile_key: str,
    index: str = "NorthAmerica",
) -> dict:
    # Returns detailed profile: name, title, company, location, headline,
    # summary, skills (up to 15), certifications, work_history (up to 10),
    # education (up to 5), languages
```

### 4.5 `seekout_get_suggestions`

```python
@mcp.tool(name="seekout_get_suggestions")
async def seekout_get_suggestions(
    query: str,
    suggestion_type: str = "company",  # company, title, skill, location, school, industry
    max_results: int = 10,
) -> dict:
    # Returns {"suggestions": [{"name": str, "id": str, "count": int}]}
```

### 4.6 `seekout_validate_query`

```python
@mcp.tool(name="seekout_validate_query")
async def seekout_validate_query(query: str) -> dict:
    # Returns {"valid": bool, "error": str | None}
```

### 4.7 `seekout_ping`

```python
@mcp.tool(name="seekout_ping")
async def seekout_ping(message: str = "pong") -> dict:
    # Returns {"echo": str, "status_code": int, "elapsed_ms": float, "error": str | None}
```

### 4.8 `seekout_get_query` (NEW)

```python
@mcp.tool(
    name="seekout_get_query",
    description=(
        "Returns the full PeopleSearchQuery object that would be built from the "
        "given parameters. Does NOT execute a search. Useful for debugging entity "
        "resolution (did 'Google' resolve to ID 60?) and seeing exactly what would "
        "be sent to the Runtime API.\n\n"
        "WHEN TO USE: When you want to inspect how parameters map to the search query "
        "before executing a search."
    ),
)
async def seekout_get_query(
    query: str | None = None,
    titles: str | None = None,
    companies: str | None = None,
    locations: str | None = None,
    skills: str | None = None,
    years_experience_min: int | None = None,
    years_experience_max: int | None = None,
    max_results: int = 10,
    skip: int = 0,
) -> dict:
    filters = flat_params_to_filters(
        titles, companies, locations, skills,
        years_experience_min, years_experience_max,
    )
    search_query = await query_builder.build(
        query=query or "", filters=filters,
        top=max(1, min(max_results, 25)), skip=max(skip, 0),
    )
    return {"people_search_query": search_query}
```

---

## 5. Default Facet Fields

Mapping from user-friendly names to Runtime API field names:

| User-facing name | Runtime API field | Entity type |
|-----------------|-------------------|-------------|
| `companies` | `cur_company_id` | Company |
| `titles` | `cur_title_id` | Title |
| `locations` | `location_ids` | Location |
| `skills` | `skills` | Skill |

```python
DEFAULT_FACET_FIELDS = ["cur_company_id", "cur_title_id", "location_ids", "skills"]

FACET_FIELD_MAP = {
    "companies": "cur_company_id",
    "titles": "cur_title_id",
    "locations": "location_ids",
    "skills": "skills",
}
```

---

## Related Specs

- [plan.md](./plan.md) — Master plan and phase overview
- [02-auth-and-deployment.md](./02-auth-and-deployment.md) — Auth modes, config, Docker, docker-compose
