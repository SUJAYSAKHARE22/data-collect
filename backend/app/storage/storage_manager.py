"""
Storage manager: responsible for the on-disk layout of every collection job.

Layout per job:

output/{job_id}/
    project/          <- collected project content
    metadata.json
    tree.json
    files.json
    logs/
    downloads/
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger(__name__)


class StorageManager:
    """Manages the standard output directory layout for a single job."""

    def __init__(self, base_output_dir: Path, job_id: str) -> None:
        self.job_id = job_id
        self.job_dir = base_output_dir / job_id
        self.project_dir = self.job_dir / "project"
        self.logs_dir = self.job_dir / "logs"
        self.downloads_dir = self.job_dir / "downloads"

    def initialize(self) -> None:
        """Create the standard directory layout for this job."""
        for directory in (self.job_dir, self.project_dir, self.logs_dir, self.downloads_dir):
            directory.mkdir(parents=True, exist_ok=True)
        logger.info("Initialized storage layout at %s", self.job_dir)

    def write_json(self, filename: str, data: dict | list) -> Path:
        """Write a JSON file (metadata.json, tree.json, files.json) to the job directory."""
        path = self.job_dir / filename
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return path

    def read_json(self, filename: str) -> dict | list | None:
        path = self.job_dir / filename
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def cleanup(self) -> None:
        """Remove the entire job directory (used on failure or explicit cleanup)."""
        if self.job_dir.exists():
            shutil.rmtree(self.job_dir, ignore_errors=True)
            logger.info("Cleaned up storage for job %s", self.job_id)

    def zip_project(self) -> Path:
        """Create a zip archive of the collected project directory for download."""
        archive_base = self.downloads_dir / f"{self.job_id}_project"
        archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=self.project_dir)
        return Path(archive_path)
