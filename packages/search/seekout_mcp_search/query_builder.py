import asyncio
from datetime import datetime

from seekout_mcp_search.entity_resolver import EntityResolver

GEOGRAPHIC_INDEXES = [
    "NorthAmerica", "SouthAmerica", "Europe", "Africa", "Asia", "Oceania",
]

DEFAULT_FACET_TYPES = ["current_company", "current_title", "location", "skills"]

FACET_TYPE_MAP = {
    "companies": "current_company",
    "titles": "current_title",
    "locations": "location",
    "skills": "skills",
    "schools": "school",
    "industries": "industry",
    "degrees": "degree",
    "majors": "major",
}

# ── Filter registry ──────────────────────────────────────────────────
# Maps friendly param name -> (api_key, builder_fn)
# Entity filters: builder returns {"alt_names": values} for resolution
# Integer range filters: builder returns {"min": v} or {"max": v}
# String/Enum filters: builder returns {"values": values}

ENTITY_FILTERS: dict[str, tuple[str, str]] = {
    # param_name -> (api_filter_key, entity_type_for_resolution)
    "titles": ("current_title", "Title"),
    "companies": ("current_company", "Company"),
    "locations": ("location", "Location"),
    "schools": ("school", "School"),
    "prev_companies": ("prev_company", "Company"),
    "prev_titles": ("prev_title", "Title"),
    "majors": ("major", "Major"),
    "degrees": ("degree", "Degree"),
    "industries": ("industry", "Industry"),
    "certifications": ("certifications", "Certification"),
}

INT_RANGE_FILTERS: dict[str, tuple[str, str]] = {
    # param_name -> (api_filter_key, bound)
    "years_experience_min": ("years_of_experience", "min"),
    "years_experience_max": ("years_of_experience", "max"),
    "company_size_min": ("company_size", "min"),
    "company_size_max": ("company_size", "max"),
    "years_in_company_min": ("years_in_company", "min"),
    "years_in_company_max": ("years_in_company", "max"),
    "years_in_role_min": ("years_in_role", "min"),
    "years_in_role_max": ("years_in_role", "max"),
}

ENUM_FILTERS: dict[str, str] = {
    # param_name -> api_filter_key
    "seniority": "seniority",
}

STRING_LIST_FILTERS: dict[str, str] = {
    # param_name -> api_filter_key
    "languages": "languages",
    "country": "country",
    "state": "state",
}


class QueryBuilder:
    """Converts filter params -> PeopleSearchQuery dict."""

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

        # Resolve entity filters in parallel
        resolution_tasks: dict[str, asyncio.Task] = {}
        for field, entity_type in [
            ("current_title", "Title"),
            ("current_company", "Company"),
            ("location", "Location"),
            ("school", "School"),
            ("prev_company", "Company"),
            ("prev_title", "Title"),
            ("major", "Major"),
            ("degree", "Degree"),
            ("industry", "Industry"),
            ("certifications", "Certification"),
        ]:
            if field in filters and "alt_names" in filters[field]:
                resolution_tasks[field] = self._entity_resolver.resolve(
                    entity_type, filters[field]["alt_names"]
                )

        # Skills go in the search string, not filters
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

            # Merge resolved entities back into filters
            for field in list(results.keys()):
                if field.startswith("_"):
                    continue
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


def compute_yoe(grad_year: int | None) -> int | None:
    """Compute years of experience from graduation year with guards."""
    if not grad_year or grad_year <= 1950:
        return None
    yoe = datetime.now().year - grad_year
    if yoe < 0:
        return None
    if yoe > 50:
        return 50
    return yoe


def flat_params_to_filters(
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
) -> dict:
    """Convert flat CSV-string params to internal filters dict."""
    filters: dict = {}

    # Entity filters: CSV string -> {"alt_names": [...]}
    entity_params = {
        "titles": ("current_title", titles),
        "companies": ("current_company", companies),
        "locations": ("location", locations),
        "schools": ("school", schools),
        "prev_companies": ("prev_company", prev_companies),
        "prev_titles": ("prev_title", prev_titles),
        "majors": ("major", majors),
        "degrees": ("degree", degrees),
        "industries": ("industry", industries),
        "certifications": ("certifications", certifications),
    }
    for _, (api_key, value) in entity_params.items():
        if value:
            names = [n.strip() for n in value.split(",") if n.strip()]
            if names:
                filters[api_key] = {"alt_names": names}

    # Skills go in internal key (injected into search string by QueryBuilder)
    if skills:
        names = [s.strip() for s in skills.split(",") if s.strip()]
        if names:
            filters["_skill_names"] = names

    # Integer range filters
    int_ranges: list[tuple[str, int | None, int | None]] = [
        ("years_of_experience", years_experience_min, years_experience_max),
        ("company_size", company_size_min, company_size_max),
        ("years_in_company", years_in_company_min, years_in_company_max),
        ("years_in_role", years_in_role_min, years_in_role_max),
    ]
    for api_key, min_val, max_val in int_ranges:
        if min_val is not None or max_val is not None:
            range_filter: dict = {}
            if min_val is not None:
                range_filter["min"] = min_val
            if max_val is not None:
                range_filter["max"] = max_val
            filters[api_key] = range_filter

    # Enum filters: CSV -> {"values": [...]}
    if seniority:
        vals = [s.strip() for s in seniority.split(",") if s.strip()]
        if vals:
            filters["seniority"] = {"values": vals}

    # String list filters: CSV -> {"values": [...]}
    string_params = {
        "languages": languages,
        "country": country,
        "state": state,
    }
    for api_key, value in string_params.items():
        if value:
            vals = [v.strip() for v in value.split(",") if v.strip()]
            if vals:
                filters[api_key] = {"values": vals}

    return filters
