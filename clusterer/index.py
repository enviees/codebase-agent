"""
index.py — Phase 2 CLI entry point.

Runs the full Phase 2 pipeline:
  2a. Embed all chunks → store in ChromaDB "chunks" collection
  2b. Embed file summaries → cluster → name → store in "patterns" collection

Usage:
  python index.py /path/to/repo
  python index.py /path/to/repo --reset        # re-index from scratch
  python index.py /path/to/repo --skip-patterns # skip pattern clustering
"""

import sys
import argparse
from pathlib import Path

# Add project root to path so sibling modules (reader, chunker, etc.) are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

# Load .env before anything else so all modules see the env vars
load_dotenv()

from reader import read_repo
from chunker import chunk_all
from patterns import build_file_summaries
from indexer import index_chunks
from clusterer import cluster_and_store_patterns
from vectordb import get_db, collection_stats


def main():
    parser = argparse.ArgumentParser(
        description="Codebase agent — Phase 2: embed and index"
    )
    parser.add_argument("repo_path", help="Path to the repository to index")
    parser.add_argument(
        "--reset", action="store_true",
        help="Clear existing index and re-embed from scratch"
    )
    parser.add_argument(
        "--skip-patterns", action="store_true",
        help="Skip pattern clustering (Phase 2b)"
    )
    args = parser.parse_args()

    print(f"\nIndexing: {args.repo_path}")
    print("=" * 60)

    # ── Phase 1 (re-run to get fresh chunks + summaries) ──────────
    print("\n[Phase 1] Reading and chunking codebase...")
    files = read_repo(args.repo_path)
    if not files:
        print("No files found.")
        sys.exit(1)

    chunks = chunk_all(files)
    if not chunks:
        print("No chunks produced.")
        sys.exit(1)

    summaries = build_file_summaries(chunks)

    # ── Phase 2a — Embed chunks ────────────────────────────────────
    print("\n[Phase 2a] Embedding chunks...")
    print("-" * 60)
    chunk_count = index_chunks(chunks, args.repo_path, reset=args.reset)

    # ── Phase 2b — Cluster patterns ───────────────────────────────
    if not args.skip_patterns:
        print("\n[Phase 2b] Discovering patterns...")
        print("-" * 60)
        pattern_count = cluster_and_store_patterns(summaries)
    else:
        pattern_count = 0
        print("\n[Phase 2b] Skipped (--skip-patterns)")

    # ── Final summary ──────────────────────────────────────────────
    db = get_db()
    stats = collection_stats(db)

    print("\n" + "=" * 60)
    print("Phase 2 complete!")
    print(f"  Chunks indexed   : {stats['chunks']}")
    print(f"  Patterns found   : {stats['patterns']}")
    print(f"  DB location      : ./.chroma")
    print()
    print("Ready for Phase 3 — run: python query.py")
    print("=" * 60)


if __name__ == "__main__":
    main()