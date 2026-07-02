"""
FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path to allow running from within the app subdirectory
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.settings import get_settings
from app.routers import github_router, local_router, status_router, website_router, zip_router
from app.utils.logger import configure_logging, get_logger

settings = get_settings()
configure_logging(log_level=settings.log_level, logs_dir=settings.logs_dir)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (environment=%s)", settings.app_name, settings.environment)
    settings.ensure_directories()
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description=(
        "Collects project data from GitHub repositories, websites, ZIP uploads, "
        "and local directories, and stores it in a standard structured format "
        "for downstream auditing systems."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(github_router.router)
app.include_router(website_router.router)
app.include_router(zip_router.router)
app.include_router(local_router.router)
app.include_router(status_router.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/", tags=["Health"])
async def root() -> dict:
    """Basic health check / service info."""
    return {
        "service": settings.app_name,
        "status": "ok",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

