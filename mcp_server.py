"""
mcp_server.py — global MCP server for Claude Code.
"""

import sys
import os

# ── Path setup — must happen before any local imports ────────────
# This file can be at any location. We find the agent root by
# looking for embedder.py as a landmark file.
_THIS_FILE   = os.path.abspath(__file__)
_THIS_DIR    = os.path.dirname(_THIS_FILE)

# Find agent root by looking for chunker.py as landmark
# (works whether mcp_server.py is at root or in a subfolder)
_CANDIDATES = [_THIS_DIR, os.path.dirname(_THIS_DIR)]
_AGENT_ROOT = None
for _candidate in _CANDIDATES:
    if os.path.exists(os.path.join(_candidate, "chunker.py")):
        _AGENT_ROOT = _candidate
        break

if _AGENT_ROOT is None:
    print(
        f"ERROR: Could not find chunker.py near {_THIS_FILE}\n"
        f"Checked: {_CANDIDATES}",
        file=sys.stderr
    )
    sys.exit(1)

# Add both root and clusterer/ subdir to path
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

_CLUSTERER_DIR = os.path.join(_AGENT_ROOT, "clusterer")
if os.path.exists(_CLUSTERER_DIR) and _CLUSTERER_DIR not in sys.path:
    sys.path.insert(0, _CLUSTERER_DIR)

# ── Load .env from agent root ────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(_AGENT_ROOT, ".env"))

# ── Project detection ─────────────────────────────────────────────
# CWD when Claude Code launches this = the project you opened
PROJECT_ROOT = os.getcwd()
PROJECT_DB   = os.path.join(PROJECT_ROOT, ".codebase-agent", "chroma")
os.environ["CHROMA_PATH"] = PROJECT_DB

# ── Now safe to import local modules ────────────────────────────
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
        return collection_stats(get_db())["chunks"] > 0
    except Exception:
        return False


def _not_indexed_msg() -> str:
    return (
        f"This project has not been indexed yet.\n\n"
        f"Run this from your project root:\n\n"
        f"  python {os.path.join(_AGENT_ROOT, 'clusterer', 'index.py')} {PROJECT_ROOT}\n\n"
        f"Or call the index_project tool directly."
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
        patterns = search_patterns(clients["patterns"], vector, n_results=2)
        patterns = [p for p in patterns if p.similarity >= 0.3]
        example_chunks = []
        if patterns:
            top = patterns[0]
            example_file = top.metadata.get("example_file", "")
            if example_file:
                ex_vector = _embed(example_file)
                example_chunks = search_chunks(clients["chunks"], ex_vector, n_results=2)
                example_chunks = [r for r in example_chunks if r.similarity >= 0.4]
        if not patterns and not example_chunks:
            return f"No conventions found for '{task}'."
        parts = [f"**Project conventions for: '{task}'**\n"]
        if patterns:
            parts.append("## Patterns to follow:")
            for p in patterns:
                parts.append(_fmt_pattern(p))
        if example_chunks:
            parts.append("\n## Example implementation (follow this structure):")
            for i, c in enumerate(example_chunks[:2]):
                parts.append(_fmt_chunk(c, i + 1))
        parts.append("\n> Match the structure, imports, naming, and file organization above.")
        return "\n\n".join(parts)
    except Exception as e:
        return f"Convention lookup error: {e}"


@mcp.tool()
def ask_codebase(question: str) -> str:
    """
    Ask any question about the codebase and get a grounded answer.
    Use for architecture questions, understanding flows, or any
    'how does X work' question.

    Args:
        question: any question about this codebase
    """
    if not _is_indexed():
        return _not_indexed_msg()
    try:
        vector  = _embed(question)
        clients = _get_clients()
        chunk_results   = search_chunks(clients["chunks"], vector, n_results=6)
        chunk_results   = [r for r in chunk_results if r.similarity >= 0.3]
        pattern_results = search_patterns(clients["patterns"], vector, n_results=2)
        pattern_results = [r for r in pattern_results if r.similarity >= 0.35]
        if not chunk_results:
            return f"No relevant code found for: '{question}'"
        context = "\n\n".join(
            f"[{i+1}] {r.metadata.get('file_path')} — {r.metadata.get('label')}\n"
            f"```\n{r.content}\n```"
            for i, r in enumerate(chunk_results)
        )
        if pattern_results:
            context += "\n\n**Relevant patterns:**\n"
            context += "\n".join(_fmt_pattern(p) for p in pattern_results)

        llm_provider = os.getenv("LLM_PROVIDER", "deepseek")
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert on this codebase. Answer using only the "
                    "provided context. Reference specific files and line numbers. "
                    "Be concise and practical."
                )
            },
            {"role": "user", "content": f"{context}\n\n---\n\nQuestion: {question}"}
        ]

        if llm_provider == "anthropic":
            from anthropic import Anthropic
            client = Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system=messages[0]["content"],
                messages=messages[1:],
            )
            answer = response.content[0].text
        else:
            from openai import OpenAI as OpenAIClient
            client = OpenAIClient(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com/v1",
            )
            response = client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=1500,
                messages=messages,
            )
            answer = response.choices[0].message.content

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
        return f"{answer}\n\n---\n**Sources:**\n" + "\n".join(sources)
    except Exception as e:
        return f"Query error: {e}"


