# [Feature Name] — [Descriptor: Plan / System Design / Implementation Plan]

**Date:** YYYY-MM-DD
**Status:** Proposed

---

## Vision

2-3 paragraphs describing the end state. What does the system look like when this is done? What makes it different from what exists today?

Include an architecture diagram showing the key components and their relationships:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Component A │────▶│  Component B │────▶│  Component C │
└──────────────┘     └──────────────┘     └──────────────┘
                           │
                           ▼
                     ┌──────────────┐
                     │  Component D │
                     └──────────────┘
```

---

## Spec Index

<!-- Include for medium/complex plans with spec files. Remove for simple single-file plans. -->

| # | Spec | What It Covers |
|---|------|----------------|
| **01** | [Data Model](./01-data-model.md) | Schema, storage layout, multi-tenancy |
| **02** | [API Design](./02-api-design.md) | Endpoints, auth, request/response shapes |
| **03** | [Subsystem Name](./03-subsystem-name.md) | Brief description |

---

## Where It Lives

<!-- Deployment context — which repo, service, directory, and infrastructure. -->

- **Repo**: `org/repo-name`
- **Service**: `service-name` (or "new service")
- **Directory**: `apps/service-name/` or relevant path
- **Infrastructure**: Cloud provider, runtime, key services

---

## Architecture

High-level component description and directory layout. Reference specs for deep-dive detail.

```
directory-layout/
├── component-a/
│   ├── models.py          # Data layer (see 01-data-model.md)
│   ├── routes.py          # API surface (see 02-api-design.md)
│   └── services/
│       └── core.py        # Business logic
└── config/
    └── settings.py
```

---

## Implementation Phases

### Phase 1: [Title] — ~X weeks

**Goal:** One sentence describing the outcome of this phase.

- [ ] [Verb-first task — Create, Implement, Add, Port, Extend]
- [ ] [Task with file reference — see `path/to/file`]
- [ ] [Task with spec reference — see [01-data-model.md](./01-data-model.md)]
- [ ] Test: [What to verify]

**Dependencies:** None

#### What Works After Phase 1

| Feature | Status | How It Works |
|---------|--------|--------------|
| [Feature 1] | Working | [Brief description] |
| [Feature 2] | Not yet | [What's still missing] |

---

### Phase 2: [Title] — ~X weeks

<!-- Same structure. Repeat for each phase. -->

---

## Key Design Decisions

| Decision | Choice | Rationale | Spec |
|----------|--------|-----------|------|
| [Decision 1] | [What we chose] | [Why this over alternatives] | [01 §1.2](./01-data-model.md#12-section) |
| [Decision 2] | [What we chose] | [Why] | — |

---

## Open Questions

Questions that need codebase exploration or stakeholder input before implementation:

1. **[Question title]:** [What we don't know yet and why it matters]
2. **[Question title]:** [Description]

---

## References

- [Link to research, analysis, or prior art if available]
- [Relevant docs, tickets, threads]
