from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import pytest

from app.config.settings import get_settings
from app.models.job import Job
from app.models.analysis import AnalysisJob
from app.schemas.responses import JobStatus
from app.services.job_service import JobRepository
from app.services.analysis_job_service import AnalysisJobRepository


@pytest.fixture
def override_output_dir(tmp_path: Path):
    settings = get_settings()
    old_output_dir = settings.output_dir
    settings.output_dir = tmp_path
    yield tmp_path
    settings.output_dir = old_output_dir


@pytest.mark.asyncio
async def test_job_restoration_from_state_json(override_output_dir: Path) -> None:
    job_id = "test_job_123"
    job_dir = override_output_dir / job_id
    job_dir.mkdir(parents=True)

    state_data = {
        "job_id": job_id,
        "input_type": "github_public",
        "source": "https://github.com/example/repo",
        "status": "completed",
        "error": None,
        "output_dir": str(job_dir),
        "created_at": "2026-07-06T19:00:00Z",
        "updated_at": "2026-07-06T19:05:00Z",
    }
    with (job_dir / "job_state.json").open("w", encoding="utf-8") as f:
        json.dump(state_data, f)

    repo = JobRepository()
    job = await repo.get(job_id)

    assert job is not None
    assert job.job_id == job_id
    assert job.input_type == "github_public"
    assert job.source == "https://github.com/example/repo"
    assert job.status == JobStatus.COMPLETED
    assert job.output_dir == str(job_dir)


@pytest.mark.asyncio
async def test_job_restoration_from_metadata_json(override_output_dir: Path) -> None:
    job_id = "test_job_456"
    job_dir = override_output_dir / job_id
    job_dir.mkdir(parents=True)

    metadata_data = {
        "input_type": "local",
        "project_name": "sample_proj",
        "source": "D:/local/path",
        "created_at": "2026-07-06T18:00:00Z",
    }
    with (job_dir / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata_data, f)

    repo = JobRepository()
    job = await repo.get(job_id)

    assert job is not None
    assert job.job_id == job_id
    assert job.input_type == "local"
    assert job.source == "D:/local/path"
    assert job.status == JobStatus.COMPLETED
    assert job.output_dir == str(job_dir)


@pytest.mark.asyncio
async def test_analysis_job_restoration_from_state_json(override_output_dir: Path) -> None:
    job_id = "test_job_789"
    analysis_id = "test_analysis_abc"
    analysis_dir = override_output_dir / job_id / "analysis" / analysis_id
    analysis_dir.mkdir(parents=True)

    state_data = {
        "analysis_id": analysis_id,
        "source_job_id": job_id,
        "formats": ["json", "markdown"],
        "status": "completed",
        "error": None,
        "confidence": 0.95,
        "created_at": "2026-07-06T19:00:00Z",
        "updated_at": "2026-07-06T19:05:00Z",
    }
    with (analysis_dir / "analysis_state.json").open("w", encoding="utf-8") as f:
        json.dump(state_data, f)

    repo = AnalysisJobRepository()
    job = await repo.get(analysis_id)

    assert job is not None
    assert job.analysis_id == analysis_id
    assert job.source_job_id == job_id
    assert job.formats == ["json", "markdown"]
    assert job.status == JobStatus.COMPLETED
    assert job.confidence == 0.95


@pytest.mark.asyncio
async def test_analysis_job_restoration_from_legacy_reports(override_output_dir: Path) -> None:
    job_id = "test_job_999"
    analysis_id = "test_analysis_xyz"
    analysis_dir = override_output_dir / job_id / "analysis" / analysis_id
    analysis_dir.mkdir(parents=True)

    with (analysis_dir / "report.json").open("w", encoding="utf-8") as f:
        f.write("{}")
    with (analysis_dir / "report.md").open("w", encoding="utf-8") as f:
        f.write("# Report")
    with (analysis_dir / "confidence.json").open("w", encoding="utf-8") as f:
        json.dump({"score": 0.88}, f)

    repo = AnalysisJobRepository()
    job = await repo.get(analysis_id)

    assert job is not None
    assert job.analysis_id == analysis_id
    assert job.source_job_id == job_id
    assert set(job.formats) == {"json", "markdown"}
    assert job.status == JobStatus.COMPLETED
    assert job.confidence == 0.88
