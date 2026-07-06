"""
In-memory job repository (thread-safe-ish via asyncio lock).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path

from app.config.settings import get_settings
from app.models.job import Job
from app.schemas.responses import JobStatus


class JobRepository:
    """Simple in-memory store for job records with disk backup/restoration."""

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
            job = self._jobs.get(job_id)
            if job is not None:
                return job
            return self._restore_job_from_disk_unlocked(job_id)

    async def update_status(
        self, job_id: str, status: JobStatus, error: str | None = None, output_dir: str | None = None
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                job = self._restore_job_from_disk_unlocked(job_id)
            if job is None:
                return
            job.status = status
            job.error = error
            if output_dir is not None:
                job.output_dir = output_dir
            job.touch()

            # Save the updated state to disk if output_dir is available
            if job.output_dir:
                try:
                    job_dir = Path(job.output_dir)
                    job_dir.mkdir(parents=True, exist_ok=True)
                    state_file = job_dir / "job_state.json"
                    with state_file.open("w", encoding="utf-8") as f:
                        json.dump({
                            "job_id": job.job_id,
                            "input_type": job.input_type,
                            "source": job.source,
                            "status": job.status.value,
                            "error": job.error,
                            "output_dir": job.output_dir,
                            "created_at": job.created_at,
                            "updated_at": job.updated_at,
                        }, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass

    def _restore_job_from_disk_unlocked(self, job_id: str) -> Job | None:
        try:
            settings = get_settings()
            job_dir = settings.output_dir / job_id
            if not job_dir.is_dir():
                return None

            state_file = job_dir / "job_state.json"
            metadata_file = job_dir / "metadata.json"

            if state_file.exists():
                with state_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                job = Job(
                    job_id=data["job_id"],
                    input_type=data["input_type"],
                    source=data["source"],
                    status=JobStatus(data["status"]),
                    error=data.get("error"),
                    output_dir=data.get("output_dir"),
                    created_at=data.get("created_at"),
                    updated_at=data.get("updated_at"),
                )
                self._jobs[job_id] = job
                return job
            elif metadata_file.exists():
                with metadata_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                job = Job(
                    job_id=job_id,
                    input_type=data.get("input_type", "unknown"),
                    source=data.get("source", "unknown"),
                    status=JobStatus.COMPLETED,
                    output_dir=str(job_dir),
                    created_at=data.get("created_at") or dt.datetime.now(dt.timezone.utc).isoformat(),
                    updated_at=data.get("created_at") or dt.datetime.now(dt.timezone.utc).isoformat(),
                )
                self._jobs[job_id] = job
                return job
        except Exception:
            pass
        return None


_job_repository = JobRepository()


def get_job_repository() -> JobRepository:
    """FastAPI dependency provider for the singleton JobRepository."""
    return _job_repository

