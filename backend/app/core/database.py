"""Async SQLAlchemy engine and session helpers."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def to_async_database_url(url: str) -> str:
    """Normalize DATABASE_URL to an asyncpg SQLAlchemy URL."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


settings = get_settings()
ASYNC_DATABASE_URL = to_async_database_url(settings.database_url)

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


import logging

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
    try:
        async with AsyncSessionLocal() as session:
            yield session
    except Exception as exc:
        logger.warning("SQLAlchemy async session warning: %s", exc)
