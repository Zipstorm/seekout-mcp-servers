---
description: Build a targeted candidate pool from a job description or hiring need
---
# Candidate Pool Build

Use this workflow when a recruiter provides a job description, role title, or
hiring need and wants to find a set of matching candidates.

## Core Principles

- **Titles go in entity filters, not boolean.** Use the `titles` param — entity
  resolution normalizes variants ("SDE1" = "Software Developer" = "Software Engineer").
- **Companies go in entity filters.** Use `companies` param — normalizes LinkedIn
  name variations (e.g. "Northrop Grumman" resolves 60+ variants).
- **Skills go in the boolean `query` as plain text.** Write `("React" OR "Vue") AND "TypeScript"`.
  Never use `skills:()` syntax — it only searches the skills section and misses
  up to 49% of candidates who list skills in job descriptions.
- **Always scope to "Current"** title and company. Never "Current or Past" — it
  pollutes results with people who left the role years ago.
- **Count before searching.** Use `seekout_count_results` first to check pool size
  before pulling profiles.

## Heuristics

- **Pool too large (>5,000)?** Add more filters: seniority, location, years of
  experience, or more specific skills in the boolean.
- **Pool too small (<50)?** Broaden: remove company filter, use OR between title
  variants, reduce required skills.
- **Pool looks wrong?** Check facets with `seekout_get_facets` — if the top
  companies or titles don't match the role, your filters need adjustment.
- **Not sure about entity names?** Use `seekout_get_suggestions` to discover
  valid company/title/skill names before searching.
- **Excluding noise?** Add `NOT cur_title:("VP" OR "Director" OR "intern")` to
  the boolean query.

## Building the Boolean Query

Start broad, then narrow:

1. Extract 2-3 title variants from the JD → `titles` filter
2. If targeting specific employers → `companies` filter
3. Extract must-have skills → plain boolean in `query` with AND
4. Extract nice-to-have skills → OR them together, AND with must-haves
5. Add location via `locations` filter and experience via `years_experience_min/max`
6. Add seniority level if specified

## Validating Results

- Check facets: do the top companies and titles make sense for this role?
- Spot-check 3-5 profiles with `seekout_get_profile` — do they look like real matches?
- If the top skills facet shows unexpected technologies, revisit your boolean

## Boolean Quick Reference

```
AND          "React" AND "TypeScript"
OR           "React" OR "React.js"
NOT          NOT "intern"
Grouping     ("React" OR "Vue") AND "TypeScript"
Title scope  cur_title:("SWE" OR "SDE")
Wildcard     eng* (matches engineer, engineering)
Proximity    "senior engineer"~1
Boost        "python"^5 OR "java"
```
