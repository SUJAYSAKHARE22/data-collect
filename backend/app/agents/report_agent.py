"""
Report Agent — Python port of ReplexAgent's ReportAgent.js.

Transforms a raw LLM AuditReport into validated, confidence-scored,
multi-format reports (Markdown / HTML / JSON). No hallucination: only
validated findings from ConfidenceValidator are used, and file references
are cross-checked against the real project's file list.
"""
from __future__ import annotations

import time

from app.agents.confidence_validator import ConfidenceValidator
from app.agents.renderers.html_renderer import HtmlRenderer
from app.agents.renderers.json_renderer import JsonRenderer
from app.agents.renderers.markdown_renderer import MarkdownRenderer
from app.agents.report_builder import ReportBuilder
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ReportAgent:
    id = "report-agent"
    name = "Report Agent"

    def __init__(self, known_file_paths: set[str]) -> None:
        self.validator = ConfidenceValidator(known_file_paths)
        self.builder = ReportBuilder()
        self.renderers = {
            "markdown": MarkdownRenderer(),
            "html": HtmlRenderer(),
            "json": JsonRenderer(),
        }

    def run(self, raw_audit_report: dict, metadata: dict, formats: list[str] | None = None) -> dict:
        start = time.monotonic()
        formats = formats or ["markdown", "html", "json"]

        validated_report, confidence = self.validator.validate(raw_audit_report)
        report_data = self.builder.build(validated_report, confidence, metadata)

        reports = []
        for fmt in formats:
            renderer = self.renderers.get(fmt)
            if renderer is None:
                logger.warning("Unknown report format requested: %s", fmt)
                continue
            reports.append(renderer.render(report_data))

        duration_ms = round((time.monotonic() - start) * 1000)
        total_bytes = sum(r["sizeBytes"] for r in reports)

        logger.info(
            "Report generated in %dms: %s (%d bytes total, confidence: %d%%)",
            duration_ms,
            ", ".join(r["format"] for r in reports),
            total_bytes,
            round(report_data["overallConfidence"]["score"] * 100),
        )

        return {
            "reports": reports,
            "data": report_data,
            "confidence": report_data["overallConfidence"],
            "metadata": {
                "agentId": self.id,
                "formats": formats,
                "totalSizeBytes": total_bytes,
                "durationMs": duration_ms,
                "validationConfidence": confidence.score,
            },
        }
