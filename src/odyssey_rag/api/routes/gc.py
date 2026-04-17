"""Admin garbage-collection endpoint.

Routes:
    POST /api/v1/admin/gc — trigger garbage collection of superseded documents
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.maintenance import schedule_gc

router = APIRouter(prefix="/admin", tags=["admin"])


class GcRequest(BaseModel):
    """Request body for garbage collection."""

    retention_days: int = Field(default=30, ge=1, description="Days to retain superseded docs")


class GcResponse(BaseModel):
    """Response from garbage collection."""

    deleted_documents: int
    retention_days: int


@router.post("/gc", response_model=GcResponse, summary="Garbage-collect superseded documents")
async def run_gc(
    body: GcRequest | None = None,
    _: str = Depends(verify_api_key),
) -> GcResponse:
    """Delete superseded documents older than the retention period.

    Superseded documents (``is_current=False``) accumulate when files are
    re-ingested with changes. This endpoint removes stale rows and their
    cascaded chunks, embeddings, and metadata.
    """
    retention_days = body.retention_days if body else 30
    deleted = await schedule_gc(retention_days=retention_days)
    return GcResponse(deleted_documents=deleted, retention_days=retention_days)
