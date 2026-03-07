"""Code Mode spike — test FastMCP CodeMode transform with SeekOut search tools.

Run: uv run python spike_code_mode.py

This creates the SeekOut search server with CodeMode transform applied,
then simulates what an LLM would see and do: search for tools, get schemas,
and execute tool calls via Python code.
"""

import asyncio
import json

from fastmcp import FastMCP
from fastmcp.experimental.transforms.code_mode import CodeMode
from unittest.mock import AsyncMock

from seekout_mcp_search.cache_store import CacheStore
from seekout_mcp_search.entity_resolver import EntityResolver
from seekout_mcp_search.query_builder import QueryBuilder
from seekout_mcp_search.tools import register_tools


# ── Mock API that returns realistic data ──────────────────────────────────

def make_mock_api():
    api = AsyncMock()
    api.ping.return_value = (200, 12.5)
    api.validate_boolean.return_value = (True, None)
    api.search_entities.return_value = [
        {"text": "Google", "id": 60, "count": 50000},
        {"text": "Google Cloud", "id": 1234, "count": 8000},
    ]
    api.get_profile.return_value = {
        "key": "abc123",
        "full_name": "Jane Smith",
        "cur_title": "Staff Software Engineer",
        "cur_company": "Google",
        "locations": ["Seattle, WA"],
        "headlines": ["Building distributed systems at scale"],
        "summary": "10+ years in backend engineering...",
        "skills": ["Python", "Go", "Kubernetes", "gRPC", "PostgreSQL"],
        "certifications": ["AWS Solutions Architect"],
        "positions": [
            {"title": "Staff SWE", "company": "Google", "start_date": "2020", "end_date": None},
            {"title": "Senior SWE", "company": "Meta", "start_date": "2016", "end_date": "2020"},
        ],
        "educations": [
            {"school": "Stanford", "degree": "MS", "major": "Computer Science"},
        ],
        "languages": ["English", "Spanish"],
        "li_urls": ["https://linkedin.com/in/janesmith"],
        "grad_year": 2012,
    }
    api.search_people.return_value = (
        {
            "search_id": "fake-search-id-001",
            "count": 1547,
            "results": [
                {
                    "key": "abc123",
                    "full_name": "Jane Smith",
                    "cur_title": "Staff Software Engineer",
                    "cur_company": "Google",
                    "locations": ["Seattle, WA"],
                    "skills": ["Python", "Go", "Kubernetes", "gRPC", "PostgreSQL"],
                    "headlines": ["Building distributed systems at scale"],
                },
                {
                    "key": "def456",
                    "full_name": "John Doe",
                    "cur_title": "Senior Backend Engineer",
                    "cur_company": "Meta",
                    "locations": ["Menlo Park, CA"],
                    "skills": ["Java", "Python", "React", "GraphQL"],
                    "headlines": ["Full-stack engineer focused on infra"],
                },
                {
                    "key": "ghi789",
                    "full_name": "Alice Chen",
                    "cur_title": "Principal Engineer",
                    "cur_company": "Amazon",
                    "locations": ["San Francisco, CA"],
                    "skills": ["Python", "AWS", "Terraform", "Kafka"],
                    "headlines": ["Cloud infrastructure at scale"],
                },
            ],
            "facets": {
                "current_company": [
                    {"name": "Google", "count": 234},
                    {"name": "Meta", "count": 189},
                    {"name": "Amazon", "count": 156},
                ],
                "current_title": [
                    {"name": "Software Engineer", "count": 567},
                    {"name": "Senior Software Engineer", "count": 432},
                ],
                "location": [
                    {"name": "Seattle, WA", "count": 321},
                    {"name": "San Francisco, CA", "count": 298},
                ],
                "skills": [
                    {"name": "Python", "count": 890},
                    {"name": "Kubernetes", "count": 456},
                ],
            },
        },
        1547,
    )
    return api


def create_code_mode_server():
    """Create server with CodeMode transform."""
    mock_api = make_mock_api()
    resolver = EntityResolver(mock_api)
    builder = QueryBuilder(resolver)
    cache = AsyncMock(spec=CacheStore)

    mcp = FastMCP("seekout-search-codemode", transforms=[CodeMode()])

    register_tools(mcp, builder, mock_api, cache)
    return mcp


def create_normal_server():
    """Create server WITHOUT CodeMode for comparison."""
    mock_api = make_mock_api()
    resolver = EntityResolver(mock_api)
    builder = QueryBuilder(resolver)
    cache = AsyncMock(spec=CacheStore)

    mcp = FastMCP("seekout-search-normal")

    register_tools(mcp, builder, mock_api, cache)
    return mcp


