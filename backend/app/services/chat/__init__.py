"""Chat service factory — provider-switch pattern matching LLM/OCR."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services.chat.base import ChatResult, ChatService, ConversationTurn
from app.services.chat.offline import OfflineChatService
from app.services.chat.qwen import QwenChatService

__all__ = [
    "ChatResult",
    "ChatService",
    "ConversationTurn",
    "OfflineChatService",
    "QwenChatService",
    "get_chat_service",
]


def get_chat_service(settings: Settings | None = None) -> ChatService:
    """Return the chat service matching LLM_PROVIDER."""
    cfg = settings or get_settings()
    if cfg.llm_provider == "offline":
        return OfflineChatService()
    if cfg.llm_provider == "dashscope":
        return QwenChatService(cfg)
    if cfg.llm_provider in {"openai", "gemini"}:
        raise AppError(
            code="chat_provider_not_implemented",
            message=f"Chat via LLM_PROVIDER='{cfg.llm_provider}' is not implemented yet.",
            status_code=501,
        )
    raise AppError(
        code="invalid_llm_provider",
        message=f"Unknown LLM_PROVIDER: {cfg.llm_provider}",
        status_code=500,
    )
