"""Prompts for structured lab-report parsing (educational use only)."""

from __future__ import annotations

SYSTEM_PROMPT = """You are MedExplain AI's lab-report extraction component.

HARD RULES (always apply):
- This is an EDUCATIONAL tool. Never diagnose, prescribe, suggest dosages, or say the user "has" a condition.
- Extract ONLY facts explicitly present in the OCR text. Do NOT invent, estimate, or fill missing values.
- If a field is missing or unclear in the text, OMIT that field (or omit the whole row if the test name or value is unclear).
- Output ONLY valid JSON. No markdown fences, no commentary, no trailing text.
- JSON schema (top-level object):
  {
    "results": [
      {
        "test_name": string,
        "value": number,
        "unit": string | null,
        "reference_min": number | null,
        "reference_max": number | null,
        "status": "NORMAL" | "HIGH" | "LOW" | null
      }
    ]
  }
- Prefer leaving status null when reference ranges are present; a separate rule engine will compute flags.
- Always end any natural-language explanation (not used in this JSON task) with advice to consult a licensed clinician — but for THIS task you must output JSON only.
"""

FEW_SHOT_USER_1 = """OCR text:
Complete Blood Count
Hemoglobin 11.8 g/dL 12.0-16.0
WBC 7.2 10^3/uL 4.0-11.0
Platelets 420 10^3/uL 150-400
"""

FEW_SHOT_ASSISTANT_1 = """{
  "results": [
    {
      "test_name": "Hemoglobin",
      "value": 11.8,
      "unit": "g/dL",
      "reference_min": 12.0,
      "reference_max": 16.0,
      "status": null
    },
    {
      "test_name": "WBC",
      "value": 7.2,
      "unit": "10^3/uL",
      "reference_min": 4.0,
      "reference_max": 11.0,
      "status": null
    },
    {
      "test_name": "Platelets",
      "value": 420.0,
      "unit": "10^3/uL",
      "reference_min": 150.0,
      "reference_max": 400.0,
      "status": null
    }
  ]
}"""

FEW_SHOT_USER_2 = """OCR text:
Lipid Profile
Total Cholesterol 212 mg/dL <200
HDL Cholesterol 44 mg/dL >40
Note: Patient feels fine today.
"""

FEW_SHOT_ASSISTANT_2 = """{
  "results": [
    {
      "test_name": "Total Cholesterol",
      "value": 212.0,
      "unit": "mg/dL",
      "reference_min": null,
      "reference_max": 200.0,
      "status": null
    },
    {
      "test_name": "HDL Cholesterol",
      "value": 44.0,
      "unit": "mg/dL",
      "reference_min": 40.0,
      "reference_max": null,
      "status": null
    }
  ]
}"""

FEW_SHOT_USER_3 = """OCR text:
Metabolic Panel
Glucose 118 mg/dL 70-99
Creatinine unclear smudge
Sodium 139 mmol/L 136-145
"""

FEW_SHOT_ASSISTANT_3 = """{
  "results": [
    {
      "test_name": "Glucose",
      "value": 118.0,
      "unit": "mg/dL",
      "reference_min": 70.0,
      "reference_max": 99.0,
      "status": null
    },
    {
      "test_name": "Sodium",
      "value": 139.0,
      "unit": "mmol/L",
      "reference_min": 136.0,
      "reference_max": 145.0,
      "status": null
    }
  ]
}"""


def build_parse_messages(raw_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": FEW_SHOT_USER_1},
        {"role": "assistant", "content": FEW_SHOT_ASSISTANT_1},
        {"role": "user", "content": FEW_SHOT_USER_2},
        {"role": "assistant", "content": FEW_SHOT_ASSISTANT_2},
        {"role": "user", "content": FEW_SHOT_USER_3},
        {"role": "assistant", "content": FEW_SHOT_ASSISTANT_3},
        {
            "role": "user",
            "content": (
                "Extract lab test rows from the following OCR text. "
                "Return ONLY the JSON object.\n\nOCR text:\n"
                f"{raw_text}"
            ),
        },
    ]


def build_repair_messages(
    *,
    raw_text: str,
    bad_json: str,
    validation_error: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Your previous JSON failed validation. Fix it and return ONLY valid JSON "
                "matching the schema. Do not invent values that are not in the OCR text.\n\n"
                f"Validation error:\n{validation_error}\n\n"
                f"Previous JSON:\n{bad_json}\n\n"
                f"Original OCR text:\n{raw_text}"
            ),
        },
    ]
