"""
Router: POST /website
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies import get_collector_service
from app.schemas.requests import WebsiteCollectRequest
from app.schemas.responses import JobCreatedResponse, JobStatus
from app.services.collector_service import CollectorService
from app.services.job_service import JobRepository, get_job_repository

router = APIRouter(tags=["Website"])


@router.post("/website", response_model=JobCreatedResponse, status_code=202)
async def collect_website(
    payload: WebsiteCollectRequest,
    background_tasks: BackgroundTasks,
    collector: CollectorService = Depends(get_collector_service),
    jobs: JobRepository = Depends(get_job_repository),
) -> JobCreatedResponse:
    """Start a crawl job for a public website URL."""
    job = await jobs.create(input_type="website", source=str(payload.url))

    background_tasks.add_task(
        collector.run_website_job,
        job,
        str(payload.url),
        payload.max_pages,
        payload.max_depth,
    )

    return JobCreatedResponse(job_id=job.job_id, status=JobStatus.PENDING)
