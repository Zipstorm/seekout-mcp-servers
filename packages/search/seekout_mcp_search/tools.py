import httpx

from fastmcp import FastMCP

from seekout_mcp_search.query_builder import QueryBuilder, flat_params_to_filters, DEFAULT_FACET_TYPES, FACET_TYPE_MAP
from seekout_mcp_search.seekout_api import SeekOutAPI
from seekout_mcp_search.session_store import SessionStore

SEEKOUT_APP_BASE_URL = "https://app.seekout.io/app"


def register_tools(
    mcp: FastMCP,
    query_builder: QueryBuilder,
    seekout_api: SeekOutAPI,
    session_store: SessionStore | None = None,
    query_store_endpoint: str = "",
    query_store_api_key: str = "",
) -> None:
    """Register all MCP tools on the FastMCP server."""

    @mcp.tool(
        name="seekout_ping",
        description=(
            "Check connectivity to the SeekOut Runtime API. "
            "Returns status code, elapsed time, and echo message."
        ),
    )
    async def seekout_ping(message: str = "pong") -> dict:
        try:
            status_code, elapsed_ms = await seekout_api.ping()
            return {
                "echo": message,
                "status_code": status_code,
                "elapsed_ms": round(elapsed_ms, 1),
                "error": None,
            }
        except Exception as e:
            return {
                "echo": message,
                "status_code": 0,
                "elapsed_ms": 0,
                "error": str(e),
            }

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
            facet_fields=DEFAULT_FACET_TYPES,
        )
        results, total_count = await seekout_api.search_people(search_query)

        return {
            "total_count": total_count,
            "returned": len(results.get("WholePersonResults", [])),
            "skip": skip,
            "candidates": _summarize_candidates(results),
            "facets": _extract_facets(results),
        }

    @mcp.tool(
        name="seekout_count_results",
        description=(
            "Get the total count of candidates matching criteria without returning profiles. "
            "Faster than seekout_search_people. Also returns facets for refinement.\n\n"
            "WHEN TO USE: Before searching, to check how many results a query returns.\n"
            "WORKFLOW: seekout_count_results -> seekout_search_people -> seekout_get_profile"
        ),
    )
    async def seekout_count_results(
        query: str | None = None,
        titles: str | None = None,
        companies: str | None = None,
        locations: str | None = None,
        skills: str | None = None,
        years_experience_min: int | None = None,
        years_experience_max: int | None = None,
    ) -> dict:
        filters = flat_params_to_filters(
            titles, companies, locations, skills,
            years_experience_min, years_experience_max,
        )
        search_query = await query_builder.build(
            query=query or "",
            filters=filters,
            top=0,
            facet_fields=DEFAULT_FACET_TYPES,
        )
        results, total_count = await seekout_api.search_people(search_query)

        return {
            "total_count": total_count,
            "facets": _extract_facets(results),
        }

    @mcp.tool(
        name="seekout_get_facets",
        description=(
            "Get facet breakdowns for a search query. Returns counts by company, title, "
            "location, and/or skills.\n\n"
            "WHEN TO USE: To understand the distribution of candidates across dimensions "
            "before or after searching."
        ),
    )
    async def seekout_get_facets(
        query: str | None = None,
        titles: str | None = None,
        companies: str | None = None,
        locations: str | None = None,
        skills: str | None = None,
        years_experience_min: int | None = None,
        years_experience_max: int | None = None,
        facet_types: str = "titles,companies,locations,skills",
    ) -> dict:
        filters = flat_params_to_filters(
            titles, companies, locations, skills,
            years_experience_min, years_experience_max,
        )
        requested_fields = [
            FACET_TYPE_MAP[ft.strip()]
            for ft in facet_types.split(",")
            if ft.strip() in FACET_TYPE_MAP
        ]
        search_query = await query_builder.build(
            query=query or "",
            filters=filters,
            top=0,
            facet_fields=requested_fields or DEFAULT_FACET_TYPES,
        )
        results, total_count = await seekout_api.search_people(search_query)

        return {
            "total_count": total_count,
            "facets": _extract_facets(results),
        }

    @mcp.tool(
        name="seekout_get_profile",
        description=(
            "Get a detailed profile for a specific candidate. "
            "Use the profile_key from seekout_search_people results.\n\n"
            "WHEN TO USE: After finding a candidate via search, to see their full profile."
        ),
    )
    async def seekout_get_profile(
        profile_key: str,
        index: str = "NorthAmerica",
    ) -> dict:
        profile = await seekout_api.get_profile(profile_key, index)
        if profile is None:
            return {"error": "Profile not found", "profile_key": profile_key}
        return _summarize_profile(profile)

    @mcp.tool(
        name="seekout_get_suggestions",
        description=(
            "Get autocomplete suggestions for entity names. "
            "Useful for discovering valid company, title, skill, location, school, "
            "or industry names.\n\n"
            "WHEN TO USE: When unsure about exact entity names to use in filters."
        ),
    )
    async def seekout_get_suggestions(
        query: str,
        suggestion_type: str = "company",
        max_results: int = 10,
    ) -> dict:
        results = await seekout_api.search_entities(
            suggestion_type, query, max_results=max_results
        )
        return {
            "suggestions": [
                {"name": r["text"], "id": r["id"], "count": r["count"]}
                for r in results
            ]
        }

    @mcp.tool(
        name="seekout_validate_query",
        description=(
            "Validate a boolean search expression. "
            "Returns whether the expression is valid and any error message.\n\n"
            "WHEN TO USE: Before using a complex boolean query in seekout_search_people."
        ),
    )
    async def seekout_validate_query(query: str) -> dict:
        is_valid, error = await seekout_api.validate_boolean(query)
        return {"valid": is_valid, "error": error}

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
            query=query or "",
            filters=filters,
            top=max(1, min(max_results, 25)),
            skip=max(skip, 0),
        )
        return {"people_search_query": search_query}

    # ── SeekOut app link tool ─────────────────────────────────────────
    if query_store_endpoint and query_store_api_key:
        @mcp.tool(
            name="seekout_get_link",
            description=(
                "Generate a SeekOut app URL for a search. Builds the search query from "
                "the given parameters, stores it in the SeekOut query store, and returns "
                "a link to https://app.seekout.io/app that opens the search in the SeekOut UI.\n\n"
                "WHEN TO USE: When the user wants to open or share search results in SeekOut.\n\n"
                "WORKFLOW: Use the same parameters as seekout_search_people."
            ),
        )
        async def seekout_get_link(
            query: str | None = None,
            titles: str | None = None,
            companies: str | None = None,
            locations: str | None = None,
            skills: str | None = None,
            years_experience_min: int | None = None,
            years_experience_max: int | None = None,
        ) -> dict:
            filters = flat_params_to_filters(
                titles, companies, locations, skills,
                years_experience_min, years_experience_max,
            )
            search_query = await query_builder.build(
                query=query or "",
                filters=filters,
            )

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        query_store_endpoint,
                        params={"code": query_store_api_key},
                        json=search_query,
                    )
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as e:
                return {"error": f"Failed to store query: {e}", "url": None}

            query_id = data.get("QueryId") or data.get("queryId")
            if not query_id:
                return {"error": "Query store returned no queryId", "url": None}

            url = f"{SEEKOUT_APP_BASE_URL}?queryId={query_id}"
            return {"url": url, "query_id": query_id}

    # ── Stateful session tools ────────────────────────────────────────
    if session_store is None:
        return

    @mcp.tool(
        name="session_create",
        description=(
            "Create a new search session. Returns a session_id to use with other "
            "session tools. Optionally set an initial boolean query.\n\n"
            "WORKFLOW: session_create -> session_add_filter (repeat) -> session_run_search\n\n"
            "Sessions expire after 1 hour of inactivity."
        ),
    )
    async def session_create(query: str = "") -> dict:
        session = await session_store.create(query=query)
        return {
            "session_id": session["session_id"],
            "query": session["query"],
            "filters": {},
            "message": "Session created. Use session_add_filter to build your search.",
        }

    @mcp.tool(
        name="session_add_filter",
        description=(
            "Add or replace a filter on an existing session.\n\n"
            "filter_type options:\n"
            "  - 'titles': job titles (e.g., ['Software Engineer', 'Staff Engineer'])\n"
            "  - 'companies': company names (e.g., ['Google', 'Meta'])\n"
            "  - 'locations': locations (e.g., ['Seattle, WA', 'San Francisco'])\n"
            "  - 'skills': skills (e.g., ['Python', 'Kubernetes'])\n"
            "  - 'years_experience_min': minimum years (e.g., ['5'])\n"
            "  - 'years_experience_max': maximum years (e.g., ['15'])\n"
            "  - 'query': boolean search query (e.g., ['Python AND Django'])\n\n"
            "Adding a filter_type that already exists replaces the previous values.\n\n"
            "WHEN TO USE: After session_create, to incrementally build a search."
        ),
    )
    async def session_add_filter(
        session_id: str,
        filter_type: str,
        values: list[str],
    ) -> dict:
        session = await session_store.add_filter(session_id, filter_type, values)
        if session is None:
            return {"error": "Session not found or expired", "session_id": session_id}
        return _format_session(session)

    @mcp.tool(
        name="session_remove_filter",
        description=(
            "Remove a filter from an existing session.\n\n"
            "filter_type: same options as session_add_filter.\n\n"
            "WHEN TO USE: To refine a search by removing a previously added filter."
        ),
    )
    async def session_remove_filter(
        session_id: str,
        filter_type: str,
    ) -> dict:
        session = await session_store.remove_filter(session_id, filter_type)
        if session is None:
            return {"error": "Session not found or expired", "session_id": session_id}
        return _format_session(session)

    @mcp.tool(
        name="session_run_search",
        description=(
            "Execute a search using the accumulated session filters. "
            "Returns candidates and facets.\n\n"
            "WHEN TO USE: After building filters with session_add_filter.\n\n"
            "PAGINATION: Use skip to page through results."
        ),
    )
    async def session_run_search(
        session_id: str,
        max_results: int = 10,
        skip: int = 0,
    ) -> dict:
        session = await session_store.get(session_id)
        if session is None:
            return {"error": "Session not found or expired", "session_id": session_id}

        filters = dict(session["filters"])
        search_query = await query_builder.build(
            query=session.get("query", ""),
            filters=filters,
            top=max(1, min(max_results, 25)),
            skip=max(skip, 0),
            facet_fields=DEFAULT_FACET_TYPES,
        )
        results, total_count = await seekout_api.search_people(search_query)

        return {
            "session_id": session_id,
            "total_count": total_count,
            "returned": len(results.get("WholePersonResults", [])),
            "skip": skip,
            "candidates": _summarize_candidates(results),
            "facets": _extract_facets(results),
        }

    @mcp.tool(
        name="session_get",
        description=(
            "Get the current state of a session — its query and accumulated filters.\n\n"
            "WHEN TO USE: To inspect what filters are currently set before running a search."
        ),
    )
    async def session_get(session_id: str) -> dict:
        session = await session_store.get(session_id)
        if session is None:
            return {"error": "Session not found or expired", "session_id": session_id}
        return _format_session(session)

    @mcp.tool(
        name="session_delete",
        description="Delete a session and free its resources.",
    )
    async def session_delete(session_id: str) -> dict:
        deleted = await session_store.delete(session_id)
        return {
            "session_id": session_id,
            "deleted": deleted,
        }


