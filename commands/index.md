---
description: Index the current project codebase. Use --reset to re-index from scratch.
argument-hint: [--reset]
---

Use the `index_project` MCP tool from the codebase-agent server to index this project.

Do NOT use bash, npx, or any shell command.
Call the tool directly:

- If $ARGUMENTS contains "--reset", call index_project with reset=true
- Otherwise call index_project with reset=false

Report the chunk count and pattern count when done.
