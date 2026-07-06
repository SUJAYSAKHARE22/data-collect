"""
In-memory analysis job repository. Mirrors app/services/job_service.py's
JobRepository pattern for the AI analysis jobs.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path

from app.config.settings import get_settings
from app.models.analysis import AnalysisJob
from app.schemas.responses import JobStatus


class AnalysisJobRepository:
    """Simple in-memory store for AI analysis job records with disk backup/restoration."""

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
            job = self._jobs.get(analysis_id)
            if job is not None:
                return job
            return self._restore_analysis_job_from_disk_unlocked(analysis_id)

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
                job = self._restore_analysis_job_from_disk_unlocked(analysis_id)
            if job is None:
                return
            job.status = status
            job.error = error
            if confidence is not None:
                job.confidence = confidence
            job.touch()

            # Save the updated state to disk
            try:
                settings = get_settings()
                analysis_dir = settings.output_dir / job.source_job_id / "analysis" / job.analysis_id
                analysis_dir.mkdir(parents=True, exist_ok=True)
                state_file = analysis_dir / "analysis_state.json"
                with state_file.open("w", encoding="utf-8") as f:
                    json.dump({
                        "analysis_id": job.analysis_id,
                        "source_job_id": job.source_job_id,
                        "formats": job.formats,
                        "status": job.status.value,
                        "error": job.error,
                        "confidence": job.confidence,
                        "created_at": job.created_at,
                        "updated_at": job.updated_at,
                    }, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    def _restore_analysis_job_from_disk_unlocked(self, analysis_id: str) -> AnalysisJob | None:
        try:
            settings = get_settings()
            output_dir = settings.output_dir
            if not output_dir.exists():
                return None

            for job_dir in output_dir.iterdir():
                if not job_dir.is_dir():
                    continue
                analysis_dir = job_dir / "analysis" / analysis_id
                if not analysis_dir.is_dir():
                    continue

                state_file = analysis_dir / "analysis_state.json"
                if state_file.exists():
                    with state_file.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    job = AnalysisJob(
                        analysis_id=data["analysis_id"],
                        source_job_id=data["source_job_id"],
                        formats=data["formats"],
                        status=JobStatus(data["status"]),
                        error=data.get("error"),
                        confidence=data.get("confidence"),
                        created_at=data.get("created_at"),
                        updated_at=data.get("updated_at"),
                    )
                    self._jobs[analysis_id] = job
                    return job

                # Fallback to check if report files exist (legacy/completed analysis)
                confidence_file = analysis_dir / "confidence.json"
                report_data_file = analysis_dir / "report_data.json"
                if confidence_file.exists() or report_data_file.exists():
                    confidence_val = None
                    if confidence_file.exists():
                        try:
                            with confidence_file.open("r", encoding="utf-8") as f:
                                conf_data = json.load(f)
                                confidence_val = conf_data.get("score")
                        except Exception:
                            pass
                    
                    formats = []
                    for fmt, ext in [("markdown", "md"), ("html", "html"), ("json", "json")]:
                        if (analysis_dir / f"report.{ext}").exists():
                            formats.append(fmt)

                    job = AnalysisJob(
                        analysis_id=analysis_id,
                        source_job_id=job_dir.name,
                        formats=formats or ["json"],
                        status=JobStatus.COMPLETED,
                        confidence=confidence_val,
                        created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        updated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    )
                    self._jobs[analysis_id] = job
                    return job
        except Exception:
            pass
        return None


_analysis_job_repository = AnalysisJobRepository()


def get_analysis_job_repository() -> AnalysisJobRepository:
    """FastAPI dependency provider for the singleton AnalysisJobRepository."""
    return _analysis_job_repository

