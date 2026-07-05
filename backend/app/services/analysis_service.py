"""
Analysis service — orchestrates the AI Analysis Agent end to end:

  1. Load the already-collected project (metadata.json/tree.json/files.json
     + project/ directory) for a completed data-collection job.
  2. Build a budget-limited code context (context_builder).
  3. Call the Kimi K2 LLM (CodeAnalysisAgent) to produce a raw AuditReport.
  4. Validate it against the real file list (ConfidenceValidator, inside
     ReportAgent) to eliminate hallucinated references.
  5. Render Markdown / HTML / JSON reports and persist them to disk next to
     the source job's output, under `analysis/{analysis_id}/`.
  6. PDF is rendered on demand from the persisted HTML (and cached).

This mirrors ReplexAgent's WebsiteAuditAgent -> ReportAgent pipeline, but
operates over locally collected project files instead of a live website.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.agents.code_analysis_agent import CodeAnalysisAgent
from app.agents.context_builder import build_project_context
from app.agents.llm_provider import KimiProvider
from app.agents.renderers.pdf_renderer import PdfRenderer
from app.agents.report_agent import ReportAgent
from app.config.settings import Settings
from app.models.analysis import AnalysisJob
from app.schemas.responses import JobStatus
from app.services.analysis_job_service import AnalysisJobRepository
from app.services.collector_service import CollectorService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisNotReadyError(Exception):
    pass


class AnalysisService:
    def __init__(
        self,
        settings: Settings,
        collector: CollectorService,
        analysis_jobs: AnalysisJobRepository,
    ) -> None:
        self._settings = settings
        self._collector = collector
        self._jobs = analysis_jobs
        self._provider = KimiProvider(
            api_key=settings.kimi_api_key,
            base_url=settings.kimi_base_url,
            model=settings.kimi_model,
            timeout_seconds=settings.kimi_timeout_seconds,
            max_retries=settings.kimi_max_retries,
        )

    @property
    def is_configured(self) -> bool:
        return self._provider.is_configured

    def _analysis_dir(self, source_job_id: str, analysis_id: str) -> Path:
        storage = self._collector.storage_for(source_job_id)
        return storage.job_dir / "analysis" / analysis_id

    async def run_analysis(self, job: AnalysisJob) -> None:
        source_storage = self._collector.storage_for(job.source_job_id)
        analysis_dir = self._analysis_dir(job.source_job_id, job.analysis_id)

        try:
            await self._jobs.update_status(job.analysis_id, JobStatus.RUNNING)

            metadata = source_storage.read_json("metadata.json")
            tree = source_storage.read_json("tree.json")
            files = source_storage.read_json("files.json")

            if metadata is None or files is None:
                raise AnalysisNotReadyError(
                    "Source job has no collected metadata/files yet. "
                    "Wait for the collection job to complete before analyzing it."
                )
            if not source_storage.project_dir.exists():
                raise AnalysisNotReadyError("Source project directory not found on disk.")

            ctx = build_project_context(
                metadata=metadata,
                tree=tree,
                files=files,
                project_dir=source_storage.project_dir,
                max_files=self._settings.analysis_max_files,
                max_file_chars=self._settings.analysis_max_file_chars,
                max_total_chars=self._settings.analysis_max_total_chars,
            )

            agent = CodeAnalysisAgent(
                self._provider,
                max_tokens=self._settings.kimi_max_tokens,
                temperature=self._settings.kimi_temperature,
            )
            raw_report = await agent.run(ctx)

            known_paths = {f.get("path") for f in files if f.get("path")}
            report_agent = ReportAgent(known_file_paths=known_paths)
            # Always render HTML internally (even if not in the requested
            # formats) since PDF generation depends on it.
            formats_to_render = list(dict.fromkeys([*job.formats, "html"]))
            result = report_agent.run(raw_report, metadata, formats=formats_to_render)

            self._persist(analysis_dir, result)

            await self._jobs.update_status(
                job.analysis_id,
                JobStatus.COMPLETED,
                confidence=result["confidence"]["score"],
            )
            logger.info(
                "Analysis %s completed for job %s (confidence=%.2f)",
                job.analysis_id,
                job.source_job_id,
                result["confidence"]["score"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Analysis %s failed: %s", job.analysis_id, exc)
            await self._jobs.update_status(job.analysis_id, JobStatus.FAILED, error=str(exc))

    def _persist(self, analysis_dir: Path, result: dict) -> None:
        analysis_dir.mkdir(parents=True, exist_ok=True)

        for report in result["reports"]:
            ext = {"markdown": "md", "html": "html", "json": "json"}[report["format"]]
            (analysis_dir / f"report.{ext}").write_text(report["content"], encoding="utf-8")

        (analysis_dir / "report_data.json").write_text(
            json.dumps(result["data"], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (analysis_dir / "confidence.json").write_text(
            json.dumps(result["confidence"], indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def read_report(self, source_job_id: str, analysis_id: str, fmt: str) -> str | dict | None:
        analysis_dir = self._analysis_dir(source_job_id, analysis_id)
        ext_map = {"markdown": "md", "html": "html", "json": "json"}
        ext = ext_map.get(fmt)
        if ext is None:
            return None
        path = analysis_dir / f"report.{ext}"
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if fmt == "json" else text

    def read_report_data(self, source_job_id: str, analysis_id: str) -> dict | None:
        analysis_dir = self._analysis_dir(source_job_id, analysis_id)
        path = analysis_dir / "report_data.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_or_render_pdf(self, source_job_id: str, analysis_id: str) -> tuple[bytes, str] | None:
        """Return (pdf_bytes, filename), rendering and caching to disk on first request."""
        analysis_dir = self._analysis_dir(source_job_id, analysis_id)
        pdf_path = analysis_dir / "report.pdf"
        if pdf_path.exists():
            data = self.read_report_data(source_job_id, analysis_id) or {}
            filename = PdfRenderer._slugify(data.get("projectName", "report")) + "-report.pdf"
            return pdf_path.read_bytes(), filename

        html_content = self.read_report(source_job_id, analysis_id, "html")
        if html_content is None:
            return None

        data = self.read_report_data(source_job_id, analysis_id) or {}
        rendered = PdfRenderer().render(html_content, project_name=data.get("projectName", "report"))
        pdf_path.write_bytes(rendered["content"])
        return rendered["content"], rendered["filename"]
