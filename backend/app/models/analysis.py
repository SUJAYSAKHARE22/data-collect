"""
In-memory analysis job record used to track AI analysis job progress.
Mirrors app/models/job.py's pattern for the data-collection jobs.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from app.schemas.responses import JobStatus


@dataclass
class AnalysisJob:
    analysis_id: str
    source_job_id: str
    formats: list[str]
    status: JobStatus = JobStatus.PENDING
    error: str | None = None
    confidence: float | None = None
    created_at: str = field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat()
    )

    def touch(self) -> None:
        self.updated_at = dt.datetime.now(dt.timezone.utc).isoformat()

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex
