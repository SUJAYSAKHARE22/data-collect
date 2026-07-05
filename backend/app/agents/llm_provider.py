"""
LLM provider adapter for the AI Analysis Agent.

Talks to the Kimi K2 model via the NVIDIA NIM OpenAI-compatible
`/chat/completions` endpoint. Structure mirrors ReplexAgent's
BaseLlmProvider + NvidiaNimProvider (retry with exponential backoff,
timeout handling, JSON-mode support) but reimplemented in async Python.
"""
from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)

RETRYABLE_MARKERS = ("timeout", "rate limit", "429", "502", "503", "connection", "network")


class LlmProviderError(Exception):
    """Raised when the LLM provider fails after all retries."""


@dataclass
class LlmUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LlmCompletionResult:
    content: str
    usage: LlmUsage = field(default_factory=LlmUsage)
    model: str = ""
    finish_reason: str | None = None


class KimiProvider:
    """
    Kimi (moonshotai/kimi-k2.x) provider via the NVIDIA NIM API.
    OpenAI-compatible chat completions endpoint, with retry + backoff.
    """

    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        model: str = "moonshotai/kimi-k2.6",
        timeout_seconds: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def complete(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        top_p: float = 1.0,
        json_mode: bool = False,
    ) -> LlmCompletionResult:
        if not self.is_configured:
            raise LlmProviderError(
                "Kimi API key is not configured. Set KIMI_API_KEY in the backend .env file."
            )

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        attempts = self.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )

                if response.status_code >= 400:
                    body = response.text[:500]
                    raise LlmProviderError(
                        f"Kimi API error {response.status_code}: {body}"
                    )

                data = response.json()
                choices = data.get("choices") or []
                choice = choices[0] if choices else {}
                message = choice.get("message") or {}
                content = message.get("content") or ""
                usage_raw = data.get("usage") or {}

                logger.info(
                    "Kimi completion succeeded (model=%s, attempt=%d, tokens=%s)",
                    self.model,
                    attempt,
                    usage_raw,
                )

                return LlmCompletionResult(
                    content=content,
                    usage=LlmUsage(
                        prompt_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
                        completion_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
                        total_tokens=int(usage_raw.get("total_tokens", 0) or 0),
                    ),
                    model=data.get("model", self.model),
                    finish_reason=choice.get("finish_reason"),
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                retryable = any(marker in str(exc).lower() for marker in RETRYABLE_MARKERS)
                logger.warning(
                    "Kimi completion failed (attempt=%d/%d, retryable=%s): %s",
                    attempt,
                    attempts,
                    retryable,
                    exc,
                )
                if attempt < attempts and retryable:
                    delay = min(1.0 * (2 ** (attempt - 1)), 20.0)
                    delay += delay * 0.1 * random.random()
                    await asyncio.sleep(delay)
                    continue
                break

        raise LlmProviderError(
            f"Kimi provider failed after {attempts} attempt(s): {last_error}"
        )

    @staticmethod
    def parse_json_content(content: str) -> dict:
        """Best-effort extraction of a JSON object from model output."""
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as orig_exc:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass

            if start != -1:
                try:
                    return KimiProvider._repair_and_parse_truncated_json(text[start:])
                except json.JSONDecodeError:
                    pass

            raise orig_exc

    @staticmethod
    def _repair_and_parse_truncated_json(text: str, max_lookback: int = 4000) -> dict:
        """
        Reconstruct state-based representation of truncated JSON string,
        truncates back to a safe point, closes open brackets/braces, and returns parsed JSON dict.
        """
        text = text.strip()
        if not text:
            return {}

        states = [None] * (len(text) + 1)
        states[0] = ((), False, False)
        stack = []
        in_string = False
        escape = False
        for idx, char in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char in ('{', '['):
                    stack.append(char)
                elif char in ('}', ']'):
                    if stack:
                        top = stack[-1]
                        if (char == '}' and top == '{') or (char == ']' and top == '['):
                            stack.pop()
            states[idx + 1] = (tuple(stack), in_string, escape)

        start_idx = len(text)
        end_idx = max(0, start_idx - max_lookback)

        for i in range(start_idx, end_idx - 1, -1):
            stack_tuple, in_string, escape = states[i]
            sub = text[:i]

            suffix = ""
            if in_string:
                if escape:
                    sub = sub[:-1]
                suffix += '"'

            for sym in reversed(stack_tuple):
                if sym == '{':
                    suffix += '}'
                elif sym == '[':
                    suffix += ']'

            try:
                return json.loads(sub + suffix)
            except json.JSONDecodeError:
                continue

        raise json.JSONDecodeError("Failed to repair truncated JSON", text, 0)
