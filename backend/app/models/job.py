"""
In-memory job record used to track collection job progress and results.

For a production deployment this would be backed by a database (e.g. Postgres,
Redis). It is kept in-memory here to avoid introducing an external dependency,
but is isolated behind JobRepository so it can be swapped out later.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from app.schemas.responses import JobStatus


@dataclass
class Job:
    job_id: str
    input_type: str
    source: str
    status: JobStatus = JobStatus.PENDING
    error: str | None = None
    output_dir: str | None = None
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
