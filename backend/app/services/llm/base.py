"""Pluggable LLM interface for structured report parsing and explanations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.llm_explain import ExplanationBundle
from app.schemas.llm_parse import ParsedTestResult


class LLMService(ABC):
    @abstractmethod
    async def parse_report(self, raw_text: str) -> list[ParsedTestResult]:
        """Extract structured test rows from OCR text. Must not invent values."""

    @abstractmethod
    async def explain_results(
        self, test_results: list[dict[str, Any]]
    ) -> ExplanationBundle:
        """Generate patient-facing explanations (educational, non-diagnostic)."""
