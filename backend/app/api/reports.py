"""Upload and report API routes."""

from __future__ import annotations

import asyncio
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.errors import AppError
from app.core.upload_validation import (
    MAX_UPLOAD_BYTES,
    validate_magic_bytes,
    validate_upload_size,
)
from app.models import Report, User
from app.schemas import ReportDetail, ReportRawTextResponse, UploadResponse
from app.services.llm import LLMService, get_llm_service
from app.services.ocr import OCRService, get_ocr_service
from app.services.report_parser import apply_parsed_results
from app.services.storage import StorageService, get_storage_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["reports"])


def _storage_dep() -> StorageService:
    return get_storage_service()


def _ocr_dep() -> OCRService:
    return get_ocr_service()


def _llm_dep() -> LLMService:
    return get_llm_service()


@router.post("/upload", response_model=UploadResponse)
async def upload_report(
    file: UploadFile = File(...),
    user_id_param: str | None = Form(None, alias="user_id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(_storage_dep),
    ocr: OCRService = Depends(_ocr_dep),
    llm: LLMService = Depends(_llm_dep),
) -> UploadResponse:
    if file.size is not None:
        validate_upload_size(file.size)

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    validate_upload_size(len(data))

    detected = validate_magic_bytes(data[:16])
    # Run Storage Upload and Gemini AI Extraction concurrently in parallel to minimize latency
    from starlette.concurrency import run_in_threadpool

    def _safe_extract(raw_data: bytes, m_type: str):
        try:
            try:
                from services.ai_service import extract_medical_report
            except ImportError:
                from backend.services.ai_service import extract_medical_report
            return extract_medical_report(raw_data, m_type)
        except Exception as exc:
            logger.warning("Gemini multimodal extraction notice: %s", exc)
            return None

    save_task = asyncio.create_task(
        storage.save(
            data=data,
            extension=detected.extension,
            content_type=detected.media_type,
        )
    )
    extract_task = asyncio.create_task(
        run_in_threadpool(_safe_extract, data, detected.media_type)
    )

    file_url, gemini_data = await asyncio.gather(save_task, extract_task)

    raw_text: str | None = gemini_data.get("summary") if gemini_data else None
    ocr_failed = False

    # 2. Fallback to Tesseract OCR only if Gemini extraction was empty
    if not gemini_data:
        try:
            ocr_result = await ocr.extract(file_url)
            raw_text = ocr_result.raw_text
        except AppError as exc:
            if exc.code in {
                "ocr_empty_result",
                "ocr_empty_pdf",
                "ocr_failed",
                "ocr_unsupported_type",
                "tesseract_not_found",
                "file_not_found",
            }:
                ocr_failed = True
                raw_text = None
            else:
                raise

    ai_summary = gemini_data.get("summary") if gemini_data else None

    raw_user_id = x_user_id or user_id_param
    user_id: uuid.UUID
    if raw_user_id:
        try:
            user_id = uuid.UUID(raw_user_id)
        except ValueError:
            user_id = uuid.uuid4()
    else:
        user_id = uuid.uuid4()

    report_id = uuid.uuid4()

    # Build result_explanations array for card popups
    result_explanations = []
    tr_batch = []
    if gemini_data and "biomarkers" in gemini_data and isinstance(gemini_data["biomarkers"], list):
        for item in gemini_data["biomarkers"]:
            tr_id = str(uuid.uuid4())
            bm = str(item.get("biomarker") or item.get("marker_name") or "Unknown Biomarker")
            raw_st = str(item.get("status", "NORMAL")).upper()
            st_val = "NORMAL"
            if "HIGH" in raw_st:
                st_val = "HIGH"
            elif "LOW" in raw_st:
                st_val = "LOW"

            val = item.get("value")
            if val is not None:
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = None

            val_txt = str(item.get("value_text") or (val if val is not None else ""))
            unit = str(item.get("unit") or "")

            ref_min = item.get("reference_min")
            if ref_min is not None:
                try:
                    ref_min = float(ref_min)
                except (ValueError, TypeError):
                    ref_min = None

            ref_max = item.get("reference_max")
            if ref_max is not None:
                try:
                    ref_max = float(ref_max)
                except (ValueError, TypeError):
                    ref_max = None

            expl = item.get("explanation")
            if not expl:
                ref_str = f"{ref_min}–{ref_max}" if (ref_min is not None and ref_max is not None) else "listed reference range"
                if st_val == "HIGH":
                    expl = f"{bm} ({val_txt} {unit}) is higher than the {ref_str}. High levels should be discussed with your physician."
                elif st_val == "LOW":
                    expl = f"{bm} ({val_txt} {unit}) is lower than the {ref_str}. Low levels should be reviewed by your physician."
                else:
                    expl = f"{bm} ({val_txt} {unit}) is within normal parameters."

            result_explanations.append({
                "test_result_id": tr_id,
                "biomarker": bm,
                "explanation": expl,
            })

            tr_batch.append({
                "id": tr_id,
                "report_id": str(report_id),
                "biomarker": bm,
                "value": val,
                "value_text": val_txt,
                "unit": unit,
                "reference_min": ref_min,
                "reference_max": ref_max,
                "status": st_val,
            })

    # Save report metadata and test results to DB via Supabase REST API
    saved_via_supabase = False
    try:
        from db.supabase_client import get_supabase_client
    except ImportError:
        from backend.db.supabase_client import get_supabase_client

    sb_client = get_supabase_client()
    if sb_client:
        try:
            try:
                sb_client.table("users").upsert({"id": str(user_id)}).execute()
            except Exception as u_exc:
                logger.warning("Supabase user insert note: %s", u_exc)

            rep_row = {
                "id": str(report_id),
                "user_id": str(user_id),
                "file_url": file_url,
                "report_type": "explained" if (gemini_data or not ocr_failed) else "parsing_failed",
                "ai_summary": ai_summary,
                "raw_text": raw_text,
                "result_explanations": result_explanations,
            }
            sb_client.table("reports").upsert(rep_row).execute()

            if tr_batch:
                sb_client.table("test_results").insert(tr_batch).execute()

            saved_via_supabase = True
            logger.info("Persisted report %s with %d explanations via Supabase REST API", report_id, len(result_explanations))
        except Exception as sb_err:
            logger.warning("Supabase REST API insert failed, falling back to SQLAlchemy: %s", sb_err)

    if not saved_via_supabase:
        try:
            existing_user = await db.scalar(select(User).where(User.id == user_id))
            if not existing_user:
                user = User(id=user_id)
                db.add(user)

            report = Report(
                id=report_id,
                user_id=user_id,
                file_url=file_url,
                report_type="explained" if (gemini_data or not ocr_failed) else "parsing_failed",
                ai_summary=ai_summary,
                raw_text=raw_text,
            )
            db.add(report)
            await db.commit()

            if gemini_data and "biomarkers" in gemini_data and isinstance(gemini_data["biomarkers"], list):
                from app.models import ResultStatus, TestResult
                for item in gemini_data["biomarkers"]:
                    try:
                        raw_st = str(item.get("status", "NORMAL")).upper()
                        st_enum = ResultStatus.NORMAL
                        if "HIGH" in raw_st:
                            st_enum = ResultStatus.HIGH
                        elif "LOW" in raw_st:
                            st_enum = ResultStatus.LOW

                        tr = TestResult(
                            id=uuid.uuid4(),
                            report_id=report_id,
                            marker_name=str(item.get("biomarker") or item.get("marker_name") or "Unknown Biomarker"),
                            value=item.get("value"),
                            value_text=str(item.get("value_text") or ""),
                            unit=str(item.get("unit") or ""),
                            reference_min=item.get("reference_min"),
                            reference_max=item.get("reference_max"),
                            status=st_enum,
                        )
                        db.add(tr)
                    except Exception:
                        pass
                await db.commit()
        except Exception as db_exc:
            logger.error("SQLAlchemy fallback insert error: %s", db_exc)

    return UploadResponse(report_id=report_id, file_url=file_url)


@router.get("/reports/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Report:
    # Try SQLAlchemy first, fallback to Supabase REST API
    result = None
    try:
        result = await db.scalar(
            select(Report)
            .where(Report.id == report_id)
            .options(selectinload(Report.test_results))
        )
    except Exception as exc:
        logger.warning("SQLAlchemy get_report error: %s", exc)

    if result is not None:
        return result

    # Fallback to Supabase REST API
    try:
        try:
            from db.supabase_client import get_supabase_client
        except ImportError:
            from backend.db.supabase_client import get_supabase_client

        sb_client = get_supabase_client()
        if sb_client:
            rep_res = sb_client.table("reports").select("*").eq("id", str(report_id)).execute()
            if rep_res.data:
                r_data = rep_res.data[0]
                tr_res = sb_client.table("test_results").select("*").eq("report_id", str(report_id)).execute()
                
                from datetime import datetime, timezone
                raw_dt = r_data.get("created_at")
                parsed_dt = datetime.now(timezone.utc)
                if raw_dt:
                    try:
                        parsed_dt = datetime.fromisoformat(str(raw_dt).replace("Z", "+00:00"))
                    except Exception:
                        pass

                from app.models import ResultStatus, TestResult
                rep = Report(
                    id=UUID(r_data["id"]),
                    user_id=UUID(r_data["user_id"]),
                    file_url=r_data["file_url"],
                    report_type=r_data.get("report_type", "explained"),
                    ai_summary=r_data.get("ai_summary"),
                    raw_text=r_data.get("raw_text"),
                    result_explanations=r_data.get("result_explanations"),
                    created_at=parsed_dt,
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
                rep.test_results = test_results
                return rep
    except Exception as sb_get_err:
        logger.warning("Supabase REST get_report error: %s", sb_get_err)

    raise AppError(
        code="report_not_found",
        message="Report not found.",
        status_code=404,
    )


@router.get("/reports/{report_id}/raw-text", response_model=ReportRawTextResponse)
async def get_report_raw_text(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ReportRawTextResponse:
    try:
        result = await db.scalar(select(Report).where(Report.id == report_id))
        if result is not None:
            return ReportRawTextResponse(report_id=result.id, raw_text=result.raw_text)
    except Exception:
        pass

    try:
        try:
            from db.supabase_client import get_supabase_client
        except ImportError:
            from backend.db.supabase_client import get_supabase_client

        sb_client = get_supabase_client()
        if sb_client:
            rep_res = sb_client.table("reports").select("id, raw_text").eq("id", str(report_id)).execute()
            if rep_res.data:
                return ReportRawTextResponse(
                    report_id=UUID(rep_res.data[0]["id"]),
                    raw_text=rep_res.data[0].get("raw_text"),
                )
    except Exception:
        pass

    raise AppError(
        code="report_not_found",
        message="Report not found.",
        status_code=404,
    )
