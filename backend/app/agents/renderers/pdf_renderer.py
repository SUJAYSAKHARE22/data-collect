"""
PDF renderer.

ReplexAgent's HtmlRenderer produces PDF-compatible HTML with the intent that
it be converted via a headless browser / print pipeline. This renderer
implements that same HTML -> PDF conversion server-side in Python, using
xhtml2pdf (pure Python, no system-level browser/binary dependency), so the
"Download PDF" feature works out of the box after `pip install -r requirements.txt`.
"""
from __future__ import annotations

import io
import re

from xhtml2pdf import pisa


class PdfRenderer:
    format = "pdf"
    mime_type = "application/pdf"

    def render(self, html_content: str, project_name: str = "report") -> dict:
        # xhtml2pdf doesn't support some modern CSS (flexbox, box-shadow); strip
        # the parts it can't parse gracefully so layout still renders sanely.
        pdf_safe_html = self._make_pdf_safe(html_content)

        buffer = io.BytesIO()
        result = pisa.CreatePDF(src=pdf_safe_html, dest=buffer)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        if result.err:
            raise RuntimeError("Failed to render PDF from report HTML")

        return {
            "format": self.format,
            "content": pdf_bytes,
            "filename": self._slugify(project_name) + "-report.pdf",
            "mimeType": self.mime_type,
            "sizeBytes": len(pdf_bytes),
        }

    @staticmethod
    def _make_pdf_safe(html_content: str) -> str:
        safe = html_content
        safe = re.sub(r"display:\s*flex;?", "", safe)
        safe = re.sub(r"box-shadow:[^;]+;?", "", safe)
        safe = re.sub(r"gap:\s*[^;]+;?", "", safe)
        safe = re.sub(r"letter-spacing:[^;]+;?", "", safe)
        return safe

    @staticmethod
    def _slugify(text: str) -> str:
        return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))
