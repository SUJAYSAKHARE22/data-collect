"""
Pydantic schemas describing the common project metadata output format.
"""
from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, Field


class InputType(str, Enum):
    GITHUB_PUBLIC = "github_public"
    GITHUB_PRIVATE = "github_private"
    WEBSITE = "website"
    ZIP = "zip"
    LOCAL = "local"


class FileRecord(BaseModel):
    path: str
    name: str
    extension: str
    size_bytes: int
    depth: int
    last_modified: str | None = None
    language: str | None = None
    hash: str | None = None
    is_dependency_file: bool = False
    is_entry_file: bool = False


class ProjectMetadata(BaseModel):
    """The common output metadata schema (metadata.json) for every input source."""

    input_type: InputType
    project_name: str
    source: str
    language: str | None = None
    framework: str | None = None
    created_at: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())

    files: list[str] = Field(default_factory=list)
    folders: list[str] = Field(default_factory=list)
    entry_files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

    # Extra, source-specific metadata (repo owner, branch, commit hash, website tech, etc.)
    extra: dict = Field(default_factory=dict)
