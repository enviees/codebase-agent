"""
mcp_server.py — global MCP server for Claude Code.

Install once, works across all projects automatically.
Each project gets its own isolated vector DB at:
  <project_root>/.codebase-agent/chroma/

How it works:
  Claude Code launches this server with CWD = your project root.
  The server detects the project automatically from CWD.
  No per-project config needed.

Global install:
  claude mcp add-json codebase-agent --scope user '{
    "command": "python",
    "args": ["/absolute/path/to/mcp_server/mcp_server.py"]
  }'
"""

import sys
import os

# Add the codebase-agent root to path so we can import our modules
_SERVER_DIR  = os.path.dirname(os.path.abspath(__file__))
_AGENT_ROOT  = os.path.dirname(_SERVER_DIR)
sys.path.insert(0, _AGENT_ROOT)

from dotenv import load_dotenv

# Load .env from agent root (for API keys)
load_dotenv(os.path.join(_AGENT_ROOT, ".env"))

# ── Project detection ─────────────────────────────────────────────
# CWD when the server starts = the project Claude Code opened
# Store the DB inside the project so each project is isolated
PROJECT_ROOT = os.getcwd()
PROJECT_DB   = os.path.join(PROJECT_ROOT, ".codebase-agent", "chroma")

# Override the CHROMA_PATH so all our modules use the project DB
os.environ["CHROMA_PATH"] = PROJECT_DB

# ─────────────────────────────────────────────────────────────────
from mcp.server.fastmcp import FastMCP
from embedder import get_client, embed_texts
from vectordb import (
    get_db,
    get_chunks_collection,
    get_patterns_collection,
    search_chunks,
    search_patterns,
    collection_stats,
)

mcp = FastMCP("codebase-agent")

# Lazy-initialized shared clients
_clients = {}


def _get_clients():
    if not _clients:
        _clients["embed"]    = get_client()
        _clients["db"]       = get_db()
        _clients["chunks"]   = get_chunks_collection(_clients["db"])
        _clients["patterns"] = get_patterns_collection(_clients["db"])
    return _clients


def _embed(text: str) -> list[float]:
    return embed_texts([text], _get_clients()["embed"])[0]


def _is_indexed() -> bool:
    try:
        db = get_db()
        return collection_stats(db)["chunks"] > 0
    except Exception:
        return False


def _not_indexed_msg() -> str:
    return (
        f"This project has not been indexed yet.\n\n"
        f"Run this command from your project root to index it:\n\n"
        f"  python {_AGENT_ROOT}/clusterer/index.py {PROJECT_ROOT}\n\n"
        f"This only needs to be done once. Re-run with --reset after major changes."
    )


def _fmt_chunk(result, idx: int) -> str:
    m = result.metadata
    lang = m.get("language", "").lower().replace(" ", "").replace("(", "").replace(")", "")
    return (
        f"[{idx}] `{m.get('file_path')}` — {m.get('label')} "
        f"lines {m.get('start_line')}–{m.get('end_line')} "
        f"({result.similarity:.0%} match)\n"
        f"```{lang}\n{result.content}\n```"
    )


def _fmt_pattern(result) -> str:
    m = result.metadata
    files = m.get("all_files", "").split(",")
    preview = ", ".join(f.strip() for f in files[:3])
    if len(files) > 3:
        preview += f" +{len(files)-3} more"
    return (
        f"**{m.get('pattern_name')}** ({result.similarity:.0%} match)\n"
        f"  {m.get('description')}\n"
        f"  When to use: {m.get('when_to_use')}\n"
        f"  Example files: {preview}"
    )


# ── Tool 1 — search_code ─────────────────────────────────────────

@mcp.tool()
def search_code(query: str, n_results: int = 5) -> str:
    """
    Semantically search the codebase for relevant code.
    Use this to find how something is implemented, locate a component,
    or understand a specific part of the codebase before editing.

    Args:
        query:     what to search for (e.g. "user authentication",
                   "how API requests are made", "Button component props")
        n_results: number of results (default 5, max 10)
    """
    if not _is_indexed():
        return _not_indexed_msg()

    try:
        vector  = _embed(query)
        clients = _get_clients()
        results = search_chunks(clients["chunks"], vector, n_results=min(n_results, 10))
        results = [r for r in results if r.similarity >= 0.3]

        if not results:
            return f"No relevant code found for: '{query}'"

        parts = [f"**{len(results)} results for '{query}'** in `{PROJECT_ROOT}`\n"]
        for i, r in enumerate(results):
            parts.append(_fmt_chunk(r, i + 1))
        return "\n\n".join(parts)

    except Exception as e:
        return f"Search error: {e}"


# ── Tool 2 — get_conventions ─────────────────────────────────────

