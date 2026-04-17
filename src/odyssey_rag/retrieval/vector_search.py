"""Vector similarity search using pgvector HNSW index.

Performs cosine-similarity search on chunk embeddings, optionally
pre-filtered by message_type and source_type metadata.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

import structlog
from sqlalchemy import text

from odyssey_rag.db.session import db_session

logger = structlog.get_logger(__name__)


@dataclass
class SearchResult:
    """A single search result from vector or BM25 search.

    Attributes:
        chunk_id:     UUID of the Chunk row.
        content:      Chunk text content.
        section:      Section label (from chunk.section).
        subsection:   Subsection label (from chunk.subsection).
        source_path:  Document source path.
        source_type:  Document source type.
        chunk_index:  Position of this chunk in its document.
        message_type: ISO 20022 message type (from chunk_metadata).
        score:        Raw similarity / BM25 score.
        rrf_score:    RRF-merged score (populated by fusion.py).
        rerank_score: Cross-encoder score (populated by reranker.py).
    """

    chunk_id: uuid.UUID
    content: str
    section: Optional[str] = None
    subsection: Optional[str] = None
    source_path: str = ""
    source_type: str = ""
    chunk_index: int = 0
    message_type: Optional[str] = None
    score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0


async def vector_search(
    query_embedding: list[float],
    filters: Optional[dict[str, str]] = None,
    limit: int = 30,
) -> list[SearchResult]:
    """Search for chunks by cosine similarity to *query_embedding*.

    Uses the pgvector ``<=>`` cosine distance operator against the
    ``chunk_embedding`` HNSW index. Results are filtered by the
    ``document.is_current`` flag and any provided metadata filters.

    Args:
        query_embedding: 768-dimensional query vector.
        filters:         Optional ``{"message_type": "pacs.008", "source_type": "..."}`` dict.
        limit:           Maximum number of results to return.

    Returns:
        List of SearchResult objects ordered by descending similarity.
    """
    filters = filters or {}
    msg_type = filters.get("message_type")
    source_type = filters.get("source_type")
    integration = filters.get("integration")

    # Build parameterized query
    # Note: pgvector embedding parameter must be cast to vector type
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
            1 - (ce.embedding <=> CAST(:embedding AS vector)) AS score
        FROM chunk c
        JOIN chunk_embedding ce ON c.id = ce.chunk_id
        JOIN document d ON c.document_id = d.id
        LEFT JOIN chunk_metadata cm ON c.id = cm.chunk_id
        WHERE d.is_current = TRUE
          AND (CAST(:msg_type AS TEXT) IS NULL OR cm.message_type = CAST(:msg_type AS TEXT))
          AND (CAST(:source_type AS TEXT) IS NULL OR d.source_type = CAST(:source_type AS TEXT))
          AND (CAST(:integration AS TEXT) IS NULL OR d.integration = CAST(:integration AS TEXT))
        ORDER BY ce.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """
    )

    # Format embedding as pgvector string: "[0.1,0.2,...]"
    embedding_str = "[" + ",".join(f"{v:.8f}" for v in query_embedding) + "]"

    results: list[SearchResult] = []
    try:
        async with db_session() as session:
            # When source_type is pre-filtered, disable the HNSW index so PostgreSQL
            # uses a sequential scan.  The HNSW index only supports post-filtering
            # (finds global top-k, then applies WHERE), which misses document types
            # whose embeddings are far from query embeddings in the global space
            # (e.g. xml_example, which contains structured XML rather than prose).
            if source_type:
                await session.execute(text("SET LOCAL enable_indexscan = off"))
            rows = await session.execute(
                sql,
                {
                    "embedding": embedding_str,
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
        logger.warning("vector_search_failed", error=str(exc))

    return results
