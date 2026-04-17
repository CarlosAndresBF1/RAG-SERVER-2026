# Odyssey RAG

Self-contained knowledge retrieval system for the **Odyssey project** — indexes all Odyssey documentation including ISO 20022/IPS annexes (A, B, C), alias/QR/home banking docs, PHP source code, XML examples, Word documents (.doc/.docx), and technical documentation. Exposes knowledge via an **MCP server** (for VS Code / AI clients) and an **Admin UI** (for management).

> **Note**: This RAG covers general Odyssey documentation, not just the BimPay/IPS integration. BimPay is one of many integrations supported.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  VS Code / AI Client (MCP)          Admin UI (Browser)          │
│       │                                  │                      │
│       ▼                                  ▼                      │
│  ┌──────────────┐              ┌──────────────────┐             │
│  │  MCP Server   │              │  Next.js Web UI   │            │
│  │  :3010        │              │  :3044             │            │
│  │  (streamable  │              │  (App Router +     │            │
│  │   HTTP)       │              │   NextAuth)        │            │
│  └──────┬───────┘              └────────┬──────────┘             │
│         │                               │                        │
│         ▼                               ▼                        │
│  ┌──────────────────────────────────────────────┐               │
│  │              RAG API (FastAPI) :8089           │               │
│  │  Search · Ingest · Sources · Stats · Admin    │               │
│  └──────────────────┬───────────────────────────┘               │
│                     │                                            │
│         ┌───────────┼───────────┐                               │
│         ▼           ▼           ▼                               │
│  ┌───────────┐ ┌─────────┐ ┌──────────┐                        │
│  │ PostgreSQL │ │ nomic   │ │ Reranker │                        │
│  │ + pgvector │ │ embed   │ │ (cross-  │                        │
│  │ :5433      │ │ (local) │ │ encoder) │                        │
│  └───────────┘ └─────────┘ └──────────┘                        │
│                                                                  │
│                Docker Compose Network                            │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, NEXTAUTH_SECRET, API keys

# 2. Start all services
docker compose up -d

# 3. Open the Admin UI
open http://localhost:3044
# Login: admin@odyssey.local / admin

# 4. Ingest documents
# Drop files into data/sources/ or use the Ingest page in the UI

# 5. Connect MCP in VS Code
# .vscode/mcp.json is pre-configured — just enter your MCP token
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| **postgres** | 5433 | PostgreSQL 16 + pgvector (vector storage) |
| **rag-api** | 8089 | FastAPI backend — search, ingest, stats, admin |
| **mcp-server** | 3010 | MCP server (streamable HTTP, 2025-03-26 spec) |
| **web** | 3044 | Next.js admin dashboard |

## Tech Stack

### Backend (Python 3.11)
- **FastAPI** — async API with auto-generated OpenAPI docs
- **SQLAlchemy** (async) + **asyncpg** — PostgreSQL ORM
- **pgvector** — vector similarity search
- **nomic-embed-text** v1.5 — local embeddings (768 dim, CPU-only)
- **cross-encoder/ms-marco-MiniLM-L-6-v2** — reranker
- **MCP SDK** 1.9.4 — Model Context Protocol server
- **LLM providers**: OpenAI, Anthropic, Google, Ollama (configurable)
- **python-docx** — Word document (.docx) parsing
- **antiword** — Legacy Word (.doc) text extraction

### Frontend (Node.js 22)
- **Next.js** 16 (App Router) + **React** 19 + **TypeScript** 5 (strict)
- **Tailwind CSS** 4 + **shadcn/ui** (@base-ui/react)
- **NextAuth.js** v5 — credentials auth with JWT sessions
- **Recharts** — charts (dashboard, feedback)
- **Sonner** — toast notifications

### MCP Tools
| Tool | Description |
|------|-------------|
| `find_message_type` | ISO 20022 message specs, PHP code, XML examples |
| `find_business_rule` | Validation rules (M/O/C/R), field constraints |
| `find_module` | Odyssey/Bimpay implementation mapping |
| `find_error` | ISO status codes, reason codes, error handling |
| `search` | Free-text hybrid search across all sources |
| `ingest` | Feed new documents into the knowledge base |

## Project Structure

```
RAG/
├── src/odyssey_rag/           # Python backend
│   ├── api/                   #   FastAPI routes + schemas (incl. /health, /metrics)
│   ├── ingestion/             #   Parsers, chunkers, pipeline
│   ├── retrieval/             #   Hybrid search, reranker, cache
│   ├── embeddings/            #   Embedding providers (nomic, OpenAI)
│   ├── llm/                   #   LLM providers (OpenAI, Anthropic, Gemini, Ollama)
│   ├── mcp_server/            #   MCP server + tools
│   ├── observability.py       #   Prometheus metrics definitions
│   ├── maintenance.py         #   Garbage collection logic
│   └── db/                    #   SQLAlchemy models + repositories
├── alembic/                   # Alembic database migrations
├── web/                       # Next.js admin UI
│   ├── src/app/               #   Pages (dashboard, sources, search, etc.)
│   ├── src/components/        #   React components
│   └── src/lib/               #   Auth, API client, utils
├── db/                        # PostgreSQL baseline schema
├── tests/                     # Backend tests (267 unit tests)
├── data/sources/              # Source documents for ingestion
├── IAContext/                  # Architecture & planning docs
├── docker-compose.yml         # Full stack orchestration
└── Makefile                   # Build/test shortcuts
```

