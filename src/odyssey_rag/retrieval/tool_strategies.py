"""Per-MCP-tool retrieval strategy customization.

Each MCP tool has slightly different retrieval requirements (source type
preferences, metadata filters, response format). This module maps tool
names to strategy configurations that the engine applies at query time.

Strategies are plain dataclasses — no DB access, no external calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolStrategy:
    """Retrieval customization for a specific MCP tool.

    Attributes:
        source_type_boosts:  ``{source_type: multiplier}`` map applied after
                             RRF (multiplies rrf_score).  Keys that are not
                             present default to 1.0.
        require_source_types: If non-empty, filter results to only these
                              source types before reranking.
        bm25_boost_terms:    Extra keywords appended to the BM25 query to
                             improve recall for domain-specific terms.
        metadata_filters:    Additional metadata filters merged with those
                             from the query processor.
        response_transform:  Optional named transform applied by the MCP
                             tool handler (e.g. ``"module_map"``).
        focus_filters:       Per-focus-value filter configs keyed by the
                             MCP tool's ``focus`` parameter value.
    """

    source_type_boosts: dict[str, float] = field(default_factory=dict)
    require_source_types: list[str] = field(default_factory=list)
    bm25_boost_terms: list[str] = field(default_factory=list)
    metadata_filters: dict[str, str] = field(default_factory=dict)
    response_transform: Optional[str] = None
    focus_filters: dict[str, dict[str, str]] = field(default_factory=dict)


# ── Strategy registry ─────────────────────────────────────────────────────────

TOOL_STRATEGIES: dict[str, ToolStrategy] = {
    "find_message_type": ToolStrategy(
        source_type_boosts={
            "annex_b_spec": 4.0,
            "xml_example": 1.2,
            "php_code": 1.0,
        },
        # focus_filters drive source_type pre-filtering at the DB level in engine.py
        focus_filters={
            "overview": {"source_type": "annex_b_spec"},
            "fields": {"source_type": "annex_b_spec"},
            "builder": {"source_type": "php_code"},
            "parser": {"source_type": "php_code"},
            "validator": {"source_type": "php_code"},
            "examples": {"source_type": "xml_example"},
            "envelope": {"source_type": "annex_b_spec"},
        },
    ),
    "find_business_rule": ToolStrategy(
        # Pre-filter DB to annex_b_spec so the cross-encoder sees spec content
        metadata_filters={"source_type": "annex_b_spec"},
        source_type_boosts={"annex_b_spec": 1.0},
        bm25_boost_terms=["mandatory", "optional", "conditional", "M", "O", "C", "rule"],
    ),
    "find_module": ToolStrategy(
        # Pre-filter DB to php_code only — all MOD questions target implementation code
        metadata_filters={"source_type": "php_code"},
        source_type_boosts={"php_code": 1.0},
        bm25_boost_terms=["class", "function", "method", "builder", "parser", "validator"],
        response_transform="module_map",
    ),
    "find_error": ToolStrategy(
        # Pre-filter to annex_b_spec — 9 of 10 ERR queries expect spec content
        metadata_filters={"source_type": "annex_b_spec"},
        source_type_boosts={"annex_b_spec": 1.0},
        bm25_boost_terms=["RJCT", "ACSP", "PDNG", "error", "reject", "reason", "code"],
        response_transform="resolution",
    ),
    "search": ToolStrategy(
        # Balanced: no source type preference
        source_type_boosts={},
    ),
    "ingest": ToolStrategy(
        # Ingest tool doesn't use retrieval
        source_type_boosts={},
    ),
}


def get_strategy(tool_name: str) -> ToolStrategy:
    """Return the ToolStrategy for *tool_name*, or a default strategy.

    Args:
        tool_name: MCP tool name (e.g. ``"find_message_type"``).

    Returns:
        Matching ToolStrategy, or a default empty strategy if unknown.
    """
    return TOOL_STRATEGIES.get(tool_name, ToolStrategy())


def apply_source_type_boosts(
    results: list,  # list[SearchResult] — avoids circular import
    boosts: dict[str, float],
) -> list:
    """Apply source-type score multipliers to result rrf_scores in-place.

    Args:
        results: List of SearchResult objects.
        boosts:  ``{source_type: multiplier}`` mapping.

    Returns:
        The same list, with rrf_score values adjusted.
    """
    for result in results:
        multiplier = boosts.get(result.source_type, 1.0)
        result.rrf_score *= multiplier
    # Re-sort after boosting
    results.sort(key=lambda r: r.rrf_score, reverse=True)
    return results


def filter_by_source_types(
    results: list,  # list[SearchResult]
    allowed_source_types: list[str],
) -> list:
    """Filter results to only those whose source_type is in *allowed_source_types*.

    Args:
        results:             List of SearchResult objects.
        allowed_source_types: Allowed source types.

    Returns:
        Filtered list (may be empty if none match).
    """
    if not allowed_source_types:
        return results
    return [r for r in results if r.source_type in allowed_source_types]
