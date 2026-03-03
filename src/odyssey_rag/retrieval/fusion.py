"""Reciprocal Rank Fusion (RRF) for hybrid search result merging.

Merges ranked result lists from vector search and BM25 search into a
single list using the RRF formula. Score magnitudes are irrelevant —
only rank positions matter, which makes RRF robust across heterogeneous
retrieval systems.

Reference: Cormack, Clarke, and Buettcher (2009).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Optional

from odyssey_rag.retrieval.vector_search import SearchResult


def reciprocal_rank_fusion(
    *result_lists: list[SearchResult],
    k: int = 60,
    top_n: int = 20,
) -> list[SearchResult]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    Formula::

        RRF_score(d) = Σ  1 / (k + rank_i(d))

    Where:
    - ``k``: smoothing constant (60 is the standard value from the paper)
    - ``rank_i(d)``: 1-based rank of document *d* in result list *i*
    - Sum is over all lists in which *d* appears

    Args:
        *result_lists: Two or more ordered lists of SearchResult objects.
                       Earlier lists have equal weight; adjust k to bias.
        k:             Smoothing constant (default 60).
        top_n:         Maximum number of merged results to return.

    Returns:
        Merged list of at most *top_n* SearchResult objects ordered by
        descending RRF score. Each result's ``rrf_score`` field is set.
    """
    rrf_scores: dict[uuid.UUID, float] = defaultdict(float)
    result_map: dict[uuid.UUID, SearchResult] = {}

    for results in result_lists:
        for rank, result in enumerate(results, start=1):
            rrf_scores[result.chunk_id] += 1.0 / (k + rank)
            # Keep the first-seen copy (vector result preferred on tie)
            if result.chunk_id not in result_map:
                result_map[result.chunk_id] = result

    sorted_ids = sorted(
        rrf_scores.keys(),
        key=lambda cid: rrf_scores[cid],
        reverse=True,
    )

    merged: list[SearchResult] = []
    for chunk_id in sorted_ids[:top_n]:
        result = result_map[chunk_id]
        result.rrf_score = rrf_scores[chunk_id]
        merged.append(result)

    return merged
