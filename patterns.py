"""
patterns.py — generates file-level summaries for pattern embedding.

Phase 1 job:  produce a summary string per file (imports + structure)
Phase 2 job:  embed those summaries, cluster them, store as patterns in ChromaDB

Why summaries instead of raw content?
  Raw files are too long and noisy to embed as a single vector.
  A short structured summary captures the essential shape of a file
  in a way the embedding model can compare meaningfully.
"""

from dataclasses import dataclass
from collections import defaultdict
from chunker import Chunk


@dataclass
class FileSummary:
    """
    A compact structural summary of one file.
    This is what gets embedded in Phase 2 to discover patterns.
    """
    file_path: str
    language: str
    imports: list[str]          # local relative imports
    component_names: list[str]  # names of components/functions defined here
    chunk_labels: list[str]     # e.g. ["component Dashboard", "hook useData"]
    summary_text: str           # the actual string we'll embed


# Only these languages are worth pattern-clustering
# JSON, HTML, Markdown etc. don't have meaningful structural patterns
PATTERN_ELIGIBLE_LANGUAGES = {
    "TypeScript (React)",
    "TypeScript",
    "JavaScript (React)",
    "JavaScript",
    "Python",
    "Vue",
    "Svelte",
    "Go",
    "Rust",
    "Java",
    "Kotlin",
    "C#",
    "Ruby",
    "PHP",
}


def _is_meaningful_summary(summary: 'FileSummary') -> bool:
    """
    Filter out files that aren't worth pattern clustering:
    - Non-code languages (JSON, HTML, Markdown)
    - Files with no imports AND no meaningful component names
    - Config/lock/test infrastructure files
    - Files in non-app directories
    """
    if summary.language not in PATTERN_ELIGIBLE_LANGUAGES:
        return False

    path_lower = summary.file_path.lower()
    parts = path_lower.replace("\\", "/").split("/")

    # Skip entire directories that are never app code
    SKIP_DIRS_IN_PATH = {
        "__mocks__", "__tests__", "__fixtures__",
        "evals", "eval", "scripts", "tools",
        "e2e", "cypress", "playwright",
        "storybook", ".storybook",
        "docs", "examples", "demo",
        "migrations", "seeds", "fixtures",
    }
    if any(part in SKIP_DIRS_IN_PATH for part in parts):
        return False

    # Skip test files by name convention
    TEST_PATTERNS = [
        ".test.", ".spec.", ".stories.",
        "-test.", "-spec.",
        "_test.", "_spec.",
    ]
    if any(p in path_lower for p in TEST_PATTERNS):
        return False

    # Skip config files by name
    CONFIG_NAMES = [
        "vite.config", "jest.config", "vitest.config",
        "tailwind.config", "tsconfig", "eslint",
        ".prettierrc", "babel.config", "webpack.config",
        "rollup.config", "postcss.config", "playwright.config",
        "next.config", "nuxt.config", "svelte.config",
        "mock-server", "setup-tests", "setuptests",
        ".env", "global.d.ts", "globals.d.ts",
    ]
    if any(name in path_lower for name in CONFIG_NAMES):
        return False

    # Skip files with no structural content worth comparing
    if not summary.imports and not summary.component_names:
        return False

    return True


def _build_summary_text(summary: 'FileSummary') -> str:
    """
    Build a short structured text that captures the file's shape.
    This is what the embedding model reads to understand the file's role.

    Example output:
      File: pages/DashboardPage.tsx (TypeScript React)
      Defines: component DashboardPage
      Imports: Header, Breadcrumbs, Button, StatCard
      Structure: page component using layout components
    """
    # Clean up import paths to just component names
    import_names = []
    for imp in summary.imports:
        name = imp.split("/")[-1]
        # Remove extensions
        for ext in [".tsx", ".ts", ".jsx", ".js"]:
            name = name.replace(ext, "")
        import_names.append(name)

    lines = [
        f"File: {summary.file_path} ({summary.language})",
        f"Defines: {', '.join(summary.chunk_labels) or 'unknown'}",
        f"Imports: {', '.join(import_names) or 'none'}",
    ]

    # Add a inferred role hint based on path
    path_lower = summary.file_path.lower()
    if any(x in path_lower for x in ["page", "screen", "view", "route"]):
        lines.append("Role: page/screen component")
    elif any(x in path_lower for x in ["layout", "template", "wrapper"]):
        lines.append("Role: layout component")
    elif any(x in path_lower for x in ["hook", "/hooks/"]):
        lines.append("Role: custom hook")
    elif any(x in path_lower for x in ["context", "provider", "store"]):
        lines.append("Role: state/context provider")
    elif any(x in path_lower for x in ["util", "helper", "lib"]):
        lines.append("Role: utility/helper")
    elif any(x in path_lower for x in ["component", "/ui/", "/common/"]):
        lines.append("Role: reusable UI component")

    return "\n".join(lines)


def build_file_summaries(chunks: list[Chunk]) -> list[FileSummary]:
    """
    Group chunks by file and produce one FileSummary per file.
    """
    # Group chunks by file
    file_chunks: dict[str, list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        file_chunks[chunk.file_path].append(chunk)

    summaries = []
    for file_path, file_chunk_list in file_chunks.items():
        first_chunk = file_chunk_list[0]

        imports = first_chunk.imports if hasattr(first_chunk, 'imports') else []

        component_names = [
            c.label for c in file_chunk_list
            if not c.label.startswith("<")
            and not c.label.startswith("{")
            and not c.label.startswith('"')
            and not c.label.startswith("import ")
            and not c.label.startswith("console")
            and not c.label.startswith("app.")
            and len(c.label) > 2
        ]

        summary = FileSummary(
            file_path=file_path,
            language=first_chunk.language,
            imports=imports,
            component_names=component_names,
            chunk_labels=component_names,
            summary_text="",
        )
        summary.summary_text = _build_summary_text(summary)

        # Only keep summaries that are worth pattern clustering
        if _is_meaningful_summary(summary):
            summaries.append(summary)

    return summaries


def print_summary_preview(summaries: list[FileSummary], max_show: int = 5):
    """Print a preview of generated file summaries."""
    print(f"\n[patterns] {len(summaries)} code files ready for pattern clustering")
    print("           (JSON, HTML, Markdown and config files excluded)")
    print("           (Patterns will be discovered automatically in Phase 2)")
    print()
    print("  Preview:")
    for s in summaries[:max_show]:
        print(f"\n  ── {s.file_path}")
        for line in s.summary_text.splitlines():
            print(f"     {line}")
    if len(summaries) > max_show:
        print(f"\n  ... and {len(summaries) - max_show} more files")