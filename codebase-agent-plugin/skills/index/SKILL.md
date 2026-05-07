---
name: index
description: Index the current project codebase into the vector database. Use when the user wants to index their project, set up the codebase agent, or re-index after major changes.
when_to_use: When user says "index this project", "index the codebase", "set up the agent", "re-index", "update the index", "index my code"
---

Call the `index_project` MCP tool from codebase-agent.

Before calling:

- Tell the user indexing is starting and may take 1-2 minutes for large codebases
- Mention it will create a `.codebase-agent/` folder inside their project (gitignored automatically)

After the tool returns:

- Report how many chunks and patterns were indexed
- Confirm the agent is ready to use
- Suggest a first question they can ask, like "how does authentication work?"

If the user wants to re-index from scratch, pass `reset=true` to the tool.
