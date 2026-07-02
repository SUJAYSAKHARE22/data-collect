"""
Loader for local project directories already present on disk.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from app.schemas.metadata import InputType, ProjectMetadata
from app.utils.file_utils import is_dependency_file, is_entry_file
from app.utils.ignore_patterns import is_ignored_dir, is_ignored_file
from app.utils.logger import get_logger
from app.utils.tree_builder import build_tree

logger = get_logger(__name__)


class LocalPathNotFoundError(Exception):
    """Raised when the provided local path does not exist or is not a directory."""


class LocalLoader:
    """Collects data from a local project directory."""

    def collect(self, source_path: str, project_dir: Path) -> tuple[dict, dict, list]:
        """
        Copy the local project into `project_dir`, then build tree/files/metadata.

        Returns (metadata_dict, tree_dict, files_list).
        """
        src = Path(source_path).expanduser().resolve()
        if not src.exists() or not src.is_dir():
            raise LocalPathNotFoundError(f"Local path does not exist or is not a directory: {src}")

        logger.info("Copying local project from %s to %s", src, project_dir)
        self._copy_tree(src, project_dir)

        tree, files, folders = build_tree(project_dir)

        entry_files = [f["path"] for f in files if is_entry_file(f["name"])]
        dependencies = [f["path"] for f in files if is_dependency_file(f["name"])]

        metadata = ProjectMetadata(
            input_type=InputType.LOCAL,
            project_name=src.name,
            source=str(src),
            files=[f["path"] for f in files],
            folders=folders,
            entry_files=entry_files,
            dependencies=dependencies,
            extra={"original_path": str(src)},
        ).model_dump()

        return metadata, tree, files

    @staticmethod
    def _copy_tree(src: Path, dst: Path) -> None:
        def ignore(dir_path: str, names: list[str]) -> list[str]:
            ignored = []
            for name in names:
                full = Path(dir_path) / name
                if full.is_dir() and is_ignored_dir(name):
                    ignored.append(name)
                elif full.is_file() and is_ignored_file(name):
                    ignored.append(name)
            return ignored

        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=ignore)
