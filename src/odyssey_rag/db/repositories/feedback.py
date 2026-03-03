"""Repository for Feedback CRUD operations.

Stores and queries user/agent quality ratings for retrieval responses.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.db.models import Feedback

logger = structlog.get_logger(__name__)


class FeedbackRepository:
    """Data access layer for the Feedback table.

    All methods accept an AsyncSession injected by the caller.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an active AsyncSession.

        Args:
            session: SQLAlchemy async session (caller-owned lifecycle).
        """
        self._session = session

    async def insert(self, feedback: Feedback) -> Feedback:
        """Persist a new feedback entry.

        Args:
            feedback: Transient Feedback instance to save.

        Returns:
            The same instance after flush.
        """
        self._session.add(feedback)
        await self._session.flush()
        logger.info(
            "feedback.inserted",
            id=str(feedback.id),
            rating=feedback.rating,
            tool=feedback.tool_name,
        )
        return feedback

    async def get_by_id(self, feedback_id: uuid.UUID) -> Feedback | None:
        """Fetch a feedback entry by primary key.

        Args:
            feedback_id: UUID primary key.

        Returns:
            Feedback instance or None if not found.
        """
        result = await self._session.execute(
            select(Feedback).where(Feedback.id == feedback_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        tool_name: str | None = None,
        rating: int | None = None,
        limit: int = 50,
    ) -> list[Feedback]:
        """List recent feedback entries with optional filters.

        Args:
            tool_name: Filter by MCP tool name (e.g. "find_message_type").
            rating: Filter by rating value (-1, 0, or 1).
            limit: Maximum number of entries to return.

        Returns:
            List of Feedback instances, newest first.
        """
        stmt = select(Feedback)
        if tool_name is not None:
            stmt = stmt.where(Feedback.tool_name == tool_name)
        if rating is not None:
            stmt = stmt.where(Feedback.rating == rating)
        stmt = stmt.order_by(Feedback.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
