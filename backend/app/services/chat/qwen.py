"""Qwen/DashScope generative chat — grounded in the full report context."""

from __future__ import annotations

import asyncio
import logging
from http import HTTPStatus
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services.chat.base import ChatResult, ChatService, ConversationTurn

logger = logging.getLogger(__name__)

# System prompt is the guardrail foundation — never diagnose, never prescribe.
_SYSTEM_PROMPT = """\
You are MedExplain AI, an educational assistant that helps users understand \
their lab report. You have been given the full context of the user's \
uploaded medical report (raw text, parsed results, and summary).

STRICT RULES — you must follow all of them without exception:
1. Answer ONLY from the provided medical report context. Do not use any external \
medical knowledge, training data, or assumptions.
2. NEVER diagnose any disease or condition. Do not say "you have X" or \
"this means you have X".
3. NEVER prescribe, recommend, or mention specific medications, dosages, \
or treatment plans.
4. If the provided report context does not contain enough information to answer the \
question, say exactly: "I can only answer from the information in your \
uploaded report, and I don't see that information here. Please consult a \
licensed healthcare professional."
5. Every response must end with: "Please consult a licensed healthcare \
professional for medical advice."
6. Keep explanations factual, calm, and educational.\
"""


def _build_messages(
    *,
    report_context: str,
    message: str,
    history: list[ConversationTurn],
) -> list[dict[str, str]]:
    system_with_context = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"=== REPORT CONTEXT ===\n{report_context}\n=== END CONTEXT ==="
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_with_context}]

    # Include the last N turns of conversation (already bounded by the API caller)
    for turn in history:
        messages.append({"role": turn.role, "content": turn.content})

    messages.append({"role": "user", "content": message})
    return messages


class QwenChatService(ChatService):
    """DashScope/Qwen generative chat grounded in stuffed report context."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.dashscope_api_key:
            raise AppError(
                code="chat_not_configured",
                message=(
                    "DASHSCOPE_API_KEY is not set. Add it to .env, or set "
                    "LLM_PROVIDER=offline for rule-based chat without an API key."
                ),
                status_code=503,
            )
        self._model = self._settings.dashscope_model

    def _call_sync(self, messages: list[dict[str, str]]) -> str:
        import dashscope
        from dashscope import Generation

        dashscope.api_key = self._settings.dashscope_api_key
        response = Generation.call(
            model=self._model,
            messages=messages,
            result_format="message",
            temperature=0.3,  # low but not zero — avoids word repetition
            max_tokens=600,
        )
        if response.status_code != HTTPStatus.OK:
            raise AppError(
                code="chat_provider_error",
                message="DashScope/Qwen chat request failed.",
                status_code=502,
                details={
                    "provider_code": getattr(response, "code", None),
                    "provider_message": getattr(response, "message", None),
                },
            )
        try:
            return response.output.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise AppError(
                code="chat_empty_response",
                message="DashScope returned an unexpected response shape.",
                status_code=502,
            ) from exc

    async def answer(
        self,
        *,
        report_id: UUID,
        message: str,
        report_context: str,
        history: list[ConversationTurn],
    ) -> ChatResult:
        if not report_context.strip():
            return ChatResult(
                answer=(
                    "I can only answer from the information in your uploaded report, "
                    "and I don't see relevant information for that question here. "
                    "Please consult a licensed healthcare professional."
                ),
                used_chunks=[],
            )

        messages = _build_messages(report_context=report_context, message=message, history=history)
        raw_answer = await asyncio.to_thread(self._call_sync, messages)
        return ChatResult(answer=raw_answer, used_chunks=["full_report_context"])
