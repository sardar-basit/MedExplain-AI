"""Orchestrate OCR text → LLM parse → reference flags → explanations → DB."""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Report, TestResult
from app.services.llm.base import LLMService
from app.services.reference_range import ReferenceRangeService

logger = logging.getLogger(__name__)


def _rows_for_explain(rows: list[TestResult]) -> list[dict]:
    return [
        {
            "id": str(row.id),
            "marker_name": row.marker_name,
            "value": row.value,
            "value_text": row.value_text,
            "unit": row.unit,
            "reference_min": row.reference_min,
            "reference_max": row.reference_max,
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        }
        for row in rows
    ]


async def apply_parsed_results(
    *,
    db: AsyncSession,
    report: Report,
    llm: LLMService,
    ranges: ReferenceRangeService | None = None,
) -> Report:
    """Parse report.raw_text, insert test_results, then generate explanations."""
    range_service = ranges or ReferenceRangeService()
    raw_text = report.raw_text or ""

    try:
        parsed = await llm.parse_report(raw_text)
    except AppError as exc:
        if exc.code in {
            "llm_parse_failed",
            "empty_ocr_text",
            "llm_provider_error",
            "llm_empty_response",
            "llm_not_configured",
        }:
            report.report_type = "parsing_failed"
            await db.commit()
            await db.refresh(report)
            return report
        raise

    rows: list[TestResult] = []
    for item in parsed:
        status = range_service.compute_status(
            value=item.value,
            reference_min=item.reference_min,
            reference_max=item.reference_max,
            llm_status=item.status,
        )
        rows.append(
            TestResult(
                id=uuid.uuid4(),
                report_id=report.id,
                marker_name=item.test_name,
                value=item.value,
                value_text=item.value_text,
                unit=item.unit or "",
                reference_min=item.reference_min,
                reference_max=item.reference_max,
                status=status,
            )
        )

    db.add_all(rows)
    report.report_type = "parsed"
    await db.commit()

    try:
        bundle = await llm.explain_results(_rows_for_explain(rows))
        report.ai_summary = bundle.overall_summary
        report.result_explanations = [
            item.model_dump(mode="json") for item in bundle.per_result_explanations
        ]
        report.doctor_questions = bundle.doctor_questions
        report.report_type = "explained"
    except AppError as exc:
        logger.warning("Explanation step failed for report %s: %s", report.id, exc.code)
        # Keep parsed rows visible; explanations remain null.
        report.report_type = "parsed"

    await db.commit()
    await db.refresh(report)

    return report
