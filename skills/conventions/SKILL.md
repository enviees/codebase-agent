---
name: conventions
description: Retrieve this project's coding conventions before creating new files. Use when the user wants to create a new page, component, hook, feature, or any new file to ensure it follows the project's existing patterns.
when_to_use: When user says "create", "add", "build", "make", "new page", "new component", "new hook", "new feature", "implement", "scaffold", "generate"
---

ALWAYS call `get_conventions` from codebase-agent BEFORE generating any new code.

Steps:

1. Call `get_conventions` with a description of what is being built
2. Read the returned patterns and example files carefully
3. Generate code that matches:
   - The same import style
   - The same component structure
   - The same naming conventions
   - The same file organization
   - The same TypeScript patterns

Never skip this step — generating code without checking conventions produces files that don't match the project style.

If no conventions are found, fall back to the patterns visible in nearby files.
