---
description: Index the current project codebase. Use --reset to re-index from scratch.
argument-hint: [--reset]
---

Step 1 — Check if venv exists:
Run: `test -f ${CLAUDE_PLUGIN_ROOT}/.venv/bin/python && echo "EXISTS" || echo "NOT_FOUND"`

Step 2 — If NOT_FOUND:

- Tell the user: "The Python environment isn't set up yet. I need to install dependencies (~30 seconds). Shall I proceed?"
- Wait for user approval
- If approved, execute the `/codebase-agent:setup` command and wait for it to complete

Step 3 — Call the MCP tool:
⚠️ Do NOT run any bash command, python command, or npx command for this step.
Use ONLY the `index_project` MCP tool from the codebase-agent server.

- If $ARGUMENTS contains "--reset", call index_project with reset=true
- Otherwise call index_project with reset=false
- Report the chunk count and pattern count from the tool response
