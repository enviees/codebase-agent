---
name: search
description: Semantically search the codebase for relevant code. Use when the user wants to find how something is implemented, locate a specific component or function, or understand a part of the codebase.
when_to_use: When user says "find", "search", "where is", "show me", "locate", "how is X implemented", "which file handles"
---

Call the `search_code` MCP tool from codebase-agent with the user's query.

After getting results, write the full answer directly in the chat — do not just show a recap line. Include:

- A plain English summary of what was found
- The most relevant file paths and line numbers
- Key code snippets if helpful
- If nothing found, suggest rephrasing or checking if the project is indexed
