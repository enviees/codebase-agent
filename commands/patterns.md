---
description: Find patterns and conventions for a specific type of file or feature in this project
argument-hint: [what you want to build, e.g. "page", "modal", "api hook"]
---

Use the `get_conventions` MCP tool from the codebase-agent server with this query: $ARGUMENTS

Do NOT use bash, npx, or any shell command.
After getting the tool response, write the full answer directly in the chat. Include:

- Pattern name and what it's for
- When to use it
- Example files that follow this pattern
- The key structure to follow (imports, component shape, naming)

End with: "Say 'create a [type]' and I'll follow this pattern automatically."
