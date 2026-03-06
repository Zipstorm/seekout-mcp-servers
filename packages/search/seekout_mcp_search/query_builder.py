import asyncio

from seekout_mcp_search.entity_resolver import EntityResolver


DEFAULT_FACET_TYPES = ["current_company", "current_title", "location", "skills"]

FACET_TYPE_MAP = {
    "companies": "current_company",
    "titles": "current_title",
    "locations": "location",
    "skills": "skills",
}


class QueryBuilder:
    """Converts Filters dict -> PeopleSearchQuery dict."""

    def __init__(self, entity_resolver: EntityResolver):
        self._entity_resolver = entity_resolver

    async def build(
        self,
        query: str = "",
        filters: dict | None = None,
        top: int = 10,
        skip: int = 0,
        index: str = "NorthAmerica",
        facet_fields: list[str] | None = None,
    ) -> dict:
        filters = dict(filters) if filters else {}
        search = query

        resolution_tasks: dict[str, asyncio.Task] = {}
        for field, entity_type in [
            ("current_title", "Title"),
            ("current_company", "Company"),
            ("location", "Location"),
        ]:
            if field in filters and "alt_names" in filters[field]:
                resolution_tasks[field] = self._entity_resolver.resolve(
                    entity_type, filters[field]["alt_names"]
                )

        skill_names = filters.pop("_skill_names", [])
        if skill_names:
            resolution_tasks["_skills"] = self._entity_resolver.resolve(
                "Skill", skill_names
            )

        if resolution_tasks:
            results = dict(
                zip(
                    resolution_tasks.keys(),
                    await asyncio.gather(*resolution_tasks.values()),
                )
            )

            for field in ["current_title", "current_company", "location"]:
                if field in results:
                    resolved = results[field]
                    ids = [r["id"] for r in resolved if r["resolved"]]
                    alt_names = [r["name"] for r in resolved if not r["resolved"]]
                    filter_val: dict = {}
                    if ids:
                        filter_val["ids"] = ids
                    if alt_names:
                        filter_val["alt_names"] = alt_names
                    filters[field] = filter_val

            if "_skills" in results:
                search = _build_skill_search(search, results["_skills"])

        pq: dict = {
            "search": search,
            "top": min(top, 25),
            "skip": max(skip, 0),
            "index": index,
        }

        if filters:
            pq["filters"] = _serialize_filters(filters)

        if facet_fields:
            pq["facets"] = [
                {"facet_type": f, "count": 10} for f in facet_fields
            ]

        return pq


def _build_skill_search(search: str, resolved_skills: list[dict]) -> str:
    terms = []
    for r in resolved_skills:
        if r["resolved"] and r["id"] is not None:
            terms.append(f"skill:{r['id']}")
        else:
            terms.append(f'"{r["name"]}"')

    if not terms:
        return search

    skill_expr = terms[0] if len(terms) == 1 else f"({' OR '.join(terms)})"
    return f"{search} AND {skill_expr}" if search.strip() else skill_expr


def _serialize_filters(filters: dict) -> dict:
    result = {}
    for key, value in filters.items():
        if key.startswith("_"):
            continue
        result[key] = value
    return result


def flat_params_to_filters(
    titles: str | None = None,
    companies: str | None = None,
    locations: str | None = None,
    skills: str | None = None,
    years_experience_min: int | None = None,
    years_experience_max: int | None = None,
) -> dict:
    filters: dict = {}

    if titles:
        names = [t.strip() for t in titles.split(",") if t.strip()]
        if names:
            filters["current_title"] = {"alt_names": names}

    if companies:
        names = [c.strip() for c in companies.split(",") if c.strip()]
        if names:
            filters["current_company"] = {"alt_names": names}

    if locations:
        names = [loc.strip() for loc in locations.split(",") if loc.strip()]
        if names:
            filters["location"] = {"alt_names": names}

    if skills:
        names = [s.strip() for s in skills.split(",") if s.strip()]
        if names:
            filters["_skill_names"] = names

    if years_experience_min is not None or years_experience_max is not None:
        yoe: dict = {}
        if years_experience_min is not None:
            yoe["min"] = years_experience_min
        if years_experience_max is not None:
            yoe["max"] = years_experience_max
        filters["years_of_experience"] = yoe

    return filters
