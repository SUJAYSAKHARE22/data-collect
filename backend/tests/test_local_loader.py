"""
Unit tests for the local directory loader.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.loaders.local.local_loader import LocalLoader, LocalPathNotFoundError


def test_local_loader_collects_project(tmp_path: Path) -> None:
    src = tmp_path / "my_project"
    (src / "app").mkdir(parents=True)
    (src / "app" / "main.py").write_text("print('hello')")
    (src / "requirements.txt").write_text("fastapi")
    (src / "venv").mkdir()
    (src / "venv" / "ignored.py").write_text("ignored")

    dest = tmp_path / "collected"
    loader = LocalLoader()
    metadata, tree, files = loader.collect(str(src), dest)

    assert metadata["input_type"] == "local"
    assert metadata["project_name"] == "my_project"
    file_paths = {f["path"] for f in files}
    assert "app/main.py" in file_paths
    assert "requirements.txt" in file_paths
    assert not any("venv" in p for p in file_paths)
    assert "requirements.txt" in metadata["dependencies"]


def test_local_loader_raises_for_missing_path(tmp_path: Path) -> None:
    loader = LocalLoader()
    with pytest.raises(LocalPathNotFoundError):
        loader.collect(str(tmp_path / "does_not_exist"), tmp_path / "out")
