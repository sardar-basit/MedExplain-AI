"""Upload file validation (magic-byte sniffing + size limits)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import AppError

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

# Magic signatures (prefix match)
_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_PDF = b"%PDF"


@dataclass(frozen=True)
class DetectedFileType:
    media_type: str
    extension: str


def detect_file_type(header: bytes) -> DetectedFileType | None:
    if header.startswith(_PNG):
        return DetectedFileType(media_type="image/png", extension=".png")
    if header.startswith(_JPEG):
        return DetectedFileType(media_type="image/jpeg", extension=".jpg")
    if header.startswith(_PDF):
        return DetectedFileType(media_type="application/pdf", extension=".pdf")
    return None


def validate_upload_size(size: int | None) -> None:
    if size is None:
        raise AppError(
            code="invalid_file_size",
            message="Could not determine upload size.",
            status_code=400,
        )
    if size <= 0:
        raise AppError(
            code="empty_file",
            message="Uploaded file is empty.",
            status_code=400,
        )
    if size > MAX_UPLOAD_BYTES:
        raise AppError(
            code="file_too_large",
            message="File exceeds the 15MB size limit.",
            status_code=400,
            details={"max_bytes": MAX_UPLOAD_BYTES, "received_bytes": size},
        )


def validate_magic_bytes(header: bytes) -> DetectedFileType:
    detected = detect_file_type(header)
    if detected is None:
        raise AppError(
            code="invalid_file_type",
            message="Only PDF, JPG, and PNG files are allowed.",
            status_code=400,
        )
    return detected
