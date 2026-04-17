"""Pydantic schemas for the Odyssey RAG API.

All request/response models for the FastAPI endpoints defined in
API_REFERENCE.md.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Health ────────────────────────────────────────────────────────────────────


class ServiceStatus(BaseModel):
    database: str
    embedding_model: str
    reranker: str


class HealthResponse(BaseModel):
    status: str  # ok | degraded
    version: str
    services: ServiceStatus


# ── Search ────────────────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    message_type: str | None = Field(
        None, pattern=r"^(pacs|camt|pain|acmt)\.\d{3}$"
    )
    source_type: str | None = None
    focus: str | None = Field(
        None,
        pattern=r"^(overview|fields|builder|parser|validator|examples|envelope)$",
    )
    top_k: int = Field(10, ge=1, le=20)


class CitationSchema(BaseModel):
    source_path: str
    section: str | None = None
    chunk_index: int


class EvidenceItem(BaseModel):
    text: str
    relevance: float = Field(..., ge=0.0, le=1.0)
    citations: list[CitationSchema]
    message_type: str | None = None
    source_type: str


class SearchResponse(BaseModel):
    query: str
    evidence: list[EvidenceItem]
    gaps: list[str]
    followups: list[str]
    metadata: dict[str, Any]


# ── Ingest ────────────────────────────────────────────────────────────────────


class IngestRequest(BaseModel):
    source_path: str = Field(..., min_length=1)
    source_type: str | None = None
    metadata_overrides: dict[str, str] | None = None
    replace_existing: bool = False


class IngestResponse(BaseModel):
    status: str  # completed | skipped | failed
    document_id: str | None = None
    source_path: str
    source_type: str | None = None
    chunks_created: int | None = None
    file_hash: str | None = None
    duration_ms: int | None = None
    reason: str | None = None
    error: str | None = None


class BatchIngestItem(BaseModel):
    source_path: str = Field(..., min_length=1)
    source_type: str | None = None
    metadata_overrides: dict[str, str] | None = None


class BatchIngestRequest(BaseModel):
    sources: list[BatchIngestItem]
    replace_existing: bool = False


class BatchIngestResultItem(BaseModel):
    source_path: str
    status: str
    chunks_created: int | None = None
    reason: str | None = None
    error: str | None = None


class BatchIngestResponse(BaseModel):
    total: int
    completed: int
    skipped: int
    failed: int
    results: list[BatchIngestResultItem]
    duration_ms: int


# ── Sources ───────────────────────────────────────────────────────────────────


class SourceItem(BaseModel):
    id: str
    source_path: str
    source_type: str
    file_hash: str
    total_chunks: int
    is_current: bool
    ingested_at: str


class SourceListResponse(BaseModel):
    items: list[SourceItem]
    total: int
    page: int
    page_size: int


class ChunkSummary(BaseModel):
    id: str
    chunk_index: int
    content: str
    token_count: int
    section: str | None = None
    subsection: str | None = None
    metadata: dict[str, Any]


class SourceDetailResponse(BaseModel):
    id: str
    source_path: str
    source_type: str
    file_hash: str
    total_chunks: int
    is_current: bool
    ingested_at: str
    chunks: list[ChunkSummary]


class DeleteSourceResponse(BaseModel):
    deleted: bool
    document_id: str
    chunks_deleted: int


# ── Chunks ────────────────────────────────────────────────────────────────────


class ChunkListResponse(BaseModel):
    items: list[ChunkSummary]
    total: int
    page: int
    page_size: int


# ── Feedback ──────────────────────────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    query: str
    chunk_id: str  # UUID string of the chunk being rated
    rating: int = Field(..., ge=-1, le=1)
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: str  # UUID of the created feedback record
    status: str  # "accepted"


# ── Errors ────────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    detail: str
    error_code: str
    context: dict[str, Any] = {}


# ── Categories ────────────────────────────────────────────────────────────────


class CategoryRuleCreate(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=500, description="Regex pattern")
    source_type: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    priority: int = Field(100, ge=0, le=10000)


class CategoryRuleUpdate(BaseModel):
    pattern: str | None = Field(None, min_length=1, max_length=500)
    source_type: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = None
    priority: int | None = Field(None, ge=0, le=10000)


class CategoryRuleResponse(BaseModel):
    id: str
    pattern: str
    source_type: str
    description: str | None = None
    priority: int
    is_active: bool
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CategoryListItem(BaseModel):
    source_type: str
    origin: str  # "hardcoded" | "custom" | "keyword"


class CategoryListResponse(BaseModel):
    items: list[dict[str, str]]
    total: int


class CategorySuggestionResponse(BaseModel):
    source_type: str
    doc_count: int


class CategoryDetectRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=1000)


class CategoryDetectResponse(BaseModel):
    filename: str
    source_type: str
