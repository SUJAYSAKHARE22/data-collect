"""
Tests for the AI Analysis Agent (ReportAgent pipeline): confidence
validation / anti-hallucination filtering, report building, and rendering.
"""
from __future__ import annotations

import pytest

from app.agents.confidence_validator import ConfidenceValidator
from app.agents.renderers.pdf_renderer import PdfRenderer
from app.agents.report_agent import ReportAgent


RAW_REPORT = {
    "executiveSummary": {
        "overview": "Small test project with one real security issue.",
        "overallRisk": "High",
        "topAction": "Remove the hardcoded secret",
    },
    "findingGroups": [
        {
            "id": "sec-1",
            "name": "Security",
            "category": "security",
            "findings": [
                {
                    "id": "f1",
                    "title": "Hardcoded secret",
                    "severity": "critical",
                    "category": "security",
                    "file": "app/main.py",
                    "description": "API key committed in source.",
                    "recommendation": "Move to environment variable.",
                },
                {
                    "id": "f2",
                    "title": "Hallucinated file reference",
                    "severity": "high",
                    "category": "security",
                    "file": "app/does_not_exist.py",
                    "description": "This references a file that was never collected.",
                    "recommendation": "n/a",
                },
            ],
        }
    ],
    "priorityMatrix": [
        {
            "findingId": "f1",
            "title": "Hardcoded secret",
            "severity": "critical",
            "category": "security",
            "priorityScore": 9.5,
            "effort": "low",
            "effortHours": 0.5,
        },
        {
            "findingId": "f2",
            "title": "Hallucinated file reference",
            "severity": "high",
            "category": "security",
            "priorityScore": 8,
            "effort": "low",
            "effortHours": 1,
        },
    ],
    "actionPlan": [
        {
            "findingId": "f1",
            "title": "Hardcoded secret",
            "action": "Move key to env var and rotate it.",
            "severity": "critical",
            "effortHours": 0.5,
            "phase": "immediate",
        },
        {
            "findingId": "f2",
            "title": "Hallucinated file reference",
            "action": "n/a",
            "severity": "high",
            "effortHours": 1,
            "phase": "immediate",
        },
    ],
}

KNOWN_FILES = {"app/main.py"}
METADATA = {"project_name": "TestProj", "source": "/local/test", "input_type": "local"}


def test_confidence_validator_drops_hallucinated_file_reference():
    validator = ConfidenceValidator(KNOWN_FILES)
    validated, confidence = validator.validate(RAW_REPORT)

    findings = validated["findingGroups"][0]["findings"]
    assert len(findings) == 1
    assert findings[0]["file"] == "app/main.py"
    assert any("does_not_exist.py" in e for e in confidence.excluded_data_points)


def test_confidence_validator_drops_priority_and_action_for_dropped_finding():
    validator = ConfidenceValidator(KNOWN_FILES)
    validated, _ = validator.validate(RAW_REPORT)

    priority_ids = {p["findingId"] for p in validated["priorityMatrix"]}
    action_ids = {a["findingId"] for a in validated["actionPlan"]}
    assert priority_ids == {"f1"}
    assert action_ids == {"f1"}


def test_report_agent_produces_all_requested_formats():
    agent = ReportAgent(known_file_paths=KNOWN_FILES)
    result = agent.run(RAW_REPORT, METADATA, formats=["markdown", "html", "json"])

    formats = {r["format"] for r in result["reports"]}
    assert formats == {"markdown", "html", "json"}
    assert result["confidence"]["score"] > 0
    assert result["data"]["developer"]["groups"][0]["count"] == 1


def test_pdf_renderer_produces_nonempty_pdf():
    agent = ReportAgent(known_file_paths=KNOWN_FILES)
    result = agent.run(RAW_REPORT, METADATA, formats=["html"])
    html_content = result["reports"][0]["content"]

    pdf = PdfRenderer().render(html_content, project_name="TestProj")
    assert pdf["sizeBytes"] > 0
    assert pdf["content"][:4] == b"%PDF"


def test_confidence_validator_rejects_non_dict_report():
    validator = ConfidenceValidator(KNOWN_FILES)
    with pytest.raises(ValueError):
        validator.validate([])
