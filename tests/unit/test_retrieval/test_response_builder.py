"""Unit tests for ResponseBuilder."""

from __future__ import annotations

import uuid

import pytest

from odyssey_rag.retrieval.query_processor import ProcessedQuery
from odyssey_rag.retrieval.response_builder import (
    Citation,
    Evidence,
    ResponseBuilder,
    RetrievalResponse,
)
from odyssey_rag.retrieval.vector_search import SearchResult


def make_result(
    rerank_score: float = 5.0,
    source_type: str = "annex_b_spec",
    message_type: str | None = "pacs.008",
    section: str | None = "Group Header",
) -> SearchResult:
    """Create a SearchResult with default high relevance."""
    return SearchResult(
        chunk_id=uuid.uuid4(),
        content="Test evidence content about pacs.008",
        section=section,
        source_type=source_type,
        message_type=message_type,
        rerank_score=rerank_score,
        rrf_score=0.1,
    )


def make_query(
    raw: str = "test query",
    msg_type: str | None = "pacs.008",
    intent: str | None = "message_type",
) -> ProcessedQuery:
    """Create a ProcessedQuery for testing."""
    return ProcessedQuery(
        raw=raw,
        normalized=raw.lower(),
        detected_message_type=msg_type,
        detected_intent=intent,
        bm25_query=raw,
        vector_query=raw,
        metadata_filters={},
    )


class TestResponseBuilder:
    """Tests for ResponseBuilder."""

    def setup_method(self) -> None:
        self.builder = ResponseBuilder(threshold=0.3, max_evidence_items=8)

    # ── Evidence building ──────────────────────────────────────────────────

    def test_build_returns_retrieval_response(self) -> None:
        """build() always returns a RetrievalResponse."""
        q = make_query()
        result = self.builder.build(q, [make_result()])
        assert isinstance(result, RetrievalResponse)

    def test_evidence_populated_from_results(self) -> None:
        """Evidence items are created from high-scoring results."""
        q = make_query()
        result = self.builder.build(q, [make_result(rerank_score=5.0)])
        assert len(result.evidence) >= 1

    def test_low_score_result_excluded(self) -> None:
        """Results with score below threshold are excluded from evidence."""
        q = make_query()
        # sigmoid(-15) ≈ 0, far below 0.3 threshold
        result = self.builder.build(q, [make_result(rerank_score=-15.0)])
        assert len(result.evidence) == 0

    def test_evidence_relevance_in_range(self) -> None:
        """Evidence relevance scores are in [0.0, 1.0]."""
        q = make_query()
        result = self.builder.build(q, [make_result(rerank_score=3.0)])
        for e in result.evidence:
            assert 0.0 <= e.relevance <= 1.0

    def test_evidence_has_citation(self) -> None:
        """Each evidence item has at least one citation."""
        q = make_query()
        result = self.builder.build(q, [make_result()])
        for e in result.evidence:
            assert len(e.citations) >= 1

    def test_evidence_message_type_set(self) -> None:
        """Evidence message_type is copied from SearchResult."""
        q = make_query()
        result = self.builder.build(q, [make_result(message_type="pacs.008")])
        assert result.evidence[0].message_type == "pacs.008"

    def test_max_evidence_items_respected(self) -> None:
        """Number of evidence items is capped at max_evidence_items."""
        builder = ResponseBuilder(threshold=0.0, max_evidence_items=3)
        q = make_query()
        results = [make_result() for _ in range(10)]
        response = builder.build(q, results)
        assert len(response.evidence) <= 3

    def test_empty_results_returns_empty_evidence(self) -> None:
        """No results produces empty evidence list."""
        q = make_query()
        result = self.builder.build(q, [])
        assert result.evidence == []

    # ── Gap detection ──────────────────────────────────────────────────────

    def test_gap_no_results(self) -> None:
        """Gap is reported when no results are found."""
        q = make_query()
        result = self.builder.build(q, [])
        assert len(result.gaps) >= 1
        assert any("No relevant" in g for g in result.gaps)

    def test_gap_missing_annex_b(self) -> None:
        """Gap reported when pacs.008 query has no annex_b_spec result."""
        q = make_query(msg_type="pacs.008")
        php_result = make_result(source_type="php_code")
        result = self.builder.build(q, [php_result])
        assert any("Annex B" in g for g in result.gaps)

    def test_no_gap_when_annex_b_present(self) -> None:
        """No gap reported when annex_b_spec result is present."""
        q = make_query(msg_type="pacs.008")
        annex_result = make_result(source_type="annex_b_spec", rerank_score=5.0)
        result = self.builder.build(q, [annex_result])
        assert not any("Annex B" in g for g in result.gaps)

    def test_gap_missing_php_for_module_intent(self) -> None:
        """Gap reported when module intent has no php_code result."""
        q = make_query(intent="module")
        annex_result = make_result(source_type="annex_b_spec", rerank_score=5.0)
        result = self.builder.build(q, [annex_result])
        assert any("PHP" in g for g in result.gaps)

    # ── Follow-up suggestions ──────────────────────────────────────────────

    def test_followups_not_empty_for_pacs008(self) -> None:
        """Follow-ups are suggested for pacs.008 queries."""
        q = make_query(msg_type="pacs.008", intent="message_type")
        result = self.builder.build(q, [make_result()])
        assert len(result.followups) > 0

    def test_followups_max_3(self) -> None:
        """At most 3 follow-ups are returned."""
        q = make_query(msg_type="pacs.008", intent="message_type")
        result = self.builder.build(q, [make_result()])
        assert len(result.followups) <= 3

    # ── to_dict ────────────────────────────────────────────────────────────

    def test_to_dict_has_required_keys(self) -> None:
        """to_dict() output has query, evidence, gaps, followups keys."""
        q = make_query()
        result = self.builder.build(q, [make_result()])
        d = result.to_dict()
        assert "query" in d
        assert "evidence" in d
        assert "gaps" in d
        assert "followups" in d

    def test_to_dict_evidence_has_text_and_relevance(self) -> None:
        """Each evidence dict has text, relevance, citations."""
        q = make_query()
        result = self.builder.build(q, [make_result(rerank_score=5.0)])
        d = result.to_dict()
        if d["evidence"]:
            e = d["evidence"][0]
            assert "text" in e
            assert "relevance" in e
            assert "citations" in e
