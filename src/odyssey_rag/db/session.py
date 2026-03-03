"""SQLAlchemy async session factory and lifecycle management.

Provides:
- get_engine()           : AsyncEngine singleton
- get_session_factory()  : async_sessionmaker singleton
- db_session()           : async context manager for one-off sessions
- close_engine()         : shutdown hook to dispose connection pool
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from odyssey_rag.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine singleton.

    Engine is configured from settings.database_url. The pool is shared
    across the application lifetime.

    Returns:
        Configured AsyncEngine instance.
    """
    global _engine  # noqa: PLW0603
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=settings.environment == "development",
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory singleton.

    Returns:
        Configured async_sessionmaker bound to the shared engine.
    """
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that provides a transactional database session.

    Automatically commits on success and rolls back on exception.

    Usage::

        async with db_session() as session:
            result = await session.execute(select(Document))

    Yields:
        AsyncSession with automatic commit/rollback lifecycle.

    Raises:
        Any exception raised by the session operations, after rollback.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_engine() -> None:
    """Dispose the connection pool — call on application shutdown.

    Resets both the engine and session factory singletons so they can be
    recreated if needed (e.g. in tests).
    """
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
