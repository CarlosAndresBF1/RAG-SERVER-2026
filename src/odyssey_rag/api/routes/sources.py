"""Source endpoints — list, detail, and delete indexed documents.

Routes:
    GET    /api/v1/sources
    GET    /api/v1/sources/{document_id}
    DELETE /api/v1/sources/{document_id}
"""

from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.deps import get_async_session
from odyssey_rag.api.schemas import (
    ChunkSummary,
    DeleteSourceResponse,
    SourceDetailResponse,
    SourceItem,
    SourceListResponse,
)
from odyssey_rag.db.repositories.chunks import ChunkRepository
from odyssey_rag.db.repositories.documents import DocumentRepository

router = APIRouter()


def _dt_str(dt) -> str:
    """Format a datetime to ISO 8601 string."""
    return dt.isoformat() if dt is not None else ""


def _parse_uuid(value: str, param: str = "document_id") -> uuid_mod.UUID:
    """Parse a UUID string, raising 400 on invalid format."""
    try:
        return uuid_mod.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {param} format (expected UUID)")


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    source_type: str | None = None,
    is_current: bool = True,
    page: int = 1,
    page_size: int = 50,
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(verify_api_key),
) -> SourceListResponse:
    """List indexed source documents with optional filtering and pagination."""
    offset = (page - 1) * page_size
    doc_repo = DocumentRepository(session)

    docs = await doc_repo.list_current(source_type=source_type, limit=page_size, offset=offset)
    total = await doc_repo.count_current(source_type=source_type)

    return SourceListResponse(
        items=[
            SourceItem(
                id=str(doc.id),
                source_path=doc.source_path,
                source_type=doc.source_type,
                file_hash=doc.file_hash,
                total_chunks=doc.total_chunks,
                is_current=doc.is_current,
                ingested_at=_dt_str(doc.created_at),
            )
            for doc in docs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sources/{document_id}", response_model=SourceDetailResponse)
async def get_source(
    document_id: str,
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(verify_api_key),
) -> SourceDetailResponse:
    """Get full detail for a document, including all its chunks."""
    doc_uuid = _parse_uuid(document_id)
    doc_repo = DocumentRepository(session)
    chunk_repo = ChunkRepository(session)

    doc = await doc_repo.get_by_id(doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    chunks = await chunk_repo.list_by_document(doc.id)

    return SourceDetailResponse(
        id=str(doc.id),
        source_path=doc.source_path,
        source_type=doc.source_type,
        file_hash=doc.file_hash,
        total_chunks=doc.total_chunks,
        is_current=doc.is_current,
        ingested_at=_dt_str(doc.created_at),
        chunks=[
            ChunkSummary(
                id=str(c.id),
                chunk_index=c.chunk_index,
                content=c.content,
                token_count=c.token_count,
                section=c.section,
                subsection=c.subsection,
                metadata=c.metadata_json or {},
            )
            for c in chunks
        ],
    )


@router.delete("/sources/{document_id}", response_model=DeleteSourceResponse)
async def delete_source(
    document_id: str,
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(verify_api_key),
) -> DeleteSourceResponse:
    """Hard-delete a document and all its associated chunks and embeddings."""
    doc_uuid = _parse_uuid(document_id)
    doc_repo = DocumentRepository(session)
    chunk_repo = ChunkRepository(session)

    doc = await doc_repo.get_by_id(doc_uuid)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    chunks_count = await chunk_repo.count_by_document(doc_uuid)
    deleted = await doc_repo.delete(doc_uuid)

    return DeleteSourceResponse(
        deleted=deleted,
        document_id=document_id,
        chunks_deleted=chunks_count,
    )
