# Decision Log — Keyser: S1, S2, S8

## S1: Garbage Collection for Superseded Documents

### Decisions
- **GC via SQL DELETE, not ORM cascade**: Used `sqlalchemy.delete()` with `WHERE is_current=False AND updated_at < cutoff` directly on the Document table. The database's `ON DELETE CASCADE` FKs handle chunk/embedding/metadata cleanup — more efficient than loading ORM objects.
- **Default 30-day retention**: Superseded documents are kept for 30 days before GC eligibility. This gives time for rollback if a bad re-ingestion occurs.
- **Separate route file `gc.py`**: Created a dedicated route module rather than adding to `admin.py` to keep admin user management separate from maintenance operations.
- **`maintenance.py` at package root**: The `schedule_gc()` function lives in a top-level module so it can be imported by both the API route and future cron/scheduler integrations.

### Files Changed
- `src/odyssey_rag/db/repositories/documents.py` — added `garbage_collect_superseded()`
- `src/odyssey_rag/maintenance.py` — new module with `schedule_gc()`
- `src/odyssey_rag/api/routes/gc.py` — new `POST /api/v1/admin/gc` endpoint
- `src/odyssey_rag/api/main.py` — registered gc router
- `tests/unit/test_db/test_garbage_collection.py` — 4 tests

---

## S2: Query Result Cache

### Decisions
- **`cachetools.TTLCache`**: Lightweight stdlib-compatible TTL cache. No Redis dependency needed for the current scale. Thread-safe by default.
- **Cache key = SHA-256(query|tool_name|sorted_context_json)**: Deterministic, collision-resistant. `json.dumps(sort_keys=True)` ensures dict ordering doesn't matter.
- **Cache integrated at `RetrievalEngine.search()` level**: Check before pipeline, store after pipeline. The `skip_cache` parameter allows force-refresh.
- **Settings in `config.py`**: `cache_ttl=300`, `cache_max_size=256`, `cache_enabled=True`. All configurable via environment variables.
- **Cache instance per engine**: The `QueryCache` lives on the `RetrievalEngine` singleton, so there's exactly one cache per application.

### Files Changed
- `src/odyssey_rag/retrieval/cache.py` — new `QueryCache` class
- `src/odyssey_rag/retrieval/engine.py` — cache integration in `search()`
- `src/odyssey_rag/config.py` — cache settings
- `pyproject.toml` — added `cachetools` dependency
- `tests/unit/test_retrieval/test_cache.py` — 18 tests

---

## S8: Observability (Metrics & Structured Logging)

### Decisions
- **Module-level metrics in `observability.py`**: All Prometheus metric objects defined at module scope — standard pattern for `prometheus_client`. Imported lazily at instrumentation sites to avoid circular imports.
- **Best-effort metrics**: All instrumentation wrapped in `try/except pass` to ensure metrics failures never break core functionality. This follows the convention that observability should be non-invasive.
- **`/metrics` endpoint with no auth**: Standard Prometheus scraping pattern. Added directly to the FastAPI app in `create_app()`.
- **Lazy import pattern for instrumentation**: `_record_search_metrics()`, `_record_ingest_metrics()`, and `_record_reranker_duration()` use deferred imports from `odyssey_rag.observability` to avoid coupling and circular imports.
- **7 metrics defined**: `rag_search_total`, `rag_search_duration_seconds`, `rag_ingest_total`, `rag_ingest_duration_seconds`, `rag_active_documents`, `rag_cache_hit_total` / `rag_cache_miss_total`, `rag_reranker_duration_seconds`.

### Files Changed
- `src/odyssey_rag/observability.py` — new metrics module
- `src/odyssey_rag/api/main.py` — `/metrics` endpoint
- `src/odyssey_rag/retrieval/engine.py` — search instrumentation
- `src/odyssey_rag/ingestion/pipeline.py` — ingest instrumentation
- `src/odyssey_rag/retrieval/reranker.py` — reranker instrumentation
- `pyproject.toml` — added `prometheus-client` dependency
- `tests/unit/test_observability.py` — 16 tests

---

## Test Summary
- **Original tests**: 223 pass (204 original, 19 from other test files; 1 pre-existing broken file `test_documents.py` due to Python 3.9 `datetime.UTC` incompatibility — not caused by our changes)
- **New tests**: 38 added (4 GC + 18 cache + 16 observability)
- **Total**: 260 passing
