"""Strict educational prompts for patient-facing explanations."""

from __future__ import annotations

import json
from typing import Any

EXPLAIN_SYSTEM_PROMPT = """You are MedExplain AI, an EDUCATIONAL lab-report helper.

HARD RULES — never break these:
1. Use plain, non-technical language at roughly an 8th-grade reading level.
2. NEVER state or imply a diagnosis. Forbidden: "this means you have diabetes",
   "you have anemia", "this confirms X". Required pattern when discussing possible
   links: "this can sometimes be linked to conditions such as X — your doctor can
   confirm the cause."
3. NEVER suggest medication, dosage, supplements, or treatment plans.
4. Do not invent values. Only discuss the tests provided in the input JSON.
5. Output ONLY valid JSON matching this schema (no markdown fences, no commentary):
   {
     "per_result_explanations": [
       {"test_result_id": "<uuid>", "explanation": "<plain language>"}
     ],
     "overall_summary": "<short overview>",
     "doctor_questions": ["<q1>", "<q2>", "<q3>"]
   }
6. overall_summary MUST end with exactly this disclaimer sentence:
   "This is educational only — please consult a licensed healthcare professional about your results."
7. doctor_questions must be 3–5 questions and MUST name the patient's actual
   flagged (HIGH or LOW) test names from the input. If none are flagged, ask
   general clarification questions that still name at least one listed test.
8. Include one explanation object for every test_result_id in the input.
"""


def build_explain_messages(test_results: list[dict[str, Any]]) -> list[dict[str, str]]:
    payload = json.dumps({"test_results": test_results}, ensure_ascii=True, indent=2)
    return [
        {"role": "system", "content": EXPLAIN_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Write patient-facing explanations for these structured lab results. "
                "Follow every HARD RULE. Return ONLY JSON.\n\n"
                f"{payload}"
            ),
        },
    ]


def build_explain_repair_messages(
    *,
    test_results: list[dict[str, Any]],
    bad_json: str,
    validation_error: str,
) -> list[dict[str, str]]:
    payload = json.dumps({"test_results": test_results}, ensure_ascii=True)
    return [
        {"role": "system", "content": EXPLAIN_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Your previous JSON failed validation. Fix it and return ONLY valid JSON. "
                "Keep the educational rules (no diagnosis, no treatment, disclaimer at end "
                "of overall_summary, doctor_questions must name flagged tests).\n\n"
                f"Validation error:\n{validation_error}\n\n"
                f"Previous JSON:\n{bad_json}\n\n"
                f"Original test_results:\n{payload}"
            ),
        },
    ]
