---
name: status
description: Check if the current project has been indexed and is ready to use. Use when the user asks about project status, whether the codebase is indexed, how many chunks are stored, or wants to verify the agent is ready.
when_to_use: When user says "check status", "is this indexed", "project status", "is the agent ready", "check if indexed"
---

Call the `project_status` MCP tool from codebase-agent and report back to the user with:

- Whether the project is indexed (✅ READY or ❌ NOT INDEXED)
- Number of chunks and patterns
- When it was last indexed
- What to do next (index if not ready, or start asking questions if ready)

Be concise. If not indexed, tell them to say "index this project" to get started.
