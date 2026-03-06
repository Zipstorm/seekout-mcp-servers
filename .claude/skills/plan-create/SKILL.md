---
name: plan-create
description: Create a strategic feature plan with work breakdown and a handoff prompt for the target repo. Interviews for ambiguities, reads research/analysis artifacts if available. Use after research and refinement, or standalone when you already have context.
argument-hint: <plan-name>
---

# Plan Create

Create a strategic feature plan using a hub-and-spoke architecture: a lean `plan.md` (the hub) that indexes into numbered deep-dive spec files (the spokes). This skill interviews the user to resolve all ambiguities, synthesizes research and analysis artifacts, and produces the plan directory plus a `handoff.md` ready to paste into the target repo for implementation.

## Process

### Step 1: Load Context

1. **Read `config.yaml`** from the repository root for user identity, GitHub repos, Jira projects, and Confluence spaces.
2. **Determine the plan name** from the first argument (`$0`). If no argument, use `AskUserQuestion` to get it.
3. **Check for existing artifacts** at `apps/plans/<plan-name>/`:
   - `research.md` — evidence base from the researcher
   - `analysis.md` — critical analysis from the sounding board
   - `state.md` — current phase tracking
4. If neither `research.md` nor `analysis.md` exists, that's fine — the user may have context from other sources or wants to plan from scratch. Note this and proceed.

### Step 2: Initialize Plan Directory

If `apps/plans/<plan-name>/` doesn't exist, create it with a `state.md`:

```markdown
# Feature Plan State: <plan-name>
## Status
- Current phase: plan
- Created: YYYY-MM-DD
- Last updated: YYYY-MM-DD
## Phase History
| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| plan | in-progress | YYYY-MM-DD | — | — |
## Checkpoint Log
- [YYYY-MM-DD] Plan creation started
```

If `state.md` already exists, update it to reflect plan phase.

### Step 3: Interview the User

**This is the most important step. Do not skip or rush it.**

Resolve all ambiguities through an iterative interview using `AskUserQuestion`. The goal is to capture every decision needed to produce a complete plan.

**Interview topics** (adapt to the feature):
- **Existing context pointers**: Are there specific Slack threads, Jira tickets, Confluence docs, or codebase files I should read before planning? The user often knows exactly where the relevant discussion or prior art lives — ask first, search later.
- **Current state**: What exists today? What's the starting point? (If not covered by research artifacts.)
- **Vision**: What does the end state look like? What should the system do when this is done?
- **Scope**: What's in? What's explicitly out? What's "nice to have" vs required?
- **Technical constraints**: Target repo, existing patterns to follow, performance requirements, infrastructure
- **Options**: Are there multiple approaches worth evaluating? Does the user have a preferred direction, or should the plan evaluate alternatives?
- **Dependencies**: What must exist first? What teams need to be consulted?
- **Risks**: What could go wrong? What's the blast radius of failure?
- **Timeline**: Any hard deadlines? What's driving the urgency?
- **Success criteria**: How do we know this is done? How do we know it's working?

**Interview rules**:
- Ask up to 4 questions at a time (respects `AskUserQuestion` limits)
- Continue iterating until all ambiguities are resolved — there is no limit on rounds
- If the user says "whatever you think is best", provide your recommendation and get explicit confirmation
- If research/analysis artifacts exist, reference specific findings when asking questions
- Don't ask questions that are already answered in `research.md` or `analysis.md`

### Step 4: Determine Plan Structure

Before writing, decide on the plan's document structure based on complexity:

**Simple feature** (1-3 phases, single subsystem):
- Single `plan.md` with all detail inline
- No spec files needed
- Skip Options Evaluated and Spec Index sections

**Medium feature** (3-6 phases OR 2+ distinct subsystems):
- `plan.md` as a lean overview/index
- 2-4 numbered spec files covering distinct subsystems
- Each spec is self-contained and independently readable

**Complex system** (6+ phases AND 3+ subsystems):
- `plan.md` as the hub — vision, architecture diagram, spec index, phase overview, key decisions, open questions
- 4-8 numbered spec files as spokes — each covering one subsystem in full depth
- Specs cross-reference each other and always link back to `plan.md`

