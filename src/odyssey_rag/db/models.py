"""SQLAlchemy ORM models for the Odyssey RAG database.

Six tables are defined here, matching the DDL in db/init/002_schema.sql:
  - Document          : Indexed source files (one per version)
  - Chunk             : Text fragments — the core retrieval unit
  - ChunkEmbedding    : 768-dim vector embedding (1:1 with Chunk)
  - ChunkMetadata     : Structured domain metadata for filtering
  - IngestJob         : Ingestion pipeline execution tracking
  - Feedback          : User/agent quality feedback

Note: Optional[X] is used instead of X | None for SQLAlchemy compatibility
across Python 3.9+ (the ORM evaluates annotation strings at class creation).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import (
    ARRAY,
    UUID,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Document(Base):
    """Indexed source file — one row per ingested document version.

    When a file changes, the old row is marked ``is_current=False`` and a
    new row is inserted (change detection via SHA-256 file hash).
    """

    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    integration: Mapped[str] = mapped_column(
        String(100), default="bimpay", nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chunks: Mapped[list[Chunk]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """Text fragment — the core unit of retrieval.

    Each chunk belongs to exactly one Document and optionally has one
    ChunkEmbedding and one ChunkMetadata row.
    """

    __tablename__ = "chunk"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subsection: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    # Pre-computed full-text search vector — updated by DB trigger
    tsvector_content: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    document: Mapped[Document] = relationship("Document", back_populates="chunks")
    embedding: Mapped[Optional[ChunkEmbedding]] = relationship(
        "ChunkEmbedding",
        back_populates="chunk",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chunk_metadata: Mapped[Optional[ChunkMetadata]] = relationship(
        "ChunkMetadata",
        back_populates="chunk",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ChunkEmbedding(Base):
    """768-dimensional vector embedding — 1:1 relationship with Chunk.

    Uses pgvector VECTOR(768) type with HNSW index for fast ANN search.
    """

    __tablename__ = "chunk_embedding"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunk.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    model_name: Mapped[str] = mapped_column(
        String(100), default="nomic-embed-text-v1.5", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunk: Mapped[Chunk] = relationship("Chunk", back_populates="embedding")


class ChunkMetadata(Base):
    """Structured domain metadata for a chunk — enables efficient filtering.

    Stores ISO 20022 and Odyssey-code domain fields so retrieval can apply
    precise pre-filters (message type, rule status, PHP class, etc.).
    """

    __tablename__ = "chunk_metadata"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunk.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ISO 20022 domain
    message_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    iso_version: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    field_xpath: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rule_status: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    data_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Odyssey code domain
    module_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    php_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    php_symbol: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Source classification
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunk: Mapped[Chunk] = relationship("Chunk", back_populates="chunk_metadata")


class IngestJob(Base):
    """Tracks each ingestion pipeline execution.

    One row per ingest request. Used for monitoring, retry logic, and
    debugging ingestion failures.
    """

    __tablename__ = "ingest_job"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending | running | completed | failed
    chunks_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Feedback(Base):
    """User and agent feedback for retrieval quality improvement.

    Ratings (-1 bad / 0 neutral / 1 good) collected after MCP tool
    responses are used to track quality trends and tune retrieval.
    """

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
