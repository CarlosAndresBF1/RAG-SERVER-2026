"""Unit tests for garbage collection of superseded documents."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from odyssey_rag.db.repositories.documents import DocumentRepository


def make_session() -> MagicMock:
    """Return a minimal mock of AsyncSession."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


class TestGarbageCollectSuperseded:
    """Tests for DocumentRepository.garbage_collect_superseded()."""

    @pytest.mark.asyncio
    async def test_gc_deletes_old_superseded_documents(self) -> None:
        """gc deletes superseded docs older than retention period."""
        session = make_session()
        mock_result = MagicMock(rowcount=5)
        session.execute = AsyncMock(return_value=mock_result)

        repo = DocumentRepository(session)
        count = await repo.garbage_collect_superseded(retention_days=30)

        session.execute.assert_called_once()
        assert count == 5

    @pytest.mark.asyncio
    async def test_gc_with_zero_results(self) -> None:
        """gc returns 0 when no superseded documents are old enough."""
        session = make_session()
        mock_result = MagicMock(rowcount=0)
        session.execute = AsyncMock(return_value=mock_result)

        repo = DocumentRepository(session)
        count = await repo.garbage_collect_superseded(retention_days=30)

        assert count == 0

    @pytest.mark.asyncio
    async def test_gc_custom_retention(self) -> None:
        """gc respects custom retention_days parameter."""
        session = make_session()
        mock_result = MagicMock(rowcount=3)
        session.execute = AsyncMock(return_value=mock_result)

        repo = DocumentRepository(session)
        count = await repo.garbage_collect_superseded(retention_days=7)

        session.execute.assert_called_once()
        assert count == 3

    @pytest.mark.asyncio
    async def test_gc_default_retention_is_30_days(self) -> None:
        """gc defaults to 30-day retention if not specified."""
        session = make_session()
        mock_result = MagicMock(rowcount=1)
        session.execute = AsyncMock(return_value=mock_result)

        repo = DocumentRepository(session)
        count = await repo.garbage_collect_superseded()

        assert count == 1
        session.execute.assert_called_once()
