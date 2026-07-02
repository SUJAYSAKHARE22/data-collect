"""
Pydantic request schemas for the FastAPI endpoints.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class GitHubCollectRequest(BaseModel):
    repo_url: HttpUrl = Field(..., description="GitHub repository URL (HTTPS)")
    branch: str | None = Field(default=None, description="Branch to clone; defaults to repo default")
    access_token: str | None = Field(
        default=None,
        description="Personal Access Token for private repositories. "
        "If omitted, falls back to server-configured GITHUB_TOKEN.",
    )


class WebsiteCollectRequest(BaseModel):
    url: HttpUrl = Field(..., description="Website URL to crawl")
    max_pages: int | None = Field(default=None, ge=1, le=500)
    max_depth: int | None = Field(default=None, ge=0, le=10)


class LocalCollectRequest(BaseModel):
    path: str = Field(..., description="Absolute path to a local project directory")
