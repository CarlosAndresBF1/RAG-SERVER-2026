"""BM25 full-text search using PostgreSQL tsvector.

Uses PostgreSQL's built-in ``websearch_to_tsquery`` and ``ts_rank_cd``
functions against the GIN-indexed ``tsvector_content`` column.
"""

from __future__ import annotations

from typing import Optional

import structlog
from sqlalchemy import text

from odyssey_rag.db.session import db_session
from odyssey_rag.retrieval.vector_search import SearchResult

logger = structlog.get_logger(__name__)


async def bm25_search(
    query: str,
    filters: Optional[dict[str, str]] = None,
    limit: int = 30,
) -> list[SearchResult]:
    """Full-text search using PostgreSQL tsvector and ts_rank_cd.

    Uses ``websearch_to_tsquery('english', :query)`` for natural-language
    query syntax (supports phrase matching and boolean operators).
    Results are optionally pre-filtered by metadata.

    Falls back to ``plainto_tsquery`` if ``websearch_to_tsquery`` is not
    available (PostgreSQL < 11).

    Args:
        query:   Natural-language or keyword query string.
        filters: Optional ``{"message_type": ..., "source_type": ...}`` dict.
        limit:   Maximum number of results to return.

    Returns:
        List of SearchResult objects ordered by descending BM25 rank.
    """
    filters = filters or {}
    msg_type = filters.get("message_type")
    source_type = filters.get("source_type")
    integration = filters.get("integration")

    # Fall back gracefully if tsvector_content is null (re-index not yet run)
    sql = text(
        """
        SELECT
            c.id AS chunk_id,
            c.content,
            c.section,
            c.subsection,
            c.chunk_index,
            d.source_path,
            d.source_type,
            cm.message_type,
            ts_rank_cd(
                c.tsvector_content,
                websearch_to_tsquery('english', :query)
            ) AS score
        FROM chunk c
        JOIN document d ON c.document_id = d.id
        LEFT JOIN chunk_metadata cm ON c.id = cm.chunk_id
        WHERE d.is_current = TRUE
          AND c.tsvector_content
                  @@ websearch_to_tsquery('english', :query)
          AND (CAST(:msg_type AS TEXT) IS NULL OR cm.message_type = CAST(:msg_type AS TEXT))
          AND (CAST(:source_type AS TEXT) IS NULL OR d.source_type = CAST(:source_type AS TEXT))
          AND (CAST(:integration AS TEXT) IS NULL OR d.integration = CAST(:integration AS TEXT))
        ORDER BY score DESC
        LIMIT :limit
        """
    )

    results: list[SearchResult] = []
    try:
        async with db_session() as session:
            rows = await session.execute(
                sql,
                {
                    "query": query,
                    "msg_type": msg_type,
                    "source_type": source_type,
                    "integration": integration,
                    "limit": limit,
                },
            )
            for row in rows.mappings():
                results.append(
                    SearchResult(
                        chunk_id=row["chunk_id"],
                        content=row["content"],
                        section=row["section"],
                        subsection=row["subsection"],
                        chunk_index=row["chunk_index"],
                        source_path=row["source_path"],
                        source_type=row["source_type"],
                        message_type=row["message_type"],
                        score=float(row["score"]),
                    )
                )
    except Exception as exc:
        logger.warning("bm25_search_failed", error=str(exc))

    return results
