# [Feature Name] — [Topic Name]

This spec covers [scope description — what this spec defines and what it does not]. It is one of several specs that together form the [feature name] plan. Start with [plan.md](./plan.md) for the full picture.

---

## 1. [First Major Section]

<!-- Open with the foundational concept for this spec's domain.
     For a data model spec, this might be the entity hierarchy.
     For an API spec, this might be the endpoint inventory.
     For a tools spec, this might be the tool/agent catalog. -->

### 1.1 [Subsection]

[Detail. Use ASCII diagrams for architecture, hierarchy, and flow:]

```
┌──────────┐     ┌──────────┐
│ Entity A │────▶│ Entity B │
└──────────┘     └──────────┘
       │
       ▼
┌──────────┐
│ Entity C │
└──────────┘
```

### 1.2 [Subsection]

[Detail. Use tables for structured data:]

| Column | Type | Description |
|--------|------|-------------|
| `field_a` | `str` | Primary identifier |
| `field_b` | `int` | Count of related items |

---

## 2. [Second Major Section]

<!-- Go deeper. This is where implementation detail lives. -->

### 2.1 [Subsection]

[Include implementation-level code when it clarifies the design:]

```python
class ExampleService:
    """Brief description of what this service does."""

    def __init__(self, config: Config):
        self.config = config

    async def process(self, input_data: InputModel) -> OutputModel:
        # Key logic described in comments
        result = await self._transform(input_data)
        return OutputModel(data=result)
```

### 2.2 [Subsection]

[Include SQL schemas when the spec covers data:]

```sql
CREATE TABLE example_table (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- indexes and constraints
    CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES orgs(id)
);

CREATE INDEX idx_example_org ON example_table(org_id);
```

---

## 3. [Third Major Section — Options / Decisions Within This Domain]

<!-- When choices exist within this spec's domain, evaluate them here.
     Use comparison tables with clear criteria. -->

### 3.1 [Option A] vs [Option B]

| Criteria | Option A | Option B |
|----------|----------|----------|
| Performance | [Assessment] | [Assessment] |
| Cost | [$/month estimate] | [$/month estimate] |
| Complexity | [Assessment] | [Assessment] |
| Scale (10x) | [What happens] | [What happens] |

**Decision:** [Option chosen] — [rationale in one sentence].

---

## 4. [Fourth Major Section — Flows / Processes]

<!-- Use flow diagrams for multi-step processes: -->

```
User Request
    │
    ▼
┌─────────────┐    ┌──────────┐
│ Step 1:     │───▶│ Step 2:  │
│ Validate    │    │ Process  │
└─────────────┘    └──────────┘
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
         ┌────────┐ ┌────────┐ ┌────────┐
         │ Path A │ │ Path B │ │ Path C │
         └────────┘ └────────┘ └────────┘
```

### 4.1 [Worked Example]

<!-- Include a concrete narrative example showing the system in action.
     Walk through a realistic scenario step by step. -->

**Scenario**: [Describe a realistic user journey or system interaction]

1. [Step 1 — what happens, what data flows where]
2. [Step 2 — include code snippets or data examples inline]
3. [Step 3 — show the output or end state]

---

## 5. [Scale & Cost Considerations]

<!-- Always address what happens at scale. Quantify costs. -->

| Metric | Current | 10x | 100x |
|--------|---------|-----|------|
| [Metric 1] | [Value] | [Projection] | [Projection] |
| [Metric 2] | [Value] | [Projection] | [Projection] |

**Estimated cost**: $X-Y/month at [usage level].

---

## Related Specs

- [plan.md](./plan.md) — Master plan and phase overview
- [01-data-model.md](./01-data-model.md) — [one-line description]
- [02-api-design.md](./02-api-design.md) — [one-line description]
