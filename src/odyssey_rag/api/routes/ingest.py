"""Ingest endpoints — POST /api/v1/ingest and POST /api/v1/ingest/batch.

Ingestion is asynchronous: the endpoint creates an IngestJob record with
status "pending", fires off the pipeline in a background task, and returns
the job_id immediately so the client can poll /api/v1/jobs for progress.
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, Depends

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.schemas import (
    BatchIngestRequest,
    IngestRequest,
)
from odyssey_rag.db.models import IngestJob
from odyssey_rag.db.repositories.ingest_jobs import IngestJobRepository
from odyssey_rag.db.session import db_session
from odyssey_rag.ingestion.pipeline import detect_source_type, ingest
from odyssey_rag.job_resilience import IngestTaskRegistry

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _run_ingest_background(
    source_path: str,
    overrides: dict[str, str] | None,
    replace_existing: bool,
) -> None:
    """Run the full ingest pipeline; exceptions are logged (never propagated)."""
    try:
        await ingest(
            source_path=source_path,
            overrides=overrides,
            replace_existing=replace_existing,
        )
    except Exception:
        logger.exception("background_ingest_failed", source_path=source_path)


@router.post("/ingest")
async def ingest_file(
    request: IngestRequest,
    _: str = Depends(verify_api_key),
):
    """Queue a single file for ingestion (returns immediately).

    Creates an IngestJob record and launches the pipeline in background.
    The client should poll ``GET /api/v1/jobs`` to track progress.
    """
    overrides: dict[str, str] = {}
    if request.source_type:
        overrides["source_type"] = request.source_type
    if request.metadata_overrides:
        overrides.update(request.metadata_overrides)

    source_type = detect_source_type(request.source_path, overrides or None)
    job_id = uuid.uuid4()

    # Persist a pending job so the UI can show it immediately
    async with db_session() as session:
        job_repo = IngestJobRepository(session)
        job = IngestJob(
            id=job_id,
            source_path=request.source_path,
            source_type=source_type,
            status="pending",
        )
        await job_repo.insert(job)

    # Fire-and-forget background processing (tracked for graceful shutdown)
    task = asyncio.create_task(
        _run_ingest_background(
            source_path=request.source_path,
            overrides=overrides or None,
            replace_existing=request.replace_existing,
        )
    )
    IngestTaskRegistry.register(job_id, task)

    return {
        "job_id": str(job_id),
        "status": "pending",
        "source_path": request.source_path,
        "source_type": source_type,
    }


@router.post("/ingest/batch")
async def ingest_batch(
    request: BatchIngestRequest,
    _: str = Depends(verify_api_key),
):
    """Queue multiple files for ingestion (returns immediately).

    Creates one IngestJob per file and launches background tasks.
    """
    jobs_created: list[dict] = []

    for item in request.sources:
        overrides: dict[str, str] = {}
        if item.source_type:
            overrides["source_type"] = item.source_type
        if item.metadata_overrides:
            overrides.update(item.metadata_overrides)

        source_type = detect_source_type(item.source_path, overrides or None)
        job_id = uuid.uuid4()

        async with db_session() as session:
            job_repo = IngestJobRepository(session)
            job = IngestJob(
                id=job_id,
                source_path=item.source_path,
                source_type=source_type,
                status="pending",
            )
            await job_repo.insert(job)

        task = asyncio.create_task(
            _run_ingest_background(
                source_path=item.source_path,
                overrides=overrides or None,
                replace_existing=request.replace_existing,
            )
        )
        IngestTaskRegistry.register(job_id, task)

        jobs_created.append({
            "job_id": str(job_id),
            "source_path": item.source_path,
            "source_type": source_type,
            "status": "pending",
        })

    return {
        "total": len(jobs_created),
        "jobs": jobs_created,
    }
