---
name: handoff-debug
description: Save or resume a debugging session across context windows. Automatically detects whether to save (active session) or resume (fresh context).
allowed-tools: Read, Write, Glob, Grep, Bash
---

# Debug Session Handoff

This skill has two modes — it auto-detects which one to use.

## Existing handoff contents (injected at invocation):

!`cat .agent/debug-handoff.md 2>/dev/null || type .agent\debug-handoff.md 2>nul || echo NO_EXISTING_HANDOFF`

## Instructions

**Determine the mode based on conversation history:**

- If this is a **fresh session** (the `/handoff-debug` invocation is the first or only user message, no prior debugging conversation): you are in **RESUME mode**.
- If there is **prior debugging conversation** in this session (the user has been working on something before invoking this): you are in **SAVE mode**.

### RESUME mode

The handoff contents above were injected from the saved file. Present them to the user as a structured summary, then say:

"Resuming from saved handoff. What would you like to tackle next?"

Read the key files listed in the handoff to rebuild context, then continue debugging from where it left off.

If the handoff shows NO_EXISTING_HANDOFF, tell the user: "No saved debug handoff found. Start debugging and run `/handoff-debug` when you want to save progress."

### SAVE mode

Analyze the full conversation history and write a structured handoff document to `.agent/debug-handoff.md` (relative to the repo root) with:

1. **Problem Statement** — What is being debugged and what are the symptoms?
2. **Root Cause Analysis** — What was discovered? What was confirmed vs hypothesized?
3. **Changes Made** — List every file modified with a brief description of each change
4. **Current State** — What's working now? What's still broken or untested?
5. **Next Steps** — What should be done next? Any open questions?
6. **Key Files** — List the most relevant files for this debugging session
7. **Important Context** — Any gotchas, version pins, environment details, or non-obvious findings

After saving, tell the user:

"Handoff saved. Run `/clear` then `/handoff-debug` to resume in a fresh context."
