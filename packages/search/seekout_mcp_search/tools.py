import asyncio

import httpx
from mcp.types import ToolAnnotations

from fastmcp import FastMCP

from seekout_mcp_search.cache_store import CacheStore
from seekout_mcp_search.query_builder import (
    QueryBuilder,
    flat_params_to_filters,
    compute_yoe,
    DEFAULT_FACET_TYPES,
    FACET_TYPE_MAP,
    GEOGRAPHIC_INDEXES,
)
from seekout_mcp_search.seekout_api import SeekOutAPI

SEEKOUT_APP_BASE_URL = "https://app.seekout.io/app"

# Concurrency limit for multi-index fan-out
_FAN_OUT_SEM = asyncio.Semaphore(6)


def register_tools(
    mcp: FastMCP,
    query_builder: QueryBuilder,
    seekout_api: SeekOutAPI,
    cache_store: CacheStore,
    query_store_endpoint: str = "",
    query_store_api_key: str = "",
) -> None:
    """Register all MCP tools on the FastMCP server."""

    # ── Connectivity ──────────────────────────────────────────────────

    @mcp.tool(
        name="seekout_ping",
        description=(
            "Check connectivity to the SeekOut Runtime API. "
            "Returns status code, elapsed time, and echo message."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
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

    # ── Search ────────────────────────────────────────────────────────

    @mcp.tool(
        name="seekout_search_people",
        description=(
            "Search for candidates matching specific criteria. "
            "Returns summarized profiles with name, title, company, location, "
            "skills, linkedin_url, years_of_experience, and a profile_key for "
            "detailed lookup.\n\n"
            "WHEN TO USE: After getting a count with seekout_count_results, "
            "or when you need to see actual candidate profiles.\n\n"
            "PAGINATION: Use skip parameter to page through results. "
            "First call: skip=0. Next page: skip=10.\n\n"
            "MULTI-INDEX: Set index='all' to search all 6 geographic regions "
            "in parallel. Results include source_index for each candidate.\n\n"
            "FILTERS: All filter params accept comma-separated values. "
            "Example: titles='Software Engineer, Staff Engineer', "
            "companies='Google, Meta', seniority='Senior, Lead'\n\n"
            "WORKFLOW: seekout_count_results -> seekout_search_people -> "
            "seekout_get_profile"
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def seekout_search_people(
        query: str | None = None,
        # Core entity filters
        titles: str | None = None,
        companies: str | None = None,
        locations: str | None = None,
        skills: str | None = None,
        schools: str | None = None,
        # Core range/enum filters
        years_experience_min: int | None = None,
        years_experience_max: int | None = None,
        seniority: str | None = None,
        # Advanced entity filters
        prev_companies: str | None = None,
        prev_titles: str | None = None,
        majors: str | None = None,
        degrees: str | None = None,
        industries: str | None = None,
        certifications: str | None = None,
        # Advanced range filters
        company_size_min: int | None = None,
        company_size_max: int | None = None,
        years_in_company_min: int | None = None,
        years_in_company_max: int | None = None,
        years_in_role_min: int | None = None,
        years_in_role_max: int | None = None,
        # String filters
        languages: str | None = None,
        country: str | None = None,
        state: str | None = None,
        # Pagination and index
        max_results: int = 10,
        skip: int = 0,
        index: str = "NorthAmerica",
    ) -> dict:
        filters = flat_params_to_filters(
            titles=titles, companies=companies, locations=locations,
            skills=skills, schools=schools,
            years_experience_min=years_experience_min,
            years_experience_max=years_experience_max,
            seniority=seniority,
            prev_companies=prev_companies, prev_titles=prev_titles,
            majors=majors, degrees=degrees, industries=industries,
            certifications=certifications,
            company_size_min=company_size_min, company_size_max=company_size_max,
            years_in_company_min=years_in_company_min,
            years_in_company_max=years_in_company_max,
            years_in_role_min=years_in_role_min,
            years_in_role_max=years_in_role_max,
            languages=languages, country=country, state=state,
        )
        clamped_top = max(1, min(max_results, 25))
        clamped_skip = max(skip, 0)

        if index == "all":
            return await _fan_out_search(
                query_builder, seekout_api, cache_store,
                query=query or "", filters=filters,
                top=clamped_top, skip=clamped_skip,
            )

        search_query = await query_builder.build(
            query=query or "", filters=filters,
            top=clamped_top, skip=clamped_skip,
            index=index, facet_fields=DEFAULT_FACET_TYPES,
        )
        results, total_count = await seekout_api.search_people(search_query)

        # Cache results by search_id
        search_id = results.get("search_id")
        if search_id:
            await cache_store.cache_search(search_id, search_query, results)

        return {
            "total_count": total_count,
            "returned": len(results.get("results", [])),
            "skip": clamped_skip,
            "search_id": search_id,
            "candidates": _summarize_candidates(results, source_index=index),
            "facets": _extract_facets(results),
        }

    @mcp.tool(
        name="seekout_count_results",
        description=(
            "Get the total count of candidates matching criteria without "
            "returning profiles. Faster than seekout_search_people. "
            "Also returns facets for refinement.\n\n"
            "WHEN TO USE: Before searching, to check how many results "
            "a query returns.\n\n"
            "FILTERS: Same filter params as seekout_search_people.\n\n"
            "WORKFLOW: seekout_count_results -> seekout_search_people -> "
            "seekout_get_profile"
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def seekout_count_results(
        query: str | None = None,
        titles: str | None = None,
        companies: str | None = None,
        locations: str | None = None,
        skills: str | None = None,
        schools: str | None = None,
        years_experience_min: int | None = None,
        years_experience_max: int | None = None,
        seniority: str | None = None,
        prev_companies: str | None = None,
        prev_titles: str | None = None,
        majors: str | None = None,
        degrees: str | None = None,
        industries: str | None = None,
        certifications: str | None = None,
        company_size_min: int | None = None,
        company_size_max: int | None = None,
        years_in_company_min: int | None = None,
        years_in_company_max: int | None = None,
        years_in_role_min: int | None = None,
        years_in_role_max: int | None = None,
        languages: str | None = None,
        country: str | None = None,
        state: str | None = None,
        index: str = "NorthAmerica",
    ) -> dict:
        filters = flat_params_to_filters(
            titles=titles, companies=companies, locations=locations,
            skills=skills, schools=schools,
            years_experience_min=years_experience_min,
            years_experience_max=years_experience_max,
            seniority=seniority,
            prev_companies=prev_companies, prev_titles=prev_titles,
            majors=majors, degrees=degrees, industries=industries,
            certifications=certifications,
            company_size_min=company_size_min, company_size_max=company_size_max,
            years_in_company_min=years_in_company_min,
            years_in_company_max=years_in_company_max,
            years_in_role_min=years_in_role_min,
            years_in_role_max=years_in_role_max,
            languages=languages, country=country, state=state,
        )
        search_query = await query_builder.build(
            query=query or "", filters=filters,
            top=0, index=index, facet_fields=DEFAULT_FACET_TYPES,
        )
        results, total_count = await seekout_api.search_people(search_query)

        return {
            "total_count": total_count,
            "facets": _extract_facets(results),
        }

    @mcp.tool(
        name="seekout_get_facets",
        description=(
            "Get facet breakdowns for a search query. Returns counts by "
            "company, title, location, skills, schools, industries, etc.\n\n"
            "WHEN TO USE: To understand the distribution of candidates "
            "across dimensions before or after searching.\n\n"
            "facet_types: comma-separated list from: titles, companies, "
            "locations, skills, schools, industries, degrees, majors"
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def seekout_get_facets(
        query: str | None = None,
        titles: str | None = None,
        companies: str | None = None,
        locations: str | None = None,
        skills: str | None = None,
        schools: str | None = None,
        years_experience_min: int | None = None,
        years_experience_max: int | None = None,
        seniority: str | None = None,
        facet_types: str = "titles,companies,locations,skills",
        index: str = "NorthAmerica",
    ) -> dict:
        filters = flat_params_to_filters(
            titles=titles, companies=companies, locations=locations,
            skills=skills, schools=schools,
            years_experience_min=years_experience_min,
            years_experience_max=years_experience_max,
            seniority=seniority,
        )
        requested_fields = [
            FACET_TYPE_MAP[ft.strip()]
            for ft in facet_types.split(",")
            if ft.strip() in FACET_TYPE_MAP
        ]
        search_query = await query_builder.build(
            query=query or "", filters=filters,
            top=0, index=index,
            facet_fields=requested_fields or DEFAULT_FACET_TYPES,
        )
        results, total_count = await seekout_api.search_people(search_query)

        return {
            "total_count": total_count,
            "facets": _extract_facets(results),
        }

    # ── Profile drill-down ────────────────────────────────────────────

    @mcp.tool(
        name="seekout_get_profile",
        description=(
            "Get a detailed profile for a specific candidate. "
            "Use the profile_key from seekout_search_people results.\n\n"
            "IMPORTANT: Pass the source_index from search results to ensure "
            "the correct geographic index is queried.\n\n"
            "WHEN TO USE: After finding a candidate via search, to see their "
            "full profile including work history, education, and contact info."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
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

    # ── Discovery / utility tools ─────────────────────────────────────

    @mcp.tool(
        name="seekout_get_suggestions",
        description=(
            "Get autocomplete suggestions for entity names. "
            "Useful for discovering valid company, title, skill, location, "
            "school, major, degree, industry, or certification names.\n\n"
            "suggestion_type: one of 'company', 'title', 'skill', 'location', "
            "'school', 'major', 'degree', 'industry', 'certification'\n\n"
            "WHEN TO USE: When unsure about exact entity names to use in "
            "filters. Example: seekout_get_suggestions(query='Goog', "
            "suggestion_type='company') returns Google, Google Cloud, etc."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
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
            "WHEN TO USE: Before using a complex boolean query in "
            "seekout_search_people. Supports AND, OR, NOT, parentheses, "
            "and field: syntax."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def seekout_validate_query(query: str) -> dict:
        is_valid, error = await seekout_api.validate_boolean(query)
        return {"valid": is_valid, "error": error}

    @mcp.tool(
        name="seekout_get_query",
        description=(
            "Returns the full PeopleSearchQuery object that would be built "
            "from the given parameters. Does NOT execute a search. Useful "
            "for debugging entity resolution and seeing exactly what would "
            "be sent to the Runtime API.\n\n"
            "WHEN TO USE: When you want to inspect how parameters map to "
            "the search query before executing a search."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def seekout_get_query(
        query: str | None = None,
        titles: str | None = None,
        companies: str | None = None,
        locations: str | None = None,
        skills: str | None = None,
        schools: str | None = None,
        years_experience_min: int | None = None,
        years_experience_max: int | None = None,
        seniority: str | None = None,
        prev_companies: str | None = None,
        prev_titles: str | None = None,
        majors: str | None = None,
        degrees: str | None = None,
        industries: str | None = None,
        certifications: str | None = None,
        max_results: int = 10,
        skip: int = 0,
        index: str = "NorthAmerica",
    ) -> dict:
        filters = flat_params_to_filters(
            titles=titles, companies=companies, locations=locations,
            skills=skills, schools=schools,
            years_experience_min=years_experience_min,
            years_experience_max=years_experience_max,
            seniority=seniority,
            prev_companies=prev_companies, prev_titles=prev_titles,
            majors=majors, degrees=degrees, industries=industries,
            certifications=certifications,
        )
        search_query = await query_builder.build(
            query=query or "", filters=filters,
            top=max(1, min(max_results, 25)),
            skip=max(skip, 0), index=index,
        )
        return {"people_search_query": search_query}

    # ── SeekOut app link ──────────────────────────────────────────────

    if query_store_endpoint and query_store_api_key:
        @mcp.tool(
            name="seekout_get_link",
            description=(
                "Generate a SeekOut app URL for a search. Builds the search "
                "query, stores it in the SeekOut query store, and returns "
                "a link that opens the search in the SeekOut UI.\n\n"
                "WHEN TO USE: When the user wants to open or share search "
                "results in the SeekOut web application."
            ),
            annotations=ToolAnnotations(
                readOnlyHint=False,
                openWorldHint=True,
            ),
        )
        async def seekout_get_link(
            query: str | None = None,
            titles: str | None = None,
            companies: str | None = None,
            locations: str | None = None,
            skills: str | None = None,
            schools: str | None = None,
            years_experience_min: int | None = None,
            years_experience_max: int | None = None,
            seniority: str | None = None,
        ) -> dict:
            filters = flat_params_to_filters(
                titles=titles, companies=companies, locations=locations,
                skills=skills, schools=schools,
                years_experience_min=years_experience_min,
                years_experience_max=years_experience_max,
                seniority=seniority,
            )
            search_query = await query_builder.build(
                query=query or "", filters=filters,
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


# ── Multi-index fan-out ───────────────────────────────────────────────


async def _fan_out_search(
    query_builder: QueryBuilder,
    seekout_api: SeekOutAPI,
    cache_store: CacheStore,
    query: str,
    filters: dict,
    top: int,
    skip: int,
) -> dict:
    """Search all geographic indexes in parallel, merge results."""
    per_index_top = max(1, (top + len(GEOGRAPHIC_INDEXES) - 1) // len(GEOGRAPHIC_INDEXES))

    async def _search_one(idx: str) -> dict:
        async with _FAN_OUT_SEM:
            sq = await query_builder.build(
                query=query, filters=dict(filters),
                top=per_index_top, skip=skip, index=idx,
                facet_fields=DEFAULT_FACET_TYPES,
            )
            results, count = await seekout_api.search_people(sq)
            return {"index": idx, "results": results, "count": count, "query": sq}

    raw_results = await asyncio.gather(
        *[_search_one(idx) for idx in GEOGRAPHIC_INDEXES],
        return_exceptions=True,
    )

    # Collect successes, skip failures
    total_count = 0
    all_candidates: list[dict] = []
    merged_facets: dict[str, dict[str, int]] = {}

    for r in raw_results:
        if isinstance(r, Exception):
            continue
        total_count += r["count"]

        candidates = _summarize_candidates(r["results"], source_index=r["index"])
        all_candidates.extend(candidates)

        # Merge facets: sum counts across indexes
        for facet_name, entries in _extract_facets(r["results"]).items():
            if facet_name not in merged_facets:
                merged_facets[facet_name] = {}
            for entry in entries:
                name = entry["name"]
                merged_facets[facet_name][name] = (
                    merged_facets[facet_name].get(name, 0) + entry["count"]
                )

        # Cache each index's results
        search_id = r["results"].get("search_id")
        if search_id:
            await cache_store.cache_search(search_id, r["query"], r["results"])

    # Round-robin merge: take candidates from each index in rotation up to top
    merged_candidates: list[dict] = []
    by_index: dict[str, list[dict]] = {}
    for c in all_candidates:
        idx = c.get("source_index", "unknown")
        by_index.setdefault(idx, []).append(c)

    idx_iters = {idx: iter(cands) for idx, cands in by_index.items()}
    while len(merged_candidates) < top and idx_iters:
        exhausted = []
        for idx, it in idx_iters.items():
            if len(merged_candidates) >= top:
                break
            try:
                merged_candidates.append(next(it))
            except StopIteration:
                exhausted.append(idx)
        for idx in exhausted:
            del idx_iters[idx]

    # Convert merged facets to list format
    facets_out: dict = {}
    for facet_name, counts in merged_facets.items():
        facets_out[facet_name] = sorted(
            [{"name": n, "count": c} for n, c in counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

    return {
        "total_count": total_count,
        "returned": len(merged_candidates),
        "skip": skip,
        "index": "all",
        "indexes_searched": GEOGRAPHIC_INDEXES,
        "candidates": merged_candidates,
        "facets": facets_out,
    }


# ── Response formatting ───────────────────────────────────────────────


def _summarize_candidates(results: dict, source_index: str = "NorthAmerica") -> list[dict]:
    """Extract candidate summaries from search results."""
    candidates = []
    for person in results.get("results", []):
        locations = person.get("locations") or []
        li_urls = person.get("li_urls") or []
        grad_year = person.get("grad_year")
        candidates.append({
            "profile_key": person.get("key"),
            "name": person.get("full_name"),
            "current_title": person.get("cur_title"),
            "current_company": person.get("cur_company"),
            "location": locations[0] if locations else None,
            "linkedin_url": li_urls[0] if li_urls else None,
            "years_of_experience": compute_yoe(grad_year),
            "grad_year": grad_year,
            "skills": (person.get("skills") or [])[:5],
            "headline": (person.get("headlines") or [None])[0],
            "source_index": source_index,
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
    li_urls = profile.get("li_urls") or []
    grad_year = profile.get("grad_year")
    return {
        "profile_key": profile.get("key"),
        "name": profile.get("full_name"),
        "current_title": profile.get("cur_title"),
        "current_company": profile.get("cur_company"),
        "location": locations[0] if locations else None,
        "linkedin_url": li_urls[0] if li_urls else None,
        "years_of_experience": compute_yoe(grad_year),
        "grad_year": grad_year,
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
