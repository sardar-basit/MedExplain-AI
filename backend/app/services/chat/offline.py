"""Offline (no-API) rule-based chat fallback grounded in full report context."""

from __future__ import annotations

import re
from uuid import UUID

from app.services.chat.base import ChatResult, ChatService, ConversationTurn

# Patterns that clearly indicate a request for diagnosis/treatment.
_GUARDRAIL_PATTERNS = [
    re.compile(r"\b(diagnos|prescri|medic(ation|ine)?|dosage|dose|drug)\b", re.I),
    re.compile(r"\b(what (should|do) i (take|eat|drink|do))\b", re.I),
    re.compile(r"\b(do i have|have i got|am i)\b", re.I),
    re.compile(r"\b(cancer|diabetes|infection|disease|disorder|syndrome)\b", re.I),
]

_OUT_OF_SCOPE_REPLY = (
    "I can only answer questions based on the results in your uploaded report. "
    "I don't see information in this report that answers that question. "
    "For medical advice, diagnosis, or treatment decisions, please consult "
    "a licensed healthcare professional."
)

_DISCLAIMER = (
    "This is an educational summary only. "
    "Please consult a licensed healthcare professional for any medical advice."
)


class OfflineChatService(ChatService):
    """Rule-based fallback chat using stuffed report_context."""

    async def answer(
        self,
        *,
        report_id: UUID,
        message: str,
        report_context: str,
        history: list[ConversationTurn],  # ignored in offline mode
    ) -> ChatResult:
        # --- guardrail: out-of-scope / treatment questions ---
        if any(p.search(message) for p in _GUARDRAIL_PATTERNS):
            return ChatResult(answer=_OUT_OF_SCOPE_REPLY, used_chunks=[])

        if not report_context.strip():
            return ChatResult(
                answer=(
                    "I can only answer questions about your uploaded report, "
                    "but no relevant report data was found. "
                    "Please consult a licensed healthcare professional."
                ),
                used_chunks=[],
            )

        q_lower = message.lower()
        question_words = set(re.findall(r"\b[a-z]{3,}\b", q_lower))

        lines = report_context.split("\n")
        matched_lines = []
        for line in lines:
            line_lower = line.lower()
            if line.strip() and any(word in line_lower for word in question_words):
                matched_lines.append(line.strip())

        # If nothing matched, return the first few structured results lines
        if not matched_lines:
            matched_lines = [l.strip() for l in lines if l.strip().startswith("-")][:3]

        if not matched_lines:
            # Fallback to the summary line if any
            matched_lines = [l.strip() for l in lines if l.strip()][:3]

        answer_body = "\n".join(matched_lines)
        if not answer_body:
            return ChatResult(answer=_OUT_OF_SCOPE_REPLY, used_chunks=[])

        answer = f"Based on your report:\n{answer_body}\n\n{_DISCLAIMER}"
        return ChatResult(answer=answer, used_chunks=["full_report_context"])
