"""Prometheus metrics for the Odyssey RAG system.

Defines counters, histograms, and gauges for key code paths:
  - Retrieval search (duration, cache hits, tool usage)
  - Ingestion pipeline (duration, success/failure)
  - Reranker (duration)
  - Active document count

Metrics are exposed via ``/metrics`` in the FastAPI app using
``prometheus_client.generate_latest()``.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Search metrics ────────────────────────────────────────────────────────────

SEARCH_TOTAL = Counter(
    "rag_search_total",
    "Total number of search requests",
    labelnames=["tool_name", "cache_hit"],
)

SEARCH_DURATION = Histogram(
    "rag_search_duration_seconds",
    "Search pipeline duration in seconds",
    labelnames=["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── Cache metrics ─────────────────────────────────────────────────────────────

CACHE_HIT_TOTAL = Counter(
    "rag_cache_hit_total",
    "Total cache hits",
)

CACHE_MISS_TOTAL = Counter(
    "rag_cache_miss_total",
    "Total cache misses",
)

# ── Ingestion metrics ─────────────────────────────────────────────────────────

INGEST_TOTAL = Counter(
    "rag_ingest_total",
    "Total ingestion attempts",
    labelnames=["source_type", "status"],
)

INGEST_DURATION = Histogram(
    "rag_ingest_duration_seconds",
    "Ingestion pipeline duration in seconds",
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# ── Document gauge ────────────────────────────────────────────────────────────

ACTIVE_DOCUMENTS = Gauge(
    "rag_active_documents",
    "Number of active (is_current=True) documents",
)

# ── Reranker metrics ──────────────────────────────────────────────────────────

RERANKER_DURATION = Histogram(
    "rag_reranker_duration_seconds",
    "Reranker duration in seconds",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
