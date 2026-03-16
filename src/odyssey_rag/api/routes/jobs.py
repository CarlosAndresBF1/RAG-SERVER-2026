from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import asc, desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.api.deps import get_async_session
from odyssey_rag.db.models import IngestJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = Query(None, description="Filter by status: pending|running|completed|failed"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """List ingestion jobs with pagination and optional status filter."""
    base = select(IngestJob)
    count_base = select(func.count()).select_from(IngestJob)

    if status:
        base = base.where(IngestJob.status == status)
        count_base = count_base.where(IngestJob.status == status)

    stmt = base.order_by(desc(IngestJob.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    total = await db.scalar(count_base) or 0
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "jobs": [
            {
                "id": str(job.id),
                "source_path": job.source_path,
                "source_type": job.source_type,
                "status": job.status,
                "chunks_created": job.chunks_created,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
            for job in jobs
        ]
    }
