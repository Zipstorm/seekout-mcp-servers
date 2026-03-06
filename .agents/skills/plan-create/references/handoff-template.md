# Implementation Handoff: [Feature Name]

> This prompt contains the strategic context for implementing [feature name]. It was produced in the command-center workspace after research, critical analysis, and planning. Paste this into a Claude Code session in the target repo to begin implementation.

---

## Strategic Context

**What**: [1-2 sentences — what are we building]

**Why**: [1-2 sentences — business/technical motivation]

**Current state**: [1-2 sentences — what exists today]

---

## Key Design Decisions

These were resolved during planning. Do not re-open:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| [Decision 1] | [Choice] | [Why] |
| [Decision 2] | [Choice] | [Why] |

---

## Architecture

[ASCII diagram showing the end-state system. Include component relationships, data flow, and key interfaces.]

---

## Spec Files

<!-- Include this section when the plan has numbered deep-dive specs. Remove for simple plans. -->

The plan includes detailed spec files for each subsystem. Reference these during implementation for schemas, code patterns, flow diagrams, and design rationale:

| Spec | What It Covers | When to Reference |
|------|----------------|-------------------|
| [01-data-model.md]([COMMAND_CENTER_PATH]/apps/plans/[PLAN_NAME]/01-data-model.md) | [Description] | [When implementing what] |
| [02-api-design.md]([COMMAND_CENTER_PATH]/apps/plans/[PLAN_NAME]/02-api-design.md) | [Description] | [When implementing what] |

---

## Implementation Phases

### Phase 1: [Title] — ~X weeks

**Goal:** [One sentence outcome]

**What Gets Built:**
- [Concrete deliverable 1]
- [Concrete deliverable 2]

**Checklist:**
- [ ] [Task 1]
- [ ] [Task 2]
- [ ] Test: [Verification step]

**What Works After Phase 1:**
- [Feature/behavior that's now functional]

### Phase 2: [Title] — ~X weeks

<!-- Same structure. Repeat for each phase. -->

---

## Open Technical Questions

These need codebase exploration before implementation:

- [ ] [Question 1 — what to look for]
- [ ] [Question 2 — what pattern to verify]

---

## Out of Scope

Do not implement these (documented for awareness):

- [Item 1] — [reason]
- [Item 2] — [reason]

---

## Success Criteria

- [ ] [Criterion 1 — concrete, testable]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

---

## Progress Tracking

As you implement, track progress in the command center so that future sessions can resume seamlessly.

**Where**: `[COMMAND_CENTER_PATH]/apps/plans/[PLAN_NAME]/progress.md`

**When to update**:
- After completing each phase (update Progress Overview table + add Phase Details entry)
- When deviating from the plan (add a Decision Changelog entry: DC-001, DC-002...)
- When hitting a blocker (add to Active Blockers table)
- On every natural stopping point (add a Session Log entry with "next session should" instructions)

**How to initialize** (if `progress.md` doesn't exist yet):

Create it with these sections:
1. **Summary** — plan name, target repo, command center path, dates, overall status
2. **Progress Overview** — phase-status table (copy phases from the plan)
3. **Active Blockers** — table with ID, severity, blocked phases, identified date, description
4. **Iteration Summary** — brief narrative of how the plan evolved during implementation
5. **Decision Changelog** — append-only table (DC-001, DC-002...) with: phase, original decision, revised decision, rationale. Later reversals get new entries referencing the original.
6. **Phase Details** — per-phase notes: files created/modified, unexpected findings, verification results
7. **Session Log** — newest-first. Each entry: what was done, what's incomplete, "next session should" instructions, codebase state

**Rules**:
- Session Log and Decision Changelog are append-only (newest first for sessions, sequential for decisions)
- Keep the Progress Overview table in sync with Phase Details — the table is the quick-scan view
- Update the Summary's "Last updated" and "Overall status" on every write
- Include file paths in Phase Details so future sessions know what was touched

---

## Suggested Next Step

Run `/plan-create` in this repo to create an implementation-level plan with phase breakdown, or start exploring the codebase to answer the open technical questions above.
