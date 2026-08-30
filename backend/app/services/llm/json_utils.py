"""Shared JSON extraction + Pydantic validation for LLM parse output."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.schemas.llm_parse import ParsedReportResults, ParsedTestResult

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


class LLMOutputError(Exception):
    """Raised when model output is not valid JSON/schema."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def extract_json_text(content: str) -> str:
    text = content.strip()
    fence = _FENCE_RE.search(text)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_and_validate(content: str) -> list[ParsedTestResult]:
    raw = extract_json_text(content)
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"Invalid JSON: {exc}") from exc

    if isinstance(payload, list):
        payload = {"results": payload}

    try:
        model = ParsedReportResults.model_validate(payload)
    except ValidationError as exc:
        raise LLMOutputError(str(exc)) from exc
    return model.results
