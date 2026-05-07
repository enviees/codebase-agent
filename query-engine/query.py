"""
query.py — Phase 3: the query engine.

For every question:
  1. Detect intent (explain vs create)
  2. Embed the question
  3. Search chunks     → relevant code snippets
  4. Search patterns   → relevant project conventions
  5. Build prompt      → send to LLM → stream answer

Two query modes:
  EXPLAIN  "how does X work?", "what does X do?"
           → retrieves chunks only, answers with code references

  CREATE   "create X", "add X", "write X"
           → retrieves chunks + best matching pattern as template
           → LLM follows your project's conventions
"""

import os
import re
import sys
from pathlib import Path

# Add project root and clusterer/ to path before any local imports
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "clusterer"))

from openai import OpenAI as OpenAIClient
from embedder import get_client, embed_texts
from vectordb import (
    get_db,
    get_chunks_collection,
    get_patterns_collection,
    search_chunks,
    search_patterns,
    SearchResult,
)

# How many chunks to retrieve per query
N_CHUNKS = 6

# How many patterns to retrieve for CREATE queries
N_PATTERNS = 2

# Minimum similarity score to include a result
MIN_SIMILARITY = 0.35

# LLM provider for answering — same env var as clusterer
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")


# ── Intent detection ──────────────────────────────────────────────

CREATE_KEYWORDS = [
    "create", "add", "build", "make", "generate", "write",
    "new page", "new component", "new hook", "new feature",
    "implement", "scaffold",
]

EXPLAIN_KEYWORDS = [
    "how", "what", "why", "where", "explain", "show",
    "does", "works", "understand", "find", "list",
]

def detect_intent(question: str) -> str:
    """Returns 'create' or 'explain'."""
    q = question.lower()
    if any(kw in q for kw in CREATE_KEYWORDS):
        return "create"
    return "explain"


# ── Prompt building ───────────────────────────────────────────────

def _format_chunk(result: SearchResult, idx: int) -> str:
    m = result.metadata
    return (
        f"[{idx}] {m.get('file_path', '?')} "
        f"({m.get('language', '?')}) — {m.get('label', '?')} "
        f"lines {m.get('start_line', '?')}–{m.get('end_line', '?')} "
        f"(similarity: {result.similarity:.0%})\n"
        f"```\n{result.content}\n```"
    )


def _format_pattern(result: SearchResult) -> str:
    m = result.metadata
    return (
        f"Pattern: {m.get('pattern_name', '?')}\n"
        f"Description: {m.get('description', '?')}\n"
        f"When to use: {m.get('when_to_use', '?')}\n"
        f"Example files: {m.get('all_files', '?')}\n"
    )


def _build_prompt(
    question: str,
    intent: str,
    chunk_results: list[SearchResult],
    pattern_results: list[SearchResult],
    history: list[dict],
) -> list[dict]:
    """Build the full message list to send to the LLM."""

    # System prompt
    system = (
        "You are an expert on this specific codebase. "
        "Answer questions using only the provided code context. "
        "Always reference specific file names and line numbers. "
        "If the context doesn't contain enough information, say so honestly. "
        "Be concise and practical."
    )

    if intent == "create":
        system += (
            "\n\nWhen asked to CREATE something, you MUST follow the project's "
            "existing patterns shown in the context. Match the exact import style, "
            "component structure, naming conventions, and file organization."
        )

    # Build context block
    context_parts = []

    if chunk_results:
        context_parts.append("## Relevant code from the codebase:\n")
        for i, r in enumerate(chunk_results):
            context_parts.append(_format_chunk(r, i + 1))

    if pattern_results and intent == "create":
        context_parts.append("\n## Project conventions to follow:\n")
        for r in pattern_results:
            context_parts.append(_format_pattern(r))

    context = "\n\n".join(context_parts)

    # Build messages — include conversation history for multi-turn
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": f"{context}\n\n---\n\nQuestion: {question}"
    })

    return messages


# ── LLM calling ───────────────────────────────────────────────────

def _get_answer_client():
    """Return OpenAI-compatible client for the answer LLM."""
    if LLM_PROVIDER == "anthropic":
        return None
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise EnvironmentError("[query] DEEPSEEK_API_KEY not found in .env")
    return OpenAIClient(api_key=api_key, base_url="https://api.deepseek.com")


def _stream_answer(messages: list[dict], client) -> str:
    """Stream the LLM answer to stdout. Returns the full response text."""
    full_response = ""

    if LLM_PROVIDER == "anthropic":
        from anthropic import Anthropic
        anthropic = Anthropic()
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]

        with anthropic.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system,
            messages=user_messages,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                full_response += text
    else:
        # DeepSeek streaming
        stream = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=2000,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            print(delta, end="", flush=True)
            full_response += delta

    print()  # newline after streaming ends
    return full_response


# ── Main query function ───────────────────────────────────────────

def query(
    question: str,
    history: list[dict] = None,
    verbose: bool = False,
) -> tuple[str, list[SearchResult], list[SearchResult]]:
    """
    Ask a question about the codebase.

    Args:
        question: the user's question
        history:  previous conversation turns for multi-turn chat
        verbose:  if True, print retrieval details

    Returns:
        (answer, chunk_results, pattern_results)
    """
    if history is None:
        history = []

    # 1. Detect intent
    intent = detect_intent(question)

    # 2. Embed the question
    embed_client = get_client()
    question_vector = embed_texts([question], embed_client)[0]

    # 3. Retrieve relevant chunks
    db = get_db()
    chunks_col  = get_chunks_collection(db)
    pattern_col = get_patterns_collection(db)

    chunk_results = search_chunks(chunks_col, question_vector, n_results=N_CHUNKS)
    chunk_results = [r for r in chunk_results if r.similarity >= MIN_SIMILARITY]

    # 4. Retrieve patterns (only for CREATE queries)
    pattern_results = []
    if intent == "create" and pattern_col.count() > 0:
        pattern_results = search_patterns(pattern_col, question_vector, n_results=N_PATTERNS)
        pattern_results = [r for r in pattern_results if r.similarity >= MIN_SIMILARITY]

    # 5. Show retrieval info if verbose
    if verbose:
        print(f"\n  intent : {intent}")
        print(f"  chunks : {len(chunk_results)} retrieved")
        for r in chunk_results:
            print(f"    {r.similarity:.0%}  {r.metadata.get('file_path')} — {r.metadata.get('label')}")
        if pattern_results:
            print(f"  patterns: {len(pattern_results)} retrieved")
            for r in pattern_results:
                print(f"    {r.similarity:.0%}  {r.metadata.get('pattern_name')}")
        print()

    # 6. Build prompt and get answer
    messages = _build_prompt(question, intent, chunk_results, pattern_results, history)
    answer_client = _get_answer_client()
    answer = _stream_answer(messages, answer_client)

    return answer, chunk_results, pattern_results