"""Qwen via DashScope SDK — structured parsing and patient-facing explanations."""

from __future__ import annotations

import asyncio
import logging
from http import HTTPStatus
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.schemas.llm_explain import ExplanationBundle
from app.schemas.llm_parse import ParsedTestResult
from app.services.llm.base import LLMService
from app.services.llm.explain_prompts import (
    build_explain_messages,
    build_explain_repair_messages,
)
from app.services.llm.explain_validate import validate_explanation_bundle
from app.services.llm.json_utils import LLMOutputError, extract_json_text, parse_and_validate
from app.services.llm.prompts import build_parse_messages, build_repair_messages

logger = logging.getLogger(__name__)


class QwenLLMService(LLMService):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.dashscope_api_key:
            raise AppError(
                code="llm_not_configured",
                message=(
                    "DASHSCOPE_API_KEY is not set. Add it to .env, or set "
                    "LLM_PROVIDER=offline for local fixture parsing without Qwen."
                ),
                status_code=503,
            )
        self._model = self._settings.dashscope_model

    def _call_sync(self, messages: list[dict[str, str]]) -> str:
        import dashscope
        from dashscope import Generation

        dashscope.api_key = self._settings.dashscope_api_key
        response = Generation.call(
            model=self._model,
            messages=messages,
            result_format="message",
            temperature=0.2,
        )
        if response.status_code != HTTPStatus.OK:
            raise AppError(
                code="llm_provider_error",
                message="DashScope/Qwen request failed.",
                status_code=502,
                details={
                    "provider_code": getattr(response, "code", None),
                    "provider_message": getattr(response, "message", None),
                },
            )
        try:
            return response.output.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise AppError(
                code="llm_empty_response",
                message="DashScope returned an unexpected response shape.",
                status_code=502,
            ) from exc

    async def _complete(self, messages: list[dict[str, str]]) -> str:
        return await asyncio.to_thread(self._call_sync, messages)

    async def parse_report(self, raw_text: str) -> list[ParsedTestResult]:
        if not raw_text or not raw_text.strip():
            raise AppError(
                code="empty_ocr_text",
                message="Cannot parse an empty OCR text.",
                status_code=400,
            )

        first = await self._complete(build_parse_messages(raw_text))
        try:
            return parse_and_validate(first)
        except LLMOutputError as first_error:
            logger.info("LLM parse validation failed; retrying once with repair prompt")
            repair = await self._complete(
                build_repair_messages(
                    raw_text=raw_text,
                    bad_json=extract_json_text(first),
                    validation_error=first_error.message,
                )
            )
            try:
                return parse_and_validate(repair)
            except LLMOutputError as second_error:
                raise AppError(
                    code="llm_parse_failed",
                    message="Could not parse lab results into valid structured JSON.",
                    status_code=422,
                    details={"validation_error": second_error.message},
                ) from second_error

    async def explain_results(
        self, test_results: list[dict[str, Any]]
    ) -> ExplanationBundle:
        if not test_results:
            raise AppError(
                code="explain_empty_input",
                message="No test results available to explain.",
                status_code=400,
            )

        expected_ids = {UUID(str(row["id"])) for row in test_results}
        first = await self._complete(build_explain_messages(test_results))
        try:
            return validate_explanation_bundle(first, expected_ids=expected_ids)
        except LLMOutputError as first_error:
            logger.info("LLM explain validation failed; retrying once")
            repair = await self._complete(
                build_explain_repair_messages(
                    test_results=test_results,
                    bad_json=extract_json_text(first),
                    validation_error=first_error.message,
                )
            )
            try:
                return validate_explanation_bundle(repair, expected_ids=expected_ids)
            except LLMOutputError as second_error:
                raise AppError(
                    code="llm_explain_failed",
                    message="Could not generate validated patient-facing explanations.",
                    status_code=422,
                    details={"validation_error": second_error.message},
                ) from second_error
