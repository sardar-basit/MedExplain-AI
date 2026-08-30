"""MedExplain AI FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Run startup tasks then yield control to the application."""
    yield  # application runs here


app = FastAPI(
    title=settings.app_name,
    description="Educational medical report interpreter — not a diagnostic tool.",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.post("/api/chat")
async def direct_api_chat(body: dict):
    """Direct /api/chat endpoint calling query_report."""
    try:
        from services.rag_service import query_report
    except ImportError:
        from backend.services.rag_service import query_report
    report_id = body.get("report_id") or body.get("reportId")
    message = body.get("message") or body.get("question") or ""
    if not report_id:
        return {"error": "report_id is required"}
    res = await query_report(report_id=report_id, user_question=message)
    return res

# Serve locally stored uploads in development (OSS URLs are absolute elsewhere).
if settings.storage_provider == "local":
    upload_root = Path(settings.local_storage_path).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(upload_root)), name="files")
