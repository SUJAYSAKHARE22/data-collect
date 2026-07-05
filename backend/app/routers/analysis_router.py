"""
Routers: POST /analyze/{job_id}, GET /analyze/status/{analysis_id},
GET /analyze/{analysis_id}/report, GET /analyze/{analysis_id}/report.pdf

The AI Analysis Agent takes an already-collected project (from /github,
/website, /zip, or /local) and produces a confidence-scored, multi-format
report (Markdown / HTML / JSON / PDF) using the Kimi K2 LLM — the same
report-generation approach used in ReplexAgent's ReportAgent, adapted here
for source code instead of live websites.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app.dependencies import get_analysis_service, get_collector_service
from app.schemas.analysis import (
    AnalysisCreatedResponse,
    AnalysisStatusResponse,
    AnalyzeRequest,
    VALID_FORMATS,
)
from app.schemas.responses import JobStatus
from app.services.analysis_job_service import AnalysisJobRepository, get_analysis_job_repository
from app.services.analysis_service import AnalysisService
from app.services.collector_service import CollectorService
from app.services.job_service import JobRepository, get_job_repository

router = APIRouter(prefix="/analyze", tags=["AI Analysis"])


async def _get_source_job_or_404(job_id: str, jobs: JobRepository):
    job = await jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Collection job not found: {job_id}")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Collection job is not completed yet (status={job.status}). "
            "Wait for /status to report 'completed' before running AI analysis.",
        )
    return job


async def _get_analysis_or_404(analysis_id: str, analysis_jobs: AnalysisJobRepository):
    job = await analysis_jobs.get(analysis_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")
    return job


@router.post("/{job_id}", response_model=AnalysisCreatedResponse, status_code=202)
async def start_analysis(
    job_id: str,
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    jobs: JobRepository = Depends(get_job_repository),
    analysis_jobs: AnalysisJobRepository = Depends(get_analysis_job_repository),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisCreatedResponse:
    await _get_source_job_or_404(job_id, jobs)

    if not analysis_service.is_configured:
        raise HTTPException(
            status_code=503,
            detail="AI Analysis Agent is not configured: set KIMI_API_KEY in the backend .env file.",
        )

    formats = request.formats or ["markdown", "html", "json"]
    invalid = [f for f in formats if f not in VALID_FORMATS]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Invalid format(s): {invalid}. Valid: {sorted(VALID_FORMATS)}")

    analysis_job = await analysis_jobs.create(source_job_id=job_id, formats=formats)
    background_tasks.add_task(analysis_service.run_analysis, analysis_job)

    return AnalysisCreatedResponse(
        analysis_id=analysis_job.analysis_id, job_id=job_id, status=analysis_job.status
    )


@router.get("/status/{analysis_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    analysis_id: str,
    analysis_jobs: AnalysisJobRepository = Depends(get_analysis_job_repository),
) -> AnalysisStatusResponse:
    job = await _get_analysis_or_404(analysis_id, analysis_jobs)
    return AnalysisStatusResponse(
        analysis_id=job.analysis_id,
        job_id=job.source_job_id,
        status=job.status,
        error=job.error,
        confidence=job.confidence,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{analysis_id}/report")
async def get_analysis_report(
    analysis_id: str,
    format: str = Query(default="json", description="markdown | html | json"),
    analysis_jobs: AnalysisJobRepository = Depends(get_analysis_job_repository),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    job = await _get_analysis_or_404(analysis_id, analysis_jobs)
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=409, detail=f"Analysis is not completed yet (status={job.status})")

    if format not in VALID_FORMATS:
        raise HTTPException(status_code=422, detail=f"Invalid format. Valid: {sorted(VALID_FORMATS)}")

    content = analysis_service.read_report(job.source_job_id, analysis_id, format)
    if content is None:
        raise HTTPException(status_code=404, detail="Report content not found")

    if format == "html":
        return HTMLResponse(content=content)
    if format == "markdown":
        return PlainTextResponse(content=content, media_type="text/markdown")
    return content  # json format -> FastAPI serializes the dict directly


@router.get("/{analysis_id}/report.pdf")
async def download_analysis_pdf(
    analysis_id: str,
    analysis_jobs: AnalysisJobRepository = Depends(get_analysis_job_repository),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> Response:
    job = await _get_analysis_or_404(analysis_id, analysis_jobs)
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=409, detail=f"Analysis is not completed yet (status={job.status})")

    result = analysis_service.get_or_render_pdf(job.source_job_id, analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found; cannot render PDF")

    pdf_bytes, filename = result
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
