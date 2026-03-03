"""Chunks endpoint — GET /api/v1/chunks.

Supports filtering by document, message type, source type, and section.
"""

from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.deps import get_async_session
from odyssey_rag.api.schemas import ChunkListResponse, ChunkSummary
from odyssey_rag.db.repositories.chunks import ChunkRepository

router = APIRouter()


@router.get("/chunks", response_model=ChunkListResponse)
async def list_chunks(
    document_id: str | None = None,
    message_type: str | None = None,
    source_type: str | None = None,
    section: str | None = None,
    page: int = 1,
    page_size: int = 50,
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(verify_api_key),
) -> ChunkListResponse:
    """List chunks with optional filters and pagination."""
    doc_uuid: uuid_mod.UUID | None = None
    if document_id is not None:
        try:
            doc_uuid = uuid_mod.UUID(document_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid document_id format (expected UUID)")

    offset = (page - 1) * page_size
    chunk_repo = ChunkRepository(session)

    chunks, total = await chunk_repo.list_with_filters(
        document_id=doc_uuid,
        message_type=message_type,
        source_type=source_type,
        section=section,
        limit=page_size,
        offset=offset,
    )

    return ChunkListResponse(
        items=[
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
        total=total,
        page=page,
        page_size=page_size,
    )
