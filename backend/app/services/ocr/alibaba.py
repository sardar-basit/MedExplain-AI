"""Alibaba Cloud OCR implementation (RecognizeAllText).

This is intentionally a STUB until credentials + SDK wiring are completed.
It documents the correct request shape and refuses to invent OCR text.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services.ocr.base import OCRResult, OCRService
from app.services.ocr.file_loader import resolve_local_path


# API: ocr-api 2021-07-07 RecognizeAllText
# Docs: https://help.aliyun.com/document_detail/442271.html
ALIBABA_OCR_REQUEST_SHAPE = {
    "endpoint": "ocr-api.cn-hangzhou.aliyuncs.com",
    "action": "RecognizeAllText",
    "version": "2021-07-07",
    "required": {
        # Exactly one of Url or body must be set
        "Url": "https://example.com/report.png",  # publicly reachable image URL
        # "body": "<binary image bytes>",  # alternative to Url (max ~10MB)
        "Type": "Advanced",  # required; Advanced is appropriate for lab reports
    },
    "recommended_for_lab_tables": {
        "OutputTable": True,
        "OutputRow": True,
        "OutputParagraph": True,
    },
    "auth": {
        "access_key_id_env": "ALIBABA_OCR_ACCESS_KEY_ID",
        "access_key_secret_env": "ALIBABA_OCR_ACCESS_KEY_SECRET",
        "endpoint_env": "ALIBABA_OCR_ENDPOINT",
    },
}


class AlibabaOCRService(OCRService):
    """Stub: validates local file exists, then raises until real SDK call is wired."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def extract(self, file_url: str) -> OCRResult:
        # Ensure the file is resolvable so callers fail for the right reason.
        resolve_local_path(file_url, self._settings)

        has_keys = bool(
            self._settings.alibaba_ocr_access_key_id
            and self._settings.alibaba_ocr_access_key_secret
        )

        # TODO: Implement real call with alibabacloud_ocr_api20210707:
        #   client.recognize_all_text(RecognizeAllTextRequest(
        #       url=file_url if publicly reachable else None,
        #       body=file_bytes if using binary upload else None,
        #       type="Advanced",
        #       output_table=True,
        #       output_row=True,
        #   ))
        # Then map response body.data.content / table blocks -> OCRResult.raw_text.
        raise AppError(
            code="alibaba_ocr_not_implemented",
            message=(
                "AlibabaOCRService is a stub. Set OCR_PROVIDER=tesseract for local "
                "dev, or implement RecognizeAllText with the documented request shape."
            ),
            status_code=501,
            details={
                "stub": True,
                "credentials_present": has_keys,
                "request_shape": ALIBABA_OCR_REQUEST_SHAPE,
                "file_url": file_url,
            },
        )
