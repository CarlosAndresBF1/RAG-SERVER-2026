# Odyssey RAG — Master Execution Plan

> **Version**: 1.0.0  
> **Date**: 2026-03-02  
> **Status**: 🟢 Executing — Phase 1 COMPLETE  
> **Executor**: Claude Sonnet 4.5 (tasks) · Claude Opus 4.6 (reviews)  
> **Last Updated**: 2026-03-02

---

## 0. Document Index

| # | Document | Purpose |
|---|----------|---------|
| 1 | [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, data flows, tech stack |
| 2 | [CONVENTIONS.md](CONVENTIONS.md) | Code style, naming, testing standards |
| 3 | [MCP_TOOLS.md](MCP_TOOLS.md) | 6 MCP tool specifications |
| 4 | [DATA_MODEL.md](DATA_MODEL.md) | PostgreSQL schema, indexes, queries |
| 5 | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) | Parsers, chunkers, metadata, embedding |
| 6 | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) | Search, fusion, reranking, response |
| 7 | [DOCKER_SETUP.md](DOCKER_SETUP.md) | Docker Compose, Dockerfile, Makefile |
| 8 | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) | Test layers, fixtures, coverage |
| 9 | [API_REFERENCE.md](API_REFERENCE.md) | FastAPI endpoints, schemas |
| 10 | [EVALUATION_SET.md](EVALUATION_SET.md) | 60+ domain questions for quality |
| 11 | [SECURITY.md](SECURITY.md) | Auth, secrets, container security |

---

## 1. Execution Model

