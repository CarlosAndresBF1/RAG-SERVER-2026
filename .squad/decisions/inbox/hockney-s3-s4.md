# Hockney — S3 + S4 Decision Log

## S3: Alembic Database Migrations

### Decisions
- **Async env.py pattern**: Used `create_async_engine` with `pool.NullPool` and `connection.run_sync()` callback — the standard Alembic async recipe. This avoids coupling to the app's singleton engine.
- **Database URL source**: `env.py` imports `get_settings().database_url` so credentials live in env vars / `.env`, never in `alembic.ini`.
- **Baseline migration**: Hand-wrote `001_baseline_schema.py` covering all 9 ORM models (Document, Chunk, ChunkEmbedding, ChunkMetadata, IngestJob, Feedback, AdminUser, McpToken, McpTokenAudit). For existing DBs, `alembic stamp head` marks them current without running DDL.
- **sys.path**: `alembic.ini` sets `prepend_sys_path = src`; `env.py` also adds `src/` to `sys.path` as a fallback.
- **Existing init scripts untouched**: `db/init/*.sql` and `db/migrations/*.sql` remain for fresh Docker setups.
- **Makefile**: Added `make migrate` target (`alembic upgrade head`). Kept legacy `db-migrate` for Docker-based workflow.

### Files Created
- `RAG/alembic.ini`
- `RAG/alembic/env.py`
- `RAG/alembic/script.py.mako`
- `RAG/alembic/versions/001_baseline_schema.py`
- `RAG/alembic/README.md`

### Files Modified
- `RAG/pyproject.toml` — added `alembic>=1.13.0,<2.0.0`
- `RAG/Makefile` — added `migrate` target

---

## S4: API Test Suite

### Decisions
- **Test client**: `httpx.AsyncClient` with `ASGITransport` — lightweight, no server socket needed.
- **Dependency overrides**: Used FastAPI's `app.dependency_overrides` for clean DI mocking (session, retrieval engine). For routes that import DB utilities directly (ingest), used `unittest.mock.patch` on the module-level symbol.
- **No real DB/embeddings**: All external deps mocked with `AsyncMock`/`MagicMock`. Tests complete in <1s.
- **Health endpoint**: Patches target the actual module where symbols are looked up at call time (`odyssey_rag.db.session.get_session_factory`, `odyssey_rag.embeddings.factory.create_embedding_provider`).
- **RetrievalEngine tests**: Mock `get_settings()` to control reranker/cache config. Mock `create_embedding_provider`, `vector_search`, and `bm25_search` at module level in `odyssey_rag.retrieval.engine`.
- **Existing tests unmodified**: All 204 original tests still pass. 26 new tests added (total 230 from S3+S4 work; 267 total including other agents' work).

### Test Coverage Added
| File | Tests | What's covered |
|------|-------|---------------|
| `test_health.py` | 3 | Health OK, DB failure → 503, embedding failure → 503 |
| `test_documents.py` | 7 | List sources, get source (found/not found/bad UUID), delete source (success/not found) |
| `test_search.py` | 6 | Search success, filters forwarded, empty query 422, invalid message_type 422, invalid focus 422, no results |
| `test_ingest.py` | 5 | Single ingest, ingest with overrides, missing source_path 422, batch ingest, empty batch |
| `test_engine.py` | 5 | Init passthrough reranker, basic search, tool context, embedding failure fallback, empty results |

### Files Created
- `RAG/tests/unit/test_api/__init__.py`
- `RAG/tests/unit/test_api/test_health.py`
- `RAG/tests/unit/test_api/test_documents.py`
- `RAG/tests/unit/test_api/test_search.py`
- `RAG/tests/unit/test_api/test_ingest.py`
- `RAG/tests/unit/test_retrieval/test_engine.py`
