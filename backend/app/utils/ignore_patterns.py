"""
Common ignore patterns used when scanning/copying project directories.
"""
from __future__ import annotations

DEFAULT_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "env",
        "dist",
        "build",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".idea",
        ".vscode",
        "target",
        ".next",
        ".nuxt",
        "coverage",
        ".tox",
        "egg-info",
    }
)

DEFAULT_IGNORED_FILE_SUFFIXES: frozenset[str] = frozenset(
    {".pyc", ".pyo", ".DS_Store"}
)


def is_ignored_dir(dir_name: str) -> bool:
    """Return True if a directory name should be skipped during traversal."""
    return dir_name in DEFAULT_IGNORED_DIRS or dir_name.endswith(".egg-info")


def is_ignored_file(file_name: str) -> bool:
    """Return True if a file should be skipped during traversal."""
    return any(file_name.endswith(suffix) for suffix in DEFAULT_IGNORED_FILE_SUFFIXES)
