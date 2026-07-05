"""
Pydantic request/response schemas for the AI Analysis Agent endpoints.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.responses import JobStatus

VALID_FORMATS = {"markdown", "html", "json"}


class AnalyzeRequest(BaseModel):
    formats: list[str] | None = Field(
        default=None,
        description="Report formats to generate. Defaults to all: markdown, html, json. "
        "PDF is always available separately via /analyze/{analysis_id}/report.pdf.",
    )


class AnalysisCreatedResponse(BaseModel):
    analysis_id: str
    job_id: str
    status: JobStatus


class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    job_id: str
    status: JobStatus
    error: str | None = None
    confidence: float | None = None
    created_at: str
    updated_at: str


class AnalysisReportResponse(BaseModel):
    analysis_id: str
    format: str
    data: dict
    confidence: dict
