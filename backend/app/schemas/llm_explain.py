"""Schemas for patient-facing LLM explanations."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResultExplanationItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    test_result_id: UUID
    explanation: str = Field(min_length=1, max_length=2000)

    @field_validator("explanation")
    @classmethod
    def _strip_explanation(cls, value: str) -> str:
        return value.strip()


class ExplanationBundle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    per_result_explanations: list[ResultExplanationItem] = Field(default_factory=list)
    overall_summary: str = Field(min_length=1, max_length=4000)
    doctor_questions: list[str] = Field(min_length=3, max_length=5)

    @field_validator("overall_summary")
    @classmethod
    def _strip_summary(cls, value: str) -> str:
        return value.strip()

    @field_validator("doctor_questions")
    @classmethod
    def _clean_questions(cls, value: list[str]) -> list[str]:
        cleaned = [q.strip() for q in value if isinstance(q, str) and q.strip()]
        if len(cleaned) < 3:
            raise ValueError("doctor_questions must contain at least 3 items")
        return cleaned[:5]
