"""
Routers: GET /status/{job_id}, GET /metadata/{job_id}, GET /tree/{job_id},
GET /download/{job_id}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.dependencies import get_collector_service
from app.schemas.responses import (
    FilesResponse,
    JobStatusResponse,
    MetadataResponse,
    TreeResponse,
)
from app.services.collector_service import CollectorService
from app.services.job_service import JobRepository, get_job_repository

router = APIRouter(tags=["Job Results"])


async def _get_job_or_404(job_id: str, jobs: JobRepository):
    job = await jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_status(
    job_id: str, jobs: JobRepository = Depends(get_job_repository)
) -> JobStatusResponse:
    job = await _get_job_or_404(job_id, jobs)
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        input_type=job.input_type,
        source=job.source,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/metadata/{job_id}", response_model=MetadataResponse)
async def get_metadata(
    job_id: str,
    jobs: JobRepository = Depends(get_job_repository),
    collector: CollectorService = Depends(get_collector_service),
) -> MetadataResponse:
    await _get_job_or_404(job_id, jobs)
    storage = collector.storage_for(job_id)
    metadata = storage.read_json("metadata.json")
    if metadata is None:
        raise HTTPException(status_code=404, detail="Metadata not yet available for this job")
    return MetadataResponse(job_id=job_id, metadata=metadata)


@router.get("/tree/{job_id}", response_model=TreeResponse)
async def get_tree(
    job_id: str,
    jobs: JobRepository = Depends(get_job_repository),
    collector: CollectorService = Depends(get_collector_service),
) -> TreeResponse:
    await _get_job_or_404(job_id, jobs)
    storage = collector.storage_for(job_id)
    tree = storage.read_json("tree.json")
    if tree is None:
        raise HTTPException(status_code=404, detail="Tree not yet available for this job")
    return TreeResponse(job_id=job_id, tree=tree)


@router.get("/files/{job_id}", response_model=FilesResponse)
async def get_files(
    job_id: str,
    jobs: JobRepository = Depends(get_job_repository),
    collector: CollectorService = Depends(get_collector_service),
) -> FilesResponse:
    await _get_job_or_404(job_id, jobs)
    storage = collector.storage_for(job_id)
    files = storage.read_json("files.json")
    if files is None:
        raise HTTPException(status_code=404, detail="Files list not yet available for this job")
    return FilesResponse(job_id=job_id, files=files)


@router.get("/download/{job_id}")
async def download_project(
    job_id: str,
    jobs: JobRepository = Depends(get_job_repository),
    collector: CollectorService = Depends(get_collector_service),
) -> FileResponse:
    job = await _get_job_or_404(job_id, jobs)
    if job.status != job.status.COMPLETED:
        raise HTTPException(status_code=409, detail=f"Job is not completed yet (status={job.status})")

    storage = collector.storage_for(job_id)
    if not storage.project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    archive_path = storage.zip_project()
    return FileResponse(
        path=str(archive_path),
        filename=f"{job_id}_project.zip",
        media_type="application/zip",
    )
