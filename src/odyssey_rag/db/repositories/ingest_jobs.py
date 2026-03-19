"""Repository for IngestJob CRUD operations.

Tracks ingestion pipeline executions: creation, status updates, and
querying pending/failed jobs for retry logic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.db.models import IngestJob

logger = structlog.get_logger(__name__)


class IngestJobRepository:
    """Data access layer for the IngestJob table.

    All methods accept an AsyncSession injected by the caller.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an active AsyncSession.

        Args:
            session: SQLAlchemy async session (caller-owned lifecycle).
        """
        self._session = session

    async def insert(self, job: IngestJob) -> IngestJob:
        """Persist a new ingest job.

        Args:
            job: Transient IngestJob instance to save.

        Returns:
            The same instance after flush.
        """
        self._session.add(job)
        await self._session.flush()
        logger.info(
            "ingest_job.created",
            id=str(job.id),
            source_path=job.source_path,
            status=job.status,
        )
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> IngestJob | None:
        """Fetch an ingest job by primary key.

        Args:
            job_id: UUID primary key.

        Returns:
            IngestJob instance or None if not found.
        """
        result = await self._session.execute(
            select(IngestJob).where(IngestJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_by_status(
        self, status: str, limit: int = 50
    ) -> list[IngestJob]:
        """List ingest jobs filtered by status.

        Args:
            status: One of "pending", "running", "completed", "failed".
            limit: Maximum rows to return.

        Returns:
            List of IngestJob instances, ordered by creation time ascending.
        """
        result = await self._session.execute(
            select(IngestJob)
            .where(IngestJob.status == status)
            .order_by(IngestJob.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_running(self, job_id: uuid.UUID) -> None:
        """Transition a job to running status and record start time.

        Args:
            job_id: UUID of the job to update.
        """
        await self._session.execute(
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(status="running", started_at=datetime.now(tz=timezone.utc))
        )

    async def mark_completed(
        self, job_id: uuid.UUID, chunks_created: int
    ) -> None:
        """Transition a job to completed status.

        Args:
            job_id: UUID of the job to update.
            chunks_created: Number of chunks produced by this ingestion.
        """
        await self._session.execute(
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(
                status="completed",
                chunks_created=chunks_created,
                completed_at=datetime.now(tz=timezone.utc),
            )
        )
        logger.info(
            "ingest_job.completed", id=str(job_id), chunks_created=chunks_created
        )

    async def mark_failed(self, job_id: uuid.UUID, error_message: str) -> None:
        """Transition a job to failed status with an error message.

        Args:
            job_id: UUID of the job to update.
            error_message: Human-readable error description.
        """
        await self._session.execute(
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(
                status="failed",
                error_message=error_message,
                completed_at=datetime.now(tz=timezone.utc),
            )
        )
        logger.error("ingest_job.failed", id=str(job_id), error=error_message)

    async def mark_cancelled(self, job_id: uuid.UUID) -> None:
        """Transition a pending or running job to cancelled status.

        Args:
            job_id: UUID of the job to cancel.
        """
        await self._session.execute(
            update(IngestJob)
            .where(
                IngestJob.id == job_id,
                IngestJob.status.in_(["pending", "running"]),
            )
            .values(
                status="cancelled",
                error_message="Cancelled by user",
                completed_at=datetime.now(tz=timezone.utc),
            )
        )
        logger.info("ingest_job.cancelled", id=str(job_id))

    async def delete_job(self, job_id: uuid.UUID) -> bool:
        """Delete a finished job record (completed, failed, or cancelled).

        Returns True if a row was deleted.
        """
        from sqlalchemy import delete as sa_delete
        result = await self._session.execute(
            sa_delete(IngestJob).where(
                IngestJob.id == job_id,
                IngestJob.status.in_(["completed", "failed", "cancelled"]),
            )
        )
        deleted = result.rowcount > 0
        if deleted:
            logger.info("ingest_job.deleted", id=str(job_id))
        return deleted

    async def find_pending_by_path(self, source_path: str) -> IngestJob | None:
        """Find the most recent pending job for a given source path.

        Used by the pipeline to re-use job records created by the API layer
        instead of creating duplicates.
        """
        result = await self._session.execute(
            select(IngestJob)
            .where(IngestJob.source_path == source_path, IngestJob.status == "pending")
            .order_by(IngestJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
