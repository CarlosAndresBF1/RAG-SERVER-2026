"""Unit tests for QueryProcessor."""

from __future__ import annotations


from odyssey_rag.retrieval.query_processor import EXPANSIONS, QueryProcessor


class TestQueryProcessor:
    """Tests for QueryProcessor."""

    def setup_method(self) -> None:
        self.processor = QueryProcessor()

    # ── Message type detection ─────────────────────────────────────────────

    def test_detect_pacs008_in_query(self) -> None:
        """Detects pacs.008 from query text."""
        q = self.processor.process("What are the mandatory fields for pacs.008?")
        assert q.detected_message_type == "pacs.008"

    def test_detect_pacs002_in_query(self) -> None:
        """Detects pacs.002 from query text."""
        q = self.processor.process("How does the FIToFIPmtStsRpt work?")
        assert q.detected_message_type == "pacs.002"

    def test_detect_camt056_from_recall(self) -> None:
        """Detects camt.056 from 'recall' keyword."""
        q = self.processor.process("How do I send a recall message?")
        assert q.detected_message_type == "camt.056"

    def test_no_message_type_when_absent(self) -> None:
        """Returns None when no ISO message type is present."""
        q = self.processor.process("Hello world")
        assert q.detected_message_type is None

    def test_tool_context_overrides_detection(self) -> None:
        """Explicit message_type in tool_context takes priority."""
        q = self.processor.process(
            "What fields are needed?",
            tool_context={"message_type": "pacs.004"},
        )
        assert q.detected_message_type == "pacs.004"

    # ── Intent detection ───────────────────────────────────────────────────

    def test_intent_business_rule_from_mandatory(self) -> None:
        """Detects business_rule intent from 'mandatory'."""
        q = self.processor.process("What are the mandatory rules for pacs.008?")
        assert q.detected_intent == "business_rule"

    def test_intent_module_from_class(self) -> None:
        """Detects module intent from 'class' keyword."""
        q = self.processor.process("Which PHP class implements pacs.008?")
        assert q.detected_intent == "module"

    def test_intent_error_from_reject(self) -> None:
        """Detects error intent from 'reject' keyword."""
        q = self.processor.process("Why was my payment rejected?")
        assert q.detected_intent == "error"

    def test_intent_general_when_no_match(self) -> None:
        """Returns 'general' intent when no specific keywords found."""
        q = self.processor.process("hello")
        assert q.detected_intent == "general"

    # ── BM25 query expansion ───────────────────────────────────────────────

    def test_bm25_query_keeps_original_terms(self) -> None:
        """BM25 query uses original terms without expansion (AND semantics)."""
        q = self.processor.process("What is the BIC field?")
        assert "bic" in q.bm25_query
        assert q.bm25_query == q.normalized

    def test_bm25_query_includes_message_type(self) -> None:
        """BM25 query includes message type when not already in the text."""
        q = self.processor.process(
            "group header fields", tool_context={"message_type": "pacs.008"}
        )
        assert "pacs.008" in q.bm25_query

    def test_bm25_query_is_string(self) -> None:
        """BM25 query is always a non-empty string."""
        q = self.processor.process("test")
        assert isinstance(q.bm25_query, str) and len(q.bm25_query) > 0

    # ── Vector query ───────────────────────────────────────────────────────

    def test_vector_query_includes_raw(self) -> None:
        """Vector query includes the raw query text."""
        q = self.processor.process("group header fields")
        assert "group header fields" in q.vector_query.lower()

    def test_vector_query_adds_message_type(self) -> None:
        """Vector query appends ISO context when message type is detected."""
        q = self.processor.process("group header for pacs.008")
        assert "pacs.008" in q.vector_query

    # ── Metadata filters ───────────────────────────────────────────────────

    def test_metadata_filter_message_type(self) -> None:
        """metadata_filters includes message_type when detected."""
        q = self.processor.process("pacs.008 group header")
        assert q.metadata_filters.get("message_type") == "pacs.008"

    def test_metadata_filter_source_type_from_context(self) -> None:
        """source_type filter is set from tool_context."""
        q = self.processor.process(
            "query", tool_context={"source_type": "annex_b_spec"}
        )
        assert q.metadata_filters.get("source_type") == "annex_b_spec"

    def test_metadata_filter_empty_when_no_type(self) -> None:
        """Metadata filters are empty when no type is detected."""
        q = self.processor.process("hello world")
        assert "message_type" not in q.metadata_filters

    # ── ProcessedQuery structure ───────────────────────────────────────────

    def test_raw_preserved(self) -> None:
        """Raw query text is preserved unchanged."""
        raw = "  What are the mandatory Fields for pacs.008?  "
        q = self.processor.process(raw)
        assert q.raw == raw

    def test_normalized_is_lowercase_stripped(self) -> None:
        """Normalized query is lowercase and stripped."""
        q = self.processor.process("  PACS.008 Fields  ")
        assert q.normalized == "pacs.008 fields"


class TestExpansions:
    """Verify the EXPANSIONS dictionary."""

    def test_pacs_in_expansions(self) -> None:
        assert "pacs" in EXPANSIONS

    def test_grphdr_in_expansions(self) -> None:
        assert "GrpHdr" in EXPANSIONS

    def test_all_values_are_strings(self) -> None:
        for key, val in EXPANSIONS.items():
            assert isinstance(val, str) and len(val) > 0
