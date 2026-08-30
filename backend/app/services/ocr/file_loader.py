"""Helpers to resolve stored file URLs to local bytes/paths."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from app.core.config import Settings, get_settings
from app.core.errors import AppError


def resolve_local_path(file_url: str, settings: Settings | None = None) -> Path:
    """Map a local storage file_url to a filesystem path."""
    cfg = settings or get_settings()
    root = Path(cfg.local_storage_path).resolve()

    parsed = urlparse(file_url)
    path = parsed.path if parsed.scheme in {"http", "https"} else file_url

    # Expected form: /files/<filename>
    marker = "/files/"
    if marker in path:
        filename = path.split(marker, 1)[1].lstrip("/").split("?")[0]
    else:
        filename = Path(path).name

    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        raise AppError(
            code="invalid_file_url",
            message="Could not resolve a safe local path for the uploaded file.",
            status_code=400,
        )

    candidate = (root / filename).resolve()
    if not str(candidate).startswith(str(root)):
        raise AppError(
            code="invalid_file_url",
            message="Resolved path escapes the upload directory.",
            status_code=400,
        )
    if not candidate.is_file():
        raise AppError(
            code="file_not_found",
            message="Uploaded file is missing from storage.",
            status_code=404,
        )
    return candidate


def read_file_bytes(file_url: str, settings: Settings | None = None) -> tuple[Path, bytes]:
    path = resolve_local_path(file_url, settings)
    return path, path.read_bytes()
