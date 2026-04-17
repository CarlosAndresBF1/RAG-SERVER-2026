"""Cross-encoder reranker for precision improvement.

Uses ``sentence-transformers`` CrossEncoder to rerank the RRF-merged
candidates with a (query, candidate) relevance score, then returns the
top-k highest-scoring results.

Falls back to identity ordering (no reranking) if the model is not
available or if reranking is disabled in settings.
"""

from __future__ import annotations

import asyncio
import time
from functools import cached_property

import structlog

from odyssey_rag.retrieval.vector_search import SearchResult

logger = structlog.get_logger(__name__)

DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """Rerank candidates using a cross-encoder relevance model.

    The cross-encoder scores (query, passage) pairs jointly, producing
    relevance estimates that are more accurate than bi-encoder (embedding)
    cosine similarities at the cost of higher computational overhead.

    Model: ``cross-encoder/ms-marco-MiniLM-L-6-v2``
    - 22M parameters
    - ~10ms per pair on CPU
    - Output range: approximately [-10, 10] (raw logits)

    Attributes:
        model_name: HuggingFace model identifier.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        """Initialise reranker.

        Args:
            model_name: HuggingFace cross-encoder model identifier.
        """
        self.model_name = model_name

    @cached_property
    def _model(self) -> object:
        """Lazy-load the CrossEncoder model on first use."""
        from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

        return CrossEncoder(self.model_name)

    async def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Rerank candidates by cross-encoder relevance score.

        Args:
            query:      The original (or vector) query string.
            candidates: Pre-filtered candidates from RRF fusion (≤ 20 typical).
            top_k:      Maximum number of results to return.

        Returns:
            Top *top_k* SearchResult objects with ``rerank_score`` set,
            ordered by descending cross-encoder score.
        """
        if not candidates:
            return []

        rerank_start = time.monotonic()
        try:
            pairs = [(query, c.content) for c in candidates]
            loop = asyncio.get_running_loop()
            scores = await loop.run_in_executor(
                None,
                self._model.predict,
                pairs,  # type: ignore[union-attr]
            )

            for candidate, score in zip(candidates, scores):
                candidate.rerank_score = float(score)

            candidates.sort(key=lambda c: c.rerank_score, reverse=True)
            result = candidates[:top_k]
            _record_reranker_duration(time.monotonic() - rerank_start)
            return result

        except Exception as exc:
            logger.warning(
                "reranker_failed_fallback",
                error=str(exc),
                model=self.model_name,
            )
            # Fallback: return by RRF score
            candidates.sort(key=lambda c: c.rrf_score, reverse=True)
            for c in candidates:
                c.rerank_score = c.rrf_score
            _record_reranker_duration(time.monotonic() - rerank_start)
            return candidates[:top_k]


class PassthroughReranker:
    """No-op reranker that returns candidates unchanged.

    Used when reranking is disabled (``reranker_enabled=false``) for
    faster development or low-latency deployments.
    """

    async def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Return the top-k candidates ordered by RRF score.

        Args:
            query:      Unused (kept for interface compatibility).
            candidates: Candidates from RRF fusion.
            top_k:      Maximum results to return.

        Returns:
            Top *top_k* candidates with ``rerank_score`` copied from ``rrf_score``.
        """
        for c in candidates:
            c.rerank_score = c.rrf_score
        sorted_cands = sorted(candidates, key=lambda c: c.rrf_score, reverse=True)
        return sorted_cands[:top_k]


def _record_reranker_duration(duration: float) -> None:
    """Record reranker duration metric if observability is available."""
    try:
        from odyssey_rag.observability import RERANKER_DURATION

        RERANKER_DURATION.observe(duration)
    except Exception:
        pass  # observability is best-effort
