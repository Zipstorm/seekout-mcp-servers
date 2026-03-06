Save or resume a debugging session across context windows. Automatically detects whether to save (active session) or resume (fresh context).

## Save: Handoff Debug

Analyze the full conversation history and write a structured debug handoff document to `.agent/debug-handoff.md` (relative to the repo root).

The handoff must cover:

1. **Problem Statement** — What is being debugged and what are the symptoms?
2. **Root Cause Analysis** — What was discovered? What was confirmed vs hypothesized?
3. **Changes Made** — List every file modified with a brief description of each change
4. **Current State** — What's working now? What's still broken or untested?
5. **Next Steps** — What should be done next? Any open questions?
6. **Key Files** — List the most relevant files for this debugging session (use paths relative to repo root)
7. **Important Context** — Any gotchas, version pins, environment details, or non-obvious findings

After saving, tell the user: "Handoff saved. Run `/clear` then `/handoff-debug` to resume in a fresh context."
