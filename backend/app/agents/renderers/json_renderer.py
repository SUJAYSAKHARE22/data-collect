"""JSON renderer — ported from ReplexAgent's JsonRenderer.js."""
from __future__ import annotations

import json


class JsonRenderer:
    format = "json"
    mime_type = "application/json"

    def render(self, data: dict) -> dict:
        content = json.dumps(data, indent=2, ensure_ascii=False)
        return {
            "format": self.format,
            "content": content,
            "filename": self._slugify(data.get("projectName", "report")) + ".json",
            "mimeType": self.mime_type,
            "sizeBytes": len(content.encode("utf-8")),
        }

    @staticmethod
    def _slugify(text: str) -> str:
        import re

        return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", text.lower()))
