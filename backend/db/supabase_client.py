"""Supabase Python SDK client initialization."""

import os
from functools import lru_cache
from typing import Optional

from supabase import Client, create_client

from app.core.config import get_settings


def get_supabase_url() -> str:
    settings = get_settings()
    url = getattr(settings, "supabase_url", "") or os.getenv("SUPABASE_URL", "")
    return url.strip()


def get_supabase_key() -> str:
    settings = get_settings()
    # Prefer service role key for backend operations; fallback to anon key or env var
    key = (
        getattr(settings, "supabase_service_role_key", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    if not key or key == "[PASTE_SERVICE_ROLE_KEY_HERE]":
        key = getattr(settings, "supabase_anon_key", "") or os.getenv("SUPABASE_ANON_KEY", "")
    return key.strip()


@lru_cache
def get_supabase_client() -> Optional[Client]:
    """Initialize and return a cached Supabase Python client instance."""
    url = get_supabase_url()
    key = get_supabase_key()

    if not url or not key:
        return None

    try:
        return create_client(url, key)
    except Exception:
        return None


# Global convenience client instance
supabase: Optional[Client] = get_supabase_client()
