# CLAUDE.md

## Purpose

Root guidance layer for the seekout-mcp-servers repo. Covers shared conventions, safety, routing, and stack info.

## Layout

- Canonical project skills live in `.agents/skills/`.
- Claude discovers skills via `.claude/skills -> ../.agents/skills` (symlink).
- Codex discovers skills from `.agents/skills/` natively and from this file.
- Cursor discovers skills from this file (`AGENTS.md` at project root).

## Scope Ownership

- Root `AGENTS.md` and `CLAUDE.md` own shared conventions, safety, and routing.
- Package-specific guidance belongs in package-local `CLAUDE.md` files.
- Current packages:
  - `packages/search/CLAUDE.md`

## Routing Rules

- If the task is under `packages/search/`, read and prioritize `packages/search/CLAUDE.md` first.
- Use root guidance as baseline policy, then apply package-local guidance when both exist.
- If package-local guidance is missing or incomplete, fall back to root plus directly relevant shared skills.

## Shared Skill Discovery

- Skills are local instructions in `.agents/skills/*/SKILL.md`.
- Use only the minimal set of skills needed for the task.
- Read each selected `SKILL.md` progressively (only enough to execute the workflow).
- Resolve relative references from the skill directory before following linked assets.

## Stack

- **Language:** Python >=3.12
- **MCP SDK:** Community FastMCP 3.0 (PrefectHQ/fastmcp)
- **Package manager:** uv (workspace monorepo)
- **Validation:** Pydantic v2 + pydantic-settings
- **HTTP client:** httpx (async)
- **Cache:** Redis (for sessions), cachetools (in-process TTL)
- **Testing:** pytest (async), pytest-asyncio
- **Linting:** ruff
- **CI:** GitHub Actions (ruff + pytest)
- **Deployment:** Docker (multi-stage with uv), AKS via Helm

## Repo Structure

```
seekout-mcp-servers/
├── packages/           # MCP server packages (one per server)
│   └── search/         # seekout-mcp-search (people search)
├── deploy/             # Helm values for AKS deployment
│   └── mcp-search/
├── plans/              # Design plans and research docs
│   ├── search-server/  # Search server plan + specs
│   └── mcp-patterns.md # General MCP patterns research
├── .agents/            # AI agent config (skills, agents, commands)
├── .claude/            # Claude Code symlinks → .agents/
├── .github/            # CI workflows
└── pyproject.toml      # uv workspace root
```

## High-level Do's and Don'ts

### Do
- Use `create_server(Settings)` factory pattern for all MCP servers
- Use pydantic-settings for all configuration
- Use async endpoints and httpx for external API calls
- Add tests for all tools, query builders, and auth logic
- Use structured error responses from MCP tools
- Pin external repo consumers to git tags, not `main`
- Keep plans in `plans/{plan-name}/` format

### Don't
- Do not add new dependencies without approval
- Do not hardcode secrets or config values
- Do not skip type hints on function signatures
- Do not use `print()` — use `logging`
- Do not put app-specific code at the workspace root

## Change Management

- Treat root docs as the source of truth for shared policy and routing.
- Treat package-local docs as the source of truth for package skill curation and task-specific conventions.
- Keep duplicated text between root and package docs minimal to reduce drift.
