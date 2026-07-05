"""
Confidence Validator — ported from ReplexAgent's ConfidenceValidator.js.

Improvement over the original: every finding/action/priority item that
references a `file` is cross-checked against the real, collected file list
for this project. Any reference to a file that does not actually exist in
the project is excluded from the validated report and logged as an
excluded data point — this is a concrete anti-hallucination check that the
original ReplexAgent validator does not perform (it only checks structural
shape, not factual grounding against a source of truth).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

VALID_CATEGORIES = {
    "architecture", "code-quality", "security", "dependencies",
    "best-practice", "documentation", "performance",
}
VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
VALID_EFFORTS = {"low", "medium", "high"}
VALID_PHASES = {"immediate", "short-term", "long-term"}


@dataclass
class ConfidenceScore:
    score: float
    rationale: str
    verified_data_points: list[str] = field(default_factory=list)
    excluded_data_points: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "rationale": self.rationale,
            "verifiedDataPoints": self.verified_data_points,
            "excludedDataPoints": self.excluded_data_points,
        }


class ConfidenceValidator:
    """Validates the raw LLM AuditReport and produces a confidence-scored, cleaned report."""

    def __init__(self, known_file_paths: set[str]) -> None:
        self.known_file_paths = known_file_paths

    def validate(self, report: dict) -> tuple[dict, ConfidenceScore]:
        if not isinstance(report, dict):
            raise ValueError("AuditReport must be a JSON object")

        verified: list[str] = []
        excluded: list[str] = []

        exec_summary = report.get("executiveSummary") or {}
        if isinstance(exec_summary, dict) and exec_summary.get("overview"):
            verified.append("executiveSummary.overview")
        else:
            excluded.append("executiveSummary.overview (missing)")

        if exec_summary.get("overallRisk"):
            verified.append("executiveSummary.overallRisk")
        if exec_summary.get("topAction"):
            verified.append("executiveSummary.topAction")

        valid_groups = []
        known_finding_ids: set[str] = set()
        for group in report.get("findingGroups") or []:
            ok, cleaned_group, reasons = self._validate_group(group)
            if ok:
                valid_groups.append(cleaned_group)
                verified.append(f"findingGroup:{group.get('id')}")
                known_finding_ids.update(f["id"] for f in cleaned_group["findings"])
                for reason in reasons:
                    excluded.append(f"findingGroup:{group.get('id')} - {reason}")
            else:
                excluded.append(f"findingGroup:{group.get('id', '?')} ({'; '.join(reasons)})")

        valid_priority = []
        for item in report.get("priorityMatrix") or []:
            ok, cleaned, reason = self._validate_priority_item(item, known_finding_ids)
            if ok:
                valid_priority.append(cleaned)
                verified.append(f"priority:{item.get('findingId')}")
            else:
                excluded.append(f"priority:{item.get('findingId', '?')} ({reason})")

        valid_actions = []
        for action in report.get("actionPlan") or []:
            ok, cleaned, reason = self._validate_action_item(action, known_finding_ids)
            if ok:
                valid_actions.append(cleaned)
                verified.append(f"action:{action.get('findingId')}")
            else:
                excluded.append(f"action:{action.get('findingId', '?')} ({reason})")

        total_findings = sum(len(g["findings"]) for g in valid_groups)
        by_severity = {sev: 0 for sev in VALID_SEVERITIES}
        by_category = {cat: 0 for cat in VALID_CATEGORIES}
        for g in valid_groups:
            for f in g["findings"]:
                by_severity[f["severity"]] += 1
                by_category[f["category"]] += 1

        validated_report = {
            "executiveSummary": {
                "overview": exec_summary.get("overview") or "No executive summary available.",
                "overallRisk": exec_summary.get("overallRisk") or "Unknown",
                "topAction": exec_summary.get("topAction") or "No actions identified",
                "totalFindings": total_findings,
                "bySeverity": by_severity,
                "byCategory": by_category,
            },
            "findingGroups": valid_groups,
            "priorityMatrix": sorted(valid_priority, key=lambda x: x["priorityScore"], reverse=True),
            "actionPlan": valid_actions,
            "metadata": {
                "validatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                "originalFindingCount": sum((g.get("count") or len(g.get("findings") or [])) for g in (report.get("findingGroups") or [])),
                "validatedFindingCount": total_findings,
                "model": report.get("_model"),
                "llmUsage": report.get("_llmUsage"),
            },
        }

        confidence = self._calculate_confidence(verified, excluded, validated_report)
        return validated_report, confidence

    def _validate_group(self, group: dict) -> tuple[bool, dict | None, list[str]]:
        reasons = []
        if not isinstance(group, dict):
            return False, None, ["not an object"]
        gid = group.get("id")
        name = group.get("name")
        category = group.get("category")
        findings = group.get("findings")

        if not gid or not isinstance(gid, str):
            reasons.append("missing id")
        if not name or not isinstance(name, str):
            reasons.append("missing name")
        if category not in VALID_CATEGORIES:
            reasons.append(f"invalid category '{category}'")
        if not isinstance(findings, list):
            reasons.append("findings not a list")

        if reasons:
            return False, None, reasons

        cleaned_findings = []
        for f in findings:
            ok, cleaned, why = self._validate_finding(f)
            if ok:
                cleaned_findings.append(cleaned)
            else:
                reasons.append(f"dropped finding {f.get('id', '?') if isinstance(f, dict) else '?'}: {why}")

        if not cleaned_findings:
            return False, None, reasons or ["no valid findings"]

        max_sev = max(cleaned_findings, key=lambda f: self._severity_rank(f["severity"]))["severity"]

        cleaned_group = {
            "id": gid,
            "name": name,
            "category": category,
            "count": len(cleaned_findings),
            "maxSeverity": max_sev,
            "findings": cleaned_findings,
        }
        return True, cleaned_group, reasons

    def _validate_finding(self, f: dict) -> tuple[bool, dict | None, str]:
        if not isinstance(f, dict):
            return False, None, "not an object"
        fid = f.get("id")
        title = f.get("title")
        severity = f.get("severity")
        category = f.get("category")
        description = f.get("description") or ""
        recommendation = f.get("recommendation") or ""
        file_path = f.get("file")

        if not fid or not title:
            return False, None, "missing id/title"
        if severity not in VALID_SEVERITIES:
            return False, None, f"invalid severity '{severity}'"
        if category not in VALID_CATEGORIES:
            return False, None, f"invalid category '{category}'"

        # Anti-hallucination check: if a file is referenced, it must be real.
        if file_path:
            if self.known_file_paths and file_path not in self.known_file_paths:
                return False, None, f"references nonexistent file '{file_path}' (excluded to prevent hallucination)"

        return True, {
            "id": fid,
            "title": title,
            "severity": severity,
            "category": category,
            "file": file_path,
            "description": description,
            "recommendation": recommendation,
        }, ""

    def _validate_priority_item(self, item: dict, known_ids: set[str]) -> tuple[bool, dict | None, str]:
        if not isinstance(item, dict):
            return False, None, "not an object"
        finding_id = item.get("findingId")
        if not finding_id or finding_id not in known_ids:
            return False, None, "findingId not in validated findings"
        severity = item.get("severity")
        category = item.get("category")
        if severity not in VALID_SEVERITIES or category not in VALID_CATEGORIES:
            return False, None, "invalid severity/category"
        try:
            score = float(item.get("priorityScore", 0))
            effort_hours = float(item.get("effortHours", 0))
        except (TypeError, ValueError):
            return False, None, "non-numeric score/hours"
        effort = item.get("effort") if item.get("effort") in VALID_EFFORTS else "medium"

        return True, {
            "findingId": finding_id,
            "title": item.get("title") or finding_id,
            "severity": severity,
            "category": category,
            "priorityScore": max(0.0, min(10.0, score)),
            "effort": effort,
            "effortHours": max(0.0, effort_hours),
        }, ""

    def _validate_action_item(self, item: dict, known_ids: set[str]) -> tuple[bool, dict | None, str]:
        if not isinstance(item, dict):
            return False, None, "not an object"
        finding_id = item.get("findingId")
        if not finding_id or finding_id not in known_ids:
            return False, None, "findingId not in validated findings"
        severity = item.get("severity")
        if severity not in VALID_SEVERITIES:
            return False, None, "invalid severity"
        try:
            effort_hours = float(item.get("effortHours", 0))
        except (TypeError, ValueError):
            effort_hours = 0.0
        phase = item.get("phase") if item.get("phase") in VALID_PHASES else "short-term"

        return True, {
            "findingId": finding_id,
            "title": item.get("title") or finding_id,
            "action": item.get("action") or "Review and address this finding.",
            "severity": severity,
            "effortHours": max(0.0, effort_hours),
            "phase": phase,
        }, ""

    @staticmethod
    def _severity_rank(sev: str) -> int:
        order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
        return order.get(sev, 0)

    def _calculate_confidence(self, verified: list[str], excluded: list[str], report: dict) -> ConfidenceScore:
        total = len(verified) + len(excluded)
        score = 0.0 if total == 0 else len(verified) / total

        has_all_sections = bool(
            report.get("executiveSummary")
            and report.get("findingGroups")
            and report.get("priorityMatrix")
            and report.get("actionPlan")
        )
        adjusted = score if has_all_sections else max(score - 0.1, 0.0)

        rationale = (
            "No data points to validate"
            if total == 0
            else f"{len(verified)} of {total} data points verified against the collected project. "
            + ("All report sections present." if has_all_sections else "Some sections missing.")
        )

        return ConfidenceScore(
            score=round(adjusted, 2),
            rationale=rationale,
            verified_data_points=verified,
            excluded_data_points=excluded,
        )
