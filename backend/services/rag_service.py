"""Hybrid RAG Service using Groq LLM API and Google Gemini fallback."""

import logging
import os
from typing import Any, Dict, List, Optional
from uuid import UUID
import requests

logger = logging.getLogger(__name__)


async def query_report(report_id: str | UUID, user_question: str) -> Dict[str, Any]:
    """Retrieve report context from Supabase / local DB & answer patient question using Groq LLM."""
    report_id_str = str(report_id)

    # 1. Retrieve report & test_results from Supabase / DB
    report_context = ""
    try:
        import asyncio

        def _fetch_context():
            try:
                from db.supabase_client import get_supabase_client
            except ImportError:
                from backend.db.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            if not supabase:
                return ""
            rep_res = supabase.table("reports").select("*").eq("id", report_id_str).execute()
            if not rep_res.data:
                return ""
            rep = rep_res.data[0]
            summary = rep.get("ai_summary", "")
            raw_text = rep.get("raw_text", "")
            tr_res = supabase.table("test_results").select("*").eq("report_id", report_id_str).execute()
            results_text = ""
            for tr in (tr_res.data or []):
                bm = tr.get("biomarker") or tr.get("marker_name", "")
                val = tr.get("value_text") or tr.get("value")
                unit = tr.get("unit", "")
                st = tr.get("status", "")
                results_text += f"- {bm}: {val} {unit} (Status: {st})\n"
            return (
                f"REPORT SUMMARY:\n{summary}\n\n"
                f"EXTRACTED LAB BIOMARKERS:\n{results_text}\n"
                f"RAW REPORT TEXT:\n{raw_text}"
            )

        report_context = await asyncio.to_thread(_fetch_context)
    except Exception as exc:
        logger.warning("Error fetching report context: %s", exc)

    if not report_context:
        report_context = f"Report ID: {report_id_str}"

    system_prompt = (
        "You are an empathetic, clear, and easy-to-understand medical AI assistant for MedExplain AI.\n"
        "Your task is to explain medical lab reports in simple, patient-friendly plain English.\n\n"
        "STRICT GUIDELINES:\n"
        "1. Be empathetic, encouraging, and clear for a non-medical user.\n"
        "2. Base your response strictly on the provided report context.\n"
        "3. MEDICAL DISCLAIMER REQUIRED: Always include a clear disclaimer stating that this response is for educational purposes only, not a medical diagnosis or treatment plan, and advise consulting a qualified physician."
    )

    # 2. Query Groq API via REST (fast, sub-second latency)
    try:
        from app.core.config import get_settings
        settings = get_settings()
        groq_key = (os.getenv("GROQ_API_KEY") or settings.groq_api_key or "").strip('"\'')
    except Exception:
        groq_key = os.getenv("GROQ_API_KEY", "").strip('"\'')
    if groq_key:
        groq_models = ["groq/compound-mini", "groq/compound", "openai/gpt-oss-20b"]
        for g_model in groq_models:
            try:
                g_url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": g_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"MEDICAL REPORT CONTEXT:\n{report_context}\n\nPATIENT QUESTION:\n{user_question}",
                        },
                    ],
                    "max_tokens": 250,
                    "temperature": 0.2,
                }
                import asyncio
                res = await asyncio.to_thread(requests.post, g_url, headers=headers, json=payload, timeout=10)
                if res.status_code == 200:
                    answer_text = res.json()["choices"][0]["message"]["content"]
                    return {
                        "answer": answer_text,
                        "report_id": report_id_str,
                        "model": f"{g_model} (Groq API)",
                        "used_chunks": ["groq_rag_context", "supabase_report"],
                    }
            except Exception as g_err:
                print(f"[DEBUG] Groq API model {g_model} error: {g_err}")
                logger.warning("Groq API model %s error: %s", g_model, g_err)

    # 3. Fallback to Gemini AI if Groq is unavailable
    try:
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip('"\'')
        if gemini_key:
            from google import genai
            from google.genai import types

            gemini_client = genai.Client(api_key=gemini_key)
            full_prompt = f"{system_prompt}\n\nREPORT CONTEXT:\n{report_context}\n\nQUESTION: {user_question}"
            for g_mod in ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]:
                try:
                    resp = gemini_client.models.generate_content(
                        model=g_mod,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(temperature=0.2),
                    )
                    if resp and resp.text:
                        return {
                            "answer": resp.text,
                            "report_id": report_id_str,
                            "model": f"{g_mod} (Gemini)",
                            "used_chunks": ["gemini_rag_context"],
                        }
                except Exception:
                    continue
    except Exception as exc:
        logger.error("Fallback LLM error: %s", exc)

    return {
        "answer": (
            "Regarding your report: Please consult your doctor for a detailed interpretation. "
            "Disclaimer: MedExplain AI provides educational summaries only and is not a substitute for professional medical advice."
        ),
        "report_id": report_id_str,
        "used_chunks": ["fallback_disclaimer"],
    }

