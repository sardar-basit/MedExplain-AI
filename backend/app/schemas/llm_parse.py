"""Pydantic schemas for LLM report parsing output."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import ResultStatus


class ParsedTestResult(BaseModel):
    """One finding extracted from OCR text (numeric lab or qualitative form value)."""

    model_config = ConfigDict(extra="ignore")

    test_name: str = Field(min_length=1, max_length=255)
    value: float | None = None
    value_text: str | None = Field(default=None, max_length=128)
    unit: str | None = Field(default=None, max_length=64)
    reference_min: float | None = None
    reference_max: float | None = None
    # LLM suggestion only — final flag comes from ReferenceRangeService.
    status: ResultStatus | None = None

    @field_validator("test_name", "unit", "value_text", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def _require_value_or_text(self) -> ParsedTestResult:
        if self.value is None and not self.value_text:
            raise ValueError("Either value or value_text is required")
        return self


class ParsedReportResults(BaseModel):
    """Top-level JSON envelope the LLM must return."""

    model_config = ConfigDict(extra="ignore")

    results: list[ParsedTestResult] = Field(default_factory=list)
