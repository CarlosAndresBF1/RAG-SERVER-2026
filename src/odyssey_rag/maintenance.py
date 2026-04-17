"""Maintenance utilities for the Odyssey RAG system.

Provides scheduled and on-demand maintenance tasks such as garbage
collection of superseded documents.
"""

from __future__ import annotations

import structlog

from odyssey_rag.db.repositories.documents import DocumentRepository
from odyssey_rag.db.session import db_session

logger = structlog.get_logger(__name__)


async def schedule_gc(retention_days: int = 30) -> int:
    """Run garbage collection for superseded documents.

    Deletes all documents where ``is_current=False`` and ``updated_at``
    is older than the given retention period. Cascaded rows (chunks,
    embeddings, metadata) are removed by the database.

    Can be called from an API endpoint or an external cron scheduler.

    Args:
        retention_days: Days to retain superseded documents before deletion.

    Returns:
        Number of documents deleted.
    """
    async with db_session() as session:
        repo = DocumentRepository(session)
        deleted = await repo.garbage_collect_superseded(retention_days)

    logger.info(
        "maintenance.gc_complete",
        deleted_documents=deleted,
        retention_days=retention_days,
    )
    return deleted
