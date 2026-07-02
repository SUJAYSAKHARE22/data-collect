"""
Unit tests for the ZIP loader, including Zip Slip protection.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.loaders.zip.zip_loader import InvalidZipError, ZipLoader, ZipSlipError


def _make_zip(tmp_path: Path, entries: dict[str, str]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    zip_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return zip_path


def test_zip_loader_extracts_normal_archive(tmp_path: Path) -> None:
    zip_path = _make_zip(
        tmp_path / "src",
        {"main.py": "print('hi')", "sub/util.py": "def f(): pass"},
    )
    project_dir = tmp_path / "extracted"

    loader = ZipLoader()
    metadata, tree, files = loader.collect(zip_path, project_dir, original_filename="sample.zip")

    assert metadata["input_type"] == "zip"
    assert (project_dir / "main.py").exists()
    assert (project_dir / "sub" / "util.py").exists()
    assert len(files) == 2


def test_zip_loader_rejects_zip_slip(tmp_path: Path) -> None:
    malicious_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../evil.txt", "malicious content")

    project_dir = tmp_path / "extracted_evil"
    loader = ZipLoader()

    with pytest.raises(ZipSlipError):
        loader.collect(malicious_zip, project_dir, original_filename="evil.zip")


def test_zip_loader_rejects_invalid_zip(tmp_path: Path) -> None:
    fake_zip = tmp_path / "not_a_zip.zip"
    fake_zip.write_text("this is not a zip file")

    loader = ZipLoader()
    with pytest.raises(InvalidZipError):
        loader.collect(fake_zip, tmp_path / "out", original_filename="not_a_zip.zip")
