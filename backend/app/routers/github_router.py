"""
Router: POST /github
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies import get_collector_service
from app.schemas.requests import GitHubCollectRequest
from app.schemas.responses import JobCreatedResponse, JobStatus
from app.services.collector_service import CollectorService
from app.services.job_service import JobRepository, get_job_repository

router = APIRouter(tags=["GitHub"])


@router.post("/github", response_model=JobCreatedResponse, status_code=202)
async def collect_github_repository(
    payload: GitHubCollectRequest,
    background_tasks: BackgroundTasks,
    collector: CollectorService = Depends(get_collector_service),
    jobs: JobRepository = Depends(get_job_repository),
) -> JobCreatedResponse:
    """Start a collection job for a public or private GitHub repository."""
    job = await jobs.create(input_type="github", source=str(payload.repo_url))

    background_tasks.add_task(
        collector.run_github_job,
        job,
        str(payload.repo_url),
        payload.branch,
        payload.access_token,
    )

    return JobCreatedResponse(job_id=job.job_id, status=JobStatus.PENDING)
