"""LLM provider factory."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services.llm.base import LLMService
from app.services.llm.offline import OfflineLLMService
from app.services.llm.qwen import QwenLLMService

__all__ = [
    "LLMService",
    "QwenLLMService",
    "OfflineLLMService",
    "get_llm_service",
]


def get_llm_service(settings: Settings | None = None) -> LLMService:
    cfg = settings or get_settings()
    if cfg.llm_provider == "dashscope":
        return QwenLLMService(cfg)
    if cfg.llm_provider == "offline":
        return OfflineLLMService()
    if cfg.llm_provider in {"openai", "gemini"}:
        raise AppError(
            code="llm_provider_not_implemented",
            message=f"LLM provider '{cfg.llm_provider}' is not implemented yet.",
            status_code=501,
        )
    raise AppError(
        code="invalid_llm_provider",
        message=f"Unknown LLM provider: {cfg.llm_provider}",
        status_code=500,
    )
