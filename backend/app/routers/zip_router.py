"""
Router: POST /zip
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File

from app.config.settings import Settings
from app.dependencies import get_app_settings, get_collector_service
from app.schemas.responses import JobCreatedResponse, JobStatus
from app.services.collector_service import CollectorService
from app.services.job_service import JobRepository, get_job_repository
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["ZIP"])


@router.post("/zip", response_model=JobCreatedResponse, status_code=202)
async def collect_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collector: CollectorService = Depends(get_collector_service),
    jobs: JobRepository = Depends(get_job_repository),
    settings: Settings = Depends(get_app_settings),
) -> JobCreatedResponse:
    """Upload a ZIP file to be extracted and processed."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")

    job = await jobs.create(input_type="zip", source=file.filename)
    storage = collector.storage_for(job.job_id)
    storage.initialize()

    upload_path = storage.downloads_dir / "upload.zip"
    size = 0
    with upload_path.open("wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_size_bytes:
                out_file.close()
                upload_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds maximum upload size of {settings.max_upload_size_mb}MB",
                )
            out_file.write(chunk)

    background_tasks.add_task(collector.run_zip_job, job, upload_path, file.filename)

    return JobCreatedResponse(job_id=job.job_id, status=JobStatus.PENDING)
