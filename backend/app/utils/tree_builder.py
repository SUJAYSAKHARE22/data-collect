"""
Directory tree + file/folder inventory builder.

Walks a directory on disk (already collected locally) and produces:
- a nested tree structure (tree.json)
- a flat list of file records (files.json)
- a flat list of folder paths (folders)
"""
from __future__ import annotations

from pathlib import Path

from app.utils.file_utils import build_file_record
from app.utils.ignore_patterns import is_ignored_dir, is_ignored_file
from app.utils.logger import get_logger

logger = get_logger(__name__)


def build_tree(
    root: Path,
    compute_hash: bool = True,
    max_files: int | None = None,
) -> tuple[dict, list[dict], list[str]]:
    """
    Walk `root` recursively and build:
      - tree: nested dict representing the directory structure
      - files: flat list of file metadata records
      - folders: flat list of relative folder paths
    """
    files: list[dict] = []
    folders: list[str] = []

    def walk(current: Path) -> dict:
        node: dict = {
            "name": current.name or str(current),
            "type": "directory",
            "children": [],
        }
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError as exc:
            logger.warning("Cannot read directory %s: %s", current, exc)
            return node

        for entry in entries:
            if entry.is_dir():
                if is_ignored_dir(entry.name):
                    continue
                rel = str(entry.relative_to(root)).replace("\\", "/")
                folders.append(rel)
                node["children"].append(walk(entry))
            elif entry.is_file():
                if is_ignored_file(entry.name):
                    continue
                if max_files is not None and len(files) >= max_files:
                    continue
                record = build_file_record(entry, root, compute_hash=compute_hash)
                files.append(record)
                node["children"].append(
                    {"name": entry.name, "type": "file", "path": record["path"]}
                )
        return node

    tree = walk(root)
    return tree, files, folders
