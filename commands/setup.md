---
description: Set up codebase-agent dependencies. Run this once after installing the plugin.
---

Check if `${CLAUDE_PLUGIN_ROOT}/.venv/bin/python` exists using Bash.

If it already exists:

- Tell the user: "Dependencies are already installed. You're ready to go — say 'index this project' to get started."
- Stop here.

If it does NOT exist:

- Tell the user: "I need to install Python dependencies for codebase-agent (~30 seconds). Shall I proceed?"
- Wait for user approval
- If approved, run: `bash ${CLAUDE_PLUGIN_ROOT}/hooks/setup.sh` and show the full output
- When complete, tell the user: "Setup done! Say 'index this project' to get started."