## Development

```bash
# Backend tests (uses project venv)
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -x

# Run via Makefile
make test-unit          # Unit tests in Docker
make test-eval          # Evaluation suite
make lint               # Ruff linter
make migrate            # Run Alembic migrations (upgrade head)

# Frontend dev (outside Docker)
cd web && npm install && npm run dev

# Frontend build
cd web && npx next build

# Rebuild specific service
docker compose up -d --build rag-api
docker compose up -d --build web
```

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | yes | Database password |
| `NEXTAUTH_SECRET` | yes | Session encryption key |
| `RAG_INTERNAL_KEY` | yes | Internal API key (web → backend) |
| `LLM_PROVIDER` | no | `openai`, `anthropic`, `gemini`, `ollama` |
| `OPENAI_API_KEY` | if openai | OpenAI API key |
| `OLLAMA_BASE_URL` | if ollama | Ollama server URL |

## Documentation

Detailed docs in [IAContext/](IAContext/):
- [ARCHITECTURE.md](IAContext/ARCHITECTURE.md) — system design, data flows
- [API_REFERENCE.md](IAContext/API_REFERENCE.md) — REST API endpoints
- [MCP_TOOLS.md](IAContext/MCP_TOOLS.md) — MCP tool specifications
- [DATA_MODEL.md](IAContext/DATA_MODEL.md) — database schema
- [SECURITY.md](IAContext/SECURITY.md) — auth, secrets, access control
- [UI.md](IAContext/UI.md) — admin UI plan and progress

## Key Design Decisions

### Asynchronous Ingestion
File ingestion is **fire-and-forget**: `POST /api/v1/ingest` creates a background job and returns a `job_id` immediately. The pipeline runs in the background via `asyncio.create_task`. Poll `GET /api/v1/jobs/{id}` for progress. This means navigating away from the ingest page does **not** interrupt processing.

### Job Management
Jobs can be **cancelled** while pending or running (`POST /api/v1/jobs/{id}/cancel`), and **deleted** once finished (`DELETE /api/v1/jobs/{id}`). Cancellation is cooperative — the pipeline checks for the `cancelled` status at key stages (before parse, before embed, before store) and aborts gracefully.

Job statuses: `pending` → `running` → `completed` | `failed` | `cancelled`

### Source Type Taxonomy
Documents are classified by `source_type` — detection is pattern-based on filename:

| Source Type | Description |
|-------------|-------------|
| `annex_b_spec` | IPS Annex B specification |
| `annex_a_spec` | Annex A specification |
| `annex_c_spec` | Annex C specification |
| `tech_doc` | BimPay technical/infrastructure docs |
| `alias_doc` | Alias documentation |
| `qr_doc` | QR / Código QR documentation |
| `banking_doc` | Home banking documentation |
| `integration_doc` | Integration guides |
| `paysett_doc` | PaySett integration documentation |
| `blite_doc` | Blite/Blossom integration documentation |
| `runbook` | Operations runbooks and playbooks |
| `architecture_doc` | Architecture and system design documents |
| `claude_context` | Claude AI context files |
| `php_code` | PHP source code |
| `xml_example` | XML message examples |
| `postman_collection` | Postman collections |
| `pdf_doc` | PDF documents |
| `word_doc` | Word documents (.doc/.docx) |
| `generic_text` | Markdown, text, RST (fallback) |

### Coverage Scope
The coverage page shows **two views**:
1. **Documentation Overview** — all documents by source type (docs, chunks, % distribution)
2. **ISO 20022 Message Matrix** — message_type × source_type (BimPay/IPS specific)

### Health Endpoints
Both services expose `/health` for Docker healthchecks and monitoring:
- **rag-api** (`GET /health`) — checks database, embedding model, and reranker connectivity. Returns `{ "status": "healthy" | "degraded" }` with per-component details.
- **mcp-server** (`GET /health`) — lightweight liveness check.

### Database Migrations (Alembic)
Schema changes are managed with **Alembic** (config at `alembic.ini`, migrations in `alembic/`):
```bash
make migrate              # Apply pending migrations (alembic upgrade head)
alembic revision --autogenerate -m "description"   # Create new migration
```

### Query Result Cache
Repeated identical queries are served from an **in-memory TTL cache** (`src/odyssey_rag/retrieval/cache.py`). This avoids re-running the full embed → search → fuse → rerank pipeline for the same query within the TTL window. Cache key is a SHA-256 hash of `(query, tool_name, tool_context)`.

### Garbage Collection
Superseded documents (re-ingested files where `is_current=False`) accumulate over time. The admin GC endpoint removes stale rows:
```
POST /api/v1/admin/gc   { "retention_days": 30 }
```
Deletes superseded documents older than the retention period, cascading to chunks, embeddings, and metadata.

### Observability (Prometheus)
The RAG API exposes `GET /metrics` in Prometheus text format. Key metrics:
- `rag_search_total` / `rag_search_duration_seconds` — search request count and latency
- `rag_ingestion_total` / `rag_ingestion_duration_seconds` — ingestion job tracking
- `rag_cache_hits_total` — query cache effectiveness
- `rag_active_documents` — gauge of current document count
