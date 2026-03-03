"""Retrieval engine — main orchestration for the full retrieval pipeline.

Entry point for all search operations. Wires together:
    QueryProcessor → Hybrid Search (Vector + BM25) → RRF → Rerank → ResponseBuilder

Designed to be instantiated once per application lifetime and reused
across requests. All I/O is async.
"""

from __future__ import annotations

import asyncio

import structlog

from odyssey_rag.config import get_settings
from odyssey_rag.embeddings.factory import create_embedding_provider
from odyssey_rag.retrieval.bm25_search import bm25_search
from odyssey_rag.retrieval.fusion import reciprocal_rank_fusion
from odyssey_rag.retrieval.query_processor import ProcessedQuery, QueryProcessor
from odyssey_rag.retrieval.reranker import CrossEncoderReranker, PassthroughReranker
from odyssey_rag.retrieval.response_builder import ResponseBuilder, RetrievalResponse
from odyssey_rag.retrieval.tool_strategies import (
    apply_source_type_boosts,
    filter_by_source_types,
    get_strategy,
)
from odyssey_rag.retrieval.vector_search import SearchResult, vector_search

logger = structlog.get_logger(__name__)

# Search candidate limits
_VECTOR_LIMIT = 30
_BM25_LIMIT = 30
_RRF_TOP_N = 20


class RetrievalEngine:
    """Main orchestrator for the hybrid retrieval pipeline.

    Lifecycle::

        engine = RetrievalEngine()
        response = await engine.search("What are mandatory fields for pacs.008?")

    Or with tool context::

        response = await engine.search(
            "show me the buildDocument method",
            tool_name="find_module",
            tool_context={"message_type": "pacs.008"},
        )

    Attributes:
        query_processor: Processes raw queries into optimized search forms.
        response_builder: Assembles reranked results into structured responses.
        _reranker:        Active reranker (cross-encoder or passthrough).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.query_processor = QueryProcessor()
        self.response_builder = ResponseBuilder(
            threshold=settings.reranker_enabled and 0.3 or 0.0,
            max_evidence_items=settings.default_top_k,
        )
        if settings.reranker_enabled:
            self._reranker: CrossEncoderReranker | PassthroughReranker = (
                CrossEncoderReranker(model_name=settings.reranker_model)
            )
        else:
            self._reranker = PassthroughReranker()

    async def search(
        self,
        raw_query: str,
        tool_name: str = "search",
        tool_context: dict[str, str] | None = None,
    ) -> RetrievalResponse:
        """Run the full retrieval pipeline for a query.

        Steps:
        1. Parse and expand the query
        2. Run vector + BM25 search concurrently
        3. Apply tool-specific strategy (boosts, source-type filters)
        4. Merge with RRF
        5. Rerank with cross-encoder (or passthrough)
        6. Assemble and return structured response

        Args:
            raw_query:    The user's natural-language query.
            tool_name:    MCP tool name for strategy selection (default ``"search"``).
            tool_context: Optional tool parameters (message_type, focus, etc.).

        Returns:
            Structured RetrievalResponse.
        """
        log = logger.bind(tool_name=tool_name, query=raw_query[:60])
        log.info("retrieval_start")

        # 1. Process query
        processed = self.query_processor.process(raw_query, tool_context)
        log.debug("query_processed", msg_type=processed.detected_message_type)

        # 2. Embed query for vector search
        try:
            settings = get_settings()
            embedding_provider = create_embedding_provider(settings)
            vectors = await embedding_provider.embed([processed.vector_query])
            query_embedding = vectors[0]
        except Exception as exc:
            log.warning("embed_query_failed", error=str(exc))
            query_embedding = []

        # 3. Run hybrid search concurrently
        vector_task = asyncio.create_task(
            vector_search(
                query_embedding,
                filters=processed.metadata_filters,
                limit=_VECTOR_LIMIT,
            )
            if query_embedding
            else _empty_task()
        )
        bm25_task = asyncio.create_task(
            bm25_search(
                processed.bm25_query,
                filters=processed.metadata_filters,
                limit=_BM25_LIMIT,
            )
        )

        vector_results, bm25_results = await asyncio.gather(vector_task, bm25_task)
        log.debug(
            "search_done",
            vector_hits=len(vector_results),
            bm25_hits=len(bm25_results),
        )

        # 4. Apply tool strategy: boosts + source-type filtering
        strategy = get_strategy(tool_name)
        all_results = list(vector_results) + list(bm25_results)

        if strategy.require_source_types:
            all_results = filter_by_source_types(
                all_results, strategy.require_source_types
            )

        # 5. RRF merge
        merged = reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            k=60,
            top_n=_RRF_TOP_N,
        )

        # Apply boosts after merge
        if strategy.source_type_boosts:
            merged = apply_source_type_boosts(merged, strategy.source_type_boosts)

        # 6. Rerank
        settings2 = get_settings()
        reranked = self._reranker.rerank(
            query=processed.vector_query,
            candidates=merged,
            top_k=settings2.default_top_k,
        )
        log.debug("reranked", top_k=len(reranked))

        # 7. Build response
        response = self.response_builder.build(processed, reranked)
        log.info(
            "retrieval_done",
            evidence_count=len(response.evidence),
            gap_count=len(response.gaps),
        )
        return response


async def _empty_task() -> list[SearchResult]:
    """Return an empty list (used when embedding is unavailable)."""
    return []
