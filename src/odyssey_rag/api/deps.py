"""FastAPI dependency injection providers.

Centralises all shared dependencies so routes stay thin and test
overrides are easy to apply.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.db.session import get_session_factory
from odyssey_rag.retrieval.engine import RetrievalEngine

# Module-level singleton — created once, reused across requests
_retrieval_engine: RetrievalEngine | None = None


def get_retrieval_engine() -> RetrievalEngine:
    """Get (or lazily create) the singleton RetrievalEngine.

    The engine holds the reranker model in memory, so we keep a single
    instance for the application lifetime.
    """
    global _retrieval_engine  # noqa: PLW0603
    if _retrieval_engine is None:
        _retrieval_engine = RetrievalEngine()
    return _retrieval_engine


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a transactional AsyncSession.

    Commits on success; rolls back on any exception.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
