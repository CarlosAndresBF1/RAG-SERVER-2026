from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.api.deps import get_async_session
from odyssey_rag.db.models import Chunk, ChunkMetadata, Document, Feedback, IngestJob

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def get_overview(db: AsyncSession = Depends(get_async_session)) -> Dict[str, Any]:
    """Get high-level statistics for the admin dashboard overview."""
    # Total documents (where is_current is True)
    doc_count_stmt = select(func.count()).select_from(Document).where(Document.is_current == True)
    doc_count = await db.scalar(doc_count_stmt) or 0

    # Total chunks
    chunk_count_stmt = select(func.count()).select_from(Chunk)
    chunk_count = await db.scalar(chunk_count_stmt) or 0

    # Ingests per day for the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    ingests_stmt = (
        select(func.date_trunc('day', IngestJob.created_at).label('day'), func.count())
        .where(IngestJob.created_at >= thirty_days_ago)
        .group_by('day')
        .order_by('day')
    )
    result = await db.execute(ingests_stmt)
    ingests_per_day = [{"date": row.day.isoformat(), "count": row.count} for row in result.all() if row.day]

    return {
        "total_documents": doc_count,
        "total_chunks": chunk_count,
        "ingests_per_day": ingests_per_day,
    }


@router.get("/coverage")
async def get_coverage(db: AsyncSession = Depends(get_async_session)) -> Dict[str, Any]:
    """Get coverage data: message_type matrix AND source_type summary.

    Returns both the original message_type × source_type matrix (for BimPay
    ISO 20022 coverage) and a broader source_type summary that includes ALL
    ingested documents regardless of whether they have a message_type.
    """
    # ── Message-type matrix (ISO 20022 / BimPay) ─────────────────────────
    mt_stmt = (
        select(ChunkMetadata.message_type, ChunkMetadata.source_type, func.count())
        .where(ChunkMetadata.message_type != None)
        .group_by(ChunkMetadata.message_type, ChunkMetadata.source_type)
    )
    mt_result = await db.execute(mt_stmt)

    matrix: list[dict[str, Any]] = []
    message_types = set()
    source_types = set()

    for row in mt_result.all():
        m_type = row.message_type
        s_type = row.source_type
        count = row.count
        message_types.add(m_type)
        source_types.add(s_type)
        matrix.append({
            "message_type": m_type,
            "source_type": s_type,
            "chunk_count": count,
        })

    # ── Source-type summary (ALL documents) ───────────────────────────────
    st_stmt = (
        select(
            Document.source_type,
            func.count(func.distinct(Document.id)).label("doc_count"),
            func.coalesce(func.sum(Document.total_chunks), 0).label("chunk_count"),
        )
        .where(Document.is_current == True)
        .group_by(Document.source_type)
    )
    st_result = await db.execute(st_stmt)
    source_type_summary = [
        {
            "source_type": row.source_type,
            "doc_count": row.doc_count,
            "chunk_count": int(row.chunk_count),
        }
        for row in st_result.all()
    ]

    return {
        "matrix": matrix,
        "message_types": sorted(list(message_types)),
        "source_types": sorted(list(source_types)),
        "source_type_summary": sorted(source_type_summary, key=lambda x: x["chunk_count"], reverse=True),
    }


@router.get("/feedback")
async def get_feedback_stats(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Get feedback KPIs, distribution, trend, and individual rows."""
    # Aggregate distribution
    stmt = select(Feedback.rating, func.count()).group_by(Feedback.rating)
    result = await db.execute(stmt)

    distribution = {"positive": 0, "neutral": 0, "negative": 0}
    total = 0
    for row in result.all():
        rating = row.rating
        count = row.count
        total += count
        if rating == 1:
            distribution["positive"] = count
        elif rating == 0:
            distribution["neutral"] = count
        elif rating == -1:
            distribution["negative"] = count

    positivity_rate = round((distribution["positive"] / total * 100), 2) if total > 0 else 0
    avg_stmt = select(func.avg(Feedback.rating))
    avg_rating = await db.scalar(avg_stmt)
    avg_rating = float(avg_rating) if avg_rating is not None else 0.0

    # Daily trend (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    trend_stmt = (
        select(
            func.date_trunc("day", Feedback.created_at).label("day"),
            func.count().label("count"),
            func.avg(Feedback.rating).label("avg_rating"),
        )
        .where(Feedback.created_at >= thirty_days_ago)
        .group_by("day")
        .order_by("day")
    )
    trend_result = await db.execute(trend_stmt)
    trend = [
        {
            "date": row.day.isoformat() if row.day else None,
            "count": row.count,
            "avg_rating": round(float(row.avg_rating), 2) if row.avg_rating is not None else 0,
        }
        for row in trend_result.all()
        if row.day
    ]

    # Paginated detail rows (newest first)
    offset = (page - 1) * page_size
    rows_stmt = (
        select(Feedback)
        .order_by(Feedback.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    rows_result = await db.execute(rows_stmt)
    rows = [
        {
            "id": str(fb.id),
            "query": fb.query,
            "rating": fb.rating,
            "comment": fb.comment,
            "tool_name": fb.tool_name,
            "chunk_ids": [str(cid) for cid in (fb.chunk_ids or [])],
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
        }
        for fb in rows_result.scalars().all()
    ]

    return {
        "total": total,
        "average_rating": round(avg_rating, 2),
        "positivity_rate": positivity_rate,
        "distribution": distribution,
        "trend": trend,
        "rows": rows,
        "page": page,
        "page_size": page_size,
    }


@router.get("/db")
async def get_db_stats(db: AsyncSession = Depends(get_async_session)) -> Dict[str, Any]:
    """Get database statistics: table sizes, row counts, total DB size."""
    # Row counts for key tables
    tables = ["document", "chunk", "chunk_metadata", "embedding", "feedback", "ingest_job", "mcp_token", "admin_user"]
    row_counts: dict[str, int] = {}
    for table in tables:
        try:
            result = await db.scalar(text(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608
            row_counts[table] = result or 0
        except Exception:
            await db.rollback()
            row_counts[table] = -1

    # Total DB size
    try:
        db_size_result = await db.scalar(
            text("SELECT pg_size_pretty(pg_database_size(current_database()))")
        )
    except Exception:
        await db.rollback()
        db_size_result = "unknown"

    # Table sizes
    try:
        table_sizes_stmt = text(
            "SELECT relname AS table, "
            "pg_size_pretty(pg_total_relation_size(relid)) AS size "
            "FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 20"
        )
        sizes_result = await db.execute(table_sizes_stmt)
        table_sizes = [
            {"table": row.table, "size": row.size}
            for row in sizes_result.all()
        ]
    except Exception:
        await db.rollback()
        table_sizes = []

    return {
        "database_size": db_size_result or "unknown",
        "row_counts": row_counts,
        "table_sizes": table_sizes,
    }
