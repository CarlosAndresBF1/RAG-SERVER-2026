"""Unit tests for the observability module."""

from __future__ import annotations


from odyssey_rag.observability import (
    ACTIVE_DOCUMENTS,
    CACHE_HIT_TOTAL,
    CACHE_MISS_TOTAL,
    INGEST_DURATION,
    INGEST_TOTAL,
    RERANKER_DURATION,
    SEARCH_DURATION,
    SEARCH_TOTAL,
)


class TestMetricsDefinitions:
    """Verify that all metric objects exist and have correct types."""

    def test_search_total_is_counter(self) -> None:
        """rag_search_total is a Counter with expected labels."""
        assert SEARCH_TOTAL._name == "rag_search"
        assert "tool_name" in SEARCH_TOTAL._labelnames
        assert "cache_hit" in SEARCH_TOTAL._labelnames

    def test_search_duration_is_histogram(self) -> None:
        """rag_search_duration_seconds is a Histogram."""
        assert SEARCH_DURATION._name == "rag_search_duration_seconds"
        assert "tool_name" in SEARCH_DURATION._labelnames

    def test_ingest_total_is_counter(self) -> None:
        """rag_ingest_total is a Counter with expected labels."""
        assert INGEST_TOTAL._name == "rag_ingest"
        assert "source_type" in INGEST_TOTAL._labelnames
        assert "status" in INGEST_TOTAL._labelnames

    def test_ingest_duration_is_histogram(self) -> None:
        """rag_ingest_duration_seconds is a Histogram."""
        assert INGEST_DURATION._name == "rag_ingest_duration_seconds"

    def test_active_documents_is_gauge(self) -> None:
        """rag_active_documents is a Gauge."""
        assert ACTIVE_DOCUMENTS._name == "rag_active_documents"

    def test_cache_hit_total_is_counter(self) -> None:
        """rag_cache_hit_total is a Counter."""
        assert CACHE_HIT_TOTAL._name == "rag_cache_hit"

    def test_cache_miss_total_is_counter(self) -> None:
        """rag_cache_miss_total is a Counter."""
        assert CACHE_MISS_TOTAL._name == "rag_cache_miss"

    def test_reranker_duration_is_histogram(self) -> None:
        """rag_reranker_duration_seconds is a Histogram."""
        assert RERANKER_DURATION._name == "rag_reranker_duration_seconds"


class TestMetricsOperations:
    """Verify metrics can be incremented/observed without errors."""

    def test_search_counter_increment(self) -> None:
        """SEARCH_TOTAL can be incremented with labels."""
        SEARCH_TOTAL.labels(tool_name="search", cache_hit="false").inc()

    def test_search_duration_observe(self) -> None:
        """SEARCH_DURATION can observe a value."""
        SEARCH_DURATION.labels(tool_name="search").observe(0.5)

    def test_ingest_counter_increment(self) -> None:
        """INGEST_TOTAL can be incremented with labels."""
        INGEST_TOTAL.labels(source_type="annex_b_spec", status="completed").inc()

    def test_ingest_duration_observe(self) -> None:
        """INGEST_DURATION can observe a value."""
        INGEST_DURATION.observe(2.5)

    def test_active_documents_set(self) -> None:
        """ACTIVE_DOCUMENTS gauge can be set."""
        ACTIVE_DOCUMENTS.set(42)

    def test_cache_counters_increment(self) -> None:
        """Cache hit/miss counters can be incremented."""
        CACHE_HIT_TOTAL.inc()
        CACHE_MISS_TOTAL.inc()

    def test_reranker_duration_observe(self) -> None:
        """RERANKER_DURATION can observe a value."""
        RERANKER_DURATION.observe(0.05)


class TestGenerateLatest:
    """Verify prometheus_client output generation works."""

    def test_generate_latest_produces_bytes(self) -> None:
        """generate_latest() returns byte string with metric names."""
        from prometheus_client import generate_latest

        output = generate_latest()
        assert isinstance(output, bytes)
        assert b"rag_search_total" in output
        assert b"rag_ingest_total" in output
        assert b"rag_active_documents" in output
        assert b"rag_cache_hit_total" in output
        assert b"rag_reranker_duration_seconds" in output
