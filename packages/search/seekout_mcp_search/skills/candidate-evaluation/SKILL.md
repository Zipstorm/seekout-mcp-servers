---
description: Evaluate a specific candidate's fit against a role using their full profile
---
# Candidate Evaluation

Use this workflow when a recruiter wants to assess a specific candidate — either
from search results or by name/profile key — against a role or set of criteria.

## Core Principles

- **Always pull the full profile** with `seekout_get_profile` before evaluating.
  Search result summaries are too thin for evaluation.
- **Evaluate against stated criteria**, not assumptions. If the recruiter said
  "5+ years Python experience", check the work history for Python roles.
- **Be specific about gaps.** Don't just say "strong fit" — call out exactly
  what matches and what's missing.

## What to Assess

### Skills match
Compare the candidate's skills list and work history descriptions against the
required and nice-to-have skills. Note which required skills are present vs
missing.

### Experience trajectory
Look at the work history progression:
- Is the seniority level trending up? (IC → Senior → Staff)
- How long at each company? (Job hopping <1yr vs stability >3yr)
- Are the companies relevant? (FAANG, startups, enterprise, etc.)

### Title alignment
Does their current title match the target role level? A "Senior Engineer"
applying for "Staff Engineer" is a stretch; the reverse may mean they're
overqualified.

### Education
Check degree, school, and major if the role has specific requirements (e.g.
MS in CS, PhD for research roles). Note: many strong candidates lack
traditional credentials.

### Location
Are they in the target location? If remote, does their timezone work?

## Comparing Multiple Candidates

When evaluating 2-3 candidates side by side:
- Pull all profiles in one `execute` block
- Create a comparison matrix: name | title | years exp | key skills match | gaps
- Highlight the strongest match and explain why
- Note trade-offs: "Candidate A has better skills match but Candidate B has
  more relevant company experience"

## Red Flags to Note

- Very short tenures across multiple roles (<1 year each)
- Title inflation (impressive title at unknown tiny company)
- Skills list doesn't match work history (claims Python but all roles are Java)
- Large unexplained gaps in work history
