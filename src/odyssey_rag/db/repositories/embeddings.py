"""Repository for ChunkEmbedding CRUD operations.

Wraps insert and lookup operations against the ``chunk_embedding`` table.
Vector similarity search queries are handled in retrieval/vector_search.py
using raw SQL for pgvector performance.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.db.models import ChunkEmbedding

logger = structlog.get_logger(__name__)


class EmbeddingRepository:
    """Data access layer for the ChunkEmbedding table.

    All methods accept an AsyncSession injected by the caller.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an active AsyncSession.

        Args:
            session: SQLAlchemy async session (caller-owned lifecycle).
        """
        self._session = session

    async def insert(self, embedding: ChunkEmbedding) -> ChunkEmbedding:
        """Persist a new chunk embedding.

        Args:
            embedding: Transient ChunkEmbedding instance to save.

        Returns:
            The same instance after flush.
        """
        self._session.add(embedding)
        await self._session.flush()
        return embedding

    async def insert_many(self, embeddings: list[ChunkEmbedding]) -> list[ChunkEmbedding]:
        """Persist multiple embeddings in one flush.

        Args:
            embeddings: List of transient ChunkEmbedding instances.

        Returns:
            The same list after flush.
        """
        for emb in embeddings:
            self._session.add(emb)
        await self._session.flush()
        return embeddings

    async def get_by_chunk_id(self, chunk_id: uuid.UUID) -> ChunkEmbedding | None:
        """Fetch the embedding for a specific chunk.

        Args:
            chunk_id: Chunk UUID (unique constraint on chunk_embedding.chunk_id).

        Returns:
            ChunkEmbedding instance or None if not found.
        """
        result = await self._session.execute(
            select(ChunkEmbedding).where(ChunkEmbedding.chunk_id == chunk_id)
        )
        return result.scalar_one_or_none()

    async def delete_by_chunk_id(self, chunk_id: uuid.UUID) -> bool:
        """Delete the embedding for a specific chunk.

        Args:
            chunk_id: Chunk UUID whose embedding should be removed.

        Returns:
            True if a row was deleted, False if not found.
        """
        emb = await self.get_by_chunk_id(chunk_id)
        if emb is None:
            return False
        await self._session.delete(emb)
        await self._session.flush()
        logger.info("embedding.deleted", chunk_id=str(chunk_id))
        return True
