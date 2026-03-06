---
name: blueprint
description: Restate requirements, assess risks, and create a phased implementation plan in the project's plan format. WAIT for user CONFIRM before touching any code. Use when starting a new feature, making architectural changes, or working on complex refactoring.
argument-hint: <what to plan>
---

# Blueprint

Analyze a feature request, restate requirements, surface risks, and produce a structured implementation plan. **Do NOT write any code until the user explicitly confirms the plan.**

This skill invokes the **planner** agent (`~/.claude/agents/planner.md`) for codebase analysis and plan generation. The planner agent is an Opus-powered specialist with access to `Read`, `Grep`, and `Glob` tools for thorough codebase exploration.

## Process

### Step 1: Understand the Request

1. Read the user's request carefully.
2. If the request references existing plans, research, or analysis artifacts, read them:
   - Check `apps/plans/<name>/` for `research.md`, `analysis.md`, `plan.md`
   - Check for linked Confluence docs, Jira tickets, or codebase files mentioned by the user
3. **Invoke the planner agent** to explore the codebase and understand the current architecture:
   - The planner will use `Glob` and `Grep` to find relevant files, patterns, existing implementations
   - The planner will use `Read` to examine key files — models, services, routes, tests
   - The planner identifies existing conventions the plan must follow
   - Pass the user's request and any loaded context to the planner agent

### Step 2: Restate Requirements

Present a clear restatement of what needs to be built. This confirms understanding before planning.

```markdown
## Requirements Restatement

**Goal**: [One sentence — what the system should do when this is done]

**In scope**:
- [Requirement 1]
- [Requirement 2]

**Out of scope**:
- [Explicitly excluded item 1]

**Assumptions**:
- [Assumption 1 — things taken as given]
```

### Step 3: Assess Risks

Surface risks BEFORE presenting the plan. Classify by severity.

```markdown
## Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|------------|
| [Description] | HIGH/MEDIUM/LOW | HIGH/MEDIUM/LOW | [How to address] |
```

### Step 4: Create the Plan

Produce the implementation plan using the format below. The plan must be specific — exact file paths, function names, schema definitions, directory layouts.

Use the **full plan format** for complex features (3+ phases, multiple subsystems). Use the **compact format** for simpler work (1-2 phases, single subsystem).

#### Full Plan Format

```markdown
# Implementation Plan: [Feature Name]

## Overview
[2-3 sentence summary of what this builds and why]

## Requirements Restatement
[From Step 2]

## Architecture

[ASCII diagram showing component relationships]

```
┌──────────────┐     ┌──────────────┐
│  Component A │────▶│  Component B │
└──────────────┘     └──────────────┘
```

### Directory Layout

```
path/to/feature/
├── __init__.py
├── service.py        # Core business logic
├── models.py         # Database models
├── routes.py         # API endpoints
└── tests/
    └── test_service.py
```

## Implementation Phases

### Phase 1: [Title] — ~X weeks

**Goal**: [One sentence]

- [ ] [Verb-first task] (File: `path/to/file.py`)
  - Action: [Specific action]
  - Why: [Reason]
  - Dependencies: None / Requires Phase N
  - Risk: Low/Medium/High
- [ ] [Next task]

**What Works After**:
| Feature | Status |
|---------|--------|
| [Feature A] | Working |
| [Feature B] | Not yet |

### Phase 2: [Title] — ~X weeks
...

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| [Decision 1] | [What we chose] | [Why] |
| [Decision 2] | [What we chose] | [Why] |

## Testing Strategy

- **Unit tests**: [What to test, which files]
- **Integration tests**: [Flows to test]
- **E2E tests**: [User journeys to verify]

## Risks & Mitigations
[From Step 3]

## Open Questions

1. **[Question title]**: [Detail — what needs investigation or stakeholder input]

## Success Criteria

- [ ] [Criterion 1]
- [ ] [Criterion 2]

## Estimated Complexity

- Backend: [X hours/days]
- Frontend: [X hours/days]
- Testing: [X hours/days]
```

#### Compact Format

For simpler features, collapse into a single section without the spec index, architecture diagram, or "What Works After" tables:

```markdown
# Implementation Plan: [Feature Name]

## Overview
[1-2 sentences]

## Steps

1. **[Step Name]** (File: `path/to/file.py`)
   - Action: [What to do]
   - Why: [Reason]
   - Risk: Low/Medium/High

2. **[Step Name]** ...

## Risks
| Risk | Severity | Mitigation |
|------|----------|------------|

## Success Criteria
- [ ] [Criterion 1]
```

### Step 5: Wait for Confirmation

After presenting the plan, **STOP and wait for explicit user confirmation**.

Output exactly:

```
**WAITING FOR CONFIRMATION**: Proceed with this plan? (yes / no / modify)
```

**Do NOT write any code, create files, or make changes until the user responds with an affirmative.**

If the user requests modifications:
- Adjust the plan based on their feedback
- Re-present the modified sections
- Wait for confirmation again

If the user confirms:
- Begin implementation following the plan's phase order
- Mark tasks as completed as you go
- If you discover something that deviates from the plan, pause and inform the user

## Formatting Conventions

Match the project's plan style:

- **ASCII diagrams**: Fenced code blocks (no language tag) for architecture, flows, state machines
- **Code blocks**: Use language tags (`python`, `sql`, `typescript`) for implementation code
- **Tables**: For all structured comparisons, decisions, risks, inventories
- **Bold** (`**term**`): For key terms, phase titles, risk severities
- **Backticks**: For file paths, function names, env vars, CLI commands
- **Verb-first checklist items**: `- [ ] Create migration for...`, `- [ ] Add endpoint to...`
- **Phase numbering**: `### Phase N: [Title] — ~X weeks`
- **Section numbering** (full format only): `## 1. Section`, `### 1.1 Subsection`

## Best Practices

1. **Be Specific**: Exact file paths, function names, variable names, schema columns
2. **Consider Edge Cases**: Error scenarios, null values, empty states, concurrent access
3. **Minimize Changes**: Extend existing code over rewriting — follow existing patterns
4. **Maintain Patterns**: Follow the project's established conventions (check existing code first)
5. **Enable Testing**: Structure changes so each phase is independently testable
6. **Think Incrementally**: Each phase should be independently verifiable and mergeable
7. **Document Decisions**: Explain why, not just what — rationale prevents re-litigation
8. **Scale Awareness**: Include cost estimates, token counts, what happens at 10x/100x where relevant

## Red Flags to Check

Before presenting the plan, verify it doesn't contain:

- Large functions (>50 lines) — break them down
- Deep nesting (>4 levels) — simplify
- Duplicated code — extract shared logic
- Missing error handling — add it
- Hardcoded values — use constants or config
- Missing tests — every phase needs a test strategy
- Plans with no testing strategy
- Steps without clear file paths
- Phases that cannot be delivered independently
- Phases that depend on unbuilt phases without stating so

## When to Escalate to plan-create

If the feature is complex enough to warrant deep-dive spec files (3+ distinct subsystems, 6+ phases), recommend using the `plan-create` skill instead. Blueprint is for in-conversation plans; plan-create produces the full hub-and-spoke plan directory with numbered specs and a handoff prompt.