```
┌─────────────────────────────────────────────────────┐
│  Phase workflow:                                     │
│                                                     │
│  Sonnet 4.6 ──→ Tasks 1..N ──→ Opus 4.6 Review     │
│       │                              │              │
│       │         ┌────────────────────┘              │
│       │         ↓                                   │
│       │    Approved? ──Yes──→ Next Phase             │
│       │         │                                   │
│       │        No                                   │
│       │         │                                   │
│       └─── Fix issues ←─────┘                       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Rules**:
1. Sonnet 4.6 executes tasks sequentially within each phase
2. After each phase, Opus 4.6 reviews all deliverables
3. No phase begins until the previous phase is approved
4. Each task has explicit acceptance criteria
5. All code follows [CONVENTIONS.md](CONVENTIONS.md)

---

## 2. Phase 1 — Project Skeleton & Infrastructure

**Goal**: Repo structure, Docker setup, database schema — zero business logic.

| Task | Description | Ref Doc | Acceptance Criteria |
|------|-------------|---------|---------------------|
| **1.1** ✅ | Initialize Git repo with structure from ARCHITECTURE.md §6 | [ARCHITECTURE.md](ARCHITECTURE.md) | All directories exist, `__init__.py` in each package |
| **1.2** ✅ | Create `pyproject.toml` with dependencies and tool config | [CONVENTIONS.md](CONVENTIONS.md) | ruff, pytest, mypy configured; all deps listed |
| **1.3** ✅ | Create `requirements.txt` + `requirements-dev.txt` | [CONVENTIONS.md](CONVENTIONS.md) | Pinned versions, split prod/dev |
| **1.4** ✅ | Create `Dockerfile` (multi-stage: base, api, mcp, dev) | [DOCKER_SETUP.md](DOCKER_SETUP.md) §3 | `docker build --target api .` succeeds |
| **1.5** ✅ | Create `docker-compose.yml` (postgres, rag-api, mcp-server) | [DOCKER_SETUP.md](DOCKER_SETUP.md) §2 | `docker compose config` validates |
| **1.6** ✅ | Create `.env.example` | [DOCKER_SETUP.md](DOCKER_SETUP.md) §5 | All env vars documented |
| **1.7** ✅ | Create `Makefile` with all targets | [DOCKER_SETUP.md](DOCKER_SETUP.md) §8 | `make up`, `make down`, `make test` work |
| **1.8** ✅ | Create DB init scripts: `001_extensions.sql`, `002_schema.sql` | [DATA_MODEL.md](DATA_MODEL.md) §3 | Schema created on `docker compose up` |
| **1.9** ✅ | Create `.gitignore`, `.dockerignore` | — | Secrets, caches, venvs excluded |
| **1.10** ✅ | Create `config/settings.py` with pydantic-settings | [CONVENTIONS.md](CONVENTIONS.md) §4 | Settings loads from env, validated |

### Phase 1 Deliverables
- [ ] Working `docker compose up` starts 3 services
- [ ] `docker compose exec postgres psql` connects and shows 6 tables
- [x] `curl localhost:8080/health` → placeholder 200 OK (FastAPI app created)
- [x] `ruff check src/` passes with zero errors ✅ verified
- [x] `mypy src/` passes with zero errors ✅ verified (19 source files)

> **Phase 1 Code Status**: All 10 tasks completed. `docker compose config` validates. ruff + mypy pass. Awaiting Docker build + full stack verification.

### 🔍 Opus 4.6 Review Gate #1
> Verify: repo structure matches ARCHITECTURE.md §6, Docker starts cleanly, DB schema matches DATA_MODEL.md §3, settings load correctly, code style matches CONVENTIONS.md.

---

## 3. Phase 2 — Embedding & Database Layer

**Goal**: Embedding provider, DB repositories, model layer — no parsers yet.

| Task | Description | Ref Doc | Acceptance Criteria |
|------|-------------|---------|---------------------|
| **2.1** | Implement `embeddings/provider.py` — nomic-embed-text wrapper | [ARCHITECTURE.md](ARCHITECTURE.md) §3.1 | `embed(["hello"])` returns 768-dim vector |
| **2.2** | Implement `embeddings/factory.py` — provider factory | [CONVENTIONS.md](CONVENTIONS.md) §4 | Configurable via `EMBEDDING_PROVIDER` env |
| **2.3** | Implement `db/models.py` — SQLAlchemy ORM models (6 tables) | [DATA_MODEL.md](DATA_MODEL.md) §3 | Models match schema DDL exactly |
| **2.4** | Implement `db/session.py` — async session factory | [CONVENTIONS.md](CONVENTIONS.md) §4 | Async session with proper lifecycle |
| **2.5** | Implement `db/repositories.py` — CRUD for document, chunk, embedding | [DATA_MODEL.md](DATA_MODEL.md) §4-5 | insert, query, delete operations work |
| **2.6** | Write unit tests for embedding provider (mocked model) | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3.5 | Tests pass, cover embed + batch |
| **2.7** | Write unit tests for repositories (mocked session) | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3.6 | Tests pass for CRUD operations |
| **2.8** | Implement `llm/provider.py` — LLM provider abstraction | [ARCHITECTURE.md](ARCHITECTURE.md) §4 | OpenAI, Anthropic, Gemini switchable |
| **2.9** | Implement `llm/factory.py` — provider factory | [CONVENTIONS.md](CONVENTIONS.md) §4 | `LLM_PROVIDER` env selects provider |

### Phase 2 Deliverables
- [ ] `pytest tests/unit/test_embeddings/ -v` — all pass
- [ ] `pytest tests/unit/test_db/ -v` — all pass
- [ ] Embedding model loads in Docker (verifiy with integration smoke test)
- [ ] DB repositories insert and query documents/chunks/embeddings

### 🔍 Opus 4.6 Review Gate #2
> Verify: embedding dimensions correct (768), ORM models match DDL, repositories use parameterized queries, LLM abstraction supports 3 providers, tests are meaningful.

---

## 4. Phase 3 — Ingestion Pipeline

**Goal**: Parse, chunk, extract metadata, embed, store — for all source types.

| Task | Description | Ref Doc | Acceptance Criteria |
|------|-------------|---------|---------------------|
| **3.1** | Implement `ingestion/parsers/base.py` — BaseParser + ParsedSection | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §3.1 | Abstract interface defined |
| **3.2** | Implement `ingestion/parsers/markdown.py` — MarkdownParser | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §3.2 | Splits by H1/H2/H3, handles Annex B tables |
| **3.3** | Implement `ingestion/parsers/php_code.py` — PhpCodeParser | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §3.3 | Extracts class/method/constants per file |
| **3.4** | Implement `ingestion/parsers/xml_example.py` — XmlExampleParser | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §3.4 | Detects message type, extracts sections |
| **3.5** | Implement `ingestion/parsers/postman.py` — PostmanParser | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §3.6 | Parses collection items to sections |
| **3.6** | Implement `ingestion/chunkers/base.py` — BaseChunker + Chunk | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §4.1 | Abstract interface defined |
| **3.7** | Implement `ingestion/chunkers/markdown.py` — MarkdownChunker | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §4.2 | Heading-aware, respects boundaries |
| **3.8** | Implement `ingestion/chunkers/php_code.py` — PhpCodeChunker | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §4.3 | Method-level chunks with class context |
| **3.9** | Implement `ingestion/chunkers/semantic.py` — SemanticChunker | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §4.5 | Token-aware paragraph splitting |
| **3.10** | Implement `ingestion/metadata/extractor.py` — MetadataExtractor | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §5 | Detects message types, XPaths, rules |
| **3.11** | Implement `ingestion/pipeline.py` — main orchestration | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §1.2 | Full flow: detect → parse → chunk → embed → store |
| **3.12** | Implement change detection & deduplication | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §8 | SHA-256 hash, skip unchanged, supersede changed |
| **3.13** | Write unit tests for all 4 parsers | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3.1 | Each parser has ≥5 test cases |
| **3.14** | Write unit tests for all 3 chunkers | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3.2 | Boundary, overlap, size tests |
| **3.15** | Write unit tests for metadata extractor | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3.3 | Message type detection, XPath extraction |
| **3.16** | Create test fixtures (`tests/fixtures/`) | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §7.2 | 5 sample files created |
| **3.17** | Write integration test for full pipeline | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §4.3 | Ingest → DB → verify chunks/embeddings |

### Phase 3 Deliverables
- [ ] `pytest tests/unit/test_parsers/ -v` — all pass
- [ ] `pytest tests/unit/test_chunkers/ -v` — all pass
- [ ] `pytest tests/unit/test_metadata/ -v` — all pass
- [ ] `pytest tests/integration/test_ingest_pipeline.py -v` — all pass
- [ ] Manual: `make seed` ingests all project sources without errors

### 🔍 Opus 4.6 Review Gate #3
> Verify: all parsers handle edge cases (empty files, malformed input), chunkers respect size limits, metadata correctly detects all 10 message types, pipeline handles re-ingestion correctly, test coverage ≥85% for ingestion module.

---

## 5. Phase 4 — Retrieval Engine

**Goal**: Hybrid search, RRF fusion, cross-encoder reranking, response assembly.

| Task | Description | Ref Doc | Acceptance Criteria |
|------|-------------|---------|---------------------|
| **4.1** | Implement `retrieval/query_processor.py` — query parsing + expansion | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) §2 | Detects message types, expands abbreviations |
| **4.2** | Implement `retrieval/vector_search.py` — pgvector similarity search | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) §3.1 | Cosine similarity with metadata filters |
| **4.3** | Implement `retrieval/bm25_search.py` — full-text search | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) §3.2 | tsvector search with ts_rank_cd |
| **4.4** | Implement `retrieval/fusion.py` — RRF merge | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) §3.3 | Merges vector + BM25 results correctly |
| **4.5** | Implement `retrieval/reranker.py` — cross-encoder | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) §4 | ms-marco-MiniLM-L-6-v2 reranking |
| **4.6** | Implement `retrieval/response_builder.py` — evidence + gaps + followups | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) §5 | Structured output with citations |
| **4.7** | Implement `retrieval/tool_strategies.py` — per-tool customization | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) §6 | 4 tool-specific strategies |
| **4.8** | Implement `retrieval/engine.py` — main orchestration | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) §1 | Full flow: query → search → fuse → rerank → respond |
| **4.9** | Write unit tests for query processor | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3.4 | Expansion, detection, filtering tests |
| **4.10** | Write unit tests for RRF fusion | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3.5 | Merge correctness, edge cases |
| **4.11** | Write unit tests for response builder | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3.6 | Threshold filtering, gap detection |
| **4.12** | Write integration test for end-to-end retrieval | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §4 | Query seeded DB, verify evidence quality |

### Phase 4 Deliverables
- [ ] `pytest tests/unit/test_retrieval/ -v` — all pass
- [ ] `pytest tests/integration/test_retrieval_e2e.py -v` — passes with seeded DB
- [ ] Manual: search returns relevant results for "pacs.008 group header"
- [ ] Latency: p50 < 500ms, p95 < 1500ms

### 🔍 Opus 4.6 Review Gate #4
> Verify: hybrid search produces better results than vector-only or BM25-only, RRF merge is correctly implemented (k=60), reranker improves precision, response builder filters low-confidence results, tool strategies correctly customize retrieval per MCP tool.

---

## 6. Phase 5 — API Layer

**Goal**: FastAPI endpoints, Pydantic schemas, error handling.

| Task | Description | Ref Doc | Acceptance Criteria |
|------|-------------|---------|---------------------|
| **5.1** | Implement `api/main.py` — FastAPI app with routers | [API_REFERENCE.md](API_REFERENCE.md) §5 | App starts, `/docs` works |
| **5.2** | Implement `api/schemas.py` — all Pydantic models | [API_REFERENCE.md](API_REFERENCE.md) §3 | Validation works, OpenAPI correct |
| **5.3** | Implement `api/routes/search.py` — search endpoint | [API_REFERENCE.md](API_REFERENCE.md) §2.2 | POST /api/v1/search returns evidence |
| **5.4** | Implement `api/routes/ingest.py` — ingest + batch endpoints | [API_REFERENCE.md](API_REFERENCE.md) §2.3-2.4 | Single and batch ingest work |
| **5.5** | Implement `api/routes/sources.py` — list, detail, delete | [API_REFERENCE.md](API_REFERENCE.md) §2.5-2.7 | CRUD operations on sources |
| **5.6** | Implement `api/routes/chunks.py` — chunk listing | [API_REFERENCE.md](API_REFERENCE.md) §2.8 | Filtered chunk queries |
| **5.7** | Implement `api/routes/feedback.py` — feedback collection | [API_REFERENCE.md](API_REFERENCE.md) §2.9 | Ratings stored in DB |
| **5.8** | Implement `api/auth.py` — API key authentication | [SECURITY.md](SECURITY.md) §2 | Auth enforced in non-dev mode |
| **5.9** | Implement `api/errors.py` — error handling middleware | [API_REFERENCE.md](API_REFERENCE.md) §4 | Consistent error format |
| **5.10** | Implement health endpoint with service checks | [API_REFERENCE.md](API_REFERENCE.md) §2.1 | DB, embedding, reranker status |
| **5.11** | Write integration tests for all API endpoints | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §4.2 | All endpoints return correct status codes |

### Phase 5 Deliverables
- [ ] `curl localhost:8080/docs` shows all endpoints
- [ ] `pytest tests/integration/test_api_endpoints.py -v` — all pass
- [ ] All endpoints return correct HTTP status codes
- [ ] Error responses follow consistent format

### 🔍 Opus 4.6 Review Gate #5
> Verify: Swagger docs complete, Pydantic validation catches bad input, auth works correctly, error responses consistent, pagination works, all integration tests pass.

---

## 7. Phase 6 — MCP Server

**Goal**: 6 MCP tools operational via stdio and HTTP/SSE transport.

| Task | Description | Ref Doc | Acceptance Criteria |
|------|-------------|---------|---------------------|
| **6.1** | Implement `mcp_server/main.py` — MCP server entry point | [MCP_TOOLS.md](MCP_TOOLS.md) §1 | Server starts, lists 6 tools |
| **6.2** | Implement `mcp_server/tools/find_message_type.py` | [MCP_TOOLS.md](MCP_TOOLS.md) §2.1 | Tool works with all focus options |
| **6.3** | Implement `mcp_server/tools/find_business_rule.py` | [MCP_TOOLS.md](MCP_TOOLS.md) §2.2 | Rules and field data returned |
| **6.4** | Implement `mcp_server/tools/find_module.py` | [MCP_TOOLS.md](MCP_TOOLS.md) §2.3 | Returns module_map object |
| **6.5** | Implement `mcp_server/tools/find_error.py` | [MCP_TOOLS.md](MCP_TOOLS.md) §2.4 | Returns resolution object |
| **6.6** | Implement `mcp_server/tools/search.py` | [MCP_TOOLS.md](MCP_TOOLS.md) §2.5 | Free-text search works |
| **6.7** | Implement `mcp_server/tools/ingest.py` | [MCP_TOOLS.md](MCP_TOOLS.md) §2.6 | Ingest via MCP tool works |
| **6.8** | Implement `mcp_server/transport.py` — dual transport (stdio + HTTP/SSE) | [MCP_TOOLS.md](MCP_TOOLS.md) §5 | Both transports work |
| **6.9** | Create `.vscode/mcp.json` for both transport modes | [DOCKER_SETUP.md](DOCKER_SETUP.md) §9 | VS Code discovers tools |
| **6.10** | Write integration tests for MCP server | [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §4.4 | All 6 tools return valid responses |

### Phase 6 Deliverables
- [ ] VS Code shows 6 Odyssey RAG tools in MCP panel
- [ ] Each tool returns structured JSON (evidence, gaps, followups)
- [ ] `pytest tests/integration/test_mcp_server.py -v` — all pass
- [ ] Both stdio and HTTP/SSE transports functional

### 🔍 Opus 4.6 Review Gate #6
> Verify: all 6 tools match MCP_TOOLS.md spec exactly, output contract includes evidence+gaps+followups, VS Code integration works, tool descriptions are clear for LLM consumption, error handling graceful.

---

## 8. Phase 7 — Seed Data & Evaluation

**Goal**: Ingest all project sources, run evaluation suite, tune quality.

| Task | Description | Ref Doc | Acceptance Criteria |
|------|-------------|---------|---------------------|
| **7.1** | Create `scripts/seed_initial_sources.py` | [INGESTION_PIPELINE.md](INGESTION_PIPELINE.md) §9 | Seeds all sources from INITIAL_SOURCES list |
| **7.2** | Create `scripts/migrate.py` — migration runner | [DATA_MODEL.md](DATA_MODEL.md) §7 | Applies numbered migrations |
| **7.3** | Run full seed ingestion | — | All ~93 documents ingested, ~430-790 chunks |
| **7.4** | Create `tests/evaluation/evaluation_questions.json` | [EVALUATION_SET.md](EVALUATION_SET.md) §3 | 60+ questions with expected answers |
| **7.5** | Implement `tests/evaluation/test_evaluation_suite.py` | [EVALUATION_SET.md](EVALUATION_SET.md) §4 | Automated precision/recall/MRR measurement |
| **7.6** | Run evaluation, analyze results | [EVALUATION_SET.md](EVALUATION_SET.md) §5 | Report generated |
| **7.7** | Tune retrieval parameters if targets not met | [RETRIEVAL_ENGINE.md](RETRIEVAL_ENGINE.md) §7 | Precision@5 ≥ 0.70, Recall@10 ≥ 0.80, MRR ≥ 0.75 |

### Phase 7 Deliverables
- [ ] `make seed` completes without errors
- [ ] `pytest tests/evaluation/ -v` — generates report
- [ ] All metrics at or above targets
- [ ] Evaluation report saved

### 🔍 Opus 4.6 Review Gate #7 (Final)
> Verify: all sources ingested correctly, evaluation metrics meet targets, weak categories identified and addressed, system end-to-end functional (Docker up → seed → search → MCP tool → VS Code). Full system review against all 11 specification documents.

---

## 9. Task Dependency Graph

```
Phase 1 (Skeleton)
  ├── 1.1-1.10 (parallel where possible)
  └── Gate #1
        │
