"""Unit tests for database repositories.

All database interactions use a mocked AsyncSession so these tests run
without a real PostgreSQL instance.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odyssey_rag.db.models import (
    Chunk,
    ChunkEmbedding,
    Document,
    Feedback,
    IngestJob,
)
from odyssey_rag.db.repositories.chunks import ChunkRepository
from odyssey_rag.db.repositories.documents import DocumentRepository
from odyssey_rag.db.repositories.embeddings import EmbeddingRepository
from odyssey_rag.db.repositories.feedback import FeedbackRepository
from odyssey_rag.db.repositories.ingest_jobs import IngestJobRepository


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_session() -> MagicMock:
    """Return a minimal mock of AsyncSession."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


def make_scalar_result(value: Any) -> MagicMock:
    """Wrap a value in a SQLAlchemy-like scalar result mock."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalars.return_value = MagicMock(all=MagicMock(return_value=[value]))
    return result


def make_scalars_result(values: list[Any]) -> MagicMock:
    """Wrap a list of values in a SQLAlchemy-like scalars result mock."""
    result = MagicMock()
    result.scalars.return_value = MagicMock(all=MagicMock(return_value=values))
    return result


def sample_document() -> Document:
    """Create a sample Document for testing."""
    return Document(
        id=uuid.uuid4(),
        source_path="/docs/annex_b.md",
        source_type="annex_b_spec",
        file_hash="abc123" * 10,  # 60 chars (SHA-256 is 64)
        integration="bimpay",
        is_current=True,
        total_chunks=0,
    )


def sample_chunk(document_id: uuid.UUID) -> Chunk:
    """Create a sample Chunk for testing."""
    return Chunk(
        id=uuid.uuid4(),
        document_id=document_id,
        content="This is a test chunk about pacs.008.",
        token_count=10,
        chunk_index=0,
        section="Group Header",
    )


# ── DocumentRepository tests ──────────────────────────────────────────────────


class TestDocumentRepository:
    """Tests for DocumentRepository."""

    @pytest.mark.asyncio
    async def test_insert_adds_and_flushes(self) -> None:
        """insert() calls session.add and session.flush."""
        session = make_session()
        repo = DocumentRepository(session)
        doc = sample_document()

        result = await repo.insert(doc)

        session.add.assert_called_once_with(doc)
        session.flush.assert_called_once()
        assert result is doc

    @pytest.mark.asyncio
    async def test_get_by_id_returns_document(self) -> None:
        """get_by_id() returns the matching Document."""
        session = make_session()
        doc = sample_document()
        session.execute = AsyncMock(return_value=make_scalar_result(doc))

        repo = DocumentRepository(session)
        result = await repo.get_by_id(doc.id)

        assert result is doc

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self) -> None:
        """get_by_id() returns None if no matching row exists."""
        session = make_session()
        session.execute = AsyncMock(return_value=make_scalar_result(None))

        repo = DocumentRepository(session)
        result = await repo.get_by_id(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_by_path_returns_document(self) -> None:
        """get_current_by_path() returns the active document for a path."""
        session = make_session()
        doc = sample_document()
        session.execute = AsyncMock(return_value=make_scalar_result(doc))

        repo = DocumentRepository(session)
        result = await repo.get_current_by_path("/docs/annex_b.md")

        assert result is doc

    @pytest.mark.asyncio
    async def test_supersede_updates_rows(self) -> None:
        """supersede() executes an UPDATE statement."""
        session = make_session()
        mock_result = MagicMock(rowcount=1)
        session.execute = AsyncMock(return_value=mock_result)

        repo = DocumentRepository(session)
        count = await repo.supersede("/docs/annex_b.md")

        session.execute.assert_called_once()
        assert count == 1

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self) -> None:
        """delete() returns False when the document does not exist."""
        session = make_session()
        session.execute = AsyncMock(return_value=make_scalar_result(None))

        repo = DocumentRepository(session)
        result = await repo.delete(uuid.uuid4())

        assert result is False
        session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_returns_true_and_deletes(self) -> None:
        """delete() removes the document and returns True."""
        session = make_session()
        doc = sample_document()
        session.execute = AsyncMock(return_value=make_scalar_result(doc))

        repo = DocumentRepository(session)
        result = await repo.delete(doc.id)

        assert result is True
        session.delete.assert_called_once_with(doc)
        session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_list_current_returns_documents(self) -> None:
        """list_current() returns active documents."""
        session = make_session()
        doc = sample_document()
        session.execute = AsyncMock(return_value=make_scalars_result([doc]))

        repo = DocumentRepository(session)
        results = await repo.list_current()

        assert len(results) == 1
        assert results[0] is doc


# ── ChunkRepository tests ─────────────────────────────────────────────────────


class TestChunkRepository:
    """Tests for ChunkRepository."""

    @pytest.mark.asyncio
    async def test_insert_adds_and_flushes(self) -> None:
        """insert() calls session.add and session.flush."""
        session = make_session()
        doc_id = uuid.uuid4()
        chunk = sample_chunk(doc_id)

        repo = ChunkRepository(session)
        result = await repo.insert(chunk)

        session.add.assert_called_once_with(chunk)
        session.flush.assert_called_once()
        assert result is chunk

    @pytest.mark.asyncio
    async def test_insert_many_adds_all_chunks(self) -> None:
        """insert_many() adds each chunk to the session."""
        session = make_session()
        doc_id = uuid.uuid4()
        chunks = [sample_chunk(doc_id) for _ in range(3)]

        repo = ChunkRepository(session)
        result = await repo.insert_many(chunks)

        assert session.add.call_count == 3
        assert result == chunks

    @pytest.mark.asyncio
    async def test_get_by_id_returns_chunk(self) -> None:
        """get_by_id() returns the matching Chunk."""
        session = make_session()
        doc_id = uuid.uuid4()
        chunk = sample_chunk(doc_id)
        session.execute = AsyncMock(return_value=make_scalar_result(chunk))

        repo = ChunkRepository(session)
        result = await repo.get_by_id(chunk.id)

        assert result is chunk

    @pytest.mark.asyncio
    async def test_list_by_document_returns_chunks(self) -> None:
        """list_by_document() returns all chunks for a document."""
        session = make_session()
        doc_id = uuid.uuid4()
        chunks = [sample_chunk(doc_id) for _ in range(5)]
        session.execute = AsyncMock(return_value=make_scalars_result(chunks))

        repo = ChunkRepository(session)
        results = await repo.list_by_document(doc_id)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_count_by_document_returns_integer(self) -> None:
        """count_by_document() returns the chunk count."""
        session = make_session()
        session.execute = AsyncMock(return_value=make_scalar_result(7))

        repo = ChunkRepository(session)
        count = await repo.count_by_document(uuid.uuid4())

        assert count == 7


# ── EmbeddingRepository tests ─────────────────────────────────────────────────


class TestEmbeddingRepository:
    """Tests for EmbeddingRepository."""

    @pytest.mark.asyncio
    async def test_insert_adds_and_flushes(self) -> None:
        """insert() persists a ChunkEmbedding."""
        session = make_session()
        chunk_id = uuid.uuid4()
        emb = ChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=chunk_id,
            embedding=[0.1] * 768,
            model_name="nomic-embed-text-v1.5",
        )

        repo = EmbeddingRepository(session)
        result = await repo.insert(emb)

        session.add.assert_called_once_with(emb)
        session.flush.assert_called_once()
        assert result is emb

    @pytest.mark.asyncio
    async def test_insert_many_adds_all(self) -> None:
        """insert_many() adds all embeddings to the session."""
        session = make_session()
        embeddings = [
            ChunkEmbedding(
                id=uuid.uuid4(),
                chunk_id=uuid.uuid4(),
                embedding=[0.1] * 768,
                model_name="nomic-embed-text-v1.5",
            )
            for _ in range(3)
        ]

        repo = EmbeddingRepository(session)
        result = await repo.insert_many(embeddings)

        assert session.add.call_count == 3
        assert result == embeddings

    @pytest.mark.asyncio
    async def test_get_by_chunk_id_returns_embedding(self) -> None:
        """get_by_chunk_id() returns the matching ChunkEmbedding."""
        session = make_session()
        chunk_id = uuid.uuid4()
        emb = ChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=chunk_id,
            embedding=[0.1] * 768,
            model_name="nomic-embed-text-v1.5",
        )
        session.execute = AsyncMock(return_value=make_scalar_result(emb))

        repo = EmbeddingRepository(session)
        result = await repo.get_by_chunk_id(chunk_id)

        assert result is emb

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self) -> None:
        """delete_by_chunk_id() returns False when no embedding exists."""
        session = make_session()
        session.execute = AsyncMock(return_value=make_scalar_result(None))

        repo = EmbeddingRepository(session)
        result = await repo.delete_by_chunk_id(uuid.uuid4())

        assert result is False


# ── FeedbackRepository tests ──────────────────────────────────────────────────


class TestFeedbackRepository:
    """Tests for FeedbackRepository."""

    @pytest.mark.asyncio
    async def test_insert_adds_feedback(self) -> None:
        """insert() persists a Feedback entry."""
        session = make_session()
        fb = Feedback(
            id=uuid.uuid4(),
            query="What fields are mandatory for pacs.008?",
            chunk_ids=[uuid.uuid4()],
            rating=1,
            tool_name="find_message_type",
        )

        repo = FeedbackRepository(session)
        result = await repo.insert(fb)

        session.add.assert_called_once_with(fb)
        session.flush.assert_called_once()
        assert result is fb

    @pytest.mark.asyncio
    async def test_list_recent_returns_feedback(self) -> None:
        """list_recent() returns feedback entries."""
        session = make_session()
        fb = Feedback(
            id=uuid.uuid4(),
            query="test query",
            chunk_ids=[uuid.uuid4()],
            rating=0,
        )
        session.execute = AsyncMock(return_value=make_scalars_result([fb]))

        repo = FeedbackRepository(session)
        results = await repo.list_recent()

        assert len(results) == 1
        assert results[0] is fb


# ── IngestJobRepository tests ─────────────────────────────────────────────────


class TestIngestJobRepository:
    """Tests for IngestJobRepository."""

    @pytest.mark.asyncio
    async def test_insert_creates_job(self) -> None:
        """insert() persists an IngestJob entry."""
        session = make_session()
        job = IngestJob(
            id=uuid.uuid4(),
            source_path="/docs/annex_b.md",
            source_type="annex_b_spec",
            status="pending",
        )

        repo = IngestJobRepository(session)
        result = await repo.insert(job)

        session.add.assert_called_once_with(job)
        session.flush.assert_called_once()
        assert result is job

    @pytest.mark.asyncio
    async def test_mark_running_executes_update(self) -> None:
        """mark_running() issues an UPDATE statement."""
        session = make_session()
        mock_result = MagicMock(rowcount=1)
        session.execute = AsyncMock(return_value=mock_result)

        repo = IngestJobRepository(session)
        await repo.mark_running(uuid.uuid4())

        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_completed_executes_update(self) -> None:
        """mark_completed() issues an UPDATE with chunks_created."""
        session = make_session()
        mock_result = MagicMock(rowcount=1)
        session.execute = AsyncMock(return_value=mock_result)

        repo = IngestJobRepository(session)
        await repo.mark_completed(uuid.uuid4(), chunks_created=42)

        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_failed_executes_update(self) -> None:
        """mark_failed() issues an UPDATE with error_message."""
        session = make_session()
        mock_result = MagicMock(rowcount=1)
        session.execute = AsyncMock(return_value=mock_result)

        repo = IngestJobRepository(session)
        await repo.mark_failed(uuid.uuid4(), error_message="File not found")

        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_by_status_returns_jobs(self) -> None:
        """list_by_status() returns jobs matching the given status."""
        session = make_session()
        job = IngestJob(
            id=uuid.uuid4(),
            source_path="/docs/annex_b.md",
            source_type="annex_b_spec",
            status="failed",
        )
        session.execute = AsyncMock(return_value=make_scalars_result([job]))

        repo = IngestJobRepository(session)
        results = await repo.list_by_status("failed")

        assert len(results) == 1
        assert results[0] is job
