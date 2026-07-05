"""
In-memory analysis job repository. Mirrors app/services/job_service.py's
JobRepository pattern for the AI analysis jobs.
"""
from __future__ import annotations

import asyncio

from app.models.analysis import AnalysisJob
from app.schemas.responses import JobStatus


class AnalysisJobRepository:
    """Simple in-memory store for AI analysis job records."""

    def __init__(self) -> None:
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = asyncio.Lock()

    async def create(self, source_job_id: str, formats: list[str]) -> AnalysisJob:
        async with self._lock:
            job = AnalysisJob(
                analysis_id=AnalysisJob.new_id(),
                source_job_id=source_job_id,
                formats=formats,
            )
            self._jobs[job.analysis_id] = job
            return job

    async def get(self, analysis_id: str) -> AnalysisJob | None:
        async with self._lock:
            return self._jobs.get(analysis_id)

    async def update_status(
        self,
        analysis_id: str,
        status: JobStatus,
        error: str | None = None,
        confidence: float | None = None,
    ) -> None:
        async with self._lock:
            job = self._jobs.get(analysis_id)
            if job is None:
                return
            job.status = status
            job.error = error
            if confidence is not None:
                job.confidence = confidence
            job.touch()


_analysis_job_repository = AnalysisJobRepository()


def get_analysis_job_repository() -> AnalysisJobRepository:
    """FastAPI dependency provider for the singleton AnalysisJobRepository."""
    return _analysis_job_repository
