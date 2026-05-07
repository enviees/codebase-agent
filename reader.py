"""
reader.py — walks a repo directory and returns readable code files.
Skips binaries, build artifacts, and noise folders automatically.
Respects .gitignore rules if present.
"""

import os
import fnmatch
from pathlib import Path
from dataclasses import dataclass, field

# Folders that are never useful to index
SKIP_DIRS = {
    ".git", ".svn", ".hg",
    "node_modules", ".venv", "venv", "env", "__pycache__",
    "dist", "build", ".next", ".nuxt", "out",
    ".cache", ".pytest_cache", ".mypy_cache",
    "coverage", ".nyc_output",
}

# File extensions we know how to handle
SUPPORTED_EXTENSIONS = {
    # Web
    ".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte",
    ".html", ".css", ".scss", ".sass",
    # Backend
    ".py", ".rb", ".php", ".java", ".kt", ".scala",
    ".go", ".rs", ".cs", ".cpp", ".c", ".h",
    # Config / data
    ".json", ".yaml", ".yml", ".toml", ".env.example",
    ".xml", ".graphql", ".sql",
    # Docs
    ".md", ".mdx", ".txt",
    # Shell
    ".sh", ".bash", ".zsh",
}

# Hard size limit — files above this are usually generated or huge
MAX_FILE_SIZE_BYTES = 200_000  # 200 KB


@dataclass
class CodeFile:
    """A single readable file from the repo."""
    path: str           # absolute path
    relative_path: str  # path relative to repo root (for display)
    extension: str      # e.g. ".py"
    language: str       # human-readable name e.g. "Python"
    content: str        # full file text
    size_bytes: int


EXTENSION_TO_LANGUAGE = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "JavaScript (React)", ".tsx": "TypeScript (React)",
    ".vue": "Vue", ".svelte": "Svelte",
    ".rb": "Ruby", ".php": "PHP", ".java": "Java",
    ".kt": "Kotlin", ".scala": "Scala", ".go": "Go",
    ".rs": "Rust", ".cs": "C#", ".cpp": "C++",
    ".c": "C", ".h": "C/C++ Header",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".sql": "SQL", ".md": "Markdown",
    ".sh": "Shell", ".bash": "Shell", ".graphql": "GraphQL",
}


def _parse_gitignore(repo_root: Path) -> list[str]:
    """
    Read .gitignore from the repo root and return a list of patterns.
    Filters out comments and empty lines.
    Supports nested .gitignore files too (common in monorepos).
    """
    patterns = []

    # Walk the repo and find ALL .gitignore files
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Don't descend into .git
        dirnames[:] = [d for d in dirnames if d != ".git"]

        if ".gitignore" in filenames:
            gitignore_path = Path(dirpath) / ".gitignore"
            try:
                content = gitignore_path.read_text(encoding="utf-8", errors="replace")
                rel_dir = Path(dirpath).relative_to(repo_root)

                for line in content.splitlines():
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Negation patterns (e.g. !important.log) — skip for now
                    if line.startswith("!"):
                        continue

                    # Prefix nested .gitignore patterns with their directory
                    if str(rel_dir) != ".":
                        line = str(rel_dir / line)

                    patterns.append(line)
            except (OSError, PermissionError):
                pass

    return patterns


def _is_gitignored(path: Path, repo_root: Path, patterns: list[str]) -> bool:
    """
    Check if a path matches any .gitignore pattern.
    Handles both file and directory patterns.
    """
    # Get the path relative to repo root
    try:
        rel_path = str(path.relative_to(repo_root))
    except ValueError:
        return False

    # Normalize to forward slashes
    rel_path = rel_path.replace("\\", "/")
    parts = rel_path.split("/")

    for pattern in patterns:
        pattern = pattern.strip("/")  # normalize

        # Match against full relative path
        if fnmatch.fnmatch(rel_path, pattern):
            return True

        # Match against just the filename
        if fnmatch.fnmatch(path.name, pattern):
            return True

        # Match against any parent directory segment
        for part in parts[:-1]:
            if fnmatch.fnmatch(part, pattern):
                return True

        # Handle directory patterns like "dist/" or "build/"
        if pattern.endswith("/"):
            dir_pattern = pattern.rstrip("/")
            for part in parts:
                if fnmatch.fnmatch(part, dir_pattern):
                    return True

    return False


def is_binary(filepath: str) -> bool:
    """Quick check: read first 8KB and look for null bytes."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except (OSError, PermissionError):
        return True


def read_repo(repo_path: str) -> list[CodeFile]:
    """
    Walk repo_path and return a list of CodeFile objects.
    Prints a summary when done.
    """
    repo_root = Path(repo_path).resolve()

    if not repo_root.exists():
        raise FileNotFoundError(f"Path not found: {repo_root}")
    if not repo_root.is_dir():
        raise NotADirectoryError(f"Not a directory: {repo_root}")

    # Load .gitignore patterns (from root and any nested .gitignore files)
    gitignore_patterns = _parse_gitignore(repo_root)
    if gitignore_patterns:
        print(f"  [gitignore] Loaded {len(gitignore_patterns)} exclusion rules")
    else:
        print(f"  [gitignore] No .gitignore found, using built-in exclusions only")

    files = []
    skipped_dirs = 0
    skipped_files = 0
    skipped_gitignore = 0

    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        original_count = len(dirnames)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS
            and not d.startswith(".")
            and not _is_gitignored(Path(dirpath) / d, repo_root, gitignore_patterns)
        ]
        skipped_dirs += original_count - len(dirnames)

        for filename in filenames:
            filepath = Path(dirpath) / filename

            # Check .gitignore before anything else
            if _is_gitignored(filepath, repo_root, gitignore_patterns):
                skipped_gitignore += 1
                continue
            ext = filepath.suffix.lower()

            # Only index supported extensions
            if ext not in SUPPORTED_EXTENSIONS:
                skipped_files += 1
                continue

            # Skip files that are too large
            try:
                size = filepath.stat().st_size
            except OSError:
                skipped_files += 1
                continue

            if size > MAX_FILE_SIZE_BYTES:
                print(f"  [skip] {filepath.name} — too large ({size // 1024} KB)")
                skipped_files += 1
                continue

            # Skip binary files
            if is_binary(str(filepath)):
                skipped_files += 1
                continue

            # Read content
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                skipped_files += 1
                continue

            # Skip empty files
            if not content.strip():
                skipped_files += 1
                continue

            relative_path = str(filepath.relative_to(repo_root))
            language = EXTENSION_TO_LANGUAGE.get(ext, "Unknown")

            files.append(CodeFile(
                path=str(filepath),
                relative_path=relative_path,
                extension=ext,
                language=language,
                content=content,
                size_bytes=size,
            ))

    print(f"\n[reader] Found {len(files)} files to index")
    print(f"         Skipped {skipped_dirs} directories, {skipped_files} files (built-in rules)")
    if skipped_gitignore:
        print(f"         Skipped {skipped_gitignore} files (matched .gitignore)")
    return files