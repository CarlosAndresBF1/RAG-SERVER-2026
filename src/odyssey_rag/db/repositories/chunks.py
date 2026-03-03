"""Repository for Chunk CRUD operations.

Provides insert, query by document, and delete operations against
the ``chunk`` table. Full-text search is handled by the retrieval layer
(retrieval/bm25_search.py) which builds raw SQL for tsvector queries.
"""

from __future__ import annotations

import uuid
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.db.models import Chunk

logger = structlog.get_logger(__name__)


class ChunkRepository:
    """Data access layer for the Chunk table.

    All methods accept an AsyncSession injected by the caller.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an active AsyncSession.

        Args:
            session: SQLAlchemy async session (caller-owned lifecycle).
        """
        self._session = session

    async def insert(self, chunk: Chunk) -> Chunk:
        """Persist a new chunk row.

        Args:
            chunk: Transient Chunk instance to save.

        Returns:
            The same instance after flush (id and defaults populated).
        """
        self._session.add(chunk)
        await self._session.flush()
        return chunk

    async def insert_many(self, chunks: list[Chunk]) -> list[Chunk]:
        """Persist multiple chunks in one flush.

        Args:
            chunks: List of transient Chunk instances.

        Returns:
            The same list after flush.
        """
        for chunk in chunks:
            self._session.add(chunk)
        await self._session.flush()
        return chunks

    async def get_by_id(self, chunk_id: uuid.UUID) -> Chunk | None:
        """Fetch a single chunk by primary key.

        Args:
            chunk_id: UUID primary key.

        Returns:
            Chunk instance or None if not found.
        """
        result = await self._session.execute(
            select(Chunk).where(Chunk.id == chunk_id)
        )
        return result.scalar_one_or_none()

    async def list_by_document(
        self,
        document_id: uuid.UUID,
        limit: int = 500,
    ) -> list[Chunk]:
        """Fetch all chunks belonging to a document, ordered by chunk_index.

        Args:
            document_id: Parent document UUID.
            limit: Maximum chunks to return.

        Returns:
            Ordered list of Chunk instances.
        """
        result = await self._session.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_document(self, document_id: uuid.UUID) -> int:
        """Count chunks for a given document.

        Args:
            document_id: Parent document UUID.

        Returns:
            Integer chunk count.
        """
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count()).select_from(Chunk).where(
                Chunk.document_id == document_id
            )
        )
        return result.scalar_one()  # type: ignore[return-value]

    async def list_with_filters(
        self,
        document_id: Optional[uuid.UUID] = None,
        message_type: Optional[str] = None,
        source_type: Optional[str] = None,
        section: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Chunk], int]:
        """List chunks with optional filters, returning (results, total_count).

        Joins with ChunkMetadata when message_type or source_type is specified.

        Args:
            document_id:  Restrict to chunks from this document.
            message_type: ISO 20022 message type filter (via ChunkMetadata).
            source_type:  Source type filter (via ChunkMetadata).
            section:      Section name filter on Chunk.section.
            limit:        Page size.
            offset:       Row offset for pagination.

        Returns:
            Tuple of (chunk list, total matching count).
        """
        from odyssey_rag.db.models import ChunkMetadata

        stmt = select(Chunk)
        count_stmt = select(func.count()).select_from(Chunk)

        # Join metadata table when filtering by its columns
        if message_type is not None or source_type is not None:
            stmt = stmt.join(ChunkMetadata, ChunkMetadata.chunk_id == Chunk.id)
            count_stmt = count_stmt.join(ChunkMetadata, ChunkMetadata.chunk_id == Chunk.id)
            if message_type is not None:
                stmt = stmt.where(ChunkMetadata.message_type == message_type)
                count_stmt = count_stmt.where(ChunkMetadata.message_type == message_type)
            if source_type is not None:
                stmt = stmt.where(ChunkMetadata.source_type == source_type)
                count_stmt = count_stmt.where(ChunkMetadata.source_type == source_type)

        if document_id is not None:
            stmt = stmt.where(Chunk.document_id == document_id)
            count_stmt = count_stmt.where(Chunk.document_id == document_id)

        if section is not None:
            stmt = stmt.where(Chunk.section == section)
            count_stmt = count_stmt.where(Chunk.section == section)

        total: int = (await self._session.execute(count_stmt)).scalar_one()  # type: ignore[assignment]
        stmt = stmt.order_by(Chunk.chunk_index).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def delete_by_document(self, document_id: uuid.UUID) -> int:
        """Delete all chunks for a document (cascade triggers DB-side).

        Args:
            document_id: Parent document UUID.

        Returns:
            Number of rows deleted.
        """
        from sqlalchemy import delete

        result = await self._session.execute(
            delete(Chunk).where(Chunk.document_id == document_id)
        )
        count: int = result.rowcount  # type: ignore[assignment]
        logger.info(
            "chunk.deleted_by_document",
            document_id=str(document_id),
            count=count,
        )
        return count
