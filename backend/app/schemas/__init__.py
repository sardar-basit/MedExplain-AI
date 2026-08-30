"""Pydantic request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import ResultStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Users ---


class UserCreate(BaseModel):
    """Empty create body — user id is server-generated."""


class UserRead(ORMModel):
    id: UUID
    created_at: datetime


# --- Test results ---


class TestResultCreate(BaseModel):
    marker_name: str = Field(min_length=1, max_length=255)
    value: float | None = None
    value_text: str | None = Field(default=None, max_length=128)
    unit: str = Field(default="", max_length=64)
    reference_min: float | None = None
    reference_max: float | None = None
    status: ResultStatus


class TestResultRead(ORMModel):
    id: UUID
    report_id: UUID
    marker_name: str
    value: float | None
    value_text: str | None = None
    unit: str
    reference_min: float | None
    reference_max: float | None
    status: ResultStatus


# --- Reports ---


class ReportCreate(BaseModel):
    user_id: UUID
    file_url: str = Field(min_length=1, max_length=1024)
    report_type: str = Field(min_length=1, max_length=100)
    ai_summary: str | None = None
    test_results: list[TestResultCreate] = Field(default_factory=list)


class ReportRead(ORMModel):
    id: UUID
    user_id: UUID
    file_url: str
    report_type: str
    ai_summary: str | None
    result_explanations: list[dict] | None = None
    doctor_questions: list[str] | None = None
    created_at: datetime


class ReportDetail(ReportRead):
    test_results: list[TestResultRead] = Field(default_factory=list)


class UploadResponse(BaseModel):
    report_id: UUID
    file_url: str


class ReportRawTextResponse(BaseModel):
    report_id: UUID
    raw_text: str | None


# --- Chat ---


class ConversationTurnSchema(BaseModel):
    """One turn in a multi-turn chat conversation."""

    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    report_id: UUID
    message: str = Field(min_length=1, max_length=2000)
    # Accept up to 6 turns of history; older turns are silently dropped.
    conversation_history: list[ConversationTurnSchema] = Field(default_factory=list, max_length=12)


class ChatResponse(BaseModel):
    answer: str
    used_chunks: list[str] = Field(default_factory=list)