@mcp.tool()
def get_conventions(task: str) -> str:
    """
    Get this project's coding conventions before creating something new.
    Always call this BEFORE creating a new page, component, hook, or feature
    to ensure your output matches the project's existing patterns.

    Args:
        task: what you're about to build
              (e.g. "create a page", "add an API hook",
               "build a data table", "create a modal")
    """
    if not _is_indexed():
        return _not_indexed_msg()

    try:
        vector  = _embed(task)
        clients = _get_clients()

        # Get matching patterns
        patterns = search_patterns(clients["patterns"], vector, n_results=2)
        patterns = [p for p in patterns if p.similarity >= 0.3]

        # Get example code from the top matching pattern
        example_chunks = []
        if patterns:
            top = patterns[0]
            example_file = top.metadata.get("example_file", "")
            if example_file:
                ex_vector = _embed(example_file)
                example_chunks = search_chunks(
                    clients["chunks"], ex_vector, n_results=2
                )
                example_chunks = [r for r in example_chunks if r.similarity >= 0.4]

        if not patterns and not example_chunks:
            return f"No conventions found for '{task}'. The project may need re-indexing."

        parts = [f"**Project conventions for: '{task}'**\n"]

        if patterns:
            parts.append("## Patterns to follow:")
            for p in patterns:
                parts.append(_fmt_pattern(p))

        if example_chunks:
            parts.append("\n## Example implementation (follow this structure):")
            for i, c in enumerate(example_chunks[:2]):
                parts.append(_fmt_chunk(c, i + 1))

        parts.append(
            "\n> Follow the structure, imports, naming conventions, "
            "and file organization shown above."
        )

        return "\n\n".join(parts)

    except Exception as e:
        return f"Convention lookup error: {e}"


# ── Tool 3 — ask_codebase ────────────────────────────────────────

@mcp.tool()
def ask_codebase(question: str) -> str:
    """
    Ask any question about the codebase and get a grounded answer.
    Use for architecture questions, understanding flows, finding where
    things are configured, or any 'how does X work' question.

    Args:
        question: any question about this codebase
    """
    if not _is_indexed():
        return _not_indexed_msg()

    try:
        # Search both chunks and patterns
        vector  = _embed(question)
        clients = _get_clients()

        chunk_results   = search_chunks(clients["chunks"], vector, n_results=6)
        chunk_results   = [r for r in chunk_results if r.similarity >= 0.3]
        pattern_results = search_patterns(clients["patterns"], vector, n_results=2)
        pattern_results = [r for r in pattern_results if r.similarity >= 0.35]

        if not chunk_results:
            return f"No relevant code found for: '{question}'"

        # Build context for the LLM
        context = "\n\n".join(
            f"[{i+1}] {r.metadata.get('file_path')} — {r.metadata.get('label')}\n"
            f"```\n{r.content}\n```"
            for i, r in enumerate(chunk_results)
        )

        if pattern_results:
            context += "\n\n**Relevant patterns:**\n"
            context += "\n".join(_fmt_pattern(p) for p in pattern_results)

        # Call LLM for the answer
        from query import _get_answer_client, LLM_PROVIDER
        import json

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert on this codebase. Answer using only the "
                    "provided context. Reference specific files and line numbers. "
                    "Be concise and practical. If context is insufficient, say so."
                )
            },
            {
                "role": "user",
                "content": f"{context}\n\n---\n\nQuestion: {question}"
            }
        ]

        answer = ""
        if LLM_PROVIDER == "anthropic":
            from anthropic import Anthropic
            client = Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=messages[1:],
                system=messages[0]["content"],
            )
            answer = response.content[0].text
        else:
            client = _get_answer_client()
            response = client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=1500,
                messages=messages,
            )
            answer = response.choices[0].message.content

        # Append sources
        sources = []
        seen = set()
        for r in chunk_results:
            fp  = r.metadata.get("file_path", "?")
            key = f"{fp}:{r.metadata.get('start_line')}"
            if key not in seen:
                seen.add(key)
                sources.append(
                    f"- `{fp}` lines {r.metadata.get('start_line')}–"
                    f"{r.metadata.get('end_line')} [{r.metadata.get('label')}]"
                )

        return f"{answer}\n\n---\n**Sources:** \n" + "\n".join(sources)

    except Exception as e:
        return f"Query error: {e}"


# ── Tool 4 — index_project ───────────────────────────────────────

@mcp.tool()
def index_project(reset: bool = False) -> str:
    """
    Index the current project into the vector database.
    Run this once when setting up a new project, or with reset=True
    after significant code changes.

    Args:
        reset: if True, clears existing index and re-indexes from scratch
    """
    try:
        from reader import read_repo
        from chunker import chunk_all
        from patterns import build_file_summaries
        from indexer import index_chunks
        from clusterer import cluster_and_store_patterns

        # Create the project DB directory
        os.makedirs(PROJECT_DB, exist_ok=True)

        # Add .codebase-agent to project .gitignore if not already there
        gitignore_path = os.path.join(PROJECT_ROOT, ".gitignore")
        if os.path.exists(gitignore_path):
            content = open(gitignore_path).read()
            if ".codebase-agent" not in content:
                with open(gitignore_path, "a") as f:
                    f.write("\n# Codebase agent index\n.codebase-agent/\n")

        result_lines = [f"Indexing `{PROJECT_ROOT}`...\n"]

        files = read_repo(PROJECT_ROOT)
        if not files:
            return "No indexable files found in this project."

        chunks = chunk_all(files)
        summaries = build_file_summaries(chunks)

        chunk_count = index_chunks(chunks, PROJECT_ROOT, reset=reset)
        result_lines.append(f"✅ {chunk_count} chunks indexed")

        pattern_count = cluster_and_store_patterns(summaries)
        result_lines.append(f"✅ {pattern_count} patterns discovered")

        result_lines.append(f"\nDB stored at: `{PROJECT_DB}`")
        result_lines.append("Ready to answer questions about this codebase.")

        return "\n".join(result_lines)

    except Exception as e:
        return f"Indexing error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")