"""OCR provider factory."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services.ocr.alibaba import AlibabaOCRService
from app.services.ocr.base import OCRResult, OCRService
from app.services.ocr.tesseract import TesseractOCRService

__all__ = [
    "OCRResult",
    "OCRService",
    "TesseractOCRService",
    "AlibabaOCRService",
    "get_ocr_service",
]


def get_ocr_service(settings: Settings | None = None) -> OCRService:
    cfg = settings or get_settings()
    if cfg.ocr_provider == "tesseract":
        return TesseractOCRService(cfg)
    if cfg.ocr_provider == "alibaba":
        return AlibabaOCRService(cfg)
    raise AppError(
        code="invalid_ocr_provider",
        message=f"Unknown OCR provider: {cfg.ocr_provider}",
        status_code=500,
    )
