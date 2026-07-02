"""
Router: POST /local
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies import get_collector_service
from app.schemas.requests import LocalCollectRequest
from app.schemas.responses import JobCreatedResponse, JobStatus
from app.services.collector_service import CollectorService
from app.services.job_service import JobRepository, get_job_repository

router = APIRouter(tags=["Local"])


@router.post("/local", response_model=JobCreatedResponse, status_code=202)
async def collect_local_directory(
    payload: LocalCollectRequest,
    background_tasks: BackgroundTasks,
    collector: CollectorService = Depends(get_collector_service),
    jobs: JobRepository = Depends(get_job_repository),
) -> JobCreatedResponse:
    """Start a collection job for a local project directory (server-side path)."""
    job = await jobs.create(input_type="local", source=payload.path)

    background_tasks.add_task(collector.run_local_job, job, payload.path)

    return JobCreatedResponse(job_id=job.job_id, status=JobStatus.PENDING)
