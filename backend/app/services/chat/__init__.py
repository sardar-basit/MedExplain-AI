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
    if cfg.llm_provider == "dashscope":
        return QwenChatService(cfg)
    return OfflineChatService()