def _format_session(session: dict) -> dict:
    """Format a session dict for tool response."""
    filters = session.get("filters", {})
    friendly: dict = {}

    if "current_title" in filters:
        friendly["titles"] = filters["current_title"].get("alt_names", [])
    if "current_company" in filters:
        friendly["companies"] = filters["current_company"].get("alt_names", [])
    if "location" in filters:
        friendly["locations"] = filters["location"].get("alt_names", [])
    if "_skill_names" in filters:
        friendly["skills"] = filters["_skill_names"]
    if "years_of_experience" in filters:
        yoe = filters["years_of_experience"]
        if "min" in yoe:
            friendly["years_experience_min"] = yoe["min"]
        if "max" in yoe:
            friendly["years_experience_max"] = yoe["max"]

    return {
        "session_id": session["session_id"],
        "query": session.get("query", ""),
        "filters": friendly,
    }


def _summarize_candidates(results: dict) -> list[dict]:
    """Extract candidate summaries from search results."""
    candidates = []
    for person in results.get("results", []):
        locations = person.get("locations") or []
        candidates.append({
            "profile_key": person.get("key"),
            "name": person.get("full_name"),
            "current_title": person.get("cur_title"),
            "current_company": person.get("cur_company"),
            "location": locations[0] if locations else None,
            "skills": (person.get("skills") or [])[:10],
            "headline": (person.get("headlines") or [None])[0],
        })
    return candidates


