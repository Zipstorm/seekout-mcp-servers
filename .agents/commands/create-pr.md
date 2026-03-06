---
argument-hint: [jira-url]
description: Create a PR against main branch with filled PR template
allowed-tools:
  - mcp__atlassian__getAccessibleAtlassianResources
  - mcp__atlassian__getVisibleJiraProjects
  - mcp__atlassian__createJiraIssue
  - mcp__atlassian__atlassianUserInfo
  - mcp__atlassian__getJiraIssue
  - mcp__atlassian__editJiraIssue
  - mcp__atlassian__getTransitionsForJiraIssue
  - mcp__atlassian__transitionJiraIssue
  - mcp__atlassian__searchJiraIssuesUsingJql
  - Bash(git add:*)
  - Bash(git commit:*)
  - Bash(git push:*)
  - Bash(gh pr create:*)
  - Bash(gh:*)
  - Bash(git:*)
  - Read
  - Glob
  - Grep
---

## Context

**Current branch:** !`git branch --show-current`

**Git status:** !`git status --short`

**Parent branch detection (reflog):**
!`git reflog show --no-abbrev HEAD | grep -E "checkout: moving from .+ to" | head -1`

**Recent commits on this branch:**
!`git log --oneline -10`

## Your Task

Create a pull request by following these steps:

### Step 0: Check Current Branch and Determine Target Branch

**Check if on main:**
If the current branch is `main`:
1. **Stop** - you cannot create a PR from the main branch to itself
2. **Ask the user** for a new branch name (suggest format: `ticket-number`)
3. Create and checkout the new branch using `git checkout -b <branch-name>`
4. Then proceed with the remaining steps

**Determine target branch for PR:**
1. Check the reflog output above to identify the parent branch (the branch you checked out from)
2. If a parent branch is detected (e.g., `checkout: moving from feature-branch to current-branch`):
   - **Ask the user**: "It looks like you branched from `<parent-branch>`. Would you like to create the PR against `<parent-branch>` or `main`?"
3. If no parent branch can be determined, default to `main`
4. Store the chosen target branch for use in Step 4

### Step 1: Check for Uncommitted Changes

Check the git status output above. If there are uncommitted changes (modified, added, or deleted files):
1. **Ask the user** if they want to commit these changes before creating the PR
2. If yes, create a commit with an appropriate message based on the changes
3. If no, proceed without committing (the uncommitted changes will not be part of the PR)

### Step 2: Get JIRA Information

A Jira ticket is required for every PR.

### Option A: Provide an Existing Ticket
If a JIRA URL was provided as an argument ($1):
- Extract the ticket number (e.g., `V2S-123` from URL or direct input)
- Use `mcp__atlassian__getJiraIssue` to fetch ticket details
- Check if the ticket has labels:
  - If no labels, apply stored label preferences (or ask the user)
- Check if the ticket has an epic:
  - If no epic, ask the user which epic to assign
- Transition the ticket to "In Progress" status using `mcp__atlassian__transitionJiraIssue`

### Option B: Create a New Ticket

If no ticket provided, **ask the user** which option they prefer and follow these steps:

1. Create the ticket in `V2S` project using `mcp__atlassian__createJiraIssue`
   - Type: Based on changes (default is `Task`)
   - Use the PR title/description to generate summary and description
   - Assign to current user
2. Set status to "In Progress" using transitions
3. **Epic Assignment:**
   - Check for stored Epic preferences in `.agents/jira.local.json`
   - If preferences exist, present them as first choices
   - Otherwise, search recent tickets: `project = V2S AND assignee = currentUser() AND updated >= -30d AND parent is not EMPTY`
   - Ask user which Epic should be the parent
   - Save selected Epic to preferences (keep max 3, most recent first)
4. **Label Assignment:**
   - Check for stored Label preferences
   - If no stored labels, search: `project = V2S AND assignee = currentUser() AND updated >= -30d AND labels is not EMPTY`
   - Present labels and ask which to apply
   - Apply labels using `mcp__atlassian__editJiraIssue`
   - Save label preferences (keep max 3, most recent first)

### Saving Preferences

Store Jira preferences in `.agents/jira.local.json`:
```json
{
  "transitions": [],
  "epics": [
    {"epicKey": "V2S-XXXX", "epicSummary": "Epic Name"}
  ],
  "labels": ["Label1", "Label2"]
}
```

When updating preferences:
- Preserve existing data (transitions, epics, labels) when updating any section
- Move selected item to beginning of array (most recent first)
- Keep only 3 most recent items per category

**Multiple JIRA tickets**: After getting the first URL, **ask the user** if there are additional JIRA tickets that should be linked to this PR. If yes, collect all URLs and extract ticket numbers from each.

### Step 3: Analyze Changes

Based on the recent commits above, run `git diff <TARGET-BRANCH>...HEAD` to see the changes compared to the target branch, then analyze:
1. **PR Type**: Determine if this is a Feature, Bug fix, or Other based on the nature of changes
2. **Description**: Write a clear, concise description of what changed and why
3. **Testing**: Identify what testing would be appropriate (Unit Tests, Manual Testing)
4. **Edge Cases**: Identify potential edge cases based on the implementation

### Step 4: Create the PR

Use `gh pr create` with the target branch determined in Step 0:

```
gh pr create --base <TARGET-BRANCH> --title "[TICKET-NUMBER]: Brief description" --body "$(cat <<'EOF'
[TICKET-NUMBER](JIRA-URL)
<!-- For multiple tickets, add each on a new line:
[TICKET-NUMBER-2](JIRA-URL-2)
[TICKET-NUMBER-3](JIRA-URL-3)
-->

## Overview
- [x] Feature/Bug/Other (mark the appropriate one and delete the unused values)

<!-- Description of changes -->

## Video or Screenshots
<!-- N/A for backend changes, or describe what screenshots would show -->

## Testing
<!-- Description of how changes were tested -->

- [ ] Unit Tests
- [ ] Debug/Manual Testing

<!-- Mark appropriate testing methods -->

## Edge Cases
<!-- List edge cases considered -->

## Checklist
- [x] I have self-reviewed my changes (required)
- [x] I have tested my changes manually (required)
- [ ] I have written unit tests for my changes
- [x] I've removed console.logs, comment blocks, test data, and other hardcoded test strings
EOF
)"
```

Replace:
- `<TARGET-BRANCH>` with the target branch determined in Step 0 (either the parent branch or `main`)
- `[TICKET-NUMBER]` with the ticket number extracted from the JIRA URL (e.g., `V2S-123` from `https://seekout.atlassian.net/browse/V2S-123`)
- `JIRA-URL` with the actual JIRA URL provided by the user
- For multiple tickets, add each `[TICKET-NUMBER](JIRA-URL)` on a new line (remove the comment markers)
- Fill in description, testing details, and edge cases based on your analysis
- Mark the appropriate checkboxes for PR type and testing methods

### Important Notes

- Create PR against the target branch determined in Step 0 (parent branch if detected, otherwise `main`)
- Provide meaningful descriptions based on actual code changes
- If tests exist for the changed code, mention them in the testing section