Phase 2 (DB + Embeddings)
  ├── 2.1-2.2 (embeddings)
  ├── 2.3-2.5 (DB layer) — parallel with embeddings
  ├── 2.6-2.7 (unit tests)
  ├── 2.8-2.9 (LLM providers)
  └── Gate #2
        │
Phase 3 (Ingestion)
  ├── 3.1 (base parser)
  ├── 3.2-3.5 (parsers — parallel after 3.1)
  ├── 3.6 (base chunker)
  ├── 3.7-3.9 (chunkers — parallel after 3.6)
  ├── 3.10 (metadata — after parsers)
  ├── 3.11-3.12 (pipeline — after all above)
  ├── 3.13-3.17 (tests — after implementations)
  └── Gate #3
        │
Phase 4 (Retrieval)
  ├── 4.1 (query processor)
  ├── 4.2-4.3 (search — parallel)
  ├── 4.4 (fusion — after 4.2+4.3)
  ├── 4.5 (reranker — parallel with 4.4)
  ├── 4.6-4.7 (response — after 4.4+4.5)
  ├── 4.8 (engine — after all above)
  ├── 4.9-4.12 (tests)
  └── Gate #4
        │
Phase 5 (API)
  ├── 5.1-5.2 (app + schemas)
  ├── 5.3-5.7 (routes — parallel after 5.1)
  ├── 5.8-5.9 (auth + errors)
  ├── 5.10-5.11 (health + tests)
  └── Gate #5
        │
