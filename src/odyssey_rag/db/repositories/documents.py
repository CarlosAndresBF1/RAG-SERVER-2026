"""Repository for Document CRUD operations.

Provides insert, query, update, and soft-delete (is_current flag)
operations against the ``document`` table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.db.models import Document

logger = structlog.get_logger(__name__)


class DocumentRepository:
    """Data access layer for the Document table.

    All methods accept an AsyncSession injected by the caller so that
    transaction boundaries are controlled at the service layer.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an active AsyncSession.

        Args:
            session: SQLAlchemy async session (caller-owned lifecycle).
        """
        self._session = session

    async def insert(self, document: Document) -> Document:
        """Persist a new document row.

        Args:
            document: Transient Document instance to save.

        Returns:
            The same instance after being added to the session.
        """
        self._session.add(document)
        await self._session.flush()  # assign DB-generated defaults without full commit
        logger.info(
            "document.inserted",
            id=str(document.id),
            source_path=document.source_path,
        )
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Fetch a document by its primary key.

        Args:
            document_id: UUID primary key.

        Returns:
            Document instance or None if not found.
        """
        result = await self._session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_current_by_path(self, source_path: str) -> Document | None:
        """Fetch the current (active) document for a given source path.

        Args:
            source_path: Original file path used as ingestion identifier.

        Returns:
            Document with is_current=True, or None if not ingested yet.
        """
        result = await self._session.execute(
            select(Document).where(
                Document.source_path == source_path,
                Document.is_current.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, file_hash: str) -> Document | None:
        """Check if a file (by SHA-256 hash) has already been ingested.

        Args:
            file_hash: SHA-256 hex digest of the file content.

        Returns:
            Matching Document or None.
        """
        result = await self._session.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def count_current(
        self,
        source_type: Optional[str] = None,
    ) -> int:
        """Count active (is_current=True) documents with optional source_type filter.

        Args:
            source_type: Optional source type to filter by.

        Returns:
            Integer count of matching documents.
        """
        stmt = select(func.count()).select_from(Document).where(Document.is_current.is_(True))
        if source_type:
            stmt = stmt.where(Document.source_type == source_type)
        result = await self._session.execute(stmt)
        return result.scalar_one()  # type: ignore[return-value]

    async def list_current(
        self,
        source_type: str | None = None,
        integration: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """List active documents with optional filters.

        Args:
            source_type: Filter by source type (e.g. "annex_b_spec").
            integration: Filter by integration name (e.g. "bimpay").
            limit: Maximum number of rows to return.
            offset: Number of rows to skip (for pagination).

        Returns:
            List of Document instances.
        """
        stmt = select(Document).where(Document.is_current.is_(True))
        if source_type:
            stmt = stmt.where(Document.source_type == source_type)
        if integration:
            stmt = stmt.where(Document.integration == integration)
        stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def supersede(self, source_path: str) -> int:
        """Mark all current documents for a path as superseded (is_current=False).

        Called before inserting a new version of the same file.

        Args:
            source_path: Path whose previous versions should be superseded.

        Returns:
            Number of rows updated.
        """
        result = await self._session.execute(
            update(Document)
            .where(
                Document.source_path == source_path,
                Document.is_current.is_(True),
            )
            .values(is_current=False, updated_at=datetime.now(tz=timezone.utc))
        )
        return result.rowcount  # type: ignore[return-value]

    async def update_chunk_count(
        self, document_id: uuid.UUID, total_chunks: int
    ) -> None:
        """Update the total_chunks counter after ingestion.

        Args:
            document_id: Document to update.
            total_chunks: Final chunk count.
        """
        await self._session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(total_chunks=total_chunks, updated_at=datetime.now(tz=timezone.utc))
        )

    async def delete(self, document_id: uuid.UUID) -> bool:
        """Hard-delete a document and cascade to chunks/embeddings.

        Args:
            document_id: UUID of the document to delete.

        Returns:
            True if a row was deleted, False if not found.
        """
        doc = await self.get_by_id(document_id)
        if doc is None:
            return False
        await self._session.delete(doc)
        await self._session.flush()
        logger.info("document.deleted", id=str(document_id))
        return True

    async def garbage_collect_superseded(self, retention_days: int = 30) -> int:
        """Delete superseded documents older than the retention period.

        Removes all Documents where ``is_current=False`` and
        ``updated_at`` is older than ``NOW() - retention_days``. Cascaded
        foreign keys (Chunk → ChunkEmbedding, ChunkMetadata) are deleted
        by the database via ``ON DELETE CASCADE``.

        Args:
            retention_days: Number of days to retain superseded documents
                            before garbage collection. Defaults to 30.

        Returns:
            Number of documents deleted.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=retention_days)
        result = await self._session.execute(
            delete(Document).where(
                Document.is_current.is_(False),
                Document.updated_at < cutoff,
            )
        )
        count: int = result.rowcount  # type: ignore[assignment]
        logger.info(
            "gc.superseded_deleted",
            deleted=count,
            retention_days=retention_days,
            cutoff=cutoff.isoformat(),
        )
        return count
