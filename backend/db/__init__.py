"""Supabase DB client and helpers package."""

try:
    from db.supabase_client import get_supabase_client, supabase
except ImportError:
    from backend.db.supabase_client import get_supabase_client, supabase

__all__ = ["supabase", "get_supabase_client"]
