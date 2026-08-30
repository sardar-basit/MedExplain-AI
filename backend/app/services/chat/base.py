"""Pluggable RAG chat interface for report Q&A."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class ConversationTurn:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class ChatResult:
    answer: str
    used_chunks: list[str] = field(default_factory=list)


class ChatService(ABC):
    """Answer a question grounded only in the provided report context."""

    @abstractmethod
    async def answer(
        self,
        *,
        report_id: UUID,
        message: str,
        report_context: str,
        history: list[ConversationTurn],
    ) -> ChatResult:
        """
        Generate an answer using ONLY the supplied report context.

        Parameters
        ----------
        report_id:
            Used for logging / telemetry only — never logged at content level.
        message:
            The user's current question.
        report_context:
            The raw text and structured test result data of the report.
        history:
            Last N conversation turns for multi-turn context.
        """
