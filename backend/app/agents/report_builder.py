"""
Report Builder — ported from ReplexAgent's ReportBuilder.js.

Takes the validated audit report + confidence score and shapes it into a
presentation-ready ReportData structure with four audiences: executive,
developer, business, and an implementation roadmap. Renderers consume this
single structure to produce Markdown / HTML / JSON / PDF output.
"""
from __future__ import annotations

import datetime as dt

HOURLY_RATE_USD = 75  # used only for the illustrative business cost estimate


class ReportBuilder:
    def build(self, validated_report: dict, confidence, metadata: dict | None = None) -> dict:
        metadata = metadata or {}
        exec_summary = validated_report["executiveSummary"]
        groups = validated_report["findingGroups"]
        priority = validated_report["priorityMatrix"]
        actions = validated_report["actionPlan"]

        total_hours = sum(a["effortHours"] for a in actions)

        quick_wins = [
            f["title"]
            for g in groups
            for f in g["findings"]
            if f["severity"] in ("low", "info")
        ][:8]

        phases = self._build_roadmap_phases(actions, priority)

        report_data = {
            "title": f"AI Project Analysis Report — {metadata.get('project_name', 'Untitled Project')}",
            "url": metadata.get("source", ""),
            "projectName": metadata.get("project_name", "Untitled Project"),
            "inputType": metadata.get("input_type", "unknown"),
            "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            "overallConfidence": confidence.to_dict(),
            "executive": {
                "overview": exec_summary["overview"],
                "totalFindings": exec_summary["totalFindings"],
                "bySeverity": exec_summary["bySeverity"],
                "byCategory": exec_summary["byCategory"],
                "overallRisk": exec_summary["overallRisk"],
                "topAction": exec_summary["topAction"],
                "estimatedTimeline": self._estimate_timeline(total_hours),
                "confidence": confidence.to_dict(),
            },
            "developer": {
                "overview": (
                    f"{exec_summary['totalFindings']} verified findings across "
                    f"{len(groups)} categories. See finding groups below for file-level detail."
                ),
                "technicalDebt": self._summarize_debt(groups),
                "quickWins": quick_wins,
                "groups": groups,
                "confidence": confidence.to_dict(),
            },
            "business": {
                "overview": (
                    "Estimated cost and effort to remediate all validated findings, "
                    "prioritized by impact and urgency."
                ),
                "totalEffortHours": round(total_hours, 1),
                "estimatedCost": round(total_hours * HOURLY_RATE_USD),
                "roi": self._roi_statement(exec_summary["overallRisk"], exec_summary["totalFindings"]),
                "impactSummary": priority,
                "confidence": confidence.to_dict(),
            },
            "roadmap": {
                "overview": "Findings grouped into an actionable, phased remediation plan.",
                "totalEstimatedHours": round(total_hours, 1),
                "estimatedTimeline": self._estimate_timeline(total_hours),
                "phases": phases,
                "confidence": confidence.to_dict(),
            },
            "metadata": validated_report["metadata"],
        }
        return report_data

    def _build_roadmap_phases(self, actions: list[dict], priority: list[dict]) -> list[dict]:
        priority_by_id = {p["findingId"]: p for p in priority}
        phase_order = ["immediate", "short-term", "long-term"]
        phase_labels = {
            "immediate": ("Immediate", "Critical/high severity items to address right away"),
            "short-term": ("Short-Term", "Medium severity items and quick wins"),
            "long-term": ("Long-Term", "Low severity and structural improvements"),
        }

        phases = []
        for phase_key in phase_order:
            items = [a for a in actions if a["phase"] == phase_key]
            if not items:
                continue
            name, description = phase_labels[phase_key]
            total_hours = sum(i["effortHours"] for i in items)
            phase_items = []
            for item in items:
                pr = priority_by_id.get(item["findingId"], {})
                phase_items.append({
                    "title": item["title"],
                    "action": item["action"],
                    "effort": pr.get("effort", "medium"),
                    "effortHours": item["effortHours"],
                    "steps": [],
                })
            phases.append({
                "name": name,
                "timeframe": phase_key.replace("-", " ").title(),
                "description": description,
                "totalHours": round(total_hours, 1),
                "items": phase_items,
            })
        return phases

    def _estimate_timeline(self, total_hours: float) -> str:
        if total_hours <= 0:
            return "No remediation work identified"
        days = total_hours / 6  # ~6 focused hours/day
        if days <= 1:
            return "Less than 1 day"
        if days <= 5:
            return f"{days:.0f} working days"
        weeks = days / 5
        return f"~{weeks:.1f} weeks"

    def _summarize_debt(self, groups: list[dict]) -> str:
        if not groups:
            return "No significant technical debt identified from the sampled files."
        top = sorted(groups, key=lambda g: len(g["findings"]), reverse=True)[:3]
        names = ", ".join(g["name"] for g in top)
        return f"Highest-concentration areas: {names}."

    def _roi_statement(self, overall_risk: str, total_findings: int) -> str:
        if total_findings == 0:
            return "No issues found in the sampled files; no remediation ROI to estimate."
        risk_language = {
            "Critical": "Addressing these findings is urgent — unresolved critical issues risk outages, breaches, or major rework.",
            "High": "Addressing these findings soon meaningfully reduces risk of incidents and future rework cost.",
            "Medium": "Addressing these findings improves maintainability and reduces the chance of compounding issues.",
            "Low": "These are largely polish items; addressing them improves code health incrementally.",
        }
        return risk_language.get(overall_risk, "Remediation reduces overall project risk and future maintenance cost.")
