"""
Application configuration.

Loads settings from environment variables / .env file using Pydantic.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    """Central application settings, loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    app_name: str = "Project Data Collector"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # --- Storage ---
    output_dir: Path = Field(default=Path("output"))
    logs_dir: Path = Field(default=Path("logs"))

    # --- GitHub ---
    github_token: str | None = Field(default=None, description="Default GitHub PAT")
    git_clone_timeout_seconds: int = Field(default=300)

    # --- Upload / ZIP ---
    max_upload_size_mb: int = Field(default=200)

    # --- Website Crawler ---
    crawler_timeout_seconds: int = Field(default=20)
    crawler_max_pages: int = Field(default=50)
    crawler_max_depth: int = Field(default=2)
    crawler_user_agent: str = Field(
        default="ProjectDataCollectorBot/1.0 (+https://example.com)"
    )

    # --- Networking ---
    http_max_retries: int = Field(default=3)
    http_retry_backoff_seconds: float = Field(default=1.5)

    # --- AI Analysis Agent (Kimi K2 via NVIDIA NIM, OpenAI-compatible) ---
    kimi_api_key: str | None = Field(default=None, description="API key for the Kimi (NVIDIA NIM) LLM provider")
    kimi_base_url: str = Field(default="https://integrate.api.nvidia.com/v1")
    kimi_model: str = Field(default="moonshotai/kimi-k2.6")
    kimi_timeout_seconds: float = Field(default=120.0)
    kimi_max_retries: int = Field(default=3)
    kimi_max_tokens: int = Field(default=4096)
    kimi_temperature: float = Field(default=0.3)

    # --- Analysis Agent context budget ---
    analysis_max_files: int = Field(default=40, description="Max number of files sent to the LLM as context")
    analysis_max_file_chars: int = Field(default=6000, description="Max characters read per file")
    analysis_max_total_chars: int = Field(default=70000, description="Max total characters of code context sent to the LLM")

    def ensure_directories(self) -> None:
        """Create base directories if they do not already exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    settings = Settings()
    settings.ensure_directories()
    return settings