@mcp.tool()
def project_status() -> str:
    """
    Check whether the current project has been indexed and is ready to use.
    Shows chunk count, pattern count, DB location, and last indexed time.
    """
    try:
        db    = get_db()
        stats = collection_stats(db)

        chunks   = stats["chunks"]
        patterns = stats["patterns"]

        # Check DB folder exists and get last modified time
        if os.path.exists(PROJECT_DB):
            last_modified = os.path.getmtime(PROJECT_DB)
            import datetime
            last_indexed = datetime.datetime.fromtimestamp(last_modified).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        else:
            last_indexed = "never"

        if chunks == 0:
            status = "❌ NOT INDEXED"
            action = (
                f"\nRun `index_project` to index this project, or:\n"
                f"  python {os.path.join(_AGENT_ROOT, 'clusterer', 'index.py')} {PROJECT_ROOT}"
            )
        else:
            status = "✅ READY"
            action = "\nAll tools are available for this project."

        return (
            f"Project: {PROJECT_ROOT}\n"
            f"Status:  {status}\n"
            f"Chunks:  {chunks}\n"
            f"Patterns: {patterns}\n"
            f"Last indexed: {last_indexed}\n"
            f"DB path: {PROJECT_DB}"
            f"{action}"
        )
    except Exception as e:
        return f"Status check error: {e}"



@mcp.tool()
def index_project(reset: bool = False) -> str:
    """
    Index the current project into the vector database.
    Run this once per project, or with reset=True after major code changes.

    Args:
        reset: if True, clears existing index and re-indexes from scratch
    """
    try:
        _query_dir = os.path.join(_AGENT_ROOT, "query-engine")
        if os.path.exists(_query_dir) and _query_dir not in sys.path:
            sys.path.insert(0, _query_dir)

        from reader import read_repo
        from chunker import chunk_all
        from patterns import build_file_summaries
        from indexer import index_chunks
        from clusterer import cluster_and_store_patterns

        os.makedirs(PROJECT_DB, exist_ok=True)

        # Auto-add .codebase-agent to project .gitignore
        gitignore_path = os.path.join(PROJECT_ROOT, ".gitignore")
        if os.path.exists(gitignore_path):
            content = open(gitignore_path).read()
            if ".codebase-agent" not in content:
                with open(gitignore_path, "a") as f:
                    f.write("\n# Codebase agent index\n.codebase-agent/\n")

        files = read_repo(PROJECT_ROOT)
        if not files:
            return "No indexable files found."

        chunks    = chunk_all(files)
        summaries = build_file_summaries(chunks)

        chunk_count   = index_chunks(chunks, PROJECT_ROOT, reset=reset)
        pattern_count = cluster_and_store_patterns(summaries)

        return (
            f"✅ Indexed `{PROJECT_ROOT}`\n"
            f"   {chunk_count} chunks\n"
            f"   {pattern_count} patterns\n"
            f"   DB: `{PROJECT_DB}`"
        )
    except Exception as e:
        return f"Indexing error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")