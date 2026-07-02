"""
File-level utility helpers: size, extension, depth, last modified, language guessing.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from app.utils.hash_utils import compute_file_hash

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rs": "Rust",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".scala": "Scala",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".md": "Markdown",
    ".sql": "SQL",
    ".sh": "Shell",
}

DEPENDENCY_FILES: frozenset[str] = frozenset(
    {
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "package.json",
        "go.mod",
        "Gemfile",
        "pom.xml",
        "build.gradle",
        "composer.json",
        "Cargo.toml",
    }
)

ENTRY_FILE_CANDIDATES: frozenset[str] = frozenset(
    {
        "main.py",
        "app.py",
        "manage.py",
        "index.js",
        "server.js",
        "main.go",
        "Main.java",
        "index.html",
        "index.ts",
        "app.js",
    }
)


def guess_language(extension: str) -> str | None:
    """Guess a programming language from a file extension."""
    return LANGUAGE_BY_EXTENSION.get(extension.lower())


def is_dependency_file(file_name: str) -> bool:
    return file_name in DEPENDENCY_FILES


def is_entry_file(file_name: str) -> bool:
    return file_name in ENTRY_FILE_CANDIDATES


def build_file_record(file_path: Path, root: Path, compute_hash: bool = True) -> dict:
    """Build a metadata record describing a single file."""
    try:
        stat = file_path.stat()
        size = stat.st_size
        modified = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).isoformat()
    except OSError:
        size = 0
        modified = None

    relative_path = file_path.relative_to(root)
    depth = len(relative_path.parts) - 1

    return {
        "path": str(relative_path).replace("\\", "/"),
        "name": file_path.name,
        "extension": file_path.suffix,
        "size_bytes": size,
        "depth": depth,
        "last_modified": modified,
        "language": guess_language(file_path.suffix),
        "hash": compute_file_hash(file_path) if compute_hash else None,
        "is_dependency_file": is_dependency_file(file_path.name),
        "is_entry_file": is_entry_file(file_path.name),
    }
