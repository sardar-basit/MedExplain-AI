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


class SupabaseStorageService(StorageService):
    """Supabase Object Storage implementation for medical-reports bucket."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._bucket_name = getattr(self._settings, "supabase_storage_bucket", "medical-reports")

    async def save(self, *, data: bytes, extension: str, content_type: str) -> str:
        try:
            from db.supabase_client import get_supabase_client
        except ImportError:
            from backend.db.supabase_client import get_supabase_client

        client = get_supabase_client()
        safe_ext = extension if extension.startswith(".") else f".{extension}"
        filename = f"{uuid.uuid4().hex}{safe_ext}"

        if not client:
            local_svc = LocalStorageService(self._settings)
            return await local_svc.save(data=data, extension=extension, content_type=content_type)

        def _upload() -> str:
            client.storage.from_(self._bucket_name).upload(
                path=filename,
                file=data,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            return client.storage.from_(self._bucket_name).get_public_url(filename)

        try:
            return await asyncio.to_thread(_upload)
        except Exception:
            local_svc = LocalStorageService(self._settings)
            return await local_svc.save(data=data, extension=extension, content_type=content_type)


def get_storage_service(settings: Settings | None = None) -> StorageService:
    cfg = settings or get_settings()
    if cfg.storage_provider == "supabase":
        return SupabaseStorageService(cfg)
    if cfg.storage_provider == "local":
        return LocalStorageService(cfg)
    if cfg.storage_provider == "oss":
        return OssStorageService()
    raise AppError(
        code="invalid_storage_provider",
        message=f"Unknown storage provider: {cfg.storage_provider}",
        status_code=500,
    )
