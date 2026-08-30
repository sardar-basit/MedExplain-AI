"""Upload and report API routes."""

from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
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
    file_url = await storage.save(
        data=data,
        extension=detected.extension,
        content_type=detected.media_type,
    )

    raw_text: str | None = None
    ocr_failed = False
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

    user_id = uuid.uuid4()
    report_id = uuid.uuid4()
    user = User(id=user_id)
    report = Report(
        id=report_id,
        user_id=user_id,
        file_url=file_url,
        report_type="parsing_failed" if ocr_failed else "pending",
        ai_summary=None,
        raw_text=raw_text,
    )
    db.add(user)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    if not ocr_failed:
        await apply_parsed_results(db=db, report=report, llm=llm)

    return UploadResponse(report_id=report_id, file_url=file_url)


@router.get("/reports/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Report:
    result = await db.scalar(
        select(Report)
        .where(Report.id == report_id)
        .options(selectinload(Report.test_results))
    )
    if result is None:
        raise AppError(
            code="report_not_found",
            message="Report not found.",
            status_code=404,
        )
    return result


@router.get("/reports/{report_id}/raw-text", response_model=ReportRawTextResponse)
async def get_report_raw_text(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ReportRawTextResponse:
    result = await db.scalar(select(Report).where(Report.id == report_id))
    if result is None:
        raise AppError(
            code="report_not_found",
            message="Report not found.",
            status_code=404,
        )
    return ReportRawTextResponse(
        report_id=result.id,
        raw_text=result.raw_text,
    )
