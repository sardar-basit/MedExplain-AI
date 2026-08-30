"""Provider-agnostic object storage interface and local implementation."""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.errors import AppError


class StorageService(ABC):
    """Abstract storage backend. Swap OSS by adding another implementation."""

    @abstractmethod
    async def save(self, *, data: bytes, extension: str, content_type: str) -> str:
        """Persist bytes and return a resolvable file URL."""


class LocalStorageService(StorageService):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._root = Path(self._settings.local_storage_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._public_base = self._settings.api_public_url.rstrip("/")

    async def save(self, *, data: bytes, extension: str, content_type: str) -> str:
        _ = content_type  # reserved for OSS metadata parity
        safe_ext = extension if extension.startswith(".") else f".{extension}"
        filename = f"{uuid.uuid4().hex}{safe_ext}"
        destination = self._root / filename

        def _write() -> None:
            destination.write_bytes(data)

        try:
            await asyncio.to_thread(_write)
        except OSError as exc:
            raise AppError(
                code="storage_write_failed",
                message="Failed to store uploaded file.",
                status_code=500,
            ) from exc

        return f"{self._public_base}/files/{filename}"


class OssStorageService(StorageService):
    """Placeholder for Alibaba OSS — implement in a later phase."""

    async def save(self, *, data: bytes, extension: str, content_type: str) -> str:
        raise AppError(
            code="storage_not_configured",
            message="OSS storage is not implemented yet. Set STORAGE_PROVIDER=local.",
            status_code=501,
        )


def get_storage_service(settings: Settings | None = None) -> StorageService:
    cfg = settings or get_settings()
    if cfg.storage_provider == "local":
        return LocalStorageService(cfg)
    if cfg.storage_provider == "oss":
        return OssStorageService()
    raise AppError(
        code="invalid_storage_provider",
        message=f"Unknown storage provider: {cfg.storage_provider}",
        status_code=500,
    )