The key signal is **distinct subsystems**, not just phase count. If the feature touches data models, an API layer, a frontend, and a deployment pipeline, those are 4 specs even if the plan is only 4 phases.

### Step 5: Create the Plan (`plan.md`)

Produce `plans/<plan-name>/plan.md` using the plan template from `references/plan-template.md`.

**For plans with spec files, `plan.md` is a lean hub.** It should:
- Give the reader the full picture in 5-10 minutes of reading
- Link to specs for deep-dive detail — never duplicate spec content in the plan
- Contain the architecture diagram, spec index, phase overview, and key decisions
- Be the entry point — someone reads `plan.md` first, then dives into specs as needed

**For simple single-file plans**, `plan.md` carries all detail inline following the full template structure.

**The plan must include** (adapt to complexity):

1. **Title + Metadata** — Plan name, date, status.
2. **Vision** — 2-3 paragraphs on the end state. Include an ASCII architecture diagram. For features with multiple components, show the relationships between them.
3. **Spec Index** (medium/complex only) — Table linking to numbered spec files with one-line descriptions.
4. **Where It Lives** — Deployment context: which repo, service, directory, and infrastructure this feature lives in.
5. **Architecture** — High-level component description, directory layout, key abstractions. Reference specs for deep-dive detail.
6. **Implementation Phases** — Each phase:
   - `### Phase N: [Title] — ~X weeks`
   - Goal (one sentence)
   - Task checklist (`- [ ]` items, verb-first, reference files and specs)
   - Dependencies on prior phases
   - What Works After (feature status table: Working / Not yet)
7. **Key Design Decisions** — Table: Decision | Choice | Rationale | Spec. Every significant architectural choice gets a row. Link to the spec section where it's discussed in detail.
8. **Open Questions** — Numbered list with bold titles. Things needing codebase exploration or stakeholder input.

### Step 6: Create Deep-Dive Specs

For medium and complex plans, create numbered spec files using the spec template from `references/spec-template.md`.

**Spec files follow a consistent structure:**

- **Title**: `# [Feature Name] — [Topic Name]`
- **Opening paragraph**: Abstract explaining scope + link back to `plan.md`
- **Numbered sections**: `## 1. Section`, `### 1.1 Subsection` — two-level numbering
- **ASCII diagrams**: Architecture, flows, state machines, hierarchy — use fenced code blocks
- **Implementation detail**: Python/SQL/TypeScript code, schema DDL, API routes, config snippets
- **Comparison tables**: When choices exist within the spec's domain, show options evaluated with rationale
- **Scale & cost awareness**: Include token counts, dollar estimates, what happens at 10x/100x
- **Related Specs footer**: Every spec ends with `## Related Specs` linking to connected specs and back to `plan.md`

**Naming convention**: `NN-descriptive-name.md` (zero-padded, kebab-case).

**Common spec topics** (adapt to the feature):
- `01-data-model.md` — Schema, storage layout, multi-tenancy, blob/file structure
- `02-tools-and-coordination.md` — Business logic, sub-systems, tool/agent coordination
- `03-memory-and-context.md` — State management, caching, context, persistence
- `04-model-selection.md` — LLM/service selection, cost analysis, provider abstraction
- `05-interaction-design.md` — Frontend, UI components, WebSocket messages, wireframes
- `06-api-and-deployment.md` — REST endpoints, security, deployment, infrastructure

Each spec should be **self-contained and independently readable**. A reader should be able to understand a spec without having read the others, though cross-references help navigation.

**What goes in specs vs plan.md:**
- **plan.md**: Vision, architecture overview, phase summary, decision index, open questions
- **Specs**: Implementation detail, code, schemas, flow diagrams, cost analysis, comparison tables, worked examples

### Step 7: Create the Handoff Prompt

Produce `plans/<plan-name>/handoff.md` using the handoff template from `references/handoff-template.md`.

