---
name: patterns
description: Find and retrieve project patterns and conventions. Use when the user wants to know how the project structures a specific type of file, what patterns exist, or before creating anything new.
when_to_use: When user says "what patterns", "show me patterns", "how does this project structure", "what conventions", "before creating", "how do we build", "how are X structured in this project"
---

Call the `get_conventions` MCP tool from codebase-agent with a description of what the user is looking for.

After getting the tool response, write the full answer directly in the chat. Include:

- The pattern name and description
- When to use it
- Example files that follow this pattern
- Key structural details (imports, component structure, naming conventions)

Tell the user they can say "create a [type]" and Claude will automatically follow this pattern.
