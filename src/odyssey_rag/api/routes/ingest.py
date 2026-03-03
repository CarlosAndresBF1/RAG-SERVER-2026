"""Ingest endpoints — POST /api/v1/ingest and POST /api/v1/ingest/batch."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.schemas import (
    BatchIngestRequest,
    BatchIngestResponse,
    BatchIngestResultItem,
    IngestRequest,
    IngestResponse,
)
from odyssey_rag.ingestion.pipeline import ingest

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_file(
    request: IngestRequest,
    _: str = Depends(verify_api_key),
) -> IngestResponse:
    """Ingest a single file into the knowledge base."""
    overrides: dict[str, str] = {}
    if request.source_type:
        overrides["source_type"] = request.source_type
    if request.metadata_overrides:
        overrides.update(request.metadata_overrides)

    start = time.monotonic()
    result = await ingest(
        source_path=request.source_path,
        overrides=overrides or None,
        replace_existing=request.replace_existing,
    )
    duration_ms = int((time.monotonic() - start) * 1000)

    return IngestResponse(
        status=result.status,
        document_id=str(result.document_id) if result.document_id else None,
        source_path=result.source_path,
        source_type=result.source_type or None,
        chunks_created=result.chunks_created if result.chunks_created > 0 else None,
        duration_ms=duration_ms,
        reason=result.reason or None,
        error=result.error or None,
    )


@router.post("/ingest/batch", response_model=BatchIngestResponse)
async def ingest_batch(
    request: BatchIngestRequest,
    _: str = Depends(verify_api_key),
) -> BatchIngestResponse:
    """Ingest multiple files concurrently."""

    async def _ingest_one(item):
        overrides: dict[str, str] = {}
        if item.source_type:
            overrides["source_type"] = item.source_type
        if item.metadata_overrides:
            overrides.update(item.metadata_overrides)
        return await ingest(
            source_path=item.source_path,
            overrides=overrides or None,
            replace_existing=request.replace_existing,
        )

    start = time.monotonic()
    results = await asyncio.gather(*[_ingest_one(item) for item in request.sources])
    duration_ms = int((time.monotonic() - start) * 1000)

    completed = sum(1 for r in results if r.status == "completed")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")

    return BatchIngestResponse(
        total=len(results),
        completed=completed,
        skipped=skipped,
        failed=failed,
        results=[
            BatchIngestResultItem(
                source_path=r.source_path,
                status=r.status,
                chunks_created=r.chunks_created if r.chunks_created > 0 else None,
                reason=r.reason or None,
                error=r.error or None,
            )
            for r in results
        ],
        duration_ms=duration_ms,
    )
