---
description: Index the current project codebase. Use --reset to re-index from scratch.
argument-hint: [--reset]
---

Before indexing, check if the Python environment is ready:

1. Check if `${CLAUDE_PLUGIN_ROOT}/.venv/bin/python` exists using Bash
2. If it does NOT exist:
   - Tell the user: "The Python environment isn't set up yet. I need to install dependencies (~30 seconds). Shall I proceed?"
   - Wait for user approval
   - If approved, execute the `/codebase-agent:setup` command and wait for it to complete
3. Once the environment is ready (either it already existed or setup just completed):
   - Call the `index_project` MCP tool from codebase-agent directly (do NOT use bash or npx)
   - If $ARGUMENTS contains "--reset", pass reset=true to the tool
   - Report the chunk count and pattern count when done
