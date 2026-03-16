# Odyssey RAG

Self-contained knowledge retrieval system for the Odyssey project — indexes ISO 20022/IPS Annex B specs, PHP source code, XML examples, and technical documentation. Exposes knowledge via an **MCP server** (for VS Code / AI clients) and an **Admin UI** (for management).

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
│  │              RAG API (FastAPI) :8080           │               │
│  │  Search · Ingest · Sources · Stats · Admin    │               │
│  └──────────────────┬───────────────────────────┘               │
│                     │                                            │
│         ┌───────────┼───────────┐                               │
│         ▼           ▼           ▼                               │
│  ┌───────────┐ ┌─────────┐ ┌──────────┐                        │
│  │ PostgreSQL │ │ nomic   │ │ Reranker │                        │
│  │ + pgvector │ │ embed   │ │ (cross-  │                        │
│  │ :5432      │ │ (local) │ │ encoder) │                        │
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
│   ├── api/                   #   FastAPI routes + schemas
│   ├── ingestion/             #   Parsers, chunkers, pipeline
│   ├── retrieval/             #   Hybrid search, reranker, response
│   ├── embeddings/            #   Embedding providers (nomic, OpenAI)
│   ├── llm/                   #   LLM providers (OpenAI, Anthropic, Gemini, Ollama)
│   ├── mcp_server/            #   MCP server + tools
│   └── db/                    #   SQLAlchemy models + repositories
├── web/                       # Next.js admin UI
│   ├── src/app/               #   Pages (dashboard, sources, search, etc.)
│   ├── src/components/        #   React components
│   └── src/lib/               #   Auth, API client, utils
├── db/                        # PostgreSQL schema + migrations
├── tests/                     # Backend tests (196 unit tests)
├── data/sources/              # Source documents for ingestion
├── IAContext/                  # Architecture & planning docs
├── docker-compose.yml         # Full stack orchestration
└── Makefile                   # Build/test shortcuts
```

## Development

```bash
# Backend tests
PYTHONPATH=src python -m pytest tests/unit/ -x

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
