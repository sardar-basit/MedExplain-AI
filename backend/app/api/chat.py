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
    report = None
    try:
        report = await db.scalar(
            select(Report)
            .where(Report.id == body.report_id)
            .options(selectinload(Report.test_results))
        )
    except Exception as db_exc:
        logger.warning("SQLAlchemy chat query note: %s", db_exc)

    if report is None:
        try:
            try:
                from db.supabase_client import get_supabase_client
            except ImportError:
                from backend.db.supabase_client import get_supabase_client

            sb_client = get_supabase_client()
            if sb_client:
                rep_res = sb_client.table("reports").select("*").eq("id", str(body.report_id)).execute()
                if rep_res.data:
                    r_data = rep_res.data[0]
                    tr_res = sb_client.table("test_results").select("*").eq("report_id", str(body.report_id)).execute()

                    from app.models import ResultStatus, TestResult
                    report = Report(
                        id=UUID(r_data["id"]),
                        user_id=UUID(r_data["user_id"]),
                        file_url=r_data["file_url"],
                        report_type=r_data.get("report_type", "explained"),
                        ai_summary=r_data.get("ai_summary"),
                        raw_text=r_data.get("raw_text"),
                        result_explanations=r_data.get("result_explanations"),
                    )
                    test_results = []
                    for tr in (tr_res.data or []):
                        st_enum = ResultStatus.NORMAL
                        raw_st = str(tr.get("status", "NORMAL")).upper()
                        if "HIGH" in raw_st:
                            st_enum = ResultStatus.HIGH
                        elif "LOW" in raw_st:
                            st_enum = ResultStatus.LOW

                        test_results.append(
                            TestResult(
                                id=UUID(tr["id"]),
                                report_id=UUID(tr["report_id"]),
                                marker_name=tr.get("biomarker") or tr.get("marker_name", "Unknown"),
                                value=tr.get("value"),
                                value_text=tr.get("value_text"),
                                unit=tr.get("unit", ""),
                                reference_min=tr.get("reference_min"),
                                reference_max=tr.get("reference_max"),
                                status=st_enum,
                            )
                        )
                    report.test_results = test_results
        except Exception as sb_err:
            logger.warning("Supabase REST chat fallback note: %s", sb_err)

    if report is None:
        # If RAG can still process directly via Groq/Gemini, attempt rag_service query before raising
        try:
            try:
                from services.rag_service import query_report
            except ImportError:
                from backend.services.rag_service import query_report
            rag_res = await query_report(report_id=body.report_id, user_question=body.message)
            answer_text = rag_res.get("answer", "")
            if answer_text:
                return ChatResponse(answer=answer_text, used_chunks=rag_res.get("used_chunks", ["rag_context"]))
        except Exception:
            pass

        raise AppError(
            code="report_not_found",
            message="Report not found.",
            status_code=404,
        )

    if report.report_type not in {"explained", "parsed", "parsing_failed"}:
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

    # --- 4. Call the RAG service / Gemini query_report ---
    try:
        try:
            from services.rag_service import query_report
        except ImportError:
            from backend.services.rag_service import query_report
        rag_res = await query_report(report_id=body.report_id, user_question=body.message)
        answer_text = rag_res.get("answer", "")
        used_chunks = rag_res.get("used_chunks", ["rag_context"])
        return ChatResponse(answer=answer_text, used_chunks=used_chunks)
    except Exception as exc:
        logger.warning("RAG service query_report fallback: %s", exc)

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
