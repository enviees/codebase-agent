"""
chunker.py — splits CodeFile objects into smaller labeled chunks.

Strategy (in order of preference):
  1. Structural split — detect function/class boundaries per language
  2. Fixed-size split  — fall back to N-line windows with overlap

Each chunk carries full metadata so the agent always knows where it came from.
"""

import re
from dataclasses import dataclass
from reader import CodeFile

# How many lines per chunk in fixed-size mode
CHUNK_SIZE_LINES = 60

# How many lines to overlap between consecutive chunks
# (so a function split across a boundary isn't lost)
OVERLAP_LINES = 10

# Minimum lines a chunk must have to be worth storing
MIN_CHUNK_LINES = 5


@dataclass
class Chunk:
    """One indexable piece of a source file."""
    chunk_id: str       # unique id, e.g. "src/auth.py::chunk_3"
    file_path: str      # relative path for display
    language: str
    start_line: int     # 1-indexed
    end_line: int
    content: str        # the actual code text
    label: str          # short human label, e.g. "function login"
    imports: list[str]  # local relative imports this file depends on


# ── Language-specific structural patterns ────────────────────────────────────
# Each pattern matches the START of a meaningful block (function, class, etc.)
# We use these to find natural split points.

STRUCTURAL_PATTERNS: dict[str, list[str]] = {
    "Python": [
        r"^(async\s+)?def\s+\w+",       # functions
        r"^class\s+\w+",                 # classes
    ],
    "JavaScript": [
        r"^(export\s+)?(default\s+)?(async\s+)?function\s+\w+",
        r"^(export\s+)?(const|let|var)\s+\w+\s*=\s*(async\s+)?\(",
        r"^(export\s+)?class\s+\w+",
    ],
    "TypeScript": [
        r"^(export\s+)?(default\s+)?(async\s+)?function\s+\w+",
        r"^(export\s+)?(const|let|var)\s+\w+\s*=\s*(async\s+)?\(",
        r"^(export\s+)?(abstract\s+)?class\s+\w+",
        r"^(export\s+)?(interface|type|enum)\s+\w+",
    ],
    "JavaScript (React)": [
        # Standard named function components
        r"^(export\s+)?(default\s+)?(async\s+)?function\s+[A-Z]\w*\s*[\(\{<]",
        # Arrow function components: const Button = ...  (must start at col 0, capitalized)
        r"^(export\s+)?const\s+[A-Z]\w*\s*[=:]",
        # Custom hooks
        r"^(export\s+)?const\s+use[A-Z]\w*\s*=",
        # Class components
        r"^(export\s+)?class\s+[A-Z]\w+",
        # Default export
        r"^export\s+default\s+function\s+[A-Z]\w*",
    ],
    "TypeScript (React)": [
        # Standard named function components
        r"^(export\s+)?(default\s+)?(async\s+)?function\s+[A-Z]\w*\s*[\(\{<]",
        # Arrow function components (capitalized, starts at col 0)
        r"^(export\s+)?const\s+[A-Z]\w*\s*[=:]",
        # Custom hooks
        r"^(export\s+)?const\s+use[A-Z]\w*\s*=",
        # Class components
        r"^(export\s+)?(abstract\s+)?class\s+[A-Z]\w+",
        # Type definitions, interfaces, enums
        r"^(export\s+)?(interface|type|enum)\s+\w+",
        # Default export
        r"^export\s+default\s+function\s+[A-Z]\w*",
        # Utility functions (lowercase) at top level
        r"^(export\s+)?const\s+[a-z]\w*\s*=\s*(async\s+)?\(",
    ],
    "Go": [
        r"^func\s+(\(\w+\s+\*?\w+\)\s+)?\w+",   # func or method
        r"^type\s+\w+\s+(struct|interface)",
    ],
    "Rust": [
        r"^(pub\s+)?(async\s+)?fn\s+\w+",
        r"^(pub\s+)?(struct|enum|trait|impl)\s+\w+",
    ],
    "Java": [
        r"^\s*(public|private|protected).*?(class|interface|enum)\s+\w+",
        r"^\s*(public|private|protected|static).*\w+\s*\(.*\)\s*\{",
    ],
    "C#": [
        r"^\s*(public|private|protected|internal).*?(class|interface|struct|enum)\s+\w+",
        r"^\s*(public|private|protected|static|async).*\w+\s*\(.*\)\s*",
    ],
    "Ruby": [
        r"^(def\s+\w+|class\s+\w+|module\s+\w+)",
    ],
    "PHP": [
        r"^(public|private|protected|static)?\s*function\s+\w+",
        r"^class\s+\w+",
    ],
    "Kotlin": [
        r"^(fun\s+\w+|(open\s+|data\s+|abstract\s+)?class\s+\w+)",
    ],
    "C++": [
        r"^\w[\w\s\*\&]+\s+\w+\s*\(",  # function definitions
        r"^(class|struct|namespace)\s+\w+",
    ],
}