def _extract_facets(results: dict) -> dict:
    """Extract facets from search results into user-friendly format."""
    raw_facets = results.get("facets", {})
    if not raw_facets:
        return {}
    facets: dict = {}

    reverse_map = {v: k for k, v in FACET_TYPE_MAP.items()}
    for field_name, values in raw_facets.items():
        friendly_name = reverse_map.get(field_name, field_name)
        facets[friendly_name] = [
            {"name": v.get("name"), "count": v.get("count")}
            for v in (values or [])
        ]

    return facets


def _summarize_profile(profile: dict) -> dict:
    """Extract a detailed profile summary."""
    locations = profile.get("locations") or []
    return {
        "profile_key": profile.get("key"),
        "name": profile.get("full_name"),
        "current_title": profile.get("cur_title"),
        "current_company": profile.get("cur_company"),
        "location": locations[0] if locations else None,
        "headline": (profile.get("headlines") or [None])[0],
        "summary": profile.get("summary"),
        "skills": (profile.get("skills") or [])[:15],
        "certifications": profile.get("certifications") or [],
        "work_history": [
            {
                "title": pos.get("title"),
                "company": pos.get("company"),
                "start_date": pos.get("start_date"),
                "end_date": pos.get("end_date"),
                "description": pos.get("description"),
            }
            for pos in (profile.get("positions") or [])[:10]
        ],
        "education": [
            {
                "school": edu.get("school"),
                "degree": edu.get("degree"),
                "major": edu.get("major"),
                "start_date": edu.get("start_date"),
                "end_date": edu.get("end_date"),
            }
            for edu in (profile.get("educations") or [])[:5]
        ],
        "languages": profile.get("languages") or [],
    }
