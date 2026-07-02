"""
Loader for uploaded ZIP archives.

Includes protection against Zip Slip (path traversal) attacks.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from app.schemas.metadata import InputType, ProjectMetadata
from app.utils.file_utils import is_dependency_file, is_entry_file
from app.utils.logger import get_logger
from app.utils.tree_builder import build_tree

logger = get_logger(__name__)


class InvalidZipError(Exception):
    """Raised when a ZIP file is invalid or fails security validation."""


class ZipSlipError(InvalidZipError):
    """Raised when a ZIP entry would extract outside the target directory (Zip Slip)."""


class ZipLoader:
    """Safely extracts uploaded ZIP archives and builds project metadata."""

    def collect(
        self, zip_path: Path, project_dir: Path, original_filename: str | None = None
    ) -> tuple[dict, dict, list]:
        """
        Safely extract `zip_path` into `project_dir`, then build tree/files/metadata.
        """
        project_dir.mkdir(parents=True, exist_ok=True)
        self._safe_extract(zip_path, project_dir)

        tree, files, folders = build_tree(project_dir)
        entry_files = [f["path"] for f in files if is_entry_file(f["name"])]
        dependencies = [f["path"] for f in files if is_dependency_file(f["name"])]

        project_name = Path(original_filename).stem if original_filename else project_dir.name

        metadata = ProjectMetadata(
            input_type=InputType.ZIP,
            project_name=project_name,
            source=original_filename or str(zip_path),
            files=[f["path"] for f in files],
            folders=folders,
            entry_files=entry_files,
            dependencies=dependencies,
        ).model_dump()

        return metadata, tree, files

    @staticmethod
    def _safe_extract(zip_path: Path, target_dir: Path) -> None:
        """Extract a ZIP archive while preventing path traversal (Zip Slip)."""
        target_dir = target_dir.resolve()

        if not zipfile.is_zipfile(zip_path):
            raise InvalidZipError(f"File is not a valid ZIP archive: {zip_path}")

        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                member_path = target_dir / member.filename
                resolved = Path(member_path).resolve()

                if not str(resolved).startswith(str(target_dir)):
                    raise ZipSlipError(
                        f"Blocked unsafe ZIP entry attempting path traversal: {member.filename}"
                    )

            logger.info("Extracting %d entries from %s", len(archive.infolist()), zip_path)
            archive.extractall(target_dir)
