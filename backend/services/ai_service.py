"""Google Gemini AI service for multimodal medical report extraction."""

import json
import logging
import os
from typing import Any, Dict, List

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        try:
            from app.core.config import get_settings
            api_key = get_settings().gemini_api_key.strip()
        except Exception:
            pass
    if not api_key or api_key == "your-gemini-api-key":
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as exc:
        logger.warning("Could not initialize Gemini Client: %s", exc)
        return None


def extract_medical_report(file_bytes: bytes, mime_type: str = "application/pdf") -> Dict[str, Any]:
    """Analyze raw PDF or Image bytes using gemini-1.5-flash to extract structured lab data."""
    active_client = get_genai_client()
    if not active_client:
        logger.warning("Gemini API key is not configured or invalid.")
        return {
            "summary": "Report uploaded. Please configure a valid GEMINI_API_KEY in backend/.env for AI extraction.",
            "biomarkers": [],
            "disclaimer": "This is an educational summary, not a medical diagnosis.",
        }

    prompt = (
        "You are an expert medical assistant. Analyze the attached medical report image or document carefully.\n\n"
        "STRICT RULES:\n"
        "1. Act as an expert medical assistant.\n"
        "2. Extract all biomarkers, test names, values, units, reference ranges, and status.\n"
        "3. Translate the findings into a plain-English summary that a patient without medical training can understand.\n"
        "4. Output the response ONLY as a valid JSON object matching the following structure:\n"
        "{\n"
        '  "summary": "Clear plain-English patient summary...",\n'
        '  "biomarkers": [\n'
        "    {\n"
        '      "biomarker": "Biomarker Name",\n'
        '      "value": 12.5,\n'
        '      "value_text": "12.5",\n'
        '      "unit": "g/dL",\n'
        '      "reference_min": 12.0,\n'
        '      "reference_max": 16.0,\n'
        '      "status": "NORMAL",\n'
        '      "explanation": "Clear 1-2 sentence patient explanation of what this test means and what your result indicates."\n'
        "    }\n"
        "  ],\n"
        '  "disclaimer": "This is an AI summary, not a medical diagnosis. Always consult with a qualified physician."\n'
        "}\n"
        "5. Always include a strict medical disclaimer.\n"
        "6. Status MUST be one of 'NORMAL', 'HIGH', or 'LOW'."
    )

    contents = []
    if file_bytes:
        # Standardize mime_type
        norm_mime = mime_type.lower()
        if "pdf" in norm_mime:
            norm_mime = "application/pdf"
        elif "png" in norm_mime:
            norm_mime = "image/png"
        elif "jpeg" in norm_mime or "jpg" in norm_mime:
            norm_mime = "image/jpeg"

        file_part = types.Part.from_bytes(data=file_bytes, mime_type=norm_mime)
        contents.append(file_part)

    contents.append(prompt)

    config = types.GenerateContentConfig(
        temperature=0.1,
        response_mime_type="application/json",
    )

    try:
        model_name = "gemini-3.6-flash"
        try:
            response = active_client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
        except Exception as model_err:
            logger.warning("Primary Gemini model %s failed (%s), trying fallback...", model_name, model_err)
            response = active_client.models.generate_content(
                model="gemini-1.5-flash",
                contents=contents,
                config=config,
            )
        text_content = response.text or "{}"
        data = json.loads(text_content)
        return data
    except Exception as exc:
        logger.error("Failed to extract medical report via Gemini API: %s", exc)
        return {
            "summary": "Extraction could not be completed automatically. Please check the document format.",
            "biomarkers": [],
            "disclaimer": "This is an AI summary, not a medical diagnosis.",
        }
