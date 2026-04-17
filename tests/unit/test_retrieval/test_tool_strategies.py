"""Unit tests for tool_strategies module."""

from __future__ import annotations

import uuid


from odyssey_rag.retrieval.tool_strategies import (
    TOOL_STRATEGIES,
    ToolStrategy,
    apply_source_type_boosts,
    filter_by_source_types,
    get_strategy,
)
from odyssey_rag.retrieval.vector_search import SearchResult


def make_result(source_type: str, rrf_score: float = 0.1) -> SearchResult:
    """Create a SearchResult for testing."""
    return SearchResult(
        chunk_id=uuid.uuid4(),
        content="Content",
        source_type=source_type,
        rrf_score=rrf_score,
    )


class TestGetStrategy:
    """Tests for get_strategy()."""

    def test_known_tool_returns_strategy(self) -> None:
        """Known tool name returns a ToolStrategy."""
        s = get_strategy("find_message_type")
        assert isinstance(s, ToolStrategy)

    def test_unknown_tool_returns_default(self) -> None:
        """Unknown tool returns a default empty strategy."""
        s = get_strategy("nonexistent_tool")
        assert isinstance(s, ToolStrategy)
        assert s.source_type_boosts == {}

    def test_all_six_tools_defined(self) -> None:
        """All 6 MCP tools have a strategy defined."""
        expected_tools = {
            "find_message_type",
            "find_business_rule",
            "find_module",
            "find_error",
            "search",
            "ingest",
        }
        assert expected_tools.issubset(set(TOOL_STRATEGIES.keys()))

    def test_find_business_rule_filters_annex_b(self) -> None:
        """find_business_rule pre-filters to annex_b_spec via metadata_filters."""
        s = get_strategy("find_business_rule")
        assert s.metadata_filters.get("source_type") == "annex_b_spec"

    def test_find_module_filters_php_code(self) -> None:
        """find_module pre-filters to php_code via metadata_filters."""
        s = get_strategy("find_module")
        assert s.metadata_filters.get("source_type") == "php_code"

    def test_find_message_type_has_boosts(self) -> None:
        """find_message_type strategy has source type boosts."""
        s = get_strategy("find_message_type")
        assert "annex_b_spec" in s.source_type_boosts
        assert s.source_type_boosts["annex_b_spec"] > 1.0


class TestApplySourceTypeBoosts:
    """Tests for apply_source_type_boosts()."""

    def test_boosts_multiply_rrf_score(self) -> None:
        """Source type boost multiplies rrf_score."""
        results = [make_result("annex_b_spec", rrf_score=0.1)]
        boosted = apply_source_type_boosts(results, {"annex_b_spec": 2.0})
        assert abs(boosted[0].rrf_score - 0.2) < 1e-9

    def test_unknown_source_type_unaffected(self) -> None:
        """Results with unknown source type are not boosted."""
        results = [make_result("unknown_type", rrf_score=0.1)]
        boosted = apply_source_type_boosts(results, {"annex_b_spec": 2.0})
        assert abs(boosted[0].rrf_score - 0.1) < 1e-9

    def test_returns_sorted_by_rrf_score(self) -> None:
        """Results are re-sorted by rrf_score after boosting."""
        results = [
            make_result("php_code", rrf_score=0.5),
            make_result("annex_b_spec", rrf_score=0.1),
        ]
        boosted = apply_source_type_boosts(results, {"annex_b_spec": 10.0})
        # annex_b_spec: 0.1 * 10 = 1.0 > php_code: 0.5
        assert boosted[0].source_type == "annex_b_spec"

    def test_empty_boosts_unchanged(self) -> None:
        """Empty boosts dict leaves results unchanged."""
        results = [make_result("annex_b_spec", rrf_score=0.3)]
        boosted = apply_source_type_boosts(results, {})
        assert abs(boosted[0].rrf_score - 0.3) < 1e-9


class TestFilterBySourceTypes:
    """Tests for filter_by_source_types()."""

    def test_filters_to_allowed_types(self) -> None:
        """Only results with allowed source types are returned."""
        results = [
            make_result("annex_b_spec"),
            make_result("php_code"),
            make_result("xml_example"),
        ]
        filtered = filter_by_source_types(results, ["annex_b_spec"])
        assert all(r.source_type == "annex_b_spec" for r in filtered)

    def test_empty_allowed_returns_all(self) -> None:
        """Empty allowed list returns all results (no filter)."""
        results = [make_result("annex_b_spec"), make_result("php_code")]
        filtered = filter_by_source_types(results, [])
        assert len(filtered) == 2

    def test_no_match_returns_empty(self) -> None:
        """Returns empty list when no results match the allowed types."""
        results = [make_result("php_code")]
        filtered = filter_by_source_types(results, ["annex_b_spec"])
        assert filtered == []

    def test_multiple_allowed_types(self) -> None:
        """Multiple allowed types are all included."""
        results = [
            make_result("annex_b_spec"),
            make_result("php_code"),
            make_result("xml_example"),
        ]
        filtered = filter_by_source_types(results, ["annex_b_spec", "php_code"])
        assert len(filtered) == 2
