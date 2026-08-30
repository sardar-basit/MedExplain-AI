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
    if cfg.llm_provider in {"gemini", "groq", "offline"}:
        return OfflineLLMService()
    if cfg.llm_provider == "openai":
        return OfflineLLMService()
    return OfflineLLMService()