Phase 6 (MCP)
  ├── 6.1 (server entry)
  ├── 6.2-6.7 (tools — parallel after 6.1)
  ├── 6.8 (transport)
  ├── 6.9 (VS Code config)
  ├── 6.10 (tests)
  └── Gate #6
        │
Phase 7 (Seed + Eval)
  ├── 7.1-7.2 (scripts)
  ├── 7.3 (seed run)
  ├── 7.4-7.5 (evaluation test setup)
  ├── 7.6-7.7 (run + tune)
  └── Gate #7 (Final)
```

---

## 10. Estimated Effort

| Phase | Tasks | Est. Complexity | Description |
|-------|-------|----------------|-------------|
| Phase 1 | 10 | Low | Boilerplate, config, Docker |
| Phase 2 | 9 | Medium | Embedding integration, ORM, LLM abstraction |
| Phase 3 | 17 | High | 4 parsers, 3 chunkers, metadata, pipeline |
| Phase 4 | 12 | High | Search, fusion, reranking, response |
| Phase 5 | 11 | Medium | REST endpoints, validation, auth |
| Phase 6 | 10 | Medium | MCP tools, dual transport |
| Phase 7 | 7 | Medium | Seed, evaluate, tune |
| **Total** | **76 tasks** | | |

---

## 11. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| nomic-embed-text model download fails in Docker | Low | High | Pre-download in Dockerfile build stage, cache in volume |
| Annex B Markdown parsing edge cases (complex tables) | Medium | Medium | Extensive fixtures, fallback to semantic chunker |
| pgvector HNSW index performance at scale | Low | Medium | Configurable ef_search, can switch to IVFFlat |
| Cross-encoder reranker too slow on CPU | Medium | Low | Configurable `reranker_enabled=false` bypass |
| MCP SDK breaking changes | Low | Medium | Pin SDK version, test both transports |
| Evaluation metrics below targets | Medium | Medium | Phase 7.7 tuning: adjust chunk size, overlap, boost weights |

---

## 12. How to Start

```bash
# 1. User gives the execution order
# 2. Sonnet 4.6 reads this PLAN.md
# 3. Sonnet starts Phase 1, Task 1.1
# 4. After Phase 1 complete → Opus 4.6 reviews
# 5. Continue through all 7 phases
```

**Awaiting execution order.**
