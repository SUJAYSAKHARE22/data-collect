"""
Pydantic response schemas for the FastAPI endpoints.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from app.schemas.metadata import ProjectMetadata


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    input_type: str
    source: str
    error: str | None = None
    created_at: str
    updated_at: str


class MetadataResponse(BaseModel):
    job_id: str
    metadata: ProjectMetadata


class TreeResponse(BaseModel):
    job_id: str
    tree: dict


class FilesResponse(BaseModel):
    job_id: str
    files: list[dict]


class FileContentResponse(BaseModel):
    job_id: str
    path: str
    content: str

