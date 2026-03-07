---
description: Map talent at specific companies — team composition, skills, tenure, and where they come from
---
# Competitive Intelligence

Use this workflow when a recruiter wants to understand a competitor's team:
"Who are the senior engineers at Stripe?", "What skills does the Google Cloud
team have?", "Where do Amazon engineers go when they leave?"

## Core Principles

- **Use `companies` filter as the anchor.** The company IS the search — everything
  else (title, skills, location) is secondary filtering.
- **Use `prev_companies` to find alumni.** "Engineers who used to work at Meta"
  tells you where talent goes after leaving.
- **Facets are your best friend.** `seekout_get_facets` on a company-filtered
  search reveals team composition without pulling individual profiles.

## Common Analyses

### Team composition
Filter by `companies='Stripe'` + a broad title like `titles='Engineer'`.
Use facets to see:
- **titles facet**: What levels/roles exist (Staff, Senior, Principal, Manager)
- **skills facet**: What tech stack they use
- **locations facet**: Where their offices/remote workers are

### Poaching targets
Filter by `companies='Competitor'` + `titles='Senior Engineer, Staff Engineer'`
+ relevant skills. Search to get actual profiles. Look for people with
long tenure (`years_in_company_min=3`) — they know the most but may be ready
for a change.

### Alumni tracking
Use `prev_companies='Meta'` + `companies='Stripe, Airbnb, Uber'` to see where
Meta engineers end up. Useful for understanding talent flow and competing offers.

### Tenure analysis
Filter by company, then look at `years_in_company` distribution via profiles.
Short average tenure = high attrition = opportunity to recruit. Long tenure =
loyalty = harder to poach but more experienced.

### Skills gap analysis
Compare your company's skills facets vs a competitor's. If they have 3x more
Kubernetes engineers, that's a capability gap.

## Heuristics

- **Start with facets, not search.** Get the landscape first, then drill into
  specific profiles.
- **Use seniority filter** to focus on the level you're targeting. Don't waste
  time on interns when sourcing Staff engineers.
- **Cross-reference with `seekout_get_suggestions`** to find the exact company
  entity name. "Google" vs "Alphabet" vs "Google Cloud" are different entities.
- **Compare 2-3 competitors** in one analysis. Chain parallel count/facet calls
  in a single `execute` block.

## Presenting Results

- Lead with the insight, not raw data: "Stripe's engineering team is 60% backend,
  heavily concentrated in SF, with Rust and Go as top skills"
- Compare companies in a table when doing competitive analysis
- Highlight actionable findings: "Their ML team has only 12 people in Seattle —
  this is a small, vulnerable team we could target"
