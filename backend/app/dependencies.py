"""
FastAPI dependency providers.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from app.config.settings import Settings, get_settings
from app.services.analysis_job_service import AnalysisJobRepository, get_analysis_job_repository
from app.services.analysis_service import AnalysisService
from app.services.collector_service import CollectorService
from app.services.job_service import JobRepository, get_job_repository


@lru_cache
def _build_collector_service() -> CollectorService:
    settings = get_settings()
    return CollectorService(settings=settings, job_repository=get_job_repository())


def get_collector_service() -> CollectorService:
    return _build_collector_service()


@lru_cache
def _build_analysis_service() -> AnalysisService:
    settings = get_settings()
    return AnalysisService(
        settings=settings,
        collector=_build_collector_service(),
        analysis_jobs=get_analysis_job_repository(),
    )


def get_analysis_service() -> AnalysisService:
    return _build_analysis_service()


def get_app_settings() -> Settings:
    return get_settings()
