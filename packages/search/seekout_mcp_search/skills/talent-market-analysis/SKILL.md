---
description: Analyze talent markets — compare candidate pools across locations, companies, or skills
---
# Talent Market Analysis

Use this workflow when a recruiter wants to understand the talent landscape:
"How many Go engineers are in Austin vs Seattle?", "What companies have the most
ML talent?", "Where should we open our next office for hiring?"

## Core Principles

- **Use `seekout_count_results` and `seekout_get_facets` — not search.** Market
  analysis is about counts and distributions, not individual profiles.
- **Compare across one dimension at a time.** Vary location while holding
  title/skills constant, or vary skills while holding location constant.
- **Use the same filters for each comparison.** If comparing Seattle vs Austin,
  the only thing that changes is the `locations` param.
- **Default to NorthAmerica index.** Only use `index='all'` if explicitly
  comparing international markets.

## Heuristics

- **Comparing cities?** Run parallel `seekout_count_results` calls with the same
  title/skills but different `locations`. Chain them in one `execute` block.
- **Understanding a talent pool?** Use `seekout_get_facets` with
  `facet_types='companies,skills,titles,locations'` to see the distribution.
- **Salary/demand proxy?** A higher count with fewer companies = concentrated
  talent. A lower count spread across many companies = competitive market.
- **Trending skills?** Compare counts for different skill combinations in the
  same location to see relative supply.

## Common Analyses

### Location comparison
Count the same role across 3-5 cities. Report: city, count, top 3 companies,
top 3 skills.

### Company talent mapping
Use `seekout_get_facets` with a broad role query to see which companies have the
most people matching that profile.

### Skills supply
For a given location + title, facet by skills to see what technologies are most
common in that talent pool.

### Competitor benchmarking
Count the same role at 3-5 competitor companies. See who has the deepest bench.

## Presenting Results

- Always include the total count for context
- Show facet breakdowns as ranked lists
- When comparing, present as a table: location/company | count | top skills
- Call out surprises: "Austin has 3x more Rust engineers than Seattle"
