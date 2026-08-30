"""Rule-based reference-range status computation."""

from __future__ import annotations

from app.models import ResultStatus


class ReferenceRangeService:
    """Compute NORMAL / HIGH / LOW in code. Do not trust the LLM for the final flag."""

    def compute_status(
        self,
        *,
        value: float | None,
        reference_min: float | None,
        reference_max: float | None,
        llm_status: ResultStatus | None = None,
    ) -> ResultStatus:
        if value is None:
            return llm_status or ResultStatus.NORMAL

        has_min = reference_min is not None
        has_max = reference_max is not None

        if has_min and value < float(reference_min):
            return ResultStatus.LOW
        if has_max and value > float(reference_max):
            return ResultStatus.HIGH
        if has_min or has_max:
            return ResultStatus.NORMAL

        # No ranges on the report — fall back to LLM suggestion if present.
        if llm_status is not None:
            return llm_status

        return ResultStatus.NORMAL