async def main():
    print("=" * 70)
    print("CODE MODE SPIKE — SeekOut MCP Search Server")
    print("=" * 70)

    # ── Compare tool surfaces ─────────────────────────────────────────
    normal = create_normal_server()
    code_mode = create_code_mode_server()

    normal_tools = await normal.list_tools()
    cm_tools = await code_mode.list_tools()

    print(f"\n--- NORMAL MODE: {len(normal_tools)} tools ---")
    for t in normal_tools:
        schema = t.inputSchema if hasattr(t, 'inputSchema') else {}
        param_count = len(schema.get("properties", {})) if schema else "?"
        print(f"  {t.name} ({param_count} params)")

    print(f"\n--- CODE MODE: {len(cm_tools)} tools ---")
    for t in cm_tools:
        desc_preview = (t.description or "")[:100].replace("\n", " ")
        print(f"  {t.name}: {desc_preview}")

    # ── Estimate token savings ────────────────────────────────────────
    normal_schema_json = json.dumps(
        [{"name": t.name, "description": t.description,
          "inputSchema": t.inputSchema if hasattr(t, 'inputSchema') and t.inputSchema else {}}
         for t in normal_tools],
        indent=2,
    )
    cm_schema_json = json.dumps(
        [{"name": t.name, "description": t.description,
          "inputSchema": t.inputSchema if hasattr(t, 'inputSchema') and t.inputSchema else {}}
         for t in cm_tools],
        indent=2,
    )
    # Rough token estimate: ~4 chars per token
    normal_tokens = len(normal_schema_json) // 4
    cm_tokens = len(cm_schema_json) // 4
    reduction = ((normal_tokens - cm_tokens) / normal_tokens * 100) if normal_tokens else 0

    print(f"\n--- TOKEN ESTIMATE ---")
    print(f"  Normal mode schema: ~{normal_tokens} tokens ({len(normal_schema_json)} chars)")
    print(f"  Code mode schema:   ~{cm_tokens} tokens ({len(cm_schema_json)} chars)")
    print(f"  Reduction:          ~{reduction:.0f}%")

    # ── Simulate LLM workflow with Code Mode ──────────────────────────
    print(f"\n{'=' * 70}")
    print("SIMULATING LLM WORKFLOW")
    print("=" * 70)

    # Helper to extract text from tool results
    def get_text(result) -> str:
        if hasattr(result, 'text'):
            return result.text
        if hasattr(result, 'content'):
            parts = result.content if isinstance(result.content, list) else [result.content]
            return "\n".join(getattr(p, 'text', str(p)) for p in parts)
        return str(result)

    # Step 1: LLM calls search to discover tools
    print("\n[Step 1] LLM calls: search(query='search people candidates')")
    search_result = await code_mode.call_tool("search", {"query": "search people candidates"})
    print(f"  Result: {get_text(search_result)[:500]}")

    # Step 2: LLM gets schema for the tool it wants
    print("\n[Step 2] LLM calls: get_schema(tools=['seekout_search_people'])")
    schema_result = await code_mode.call_tool("get_schema", {"tools": ["seekout_search_people"]})
    print(f"  Result: {get_text(schema_result)[:500]}")

    # Step 3: LLM writes code to execute a search
    print("\n[Step 3] LLM calls: execute(code=...)")
    code = """
result = await call_tool("seekout_search_people", {
    "query": "distributed systems",
    "companies": "Google, Meta",
    "skills": "Python, Kubernetes",
    "max_results": 3
})
return result
"""
    print(f"  Code:\n{code}")
    try:
        exec_result = await code_mode.call_tool("execute", {"code": code})
        print(f"  Result (first 800 chars): {get_text(exec_result)[:800]}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")

    # Step 4: LLM chains multiple calls in one execute
    print(f"\n[Step 4] LLM chains: count -> search -> get_profile in one execute")
    chained_code = """
# First get a count
count_result = await call_tool("seekout_count_results", {
    "query": "machine learning",
    "skills": "Python, PyTorch"
})

# Then search
search_result = await call_tool("seekout_search_people", {
    "query": "machine learning",
    "skills": "Python, PyTorch",
    "max_results": 3
})

# Get first candidate's profile
candidates = search_result.get("candidates", [])
if candidates:
    profile = await call_tool("seekout_get_profile", {
        "profile_key": candidates[0]["profile_key"]
    })
    return {
        "total_count": count_result.get("total_count"),
        "first_candidate": candidates[0]["name"],
        "profile_skills": profile.get("skills", []),
    }
return {"error": "no candidates"}
"""
    print(f"  Code:\n{chained_code}")
    try:
        exec_result = await code_mode.call_tool("execute", {"code": chained_code})
        print(f"  Result: {get_text(exec_result)[:800]}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("SPIKE SUMMARY")
    print("=" * 70)
    print(f"  Normal tools:    {len(normal_tools)}")
    print(f"  Code Mode tools: {len(cm_tools)} (search, get_schema, execute)")
    print(f"  Token reduction: ~{reduction:.0f}%")
    print(f"  LLM can chain multiple API calls in one execute block")
    print(f"  LLM discovers tools on-demand via search")


if __name__ == "__main__":
    asyncio.run(main())
