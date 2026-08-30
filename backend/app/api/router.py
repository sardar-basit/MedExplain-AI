"""API route modules."""

from fastapi import APIRouter

from app.api import chat, health, reports

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(reports.router)
api_router.include_router(chat.router)
