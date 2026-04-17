"""Unit tests for RRF fusion."""

from __future__ import annotations

import uuid


from odyssey_rag.retrieval.fusion import reciprocal_rank_fusion
from odyssey_rag.retrieval.vector_search import SearchResult


def make_result(
    chunk_id: uuid.UUID | None = None,
    score: float = 1.0,
    source_type: str = "annex_b_spec",
) -> SearchResult:
    """Create a SearchResult for testing."""
    return SearchResult(
        chunk_id=chunk_id or uuid.uuid4(),
        content="Test content",
        source_type=source_type,
        score=score,
    )


class TestReciprocalRankFusion:
    """Tests for reciprocal_rank_fusion()."""

    def test_empty_inputs_returns_empty(self) -> None:
        """Two empty lists produce an empty result."""
        result = reciprocal_rank_fusion([], [])
        assert result == []

    def test_single_list_preserves_order(self) -> None:
        """Single list returns items in original (rank) order."""
        ids = [uuid.uuid4() for _ in range(5)]
        results = [make_result(chunk_id=cid) for cid in ids]
        merged = reciprocal_rank_fusion(results)
        merged_ids = [r.chunk_id for r in merged]
        assert merged_ids == ids

    def test_common_item_boosted(self) -> None:
        """An item appearing in both lists scores higher than one only in one."""
        shared_id = uuid.uuid4()
        only_in_a = uuid.uuid4()

        list_a = [make_result(chunk_id=shared_id), make_result(chunk_id=only_in_a)]
        list_b = [make_result(chunk_id=shared_id)]

        merged = reciprocal_rank_fusion(list_a, list_b)
        assert merged[0].chunk_id == shared_id

    def test_rrf_score_is_set(self) -> None:
        """rrf_score field is populated for all merged results."""
        results = [make_result() for _ in range(3)]
        merged = reciprocal_rank_fusion(results)
        for r in merged:
            assert r.rrf_score > 0.0

    def test_top_n_limits_output(self) -> None:
        """Merged list is at most top_n items."""
        results = [make_result() for _ in range(30)]
        merged = reciprocal_rank_fusion(results, top_n=5)
        assert len(merged) <= 5

    def test_formula_k60(self) -> None:
        """RRF score for rank-1 item with k=60 equals 1/61."""
        cid = uuid.uuid4()
        results = [make_result(chunk_id=cid)]
        merged = reciprocal_rank_fusion(results, k=60)
        expected = 1.0 / (60 + 1)
        assert abs(merged[0].rrf_score - expected) < 1e-9

    def test_two_lists_with_disjoint_items(self) -> None:
        """Disjoint items appear in merged output with correct count."""
        list_a = [make_result() for _ in range(3)]
        list_b = [make_result() for _ in range(3)]
        merged = reciprocal_rank_fusion(list_a, list_b)
        assert len(merged) == 6

    def test_rrf_score_decreases_with_rank(self) -> None:
        """Higher-ranked items in a single list get higher RRF scores."""
        ids = [uuid.uuid4() for _ in range(5)]
        results = [make_result(chunk_id=cid) for cid in ids]
        merged = reciprocal_rank_fusion(results, k=60)
        # First item (rank 1) should have highest score
        scores = [r.rrf_score for r in merged]
        assert scores == sorted(scores, reverse=True)

    def test_duplicate_chunk_id_counted_once_per_list(self) -> None:
        """Each result list contributes to the score exactly once per item."""
        cid = uuid.uuid4()
        list_a = [make_result(chunk_id=cid), make_result(chunk_id=cid)]  # duplicated
        merged = reciprocal_rank_fusion(list_a, k=60)
        # Should appear once in output
        assert len([r for r in merged if r.chunk_id == cid]) == 1

    def test_three_lists_merged(self) -> None:
        """Three result lists are merged correctly."""
        shared = uuid.uuid4()
        list_a = [make_result(chunk_id=shared)]
        list_b = [make_result(chunk_id=shared)]
        list_c = [make_result(chunk_id=shared)]
        merged = reciprocal_rank_fusion(list_a, list_b, list_c, k=60)
        # shared item appears in all 3 lists: score = 3 * 1/(60+1)
        assert len(merged) == 1
        expected = 3 * (1.0 / 61)
        assert abs(merged[0].rrf_score - expected) < 1e-9
