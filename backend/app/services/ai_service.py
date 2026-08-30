"""Module bridge for backend/services/ai_service.py."""

try:
    from services.ai_service import client, extract_medical_report
except ImportError:
    from backend.services.ai_service import client, extract_medical_report

__all__ = ["client", "extract_medical_report"]
