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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, INET
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
    )  # pending | running | completed | failed | cancelled
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


# ── Admin & MCP Token models (Phase 2) ──────────────────────────────────


class AdminUser(Base):
    """Admin user for the web UI dashboard."""

    __tablename__ = "admin_user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tokens: Mapped[list[McpToken]] = relationship(
        "McpToken", back_populates="issuer", cascade="all, delete-orphan"
    )


class McpToken(Base):
    """MCP access token — hashed, with scopes and expiry."""

    __tablename__ = "mcp_token"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    issued_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_user.id"),
        nullable=False,
    )
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    issuer: Mapped[AdminUser] = relationship("AdminUser", back_populates="tokens")
    audit_logs: Mapped[list[McpTokenAudit]] = relationship(
        "McpTokenAudit", back_populates="token", cascade="all, delete-orphan"
    )


class McpTokenAudit(Base):
    """Audit log entry for MCP token usage."""

    __tablename__ = "mcp_token_audit"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    token_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_token.id"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    token: Mapped[McpToken] = relationship("McpToken", back_populates="audit_logs")
