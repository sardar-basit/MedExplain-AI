"""Module bridge for backend/services/rag_service.py."""

try:
    from services.rag_service import get_embeddings_model, get_groq_llm, query_report
except ImportError:
    from backend.services.rag_service import get_embeddings_model, get_groq_llm, query_report

__all__ = ["get_embeddings_model", "get_groq_llm", "query_report"]
