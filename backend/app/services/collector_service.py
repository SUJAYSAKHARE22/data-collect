"""
Collector service: orchestrates a loader + storage manager to run a full
collection job, independent of the FastAPI transport layer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.config.settings import Settings
from app.loaders.github.github_loader import GitHubLoader
from app.loaders.local.local_loader import LocalLoader
from app.loaders.website.website_loader import WebsiteLoader
from app.loaders.zip.zip_loader import ZipLoader
from app.models.job import Job
from app.schemas.responses import JobStatus
from app.services.job_service import JobRepository
from app.storage.storage_manager import StorageManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CollectorService:
    """High-level entry point used by routers to run collection jobs."""

    def __init__(self, settings: Settings, job_repository: JobRepository) -> None:
        self._settings = settings
        self._jobs = job_repository
        self._github_loader = GitHubLoader(
            default_token=settings.github_token,
            clone_timeout_seconds=settings.git_clone_timeout_seconds,
        )
        self._website_loader = WebsiteLoader(
            timeout_seconds=settings.crawler_timeout_seconds,
            user_agent=settings.crawler_user_agent,
            max_retries=settings.http_max_retries,
            retry_backoff_seconds=settings.http_retry_backoff_seconds,
        )
        self._zip_loader = ZipLoader()
        self._local_loader = LocalLoader()

    def storage_for(self, job_id: str) -> StorageManager:
        return StorageManager(self._settings.output_dir, job_id)

    async def run_github_job(
        self, job: Job, repo_url: str, branch: str | None, access_token: str | None
    ) -> None:
        await self._run(
            job,
            lambda storage: self._github_loader.collect(
                repo_url, storage.project_dir, branch=branch, access_token=access_token
            ),
        )

    async def run_website_job(
        self, job: Job, url: str, max_pages: int | None, max_depth: int | None
    ) -> None:
        await self._run(
            job,
            lambda storage: self._website_loader.collect(
                url,
                storage.project_dir,
                max_pages=max_pages or self._settings.crawler_max_pages,
                max_depth=max_depth if max_depth is not None else self._settings.crawler_max_depth,
            ),
        )

    async def run_zip_job(self, job: Job, zip_path: Path, original_filename: str | None) -> None:
        await self._run(
            job,
            lambda storage: self._zip_loader.collect(
                zip_path, storage.project_dir, original_filename=original_filename
            ),
        )

    async def run_local_job(self, job: Job, source_path: str) -> None:
        await self._run(
            job,
            lambda storage: self._local_loader.collect(source_path, storage.project_dir),
        )

    async def _run(
        self,
        job: Job,
        collect_fn: Callable[[StorageManager], tuple[dict, dict, list]],
    ) -> None:
        """Common execution wrapper: initializes storage, runs the loader, persists outputs."""
        storage = self.storage_for(job.job_id)
        try:
            storage.initialize()
            await self._jobs.update_status(job.job_id, JobStatus.RUNNING, output_dir=str(storage.job_dir))

            metadata, tree, files = collect_fn(storage)

            storage.write_json("metadata.json", metadata)
            storage.write_json("tree.json", tree)
            storage.write_json("files.json", files)

            await self._jobs.update_status(job.job_id, JobStatus.COMPLETED, output_dir=str(storage.job_dir))
            logger.info("Job %s completed successfully", job.job_id)
        except Exception as exc:  # noqa: BLE001 - convert any failure into job failure state
            logger.exception("Job %s failed: %s", job.job_id, exc)
            await self._jobs.update_status(job.job_id, JobStatus.FAILED, error=str(exc))
