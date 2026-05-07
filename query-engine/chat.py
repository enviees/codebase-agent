"""
chat.py — Phase 3 CLI: interactive chat with your codebase.

Usage:
  python chat.py                  ← starts interactive chat
  python chat.py --verbose        ← shows which files were retrieved
  python chat.py --question "..." ← single question, non-interactive

Examples:
  > how does authentication work?
  > what components does the dashboard use?
  > create a new settings page
  > where is the API base URL configured?
"""

import argparse
from dotenv import load_dotenv
load_dotenv()

from query import query
from vectordb import get_db, collection_stats


WELCOME = """
╔══════════════════════════════════════════════════════════╗
║           Codebase Agent — ready to answer               ║
╚══════════════════════════════════════════════════════════╝
  Type your question and press Enter.
  Commands:
    /verbose   toggle source file display on/off
    /clear     clear conversation history
    /stats     show index stats
    /exit      quit

"""

DIVIDER = "─" * 60


def print_sources(chunk_results, pattern_results):
    """Print the files used to generate the answer."""
    if not chunk_results and not pattern_results:
        return

    print(f"\n  {DIVIDER}")
    print("  Sources:")
    seen = set()
    for r in chunk_results:
        fp = r.metadata.get("file_path", "?")
        label = r.metadata.get("label", "")
        start = r.metadata.get("start_line", "?")
        end   = r.metadata.get("end_line", "?")
        key   = f"{fp}:{start}"
        if key not in seen:
            seen.add(key)
            print(f"    {r.similarity:.0%}  {fp}:{start}–{end}  [{label}]")

    if pattern_results:
        print("  Conventions used:")
        for r in pattern_results:
            name  = r.metadata.get("pattern_name", "?")
            files = r.metadata.get("all_files", "")
            print(f"    {r.similarity:.0%}  pattern: {name}")
            if files:
                first = files.split(",")[0].strip()
                print(f"         example: {first}")
    print(f"  {DIVIDER}\n")


def run_chat(verbose: bool = False):
    """Run the interactive chat loop."""
    print(WELCOME)

    # Check index exists
    db = get_db()
    stats = collection_stats(db)
    if stats["chunks"] == 0:
        print("  ⚠️  No chunks found in the index.")
        print(f"  DB path: {get_db().get_settings().persist_directory}")
        print()
        print("  This usually means one of:")
        print("  1. You haven't run Phase 2 yet")
        print("     → python index.py /path/to/your/repo")
        print()
        print("  2. You're running chat.py from a different directory")
        print("     than where index.py created the .chroma folder")
        print("     → cd into the codebase-agent folder and run again")
        print()
        return

    print(f"  Index: {stats['chunks']} chunks, {stats['patterns']} patterns\n")

    history = []
    show_sources = verbose

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nBye!")
            break

        if not user_input:
            continue

        # ── Commands ──────────────────────────────────────────────
        if user_input.lower() == "/exit":
            print("Bye!")
            break

        if user_input.lower() == "/clear":
            history = []
            print("  [chat] Conversation cleared.\n")
            continue

        if user_input.lower() == "/verbose":
            show_sources = not show_sources
            state = "on" if show_sources else "off"
            print(f"  [chat] Source display {state}.\n")
            continue

        if user_input.lower() == "/stats":
            stats = collection_stats(db)
            print(f"  Chunks  : {stats['chunks']}")
            print(f"  Patterns: {stats['patterns']}\n")
            continue

        # ── Query ──────────────────────────────────────────────────
        print(f"\nAgent: ", end="", flush=True)

        answer, chunks, patterns = query(
            question=user_input,
            history=history,
            verbose=False,  # verbose handled separately below
        )

        if show_sources:
            print_sources(chunks, patterns)

        # Keep last 6 turns in history (3 exchanges)
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": answer})
        history = history[-6:]

        print()


def run_single(question: str, verbose: bool = False):
    """Answer a single question and exit."""
    print(f"\nQuestion: {question}")
    print(f"{DIVIDER}")
    print("Answer: ", end="", flush=True)

    answer, chunks, patterns = query(question, verbose=verbose)

    print(f"\n{DIVIDER}")
    print_sources(chunks, patterns)


def main():
    parser = argparse.ArgumentParser(
        description="Codebase agent — Phase 3: chat with your codebase"
    )
    parser.add_argument(
        "--question", "-q",
        help="Ask a single question (non-interactive mode)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show which files were used to generate each answer",
    )
    args = parser.parse_args()

    if args.question:
        run_single(args.question, verbose=args.verbose)
    else:
        run_chat(verbose=args.verbose)


if __name__ == "__main__":
    main()