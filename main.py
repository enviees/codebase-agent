"""
main.py — Phase 1 CLI

Usage:
  python main.py <path-to-repo>

Reads the repo, chunks all files, and prints a preview so you
can verify everything looks right before Phase 2 (embedding).
"""

import sys
import argparse
from reader import read_repo
from chunker import chunk_all
from patterns import build_file_summaries, print_summary_preview


def print_chunk_preview(chunks, max_preview: int = 3):
    """Print a sample of chunks so you can visually verify the output."""
    print("\n" + "=" * 60)
    print("CHUNK PREVIEW (first few chunks)")
    print("=" * 60)

    for chunk in chunks[:max_preview]:
        print(f"\n  id       : {chunk.chunk_id}")
        print(f"  file     : {chunk.file_path}")
        print(f"  language : {chunk.language}")
        print(f"  lines    : {chunk.start_line}–{chunk.end_line}")
        print(f"  label    : {chunk.label}")
        print(f"  content  :")
        # Show first 6 lines of content, indented
        content_lines = chunk.content.splitlines()[:6]
        for line in content_lines:
            print(f"    {line}")
        if len(chunk.content.splitlines()) > 6:
            print(f"    ... ({len(chunk.content.splitlines())} lines total)")
        print()


def print_file_summary(files):
    """Print per-language breakdown of indexed files."""
    from collections import Counter
    lang_count = Counter(f.language for f in files)

    print("\n" + "=" * 60)
    print("FILES BY LANGUAGE")
    print("=" * 60)
    for lang, count in lang_count.most_common():
        print(f"  {lang:<30} {count} file{'s' if count > 1 else ''}")


def main():
    parser = argparse.ArgumentParser(
        description="Codebase agent — Phase 1: read and chunk a repo"
    )
    parser.add_argument(
        "repo_path",
        help="Path to the repository you want to index"
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=3,
        help="Number of chunks to preview (default: 3)"
    )
    args = parser.parse_args()

    print(f"\nIndexing: {args.repo_path}")
    print("-" * 60)

    # Phase 1a: read files
    files = read_repo(args.repo_path)

    if not files:
        print("\nNo indexable files found. Check the path and try again.")
        sys.exit(1)

    # Phase 1b: chunk files
    chunks = chunk_all(files)

    if not chunks:
        print("\nNo chunks produced. Files may be too small or unrecognized.")
        sys.exit(1)

    # Phase 1c: generate file summaries for pattern embedding (Phase 2)
    summaries = build_file_summaries(chunks)
    print_summary_preview(summaries)

    # Summary output
    print_file_summary(files)
    print_chunk_preview(chunks, max_preview=args.preview)

    print("=" * 60)
    print(f"Phase 1 complete.")
    print(f"  {len(files)} files read")
    print(f"  {len(chunks)} chunks ready for embedding (Phase 2)")
    print("=" * 60)


if __name__ == "__main__":
    main()