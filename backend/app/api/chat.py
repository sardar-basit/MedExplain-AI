"""Chat endpoint — POST /api/v1/chat."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.errors import AppError
from app.models import Report
from app.schemas import ChatRequest, ChatResponse
from app.services.chat import ConversationTurn, get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Maximum history turns forwarded to the LLM (last N turns = last 2N messages)
_MAX_HISTORY_TURNS = 6


def _chat_service_dep():
    return get_chat_service()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    chat_svc=Depends(_chat_service_dep),
) -> ChatResponse:
    """Answer a question grounded in the specified report's full database context."""
    # --- 1. Validate report exists and load results ---
    report = await db.scalar(
        select(Report)
        .where(Report.id == body.report_id)
        .options(selectinload(Report.test_results))
    )
    if report is None:
        raise AppError(
            code="report_not_found",
            message="Report not found.",
            status_code=404,
        )

    if report.report_type not in {"explained", "parsed"}:
        raise AppError(
            code="report_not_ready",
            message=(
                "This report has not finished processing yet. "
                "Please wait until the status is 'parsed' or 'explained'."
            ),
            status_code=409,
        )

    # --- 2. Construct report context ---
    results_str = ""
    for r in report.test_results:
        val_str = r.value_text if r.value_text else (str(r.value) if r.value is not None else "—")
        ref_str = f" (ref {r.reference_min} - {r.reference_max})" if (r.reference_min is not None or r.reference_max is not None) else ""
        results_str += f"- {r.marker_name}: {val_str} {r.unit}{ref_str} | Status: {r.status.value if hasattr(r.status, 'value') else str(r.status)}\n"

    report_context = (
        f"REPORT SUMMARY:\n{report.ai_summary or 'None'}\n\n"
        f"STRUCTURED LAB RESULTS:\n{results_str}\n"
        f"RAW OCR TEXT:\n{report.raw_text or 'None'}"
    )

    # --- 3. Bound and convert history ---
    history_turns = body.conversation_history[-(_MAX_HISTORY_TURNS * 2):]
    history = [
        ConversationTurn(role=t.role, content=t.content)
        for t in history_turns
    ]

    # --- 4. Call the chat service ---
    result = await chat_svc.answer(
        report_id=body.report_id,
        message=body.message,
        report_context=report_context,
        history=history,
    )

    logger.info(
        "chat: report=%s context_len=%d answer_len=%d",
        body.report_id,
        len(report_context),
        len(result.answer),
    )

    return ChatResponse(answer=result.answer, used_chunks=["full_report_context"])
