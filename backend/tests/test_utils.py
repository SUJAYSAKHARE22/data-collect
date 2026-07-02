"""
Unit tests for app.utils helpers.
"""
from __future__ import annotations

from pathlib import Path

from app.utils.file_utils import guess_language, is_dependency_file, is_entry_file
from app.utils.hash_utils import compute_file_hash
from app.utils.ignore_patterns import is_ignored_dir, is_ignored_file
from app.utils.tree_builder import build_tree


def test_guess_language() -> None:
    assert guess_language(".py") == "Python"
    assert guess_language(".ts") == "TypeScript"
    assert guess_language(".unknown_ext") is None


def test_is_dependency_file() -> None:
    assert is_dependency_file("requirements.txt") is True
    assert is_dependency_file("package.json") is True
    assert is_dependency_file("random.txt") is False


def test_is_entry_file() -> None:
    assert is_entry_file("main.py") is True
    assert is_entry_file("random.py") is False


def test_is_ignored_dir() -> None:
    assert is_ignored_dir("node_modules") is True
    assert is_ignored_dir("__pycache__") is True
    assert is_ignored_dir("src") is False


def test_is_ignored_file() -> None:
    assert is_ignored_file("module.pyc") is True
    assert is_ignored_file("module.py") is False


def test_compute_file_hash(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello world")
    digest = compute_file_hash(file_path)
    assert len(digest) == 64  # sha256 hex digest length
    # Hashing the same content twice should be deterministic
    assert digest == compute_file_hash(file_path)


def test_build_tree(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')")
    (tmp_path / "README.md").write_text("# Hello")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("ignored")

    tree, files, folders = build_tree(tmp_path)

    file_paths = {f["path"] for f in files}
    assert "src/main.py" in file_paths
    assert "README.md" in file_paths
    assert not any("node_modules" in p for p in file_paths)
    assert "src" in folders
    assert "node_modules" not in folders
