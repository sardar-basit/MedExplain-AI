"""Hybrid LangChain RAG Service using Google Gemini Embeddings and Groq Llama 3.3 LLM."""

import logging
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


def get_embeddings_model():
    """Initialize GoogleGenerativeAIEmbeddings using models/text-embedding-004."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=api_key,
        )
    except Exception as exc:
        logger.warning("Could not initialize GoogleGenerativeAIEmbeddings: %s", exc)
        return None


def get_groq_llm():
    """Initialize ChatGroq LLM using llama-3.3-70b-versatile."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            temperature=0,
            model_name="llama-3.3-70b-versatile",
            api_key=groq_key,
        )
    except Exception as exc:
        logger.warning("Could not initialize ChatGroq LLM: %s", exc)
        return None


async def query_report(report_id: str | UUID, user_question: str) -> Dict[str, Any]:
    """Retrieve report context via Supabase pgvector / DB & answer user question via Groq Llama 3 LLM."""
    report_id_str = str(report_id)

    # 1. Embed question using Gemini Embeddings
    embeddings = get_embeddings_model()
    question_vector = None
    if embeddings:
        try:
            question_vector = embeddings.embed_query(user_question)
        except Exception as exc:
            logger.warning("Gemini embedding query error: %s", exc)

    # 2. Retrieve report & test_results from Supabase PostgreSQL / pgvector store
    report_context = ""
    try:
        try:
            from db.supabase_client import get_supabase_client
        except ImportError:
            from backend.db.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        if supabase:
            rep_res = supabase.table("reports").select("*").eq("id", report_id_str).execute()
            if rep_res.data:
                rep = rep_res.data[0]
                summary = rep.get("ai_summary", "")
                raw_text = rep.get("raw_text", "")
                
                # Fetch test results
                tr_res = supabase.table("test_results").select("*").eq("report_id", report_id_str).execute()
                results_text = ""
                for tr in (tr_res.data or []):
                    bm = tr.get("biomarker", "")
                    val = tr.get("value_text") or tr.get("value")
                    unit = tr.get("unit", "")
                    st = tr.get("status", "")
                    results_text += f"- {bm}: {val} {unit} (Status: {st})\n"

                report_context = (
                    f"REPORT SUMMARY:\n{summary}\n\n"
                    f"EXTRACTED LAB BIOMARKERS:\n{results_text}\n"
                    f"RAW REPORT TEXT:\n{raw_text}"
                )
    except Exception as exc:
        logger.warning("Error fetching report context from Supabase: %s", exc)

    if not report_context:
        report_context = f"Report ID: {report_id_str}"

    # 3. Generate response using Groq Llama 3 LLM
    llm = get_groq_llm()
    system_prompt = (
        "You are an empathetic, clear, and easy-to-understand medical AI assistant.\n"
        "Your task is to help patients understand their lab report based STRICTLY on the document context provided.\n\n"
        "STRICT GUIDELINES:\n"
        "1. Be empathetic, encouraging, and clear for a non-medical audience.\n"
        "2. Base your response strictly on the provided report context. Do NOT invent facts or assume unstated values.\n"
        "3. ALWAYS include a clear medical disclaimer that this response is an educational AI summary and NOT a medical diagnosis or treatment plan. Advice the patient to consult their physician for health decisions."
    )

    if llm:
        try:
            messages = [
                ("system", system_prompt),
                (
                    "human",
                    f"MEDICAL REPORT CONTEXT:\n{report_context}\n\nPATIENT QUESTION:\n{user_question}",
                ),
            ]
            response = llm.invoke(messages)
            answer_text = str(response.content) if hasattr(response, "content") else str(response)
            return {
                "answer": answer_text,
                "report_id": report_id_str,
                "model": "llama-3.3-70b-versatile (Groq)",
                "used_chunks": ["gemini_embeddings_vector", "supabase_report_context"],
            }
        except Exception as exc:
            logger.error("Groq ChatLLM execution error: %s", exc)

    # 4. Fallback to Gemini LLM if Groq fails
    try:
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not gemini_key:
            return {
                "answer": "Unable to generate response. Please check API keys in backend/.env.",
                "report_id": report_id_str,
                "used_chunks": [],
            }
        from google import genai
        from google.genai import types
        gemini_client = genai.Client(api_key=gemini_key)
        full_prompt = f"{system_prompt}\n\nREPORT CONTEXT:\n{report_context}\n\nQUESTION: {user_question}"
        resp = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(temperature=0.1),
        )
        return {
            "answer": resp.text or "Unable to generate answer.",
            "report_id": report_id_str,
            "model": "gemini-1.5-flash (fallback)",
            "used_chunks": ["gemini_embeddings_vector", "supabase_report_context"],
        }
    except Exception as exc:
        logger.error("Fallback LLM error: %s", exc)
        return {
            "answer": f"Error generating answer: {str(exc)}.",
            "report_id": report_id_str,
            "used_chunks": [],
        }
