"""Validate LLM explanation JSON into ExplanationBundle."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.schemas.llm_explain import ExplanationBundle
from app.services.llm.json_utils import LLMOutputError, extract_json_text

DISCLAIMER = (
    "This is educational only — please consult a licensed healthcare professional "
    "about your results."
)

_DIAGNOSTIC_PATTERNS = (
    "you have ",
    "this means you have",
    "this confirms",
    "you are diagnosed",
    "diagnosis is",
    "take ",
    "mg ",
    "dosage",
    "prescribe",
    "medication",
    "should start",
    "treat with",
)


def _assert_safe_language(bundle: ExplanationBundle) -> None:
    texts = [bundle.overall_summary, *bundle.doctor_questions]
    texts.extend(item.explanation for item in bundle.per_result_explanations)
    lowered = " ".join(texts).lower()
    for pattern in _DIAGNOSTIC_PATTERNS:
        # Allow "your doctor" / "conditions such as" style language; block hard diagnoses.
        if pattern in {"you have ", "this means you have", "this confirms", "you are diagnosed"}:
            if pattern in lowered:
                raise LLMOutputError(
                    f"Explanation language violates non-diagnosis rule (matched: {pattern!r})."
                )
        if pattern in {"dosage", "prescribe", "medication", "treat with", "should start"}:
            if pattern in lowered:
                raise LLMOutputError(
                    f"Explanation language violates no-treatment rule (matched: {pattern!r})."
                )


def _ensure_disclaimer(summary: str) -> str:
    text = summary.strip()
    if DISCLAIMER.lower() not in text.lower():
        if not text.endswith("."):
            text += "."
        text = f"{text} {DISCLAIMER}"
    return text


def validate_explanation_bundle(
    content: str,
    *,
    expected_ids: set[UUID],
) -> ExplanationBundle:
    raw = extract_json_text(content)
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"Invalid JSON: {exc}") from exc

    try:
        bundle = ExplanationBundle.model_validate(payload)
    except ValidationError as exc:
        raise LLMOutputError(str(exc)) from exc

    returned_ids = {item.test_result_id for item in bundle.per_result_explanations}
    if returned_ids != expected_ids:
        missing = expected_ids - returned_ids
        extra = returned_ids - expected_ids
        raise LLMOutputError(
            f"Explanation IDs mismatch. missing={sorted(str(x) for x in missing)} "
            f"extra={sorted(str(x) for x in extra)}"
        )

    bundle.overall_summary = _ensure_disclaimer(bundle.overall_summary)
    _assert_safe_language(bundle)
    return bundle
