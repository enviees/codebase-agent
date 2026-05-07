---
name: search
description: Semantically search the codebase for relevant code. Use when the user wants to find how something is implemented, locate a specific component or function, or understand a part of the codebase.
when_to_use: When user says "find", "search", "where is", "show me", "locate", "how is X implemented", "which file handles"
---

Call the `search_code` MCP tool from codebase-agent with the user's query.

After getting results:

- Summarize what was found in plain English
- Highlight the most relevant file and function
- Reference exact file paths and line numbers
- If nothing relevant was found, suggest rephrasing or checking if the project is indexed

Do not just dump the raw results — synthesize them into a useful answer.
