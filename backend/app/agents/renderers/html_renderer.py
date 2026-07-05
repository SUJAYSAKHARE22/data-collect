"""
HTML renderer — ported from ReplexAgent's HtmlRenderer.js.

Produces self-contained HTML with inline CSS. This same HTML is what the
PDF renderer converts to PDF (identical method to how ReplexAgent's
HtmlRenderer output is described as "PDF compatible" for browser-print /
headless conversion).
"""
from __future__ import annotations

import html
import re


class HtmlRenderer:
    format = "html"
    mime_type = "text/html"

    def render(self, data: dict) -> dict:
        content = "\n".join([
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="UTF-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f"<title>{self._esc(data['title'])}</title>",
            "<style>", self._css(), "</style>",
            "</head>",
            "<body>",
            '<div class="container">',
            self._header(data),
            self._confidence_badge(data["overallConfidence"], "Overall Confidence"),
            self._executive(data["executive"]),
            self._developer(data["developer"]),
            self._business(data["business"]),
            self._roadmap(data["roadmap"]),
            self._footer(data),
            "</div>",
            "</body>",
            "</html>",
        ])
        return {
            "format": self.format,
            "content": content,
            "filename": self._slugify(data.get("projectName", "report")) + ".html",
            "mimeType": self.mime_type,
            "sizeBytes": len(content.encode("utf-8")),
        }

    def _header(self, data: dict) -> str:
        return f"""
      <header class="report-header">
        <h1>{self._esc(data['title'])}</h1>
        <div class="meta">
          <span><strong>Source:</strong> {self._esc(data.get('url', 'N/A'))}</span>
          <span><strong>Generated:</strong> {self._esc(data['generatedAt'])}</span>
        </div>
      </header>"""

    def _confidence_badge(self, confidence: dict, label: str) -> str:
        pct = round(confidence["score"] * 100)
        cls = "high" if confidence["score"] >= 0.8 else "medium" if confidence["score"] >= 0.5 else "low"
        excluded_html = ""
        if confidence["excludedDataPoints"]:
            items = "".join(f"<li>{self._esc(e)}</li>" for e in confidence["excludedDataPoints"])
            excluded_html = (
                f'<details class="excluded"><summary>Excluded data '
                f'({len(confidence["excludedDataPoints"])})</summary><ul>{items}</ul></details>'
            )
        return f"""
      <div class="confidence-badge {cls}">
        <span class="label">{self._esc(label)}</span>
        <span class="score">{pct}%</span>
        <span class="rationale">{self._esc(confidence['rationale'])}</span>
        {excluded_html}
      </div>"""

    def _executive(self, exec_data: dict) -> str:
        sev_html = "".join(
            f'<span class="severity-badge {sev}">{sev.title()}: {count}</span> '
            for sev, count in exec_data["bySeverity"].items() if count > 0
        )
        cat_rows = "".join(
            f"<tr><td>{self._fmt_category(cat)}</td><td>{count}</td></tr>"
            for cat, count in exec_data["byCategory"].items() if count > 0
        )
        return f"""
      <section class="report-section executive">
        <h2>Executive Summary</h2>
        <p class="overview">{self._esc(exec_data['overview'])}</p>
        <div class="risk-card">
          <div class="risk-label">Overall Risk</div>
          <div class="risk-value">{self._esc(exec_data['overallRisk'])}</div>
        </div>
        <div class="stats-row">
          <div class="stat"><span class="stat-value">{exec_data['totalFindings']}</span><span class="stat-label">Total Findings</span></div>
          <div class="stat"><span class="stat-value">{self._esc(exec_data['estimatedTimeline'])}</span><span class="stat-label">Timeline</span></div>
        </div>
        <div class="top-action"><strong>Top Action:</strong> {self._esc(exec_data['topAction'])}</div>
        <h3>By Severity</h3>
        <div class="severity-badges">{sev_html}</div>
        <h3>By Category</h3>
        <table class="data-table"><thead><tr><th>Category</th><th>Count</th></tr></thead><tbody>{cat_rows}</tbody></table>
        {self._confidence_badge(exec_data['confidence'], 'Section Confidence')}
      </section>"""

    def _developer(self, dev: dict) -> str:
        group_html = ""
        for g in dev["groups"]:
            finding_items = []
            for f in g["findings"]:
                file_html = f' <code>{self._esc(f["file"])}</code>' if f.get("file") else ""
                finding_items.append(
                    f'<li class="finding-item"><span class="finding-title">{self._esc(f["title"])}</span> '
                    f'<span class="severity-badge {f["severity"]}">{f["severity"].title()}</span>'
                    f'{file_html}<br>'
                    f'<span class="finding-desc">{self._esc(f["description"])}</span><br>'
                    f'<span class="recommendation">Recommendation: {self._esc(f["recommendation"])}</span></li>'
                )
            finding_html = "".join(finding_items)
            group_html += (
                f'<div class="finding-group"><h4>{self._esc(g["name"])} '
                f'<span class="count">({g["count"]} findings)</span></h4>'
                f'<ul class="findings-list">{finding_html}</ul></div>'
            )

        quick_wins_html = (
            f'<ul class="quick-wins">{"".join(f"<li>{self._esc(q)}</li>" for q in dev["quickWins"])}</ul>'
            if dev["quickWins"] else "<p>No quick wins identified.</p>"
        )

        return f"""
      <section class="report-section developer">
        <h2>Developer Report</h2>
        <p class="overview">{self._esc(dev['overview'])}</p>
        <h3>Technical Debt</h3>
        <p>{self._esc(dev['technicalDebt'])}</p>
        <h3>Quick Wins</h3>
        {quick_wins_html}
        <h3>Finding Groups</h3>
        {group_html}
        {self._confidence_badge(dev['confidence'], 'Section Confidence')}
      </section>"""

    def _business(self, biz: dict) -> str:
        rows = "".join(
            f"<tr><td>{self._esc(item['title'])}</td>"
            f'<td><span class="impact-badge {item["severity"]}">{item["severity"].title()}</span></td>'
            f"<td>{item['effort'].title()}</td><td>{item['effortHours']}h</td>"
            f"<td>{item['priorityScore']:.1f}</td></tr>"
            for item in biz["impactSummary"]
        )
        return f"""
      <section class="report-section business">
        <h2>Business Summary</h2>
        <p class="overview">{self._esc(biz['overview'])}</p>
        <div class="financials">
          <div class="stat"><span class="stat-value">{biz['totalEffortHours']}h</span><span class="stat-label">Total Effort</span></div>
          <div class="stat"><span class="stat-value">${biz['estimatedCost']:,}</span><span class="stat-label">Estimated Cost</span></div>
        </div>
        <h3>ROI</h3>
        <p>{self._esc(biz['roi'])}</p>
        <h3>Impact Summary</h3>
        <table class="data-table">
          <thead><tr><th>Finding</th><th>Severity</th><th>Effort</th><th>Hours</th><th>Priority</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        {self._confidence_badge(biz['confidence'], 'Section Confidence')}
      </section>"""

    def _roadmap(self, roadmap: dict) -> str:
        phase_html = ""
        for p in roadmap["phases"]:
            items_html = "".join(
                f'<li class="roadmap-item"><strong>{self._esc(i["title"])}</strong> '
                f'<span class="effort-badge">{i["effort"].title()} — {i["effortHours"]}h</span>'
                f'<p>{self._esc(i["action"])}</p></li>'
                for i in p["items"]
            )
            phase_html += (
                f'<div class="roadmap-phase"><h4>{self._esc(p["name"])}</h4>'
                f'<div class="phase-meta"><span class="timeframe">{self._esc(p["timeframe"])}</span> — {self._esc(p["description"])}</div>'
                f'<div class="phase-hours">{p["totalHours"]} hours</div>'
                f'<ul class="phase-items">{items_html}</ul></div>'
            )
        return f"""
      <section class="report-section roadmap">
        <h2>Implementation Roadmap</h2>
        <p class="overview">{self._esc(roadmap['overview'])}</p>
        <div class="stats-row">
          <div class="stat"><span class="stat-value">{roadmap['totalEstimatedHours']}h</span><span class="stat-label">Total Hours</span></div>
          <div class="stat"><span class="stat-value">{self._esc(roadmap['estimatedTimeline'])}</span><span class="stat-label">Timeline</span></div>
        </div>
        {phase_html}
        {self._confidence_badge(roadmap['confidence'], 'Section Confidence')}
      </section>"""

    def _footer(self, data: dict) -> str:
        pct = round(data["overallConfidence"]["score"] * 100)
        return f"""
      <footer class="report-footer">
        <p>Report generated by the AI Analysis Agent (Kimi K2)</p>
        <p class="confidence-footer">Confidence: {pct}% — {self._esc(data['overallConfidence']['rationale'])}</p>
      </footer>"""

    def _css(self) -> str:
        return """
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1a1a2e; background: #f8f9fa; }
      .container { max-width: 900px; margin: 0 auto; padding: 2rem; }
      .report-header { text-align: center; margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 3px solid #0f3460; }
      .report-header h1 { font-size: 1.8rem; color: #0f3460; margin-bottom: 0.5rem; }
      .meta { display: flex; gap: 2rem; justify-content: center; color: #666; font-size: 0.9rem; flex-wrap: wrap; }
      .report-section { background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
      .report-section h2 { color: #0f3460; font-size: 1.4rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #e94560; }
      .report-section h3 { color: #16213e; margin: 1.2rem 0 0.6rem; font-size: 1.1rem; }
      .report-section h4 { color: #0f3460; margin: 1rem 0 0.4rem; }
      .overview { color: #444; margin-bottom: 1rem; }
      .risk-card { background: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; margin: 1rem 0; border-radius: 4px; }
      .risk-label { font-size: 0.8rem; text-transform: uppercase; color: #856404; letter-spacing: 0.05em; }
      .risk-value { font-size: 1.2rem; font-weight: 600; color: #856404; }
      .stats-row { display: flex; gap: 1.5rem; margin: 1rem 0; }
      .stat { text-align: center; flex: 1; padding: 0.8rem; background: #f1f3f5; border-radius: 6px; }
      .stat-value { display: block; font-size: 1.3rem; font-weight: 700; color: #0f3460; }
      .stat-label { display: block; font-size: 0.75rem; color: #666; text-transform: uppercase; letter-spacing: 0.05em; }
      .top-action { padding: 0.8rem; background: #e8f4f8; border-radius: 4px; margin: 1rem 0; }
      .data-table { width: 100%; border-collapse: collapse; margin: 0.8rem 0; }
      .data-table th, .data-table td { padding: 0.5rem 0.8rem; text-align: left; border-bottom: 1px solid #e9ecef; }
      .data-table th { background: #f1f3f5; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.03em; }
      .severity-badge, .impact-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.8rem; font-weight: 600; }
      .severity-badge.critical, .impact-badge.critical { background: #dc3545; color: #fff; }
      .severity-badge.high, .impact-badge.high { background: #fd7e14; color: #fff; }
      .severity-badge.medium, .impact-badge.medium { background: #ffc107; color: #212529; }
      .severity-badge.low, .impact-badge.low { background: #28a745; color: #fff; }
      .severity-badge.info, .impact-badge.info { background: #17a2b8; color: #fff; }
      .severity-badges { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0; }
      .finding-group { margin: 1rem 0; padding: 0.8rem; background: #f8f9fa; border-radius: 6px; border-left: 3px solid #0f3460; }
      .finding-group h4 { margin-bottom: 0.5rem; }
      .count { font-weight: normal; color: #666; font-size: 0.85rem; }
      .findings-list { list-style: none; padding: 0; }
      .finding-item { padding: 0.5rem 0; border-bottom: 1px solid #e9ecef; }
      .finding-title { font-weight: 600; }
      .finding-desc { color: #444; font-size: 0.9rem; }
      .recommendation { color: #1a7f37; font-size: 0.9rem; }
      .quick-wins { margin: 0.5rem 0; }
      .quick-wins li { padding: 0.3rem 0; color: #28a745; }
      .financials { display: flex; gap: 1.5rem; margin: 1rem 0; }
      .effort-badge { display: inline-block; padding: 0.1rem 0.4rem; background: #e9ecef; border-radius: 3px; font-size: 0.8rem; margin-left: 0.5rem; }
      .roadmap-phase { margin: 1.5rem 0; padding: 1rem; background: #f8f9fa; border-radius: 6px; border-left: 4px solid #e94560; }
      .phase-meta { color: #666; font-size: 0.9rem; margin-bottom: 0.5rem; }
      .timeframe { font-weight: 600; color: #0f3460; }
      .phase-hours { font-weight: 600; color: #e94560; margin-bottom: 0.5rem; }
      .phase-items { list-style: none; padding: 0; }
      .roadmap-item { padding: 0.6rem 0; border-bottom: 1px solid #e9ecef; }
      .roadmap-item p { margin: 0.3rem 0 0; color: #555; font-size: 0.9rem; }
      .confidence-badge { margin: 1rem 0; padding: 0.8rem; border-radius: 6px; font-size: 0.85rem; }
      .confidence-badge.high { background: #d4edda; border-left: 4px solid #28a745; }
      .confidence-badge.medium { background: #fff3cd; border-left: 4px solid #ffc107; }
      .confidence-badge.low { background: #f8d7da; border-left: 4px solid #dc3545; }
      .confidence-badge .label { font-weight: 600; display: block; }
      .confidence-badge .score { font-size: 1.1rem; font-weight: 700; }
      .confidence-badge .rationale { display: block; color: #555; margin-top: 0.3rem; }
      .excluded { margin-top: 0.5rem; }
      .excluded ul { margin: 0.3rem 0 0 1rem; font-size: 0.8rem; color: #888; }
      .report-footer { text-align: center; padding: 1.5rem; color: #666; font-size: 0.85rem; border-top: 2px solid #e9ecef; margin-top: 1rem; }
      .confidence-footer { font-style: italic; margin-top: 0.3rem; }
      code { background: #eef1f4; padding: 0.05rem 0.35rem; border-radius: 3px; font-size: 0.85em; }
      @media print { .container { max-width: 100%; padding: 1rem; } .report-section { break-inside: avoid; box-shadow: none; border: 1px solid #ddd; } }
      @media (max-width: 600px) { .container { padding: 1rem; } .stats-row, .financials { flex-direction: column; } .meta { flex-direction: column; gap: 0.3rem; } }
    """

    @staticmethod
    def _esc(value) -> str:
        if value is None:
            return ""
        return html.escape(str(value), quote=True)

    @staticmethod
    def _fmt_category(cat: str) -> str:
        mapping = {
            "seo": "SEO", "security": "Security", "performance": "Performance",
            "architecture": "Architecture", "code-quality": "Code Quality",
            "dependencies": "Dependencies", "best-practice": "Best Practice",
            "documentation": "Documentation",
        }
        return mapping.get(cat, cat.replace("-", " ").title())

    @staticmethod
    def _slugify(text: str) -> str:
        return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))
