"""
Code Analysis Agent — the Python/Kimi equivalent of ReplexAgent's
WebsiteAuditAgent, adapted for source code instead of live websites.

Given a ProjectContext (collected metadata + budget-limited file content),
it prompts the Kimi K2 model to return a strict JSON "AuditReport" covering
architecture, code quality, security, dependencies, best practices, and
documentation. The JSON schema is enforced and re-requested once on
malformed output before failing, and every finding is later cross-checked
against the real file list by ConfidenceValidator so nothing hallucinated
about a nonexistent file makes it into the final report.
"""
from __future__ import annotations

import json

from app.agents.context_builder import ProjectContext, render_context_prompt
from app.agents.llm_provider import KimiProvider, LlmProviderError
from app.utils.logger import get_logger

logger = get_logger(__name__)

VALID_CATEGORIES = [
    "architecture",
    "code-quality",
    "security",
    "dependencies",
    "best-practice",
    "documentation",
    "performance",
]
VALID_SEVERITIES = ["critical", "high", "medium", "low", "info"]

SYSTEM_PROMPT = """You are a senior staff software engineer performing a rigorous, evidence-based code review.

You will be given collected metadata and a budget-limited sample of source files from a real project.

STRICT RULES:
1. Base every finding ONLY on the files and metadata actually shown to you. NEVER invent a file path, function name, or dependency that was not shown.
2. If a `file` field is included in a finding, it MUST exactly match one of the file paths shown in the "SOURCE FILES" section.
3. If you are not confident about something, lower its severity to "info" or omit it rather than guessing.
4. Respond with ONLY a single valid JSON object — no markdown fences, no commentary, no trailing text.
5. Follow the exact JSON schema given in the user message.
"""

USER_INSTRUCTIONS = """Analyze the project below and return a JSON object with this exact shape:

{
  "executiveSummary": {
    "overview": "2-4 sentence plain-English summary of the project and its overall health",
    "overallRisk": "Low" | "Medium" | "High" | "Critical",
    "topAction": "single most important next action, one sentence"
  },
  "findingGroups": [
    {
      "id": "kebab-case-id",
      "name": "Human readable group name",
      "category": one of {categories},
      "maxSeverity": one of {severities},
      "findings": [
        {
          "id": "kebab-case-id",
          "title": "short finding title",
          "severity": one of {severities},
          "category": one of {categories},
          "file": "exact/path/from/source/files (omit or null if project-wide)",
          "description": "what was found and why it matters",
          "recommendation": "concrete, actionable fix"
        }
      ]
    }
  ],
  "priorityMatrix": [
    {
      "findingId": "matches a finding id above",
      "title": "short title",
      "severity": one of {severities},
      "category": one of {categories},
      "priorityScore": number 0-10 (higher = more urgent),
      "effort": "low" | "medium" | "high",
      "effortHours": number
    }
  ],
  "actionPlan": [
    {
      "findingId": "matches a finding id above",
      "title": "short title",
      "action": "concrete next step",
      "severity": one of {severities},
      "effortHours": number,
      "phase": "immediate" | "short-term" | "long-term"
    }
  ]
}

Cover at least these categories where evidence supports it: architecture, code-quality, security, dependencies, best-practice, documentation, performance.
Aim for 6-16 total findings across all groups: fewer, well-evidenced findings are better than many speculative ones.

PROJECT DATA:
{context}
""".replace("{categories}", " | ".join(f'"{c}"' for c in VALID_CATEGORIES)).replace(
    "{severities}", " | ".join(f'"{s}"' for s in VALID_SEVERITIES)
)


class CodeAnalysisAgent:
    """Runs the LLM-powered audit and returns a raw (unvalidated) AuditReport dict."""

    id = "code-analysis-agent"
    name = "Code Analysis Agent"

    def __init__(self, provider: KimiProvider, max_tokens: int = 4096, temperature: float = 0.3) -> None:
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def run(self, ctx: ProjectContext) -> dict:
        context_text = render_context_prompt(ctx)
        user_prompt = USER_INSTRUCTIONS.replace("{context}", context_text)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None
        for attempt in (1, 2):
            try:
                result = await self.provider.complete(
                    messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    json_mode=True,
                )
                report = KimiProvider.parse_json_content(result.content)
                report["_llmUsage"] = {
                    "promptTokens": result.usage.prompt_tokens,
                    "completionTokens": result.usage.completion_tokens,
                    "totalTokens": result.usage.total_tokens,
                }
                report["_model"] = result.model or self.provider.model
                return report
            except (json.JSONDecodeError, LlmProviderError) as exc:
                last_error = exc
                logger.warning("Code analysis attempt %d failed: %s", attempt, exc)
                if attempt == 1:
                    messages.append(
                        {
                            "role": "user",
                            "content": "Your previous response was not valid JSON matching the schema. "
                            "Respond again with ONLY the corrected JSON object, nothing else.",
                        }
                    )
                    continue
                break

        raise LlmProviderError(f"Code analysis failed after retries: {last_error}")
