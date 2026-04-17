"""Retrieval engine — main orchestration for the full retrieval pipeline.

Entry point for all search operations. Wires together:
    QueryProcessor → Hybrid Search (Vector + BM25) → RRF → Rerank → ResponseBuilder

Designed to be instantiated once per application lifetime and reused
across requests. All I/O is async.
"""

from __future__ import annotations

import asyncio
import time

import structlog

from odyssey_rag.config import get_settings
from odyssey_rag.embeddings.factory import create_embedding_provider
from odyssey_rag.retrieval.bm25_search import bm25_search
from odyssey_rag.retrieval.cache import QueryCache
from odyssey_rag.retrieval.fusion import reciprocal_rank_fusion
from odyssey_rag.retrieval.query_processor import QueryProcessor
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
_VECTOR_LIMIT = 50
_BM25_LIMIT = 30
_RRF_TOP_N = 30


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
            threshold=0.0,  # No score filter — DB pre-filtering handles source type; cross-encoder orders by relevance
            max_evidence_items=settings.default_top_k,
        )
        if settings.reranker_enabled:
            self._reranker: CrossEncoderReranker | PassthroughReranker = CrossEncoderReranker(
                model_name=settings.reranker_model
            )
        else:
            self._reranker = PassthroughReranker()

        self._cache = QueryCache(
            max_size=settings.cache_max_size,
            ttl=settings.cache_ttl,
            enabled=settings.cache_enabled,
        )

    async def search(
        self,
        raw_query: str,
        tool_name: str = "search",
        tool_context: dict[str, str] | None = None,
        skip_cache: bool = False,
    ) -> RetrievalResponse:
        """Run the full retrieval pipeline for a query.

        Steps:
        1. Check cache for identical query
        2. Parse and expand the query
        3. Run vector + BM25 search concurrently
        4. Apply tool-specific strategy (boosts, source-type filters)
        5. Merge with RRF
        6. Rerank with cross-encoder (or passthrough)
        7. Assemble and return structured response
        8. Store in cache

        Args:
            raw_query:    The user's natural-language query.
            tool_name:    MCP tool name for strategy selection (default ``"search"``).
            tool_context: Optional tool parameters (message_type, focus, etc.).
            skip_cache:   If ``True``, bypass the cache for this request.

        Returns:
            Structured RetrievalResponse.
        """
        log = logger.bind(tool_name=tool_name, query=raw_query[:60])
        log.info("retrieval_start")
        start_time = time.monotonic()

        # ── Cache lookup ─────────────────────────────────────────────────
        if not skip_cache:
            cached = self._cache.get(raw_query, tool_name, tool_context)
            if cached is not None:
                duration = time.monotonic() - start_time
                log.info("retrieval_cache_hit", duration=duration)
                _record_search_metrics(tool_name, cache_hit=True, duration=duration)
                return cached

        # 1. Process query
        processed = self.query_processor.process(raw_query, tool_context)
        log.debug("query_processed", msg_type=processed.detected_message_type)

        # 2. Get tool strategy early (needed to build merged filters)
        strategy = get_strategy(tool_name)

        # 3. Build merged metadata filters: query filters + strategy filters + focus filters
        all_filters: dict[str, str] = {**processed.metadata_filters}
        all_filters.update(strategy.metadata_filters)
        # Apply focus-specific source_type filter when focus param is provided
        focus = (tool_context or {}).get("focus")
        if focus:
            focus_meta = strategy.focus_filters.get(focus, {})
            if "source_type" in focus_meta:
                all_filters["source_type"] = focus_meta["source_type"]
        # When source_type is pre-filtered, remove message_type — some document types
        # (e.g. xml_example) store no message_type in chunk_metadata, so the DB filter
        # would return zero rows. Vector similarity handles message specificity instead.
        if "source_type" in all_filters:
            all_filters.pop("message_type", None)

        # Pass integration filter directly from tool_context
        integration = (tool_context or {}).get("integration")
        if integration:
            all_filters["integration"] = integration

        # 4. Embed query for vector search
        try:
            settings = get_settings()
            embedding_provider = create_embedding_provider(settings)
            vectors = await embedding_provider.embed([processed.vector_query])
            query_embedding = vectors[0]
        except Exception as exc:
            log.warning("embed_query_failed", error=str(exc))
            query_embedding = []

        # 5. Run hybrid search concurrently using merged filters
        vector_task = asyncio.create_task(
            vector_search(
                query_embedding,
                filters=all_filters,
                limit=_VECTOR_LIMIT,
            )
            if query_embedding
            else _empty_task()
        )
        # Append strategy-specific BM25 boost terms to expand recall
        bm25_q = processed.bm25_query
        if strategy.bm25_boost_terms:
            bm25_q = bm25_q + " " + " ".join(strategy.bm25_boost_terms)
        bm25_task = asyncio.create_task(
            bm25_search(
                bm25_q,
                filters=all_filters,
                limit=_BM25_LIMIT,
            )
        )

        vector_results, bm25_results = await asyncio.gather(vector_task, bm25_task)
        log.debug(
            "search_done",
            vector_hits=len(vector_results),
            bm25_hits=len(bm25_results),
        )

        # 6. RRF merge
        merged = reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            k=60,
            top_n=_RRF_TOP_N,
        )

        # Apply source-type filter and boosts after RRF merge
        if strategy.require_source_types:
            merged = filter_by_source_types(merged, strategy.require_source_types)

        if strategy.source_type_boosts:
            merged = apply_source_type_boosts(merged, strategy.source_type_boosts)

        # 6. Rerank
        settings2 = get_settings()
        reranked = await self._reranker.rerank(
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

        # ── Cache store & metrics ────────────────────────────────────────
        if not skip_cache:
            self._cache.put(raw_query, tool_name, tool_context, response)
        duration = time.monotonic() - start_time
        _record_search_metrics(tool_name, cache_hit=False, duration=duration)

        return response


def _record_search_metrics(tool_name: str, *, cache_hit: bool, duration: float) -> None:
    """Record search metrics if the observability module is available."""
    try:
        from odyssey_rag.observability import (
            CACHE_HIT_TOTAL,
            CACHE_MISS_TOTAL,
            SEARCH_DURATION,
            SEARCH_TOTAL,
        )

        SEARCH_TOTAL.labels(tool_name=tool_name, cache_hit=str(cache_hit).lower()).inc()
        SEARCH_DURATION.labels(tool_name=tool_name).observe(duration)
        if cache_hit:
            CACHE_HIT_TOTAL.inc()
        else:
            CACHE_MISS_TOTAL.inc()
    except Exception:
        pass  # observability is best-effort


async def _empty_task() -> list[SearchResult]:
    """Return an empty list (used when embedding is unavailable)."""
    return []
