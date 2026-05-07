#!/usr/bin/env python3
"""
hooks/check_index.py — UserPromptSubmit hook for codebase-agent plugin.

Fires before EVERY prompt. Checks if the current project is indexed.

Exit 0 → project is indexed, inject status silently into context
Exit 2 → project NOT indexed, block the prompt and tell Claude to enforce indexing
"""

import sys
import os
import json

# Read the hook input from stdin
try:
    hook_input = json.loads(sys.stdin.read())
except Exception:
    # If we can't read input, don't block — fail silently
    sys.exit(0)

# Get the project root from Claude Code's environment
project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

# The DB path the MCP server would create
db_path = os.path.join(project_dir, ".codebase-agent", "chroma")

# Check if the project has been indexed
# We consider it indexed if the chroma directory exists and has content
def is_indexed(db_path: str) -> bool:
    if not os.path.exists(db_path):
        return False
    # ChromaDB creates a chroma.sqlite3 file when indexed
    sqlite_path = os.path.join(db_path, "chroma.sqlite3")
    if not os.path.exists(sqlite_path):
        return False
    # Check it has actual content (> 100KB means real data)
    size = os.path.getsize(sqlite_path)
    return size > 100_000


def get_chunk_count(db_path: str) -> int:
    """Try to read chunk count from ChromaDB without importing chromadb."""
    try:
        import sqlite3
        sqlite_path = os.path.join(db_path, "chroma.sqlite3")
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        # ChromaDB stores embeddings in the embeddings table
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return -1


# ── Main logic ────────────────────────────────────────────────────

if not is_indexed(db_path):
    # Exit 0 = never block, just inject a gentle reminder into context
    # Claude will see this and add a note at the end of its response
    print(
        f"[codebase-agent: not indexed] "
        f"This project has not been indexed yet. "
        f"Answer the user's question as best you can, but at the very end of your response "
        f"add this note on its own line, formatted exactly like this:\n\n"
        f"> 💡 **Tip:** Your answers will be more accurate if you index this codebase first. "
        f"Just say **\"index this project\"** and I'll scan it for you — takes 1–2 minutes."
    )
    sys.exit(0)

else:
    # Exit 0 = allow, inject context silently
    chunk_count = get_chunk_count(db_path)
    count_str = f"{chunk_count} chunks" if chunk_count > 0 else "indexed"

    # This stdout is injected into Claude's context before it processes the prompt
    print(
        f"[codebase-agent] Project is indexed ({count_str}). "
        f"Use search_code, get_conventions, and ask_codebase tools "
        f"to ground answers in actual project code. "
        f"Always call get_conventions before creating new files."
    )
    sys.exit(0)