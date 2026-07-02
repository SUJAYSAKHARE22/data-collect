"""
In-memory job repository (thread-safe-ish via asyncio lock).
"""
from __future__ import annotations

import asyncio

from app.models.job import Job
from app.schemas.responses import JobStatus


class JobRepository:
    """Simple in-memory store for job records."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create(self, input_type: str, source: str) -> Job:
        async with self._lock:
            job = Job(job_id=Job.new_id(), input_type=input_type, source=source)
            self._jobs[job.job_id] = job
            return job

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_status(
        self, job_id: str, status: JobStatus, error: str | None = None, output_dir: str | None = None
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = status
            job.error = error
            if output_dir is not None:
                job.output_dir = output_dir
            job.touch()


_job_repository = JobRepository()


def get_job_repository() -> JobRepository:
    """FastAPI dependency provider for the singleton JobRepository."""
    return _job_repository