def _extract_label(line: str, language: str) -> str:
    """
    Pull a short human-readable label from the first line of a chunk.
    e.g. "def login(user, pass):" → "function login"
    """
    line = line.strip()

    # React components (capitalized const) and hooks (use*)
    m = re.match(r"(?:export\s+)?(?:const|let)\s+(use[A-Z]\w*)\s*=", line)
    if m:
        return f"hook {m.group(1)}"

    m = re.match(r"(?:export\s+)?(?:const|let)\s+([A-Z]\w*)\s*[=:]", line)
    if m:
        return f"component {m.group(1)}"

    # Default export component
    m = re.match(r"export\s+default\s+(?:function\s+)?([A-Z]\w*)", line)
    if m:
        return f"component {m.group(1)} (default)"

    # Python
    m = re.match(r"(async\s+)?def\s+(\w+)", line)
    if m:
        return f"function {m.group(2)}"

    m = re.match(r"class\s+(\w+)", line)
    if m:
        return f"class {m.group(1)}"

    # JS/TS functions
    m = re.match(r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)", line)
    if m:
        return f"function {m.group(1)}"

    m = re.match(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=", line)
    if m:
        return f"const {m.group(1)}"

    # interfaces / types
    m = re.match(r"(?:export\s+)?(?:interface|type|enum)\s+(\w+)", line)
    if m:
        return f"{m.group(0).split()[0]} {m.group(1)}"

    # Go
    m = re.match(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)", line)
    if m:
        return f"func {m.group(1)}"

    # Rust
    m = re.match(r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", line)
    if m:
        return f"fn {m.group(1)}"

    # Java / C#
    m = re.match(r".*?(class|interface|struct|enum)\s+(\w+)", line)
    if m:
        return f"{m.group(1)} {m.group(2)}"

    # Ruby
    m = re.match(r"def\s+(\w+)", line)
    if m:
        return f"method {m.group(1)}"

    # Default fallback
    return line[:50] if len(line) > 50 else line


def _split_structural(file: CodeFile) -> list[tuple[int, int]]:
    """
    Return (start, end) line index pairs using language-specific patterns.
    Lines are 0-indexed internally; converted to 1-indexed in the Chunk.
    """
    patterns = STRUCTURAL_PATTERNS.get(file.language, [])
    if not patterns:
        return []

    compiled = [re.compile(p) for p in patterns]
    lines = file.content.splitlines()

    # Find all lines that start a new block
    split_points = []
    for i, line in enumerate(lines):
        for pat in compiled:
            if pat.match(line):
                split_points.append(i)
                break

    if not split_points:
        return []  # no structure found at all, fall back to fixed-size

    # Build ranges: each block runs from its split point to just before the next
    ranges = []
    for i, start in enumerate(split_points):
        end = split_points[i + 1] - 1 if i + 1 < len(split_points) else len(lines) - 1
        ranges.append((start, end))

    return ranges


def _split_fixed(file: CodeFile) -> list[tuple[int, int]]:
    """
    Fall back: fixed-size sliding window with overlap.
    For data/config/doc formats, skip overlap to avoid near-duplicate chunks.
    """
    lines = file.content.splitlines()
    total = len(lines)
    ranges = []

    # These formats have no code structure — overlap just creates duplicates
    NO_OVERLAP_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".md", ".mdx", ".txt", ".html", ".css", ".scss", ".sass"}
    use_overlap = file.extension not in NO_OVERLAP_EXTENSIONS

    start = 0
    while start < total:
        end = min(start + CHUNK_SIZE_LINES - 1, total - 1)
        ranges.append((start, end))
        if use_overlap:
            next_start = end + 1 - OVERLAP_LINES
        else:
            next_start = end + 1  # no overlap
        if next_start <= start:   # safety: always advance
            next_start = start + 1
        start = next_start

    return ranges


def _parse_imports(content: str, language: str) -> list[str]:
    """
    Extract local import paths from a file.
    Only keeps relative imports (./  or  ../) — ignores node_modules/stdlib.
    """
    imports = []

    if language in ("TypeScript (React)", "TypeScript", "JavaScript (React)", "JavaScript"):
        # matches: import ... from './path' or '../path'
        pattern = re.compile(r'from\s+["\'](\./|\.\./)[^"\']+["\']')
        for match in pattern.finditer(content):
            raw = match.group(0)
            # extract just the path
            path_match = re.search(r'["\']([^"\']+)["\']', raw)
            if path_match:
                imports.append(path_match.group(1))

    elif language == "Python":
        # matches: from .module import X  or  from ..module import X
        pattern = re.compile(r'from\s+(\.+[\w.]*)\s+import')
        for match in pattern.finditer(content):
            imports.append(match.group(1))

    return list(set(imports))  # deduplicate


def chunk_file(file: CodeFile) -> list[Chunk]:
    """
    Chunk a single CodeFile. Returns a list of Chunk objects.
    """
    lines = file.content.splitlines()

    # Parse imports once per file — shared across all chunks in that file
    file_imports = _parse_imports(file.content, file.language)

    # Try structural split first
    ranges = _split_structural(file)

    # Fall back to fixed-size if structural didn't find enough blocks
    if not ranges:
        ranges = _split_fixed(file)

    chunks = []
    for idx, (start, end) in enumerate(ranges):
        chunk_lines = lines[start : end + 1]

        # Skip chunks that are too short
        if len(chunk_lines) < MIN_CHUNK_LINES:
            continue

        content = "\n".join(chunk_lines)
        first_line = chunk_lines[0].strip()
        label = _extract_label(first_line, file.language)

        chunk_id = f"{file.relative_path}::chunk_{idx}"

        chunks.append(Chunk(
            chunk_id=chunk_id,
            file_path=file.relative_path,
            language=file.language,
            start_line=start + 1,     # convert to 1-indexed
            end_line=end + 1,
            content=content,
            label=label,
            imports=file_imports,
        ))

    return chunks


def chunk_all(files: list[CodeFile]) -> list[Chunk]:
    """
    Chunk every file in the list. Prints a summary when done.
    """
    all_chunks: list[Chunk] = []

    for file in files:
        file_chunks = chunk_file(file)
        all_chunks.extend(file_chunks)

    # Stats
    structural_count = sum(
        1 for f in files if _split_structural(f)
    )
    fixed_count = len(files) - structural_count

    print(f"\n[chunker] {len(all_chunks)} chunks from {len(files)} files")
    print(f"          {structural_count} files chunked structurally")
    print(f"          {fixed_count} files chunked by fixed size")

    return all_chunks