The handoff prompt is a self-contained document designed to be pasted into a Claude Code session in the target repo. It contains:
- Strategic context (what, why, current state) — so the implementation session doesn't need to re-derive intent
- Key design decisions — prevents re-opening settled questions
- Architecture overview — system diagram or component description
- Phased work breakdown with checklists — ready for implementation
- "What Works After" summaries — clear phase exit criteria
- Open technical questions — things that need codebase exploration
- Spec file references — pointers to deep-dive specs for implementation detail
- Success criteria — definition of done for the whole feature
- Progress tracking section — tells the implementing agent where and how to write back progress

**Template variables to fill in**:
- Replace `[COMMAND_CENTER_PATH]` with the absolute path to the command center repo root (read from the current working directory)
- Replace `[PLAN_NAME]` with the plan name from Step 1

### Step 8: Update State and Present

1. Update `state.md`:
   - Set phase to `completed`
   - Log the completion timestamp
2. Present a summary to the user:
   - Plan overview (2-3 sentences)
   - Key decisions made
   - Phase breakdown summary (number of phases, estimated total duration)
   - Files produced (list all plan files created)
   - Next step: copy `handoff.md` to the target repo

## Key Principles

- **Hub-and-spoke is the default.** `plan.md` is the overview; specs carry the detail. Only simple features (1-3 phases, single subsystem) use a single file.
- **Specs are self-contained.** Each spec should be independently readable. Open with an abstract, close with Related Specs. Cross-reference, don't duplicate.
- **Interview depth over speed.** A 15-minute interview saves days of wrong-direction implementation. Don't rush it.
- **ASCII diagrams everywhere.** Architecture, flows, state machines, hierarchy, wireframes — use box diagrams liberally. They communicate faster than prose.
- **Implementation-level detail in specs.** Specs contain near-production code: Python classes, SQL DDL, API routes, TypeScript interfaces, config snippets. The spec should be close enough to implement from directly.
- **Show the work on decisions.** Don't just state choices — show the rationale. Use comparison tables with criteria (Effectiveness, Complexity, Cost, Risk) when multiple options exist.
- **Scale and cost awareness.** Include token counts, dollar estimates per month, what happens at 10x and 100x users. Every design decision has cost implications — quantify them.
- **"What Works After" is non-negotiable.** Every phase must answer: what can I verify after completing this?
- **The handoff is the product.** The plan is for the user. The handoff is for the implementation session. Both must be complete and self-contained.
- **Reference the evidence.** When making claims in the plan, reference findings from `research.md` and `analysis.md`. Don't assert things that weren't established during research.
- **Decisions are final.** Once captured in the design decisions table, decisions don't get re-opened in the handoff. The implementation session should not re-litigate what was decided here.
- **Cross-reference liberally.** Use relative markdown links between specs and from plan.md to spec sections. Every spec ends with a Related Specs section.

## Formatting Conventions

These apply to `plan.md` and all spec files:

- **Title format**: `# [Feature Name] — [Topic Name]`
- **Section numbering**: Two-level — `## 1. Major Section`, `### 1.1 Subsection`
- **Horizontal rules** (`---`): Between major sections
- **ASCII diagrams**: Fenced code blocks (no language tag) for architecture, flows, state machines, wireframes
- **Code blocks**: Use language tags (`python`, `sql`, `typescript`, `json`) for implementation code
- **Tables**: For all structured comparisons, inventories, decision matrices
- **Bold** (`**term**`): For key terms, not italics
- **Backticks**: For file paths, function names, env vars, CLI commands
- **Relative links**: `[02-tools-and-coordination.md](./02-tools-and-coordination.md)` for cross-references

## Important Notes

- **This is a principal engineer.** Plans should be at the architecture level — concrete enough to implement from (file paths, schemas, endpoints) but focused on what and why, not line-by-line how.
- **Use `AskUserQuestion` for all clarification.** Never assume. If something could go two ways, ask.
- **The target repo may be different.** The handoff prompt will be used in a different Claude Code session, possibly a different codebase. It must be self-contained.
- **Include code-level detail where it matters.** Directory trees, before/after diffs, config snippets, schema definitions, and Python class outlines make plans actionable. Abstract descriptions don't.
