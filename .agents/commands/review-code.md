---
name: review-code
description: Reviews code against project coding guidelines and best practices. Use when reviewing code changes, checking for guideline violations, or improving existing code quality.
---

# Code Review

Use this skill to review code changes against the project's coding guidelines and best practices. Reference skill files that have related context to the changes made in this branch. Skills are located in `.agents/skills/` (also symlinked at `.claude/skills/`).

## Repo Scope

This review targets Python MCP server code in `packages/`. When gathering changes and running checks, scope commands to the relevant package directory where possible.

## Getting Branch Changes

Before reviewing, gather all changes on the current branch using these git commands:

### 1. Identify the current branch and base branch

```bash
git branch --show-current

git fetch origin
```

### 2. List all changed files on the branch

```bash
# List files changed compared to main branch
git diff --name-only origin/main...HEAD

# Or with status indicators (A=added, M=modified, D=deleted)
git diff --name-status origin/main...HEAD
```

### 3. View the full diff of all changes

```bash
# Full diff of all changes on the branch
git diff origin/main...HEAD

# Diff for Python files only
git diff origin/main...HEAD -- '*.py'

# Diff scoped to a specific package
git diff origin/main...HEAD -- 'packages/search/'
```

### 4. Review commit history on the branch

```bash
# List commits on this branch not in main
git log origin/main..HEAD --oneline

# With more detail including changed files
git log origin/main..HEAD --stat
```

### 5. Read the changed files

After identifying changed files, read each one to perform the review.

**Note**: If the base branch is not `main`, replace `origin/main` with the appropriate base branch.

## Review Checklist

Build a checklist dynamically based on the changes in this branch:

### 1. Run Static Analysis

Always run linting first:

```bash
cd packages/search && uv run ruff check seekout_mcp_search/ tests/
```

If errors are found, fix each issue and re-run until resolved.

### 2. Run Tests

```bash
cd packages/search && uv run pytest -v
```

### 3. Find Relevant Skills

Based on the patterns in the changed code, identify which skill files apply:

- **All Python files**: `python-code-style`, `python-anti-patterns`, `python-type-safety`
- **Config/settings changes**: `python-configuration`
- **Error handling**: `python-error-handling`, `python-resilience`
- **Async code**: `async-python-patterns`
- **Test files**: `python-testing-patterns`
- **Resource management (connections, clients)**: `python-resource-management`
- **Logging/metrics**: `python-observability`
- **Architecture/patterns**: `python-design-patterns`
- **Performance concerns**: `python-performance-optimization`
- **Packaging/dependencies**: `python-packaging`, `uv-package-manager`

List the skills folder and read the relevant skill files to understand the guidelines.

### 4. Build the Checklist

For each relevant skill, create a checklist section using this format:

```markdown
### [Skill Topic Name]

- [ ] [Rule or guideline from the skill]
- [ ] [Another rule - phrased as what the code SHOULD do]
- [ ] [Continue for each key rule in the skill]
```

**Example** (if reviewing async code changes):

```markdown
### Async Python Patterns

- [ ] Uses `async with` for httpx clients
- [ ] No blocking calls inside async functions
- [ ] Uses `asyncio.gather()` for independent concurrent operations

### Python Error Handling

- [ ] No bare `except:` clauses
- [ ] Specific exception types caught
- [ ] Resources cleaned up in `finally` or context managers
```

### 5. Review Against Checklist

Go through each checklist item and verify the changed code follows the guideline. Mark items as checked or note violations.

## How to Use

1. Get the branch changes using the git commands above
2. Run ruff check and pytest
3. Identify which skills are relevant based on the changed files
4. Read those skill files and build a checklist
5. Review each changed file against the checklist
6. For each violation found:
   - Identify the specific guideline being violated
   - Provide the corrected code
7. Prioritize fixes by impact:
   - **High**: Security issues, type safety, async correctness, missing error handling
   - **Medium**: Code style, design patterns, resource management
   - **Low**: Naming conventions, documentation

## Example Review Output

When reporting issues, use this format:

```
### Issue: [Brief description]

**Skill**: [Name of skill file, e.g., python-error-handling]
**Rule**: [Specific rule being violated]

**Current code**:
```python
# problematic code
```

**Suggested fix**:
```python
# corrected code following the skill's guidelines
```
```

## Quick Reference

| Pattern | Avoid | Prefer |
|---------|-------|--------|
| Async HTTP | `requests` / sync httpx | `httpx.AsyncClient` with `async with` |
| Config values | Hardcoded strings | `pydantic-settings` |
| Error handling | Bare `except:` | Specific exception types |
| Resource cleanup | Manual `.close()` | `async with` / context managers |
| Type hints | `Any` / no hints | Specific types, `Optional` |
| Logging | `print()` | `logging` module |
| Testing | No tests | pytest with async fixtures |
| Mutable defaults | `def f(x=[])` | `def f(x=None)` |
| Null checks | `== None` | `is None` |
| String building | `+` in loops | `"".join()` or f-strings |
| Imports | `from x import *` | Explicit imports |
| State | Module-level globals | Factory pattern / DI |
| Dependencies | Adding without asking | Get approval first |
| File naming | `MyModule.py` | `my_module.py` (snake_case) |
