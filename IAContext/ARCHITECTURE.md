# Odyssey RAG — Architecture Document

> **Version**: 1.0.0  
> **Date**: 2026-03-02  
> **Status**: Planning  
> **Audience**: AI agents (Sonnet/Opus) executing tasks, human reviewers

---

## 1. System Overview

The Odyssey RAG is a **self-contained, dockerized knowledge retrieval system** that indexes Odyssey project documentation (ISO 20022/IPS Annex B specs, PHP source code, XML examples, technical docs) and exposes it via an **MCP server** consumable from VS Code and other AI clients.

### 1.1 Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Domain-first tools** | MCP tools modeled on ISO 20022 message types, not generic REST |
| **Provider-agnostic LLM** | Swap OpenAI ↔ Claude ↔ local via config, no code changes |
| **Local embeddings** | nomic-embed runs in-container, zero API cost for indexing |
| **Hybrid search** | Vector (semantic) + BM25 (keyword) for engineering queries |
| **Strict citations** | Every response links to source chunk; gaps reported explicitly |
| **Extensible ingestion** | New doc types (PDF, Markdown, code) added via pluggable parsers |
| **Single docker compose** | `docker compose up` starts everything: Postgres+pgvector, RAG API, MCP server |

### 1.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VS Code / AI Client                          │
│                                                                     │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│   │  Copilot /   │    │  Claude     │    │  Other MCP  │            │
│   │  Agent Mode  │    │  Code       │    │  Client     │            │
│   └──────┬───────┘    └──────┬──────┘    └──────┬──────┘            │
│          │                   │                   │                   │
└──────────┼───────────────────┼───────────────────┼───────────────────┘
           │ MCP (stdio)       │ MCP (HTTP/SSE)    │ MCP (HTTP/SSE)
           │                   │                   │
┌──────────┼───────────────────┼───────────────────┼───────────────────┐
│          ▼                   ▼                   ▼                   │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │                   MCP Server (Python)                    │        │
│  │                                                         │        │
│  │  Tools:                                                 │        │
│  │  ├─ oddysey_rag.find_message_type                       │        │
│  │  ├─ oddysey_rag.find_business_rule                      │        │
│  │  ├─ oddysey_rag.find_module                             │        │
│  │  ├─ oddysey_rag.find_error                              │        │
│  │  ├─ oddysey_rag.search (free-text)                      │        │
│  │  └─ oddysey_rag.ingest (feed new docs)                  │        │
│  │                                                         │        │
│  │  Transports: stdio + HTTP/SSE (dual mode)               │        │
│  └────────────────────────┬────────────────────────────────┘        │
│                           │                                         │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │                  RAG API (FastAPI)                       │        │
│  │                                                         │        │
│  │  Endpoints:                                             │        │
│  │  ├─ POST /api/v1/search     (hybrid retrieval)          │        │
│  │  ├─ GET  /api/v1/chunk/{id} (get source chunk)          │        │
│  │  ├─ POST /api/v1/ingest     (feed documents)            │        │
│  │  ├─ GET  /api/v1/sources    (list indexed sources)      │        │
│  │  └─ GET  /api/v1/health     (healthcheck)               │        │
│  │                                                         │        │
│  │  Orchestration: LangChain (agent flow)                  │        │
│  │  Data/Index:    LlamaIndex (chunking, indexing)         │        │
│  └────────────┬───────────────────────┬────────────────────┘        │
│               │                       │                             │
│               ▼                       ▼                             │
│  ┌────────────────────┐  ┌─────────────────────────────┐           │
│  │  Embedding Service  │  │  PostgreSQL + pgvector       │           │
│  │  (nomic-embed)      │  │                             │           │
│  │                     │  │  Tables:                    │           │
│  │  Local model,       │  │  ├─ documents               │           │
│  │  runs in container  │  │  ├─ chunks                  │           │
│  │                     │  │  ├─ embeddings              │           │
│  └─────────────────────┘  │  ├─ metadata                │           │
│                           │  ├─ feedback                │           │
│                           │  └─ ingest_jobs             │           │
│                           └─────────────────────────────┘           │
│                                                                     │
│                     Docker Compose Network                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Details

### 2.1 MCP Server

**Purpose**: Expose RAG capabilities as MCP tools consumable by VS Code, Claude Code, and any MCP-compatible client.

| Aspect | Decision |
|--------|----------|
| **Language** | Python 3.11+ |
| **Framework** | `mcp` Python SDK (official Anthropic SDK) |
| **Transport** | Dual: `stdio` (local dev) + `HTTP/SSE` (centralized team) |
| **Auth** | API key via `Authorization: Bearer` header (HTTP mode) |
| **Tools exposed** | 6 tools (see [MCP_TOOLS.md](MCP_TOOLS.md)) |

**Dual transport** means:
- **stdio mode**: Developer runs MCP server locally via `.vscode/mcp.json` → `command: python -m oddysey_rag.mcp_server`
- **HTTP/SSE mode**: MCP server runs as Docker service, team points to `http://localhost:8081/mcp` (or remote URL)

### 2.2 RAG API (FastAPI)

**Purpose**: Core search and ingestion service. The MCP server calls this internally.

| Aspect | Decision |
|--------|----------|
| **Framework** | FastAPI 0.100+ |
| **Orchestration** | LangChain (chain-of-thought, tool routing, reranking flow) |
| **Data indexing** | LlamaIndex (document loading, chunking, index management) |
| **Port** | 8080 (internal), optionally exposed |
| **Docs** | Auto-generated OpenAPI at `/docs` |

**Key design**: The API is **stateless per request**. All state lives in PostgreSQL. This allows horizontal scaling if needed later.

### 2.3 Embedding Service

| Aspect | Decision |
|--------|----------|
| **Model** | `nomic-embed-text` v1.5 (768 dimensions) |
| **Runtime** | Runs locally inside Docker container (no external API calls) |
| **Framework** | `sentence-transformers` or `ollama` as inference backend |
| **Fallback** | Config flag to switch to OpenAI `text-embedding-3-small` or Cohere |

**Why nomic-embed**: Open-source, runs on CPU (no GPU required), 8192 token context window, good performance on code + technical text, zero cost.

### 2.4 PostgreSQL + pgvector

| Aspect | Decision |
|--------|----------|
| **Image** | `pgvector/pgvector:pg16` |
| **Extensions** | `pgvector` (vector similarity), `pg_trgm` (trigram for BM25-like text search) |
| **Port** | 5432 (internal), optionally exposed for debugging |
| **Persistence** | Docker named volume `rag_pgdata` |

**Why pgvector over dedicated vector DBs**: Already using Postgres in Odyssey ecosystem. Single DB for vectors + metadata + feedback + full-text search. Simpler ops.

---

## 3. Data Flow

### 3.1 Ingestion Flow (Offline)

```
Source Files                    Ingestion Pipeline                    Storage
─────────────                   ──────────────────                    ───────
                                
┌──────────────┐   ┌─────────────────────────────────────────────┐
│ Markdown      │──▶│ 1. Source Detection (file type resolver)    │
│ (Annex B,     │   │                                             │
│  CLAUDE.md,   │   │ 2. Parser (per source_type)                 │
│  Tech docs)   │   │    ├─ MarkdownParser    → sections/headers  │
│               │   │    ├─ PhpCodeParser     → classes/functions  │
├──────────────┤   │    ├─ XmlExampleParser  → message structure  │
│ PHP Code      │──▶│    ├─ PdfParser         → text + tables     │
│ (Bimpay 56    │   │    ├─ PostmanParser     → requests/examples │
│  files)       │   │    └─ GenericTextParser → fallback          │
│               │   │                                             │
├──────────────┤   │ 3. Chunking Strategy (per source type)       │
│ XML Examples  │──▶│    ├─ Markdown: by heading hierarchy        │
│ (IPS messages │   │    ├─ PHP: by class/function + docblock     │   ┌──────────┐
│  pacs, camt,  │   │    ├─ XML: by message type + section       │──▶│ chunks   │
│  pain)        │   │    └─ PDF: by section/page                  │   │ table    │
│               │   │                                             │   └──────────┘
├──────────────┤   │ 4. Metadata Extraction                       │
│ PDFs          │──▶│    ├─ source_type (pdf_doc, php_code, etc)  │   ┌──────────┐
│ (future)      │   │    ├─ message_type (pacs.008, camt.056...)  │──▶│ metadata │
│               │   │    ├─ iso_version (pacs.008.001.12)         │   │ table    │
├──────────────┤   │    ├─ module_path (Bimpay/Messages/...)      │   └──────────┘
│ Postman       │──▶│    ├─ doc_version, section, subsection      │
│ Collections   │   │    └─ field_xpath, rule_status (M/O/C/R)   │   ┌──────────┐
└──────────────┘   │                                             │   │embeddings│
                    │ 5. Embedding (nomic-embed)                  │──▶│ table    │
                    │    └─ chunk text → 768-dim vector           │   └──────────┘
                    │                                             │
                    │ 6. Storage (PostgreSQL + pgvector)           │   ┌──────────┐
                    │    └─ INSERT chunks + embeddings + metadata  │──▶│documents │
                    │                                             │   │ table    │
                    └─────────────────────────────────────────────┘   └──────────┘
```

### 3.2 Query Flow (Online)

```
User Query                     Retrieval Pipeline                      Response
──────────                     ──────────────────                      ────────

"How do I build      ┌─────────────────────────────────────┐
 a pacs.008 for      │ 1. Query Analysis                    │
 500 BBD?"           │    ├─ Extract: message_type=pacs.008 │
         │           │    ├─ Extract: amount context          │
         │           │    └─ Build metadata filters           │
         ▼           │                                       │
┌─────────────┐      │ 2. Hybrid Search                      │
│ MCP Tool:    │─────▶│    ├─ Vector search (semantic)        │
│ find_message │      │    │   cosine_similarity(query_emb,   │
│ _type        │      │    │   chunk_emb) → top 20            │
└─────────────┘      │    ├─ BM25 search (keyword)           │
                      │    │   ts_rank(tsvector, query) → 20  │
                      │    └─ Merge + deduplicate → top 20    │
                      │                                       │
                      │ 3. Metadata Filtering                 │
                      │    └─ WHERE message_type = 'pacs.008' │
                      │      AND source_type IN (...)          │
                      │                                       │
                      │ 4. Reranking (cross-encoder)          │     ┌────────────┐
                      │    └─ Score(query, chunk) → top 5-8   │────▶│ evidence[] │
                      │                                       │     │ gaps[]     │
                      │ 5. Response Assembly                  │     │ followups[]│
                      │    ├─ Format evidence with citations   │     └────────────┘
                      │    ├─ Identify gaps (missing sources)  │
                      │    └─ Suggest follow-up queries        │
                      └─────────────────────────────────────┘
```

---

## 4. Technology Stack (Locked Decisions)

| Layer | Technology | Version | Why |
|-------|-----------|---------|-----|
| **Language** | Python | 3.11+ | Ecosystem (LlamaIndex, LangChain, FastAPI) |
| **Web framework** | FastAPI | 0.100+ | Async, auto-docs, type-safe |
| **RAG data/index** | LlamaIndex | 0.10+ | Best chunking, document loaders, index management |
| **RAG orchestration** | LangChain | 0.2+ | Chain-of-thought, tool routing, agent patterns |
| **Vector DB** | PostgreSQL + pgvector | PG16 + pgvector 0.7+ | Unified storage, team familiarity |
| **Full-text search** | PostgreSQL `tsvector` + `pg_trgm` | Built-in | BM25-equivalent, no extra service |
| **Embeddings** | nomic-embed-text v1.5 | 768 dim | Local, free, 8K context, good on code |
| **Reranker** | Cross-encoder (local) | `ms-marco-MiniLM-L-6-v2` or similar | Improves precision, no API cost |
| **MCP SDK** | `mcp` (Anthropic official) | Latest | Dual transport (stdio + HTTP/SSE) |
| **LLM (generation)** | OpenAI GPT-4o (primary) | API | Response generation, summarization |
| **LLM (alt)** | Claude (Anthropic) | API | Provider-agnostic adapter pattern |
| **LLM (alt)** | Gemini (Google) | API | Provider-agnostic adapter pattern |
| **Container** | Docker + Docker Compose | v2 | Single `docker compose up` |
| **PDF parsing** | `pdfplumber` + `pypdf` | Latest | Text + table extraction |
| **Testing** | pytest + pytest-asyncio | Latest | Async FastAPI + pipeline tests |
| **Linting** | ruff | Latest | Fast, replaces flake8+isort+black |

### 4.1 LLM Provider Abstraction

```python
# config/llm_config.py — switching providers is a config change, not a code change
LLM_PROVIDERS = {
    "openai": {
        "class": "langchain_openai.ChatOpenAI",
        "model": "gpt-4o",
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "class": "langchain_anthropic.ChatAnthropic",
        "model": "claude-sonnet-4-20250514",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "gemini": {
        "class": "langchain_google_genai.ChatGoogleGenerativeAI",
        "model": "gemini-2.5-pro",
        "env_key": "GOOGLE_API_KEY",
    },
}
# Selected via: LLM_PROVIDER=openai in .env
```

---

## 5. Docker Compose Topology

```yaml
# docker-compose.yml (simplified view)
services:
  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - rag_pgdata:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d  # schema + extensions
    ports:
      - "${DB_PORT:-5432}:5432"

  rag-api:
    build: ./src
    depends_on: [postgres]
    environment:
      - DATABASE_URL=postgresql://rag:${DB_PASSWORD}@postgres:5432/odyssey_rag
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - EMBEDDING_MODEL=nomic-embed-text
    ports:
      - "${API_PORT:-8080}:8080"
    volumes:
      - ./data/sources:/app/data/sources  # mount source docs for ingestion

  mcp-server:
    build: ./src
    command: ["python", "-m", "odyssey_rag.mcp_server", "--transport", "sse"]
    depends_on: [rag-api]
    environment:
      - RAG_API_URL=http://rag-api:8080
      - MCP_API_KEY=${MCP_API_KEY}
    ports:
      - "${MCP_PORT:-8081}:8081"

volumes:
  rag_pgdata:
```

---

## 6. Repository Structure

```
RAG/
├── IAContext/                # Planning & architecture documentation
│   ├── ARCHITECTURE.md      # This document
│   ├── CONVENTIONS.md       # Code style, naming, commit conventions
│   ├── MCP_TOOLS.md         # Detailed MCP tool specifications
│   ├── DATA_MODEL.md        # PostgreSQL schema, indexes, migrations
│   ├── INGESTION_PIPELINE.md # Parsers, chunkers, embedding pipeline
│   ├── RETRIEVAL_ENGINE.md  # Hybrid search, reranking, response assembly
│   ├── DOCKER_SETUP.md      # Docker compose, networking, volumes, secrets
│   ├── TESTING_STRATEGY.md  # Unit/integration/eval testing approach
│   ├── API_REFERENCE.md     # FastAPI endpoints, request/response schemas
│   ├── EVALUATION_SET.md    # 50+ real questions for quality measurement
│   ├── SECURITY.md          # Auth, secrets management, access control
│   └── PLAN.md              # Master task plan (ordered, with agent assignment)
├── instructions.md          # Original requirements (reference only)
│
├── docker-compose.yml       # Full stack definition
├── .env.example             # Environment variable template
├── Makefile                 # Build/test/run shortcuts
├── .gitignore               # Python + Docker ignores
│
├── db/
│   ├── init/
│   │   ├── 001_extensions.sql   # CREATE EXTENSION pgvector, pg_trgm
│   │   └── 002_schema.sql      # Full schema (documents, chunks, embeddings, ...)
│   └── migrations/              # Incremental schema changes
│
├── src/
│   ├── odyssey_rag/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entrypoint
│   │   ├── config.py            # Settings from env vars
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── search.py    # POST /api/v1/search
│   │   │   │   ├── ingest.py    # POST /api/v1/ingest
│   │   │   │   ├── sources.py   # GET /api/v1/sources
│   │   │   │   ├── chunks.py    # GET /api/v1/chunk/{id}
│   │   │   │   └── health.py    # GET /api/v1/health
│   │   │   ├── schemas/         # Pydantic request/response models
│   │   │   └── dependencies.py  # DI (db session, embedding service, etc.)
│   │   │
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py      # Orchestrates: detect → parse → chunk → embed → store
│   │   │   ├── parsers/
│   │   │   │   ├── base.py          # Abstract parser interface
│   │   │   │   ├── markdown.py      # Markdown (Annex B, CLAUDE.md, tech docs)
│   │   │   │   ├── php_code.py      # PHP source (Bimpay classes/functions)
│   │   │   │   ├── xml_example.py   # XML (IPS message examples)
│   │   │   │   ├── pdf.py           # PDF (future documentation)
│   │   │   │   ├── postman.py       # Postman collections
│   │   │   │   └── generic.py       # Fallback text parser
│   │   │   ├── chunkers/
│   │   │   │   ├── base.py          # Abstract chunker interface
│   │   │   │   ├── markdown.py      # Chunk by heading hierarchy
│   │   │   │   ├── php_code.py      # Chunk by class/function
│   │   │   │   ├── xml_message.py   # Chunk by message section
│   │   │   │   └── semantic.py      # Token-aware with overlap
│   │   │   └── metadata/
│   │   │       ├── extractor.py     # Extract metadata from chunks
│   │   │       └── taxonomy.py      # Source types, message types, field types
│   │   │
│   │   ├── retrieval/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py        # Hybrid search orchestrator
│   │   │   ├── vector_search.py # pgvector cosine similarity
│   │   │   ├── text_search.py   # PostgreSQL full-text (BM25-like)
│   │   │   ├── reranker.py      # Cross-encoder reranking
│   │   │   ├── filters.py       # Metadata filter builder
│   │   │   └── response.py      # Evidence + gaps + followups assembly
│   │   │
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py      # Abstract embedding interface
│   │   │   ├── nomic.py         # nomic-embed-text local
│   │   │   ├── openai.py        # OpenAI embeddings (fallback)
│   │   │   └── cohere.py        # Cohere embeddings (fallback)
│   │   │
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py      # Abstract LLM interface
│   │   │   ├── openai.py        # OpenAI GPT-4o
│   │   │   ├── anthropic.py     # Claude
│   │   │   └── gemini.py        # Google Gemini
│   │   │
│   │   ├── mcp_server/
│   │   │   ├── __init__.py
│   │   │   ├── server.py        # MCP server setup (dual transport)
│   │   │   ├── tools/
│   │   │   │   ├── find_message_type.py
│   │   │   │   ├── find_business_rule.py
│   │   │   │   ├── find_module.py
│   │   │   │   ├── find_error.py
│   │   │   │   ├── search.py
│   │   │   │   └── ingest.py
│   │   │   └── auth.py          # API key validation for HTTP mode
│   │   │
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── session.py       # SQLAlchemy async session
│   │       ├── models.py        # ORM models
│   │       └── repositories/
│   │           ├── chunks.py    # Chunk CRUD + search
│   │           ├── documents.py # Document CRUD
│   │           └── feedback.py  # Feedback storage
│   │
│   ├── Dockerfile
│   ├── pyproject.toml           # Dependencies (poetry/pip)
│   └── requirements.txt         # Pinned deps (fallback)
│
├── tests/
│   ├── conftest.py              # Shared fixtures (test DB, mock embeddings)
│   ├── unit/
│   │   ├── test_parsers/        # One file per parser
│   │   ├── test_chunkers/       # One file per chunker
│   │   ├── test_retrieval/      # Search, rerank, filter tests
│   │   ├── test_embeddings/     # Embedding provider tests
│   │   └── test_mcp_tools/      # MCP tool logic tests
│   ├── integration/
│   │   ├── test_ingestion_pipeline.py
│   │   ├── test_search_flow.py
│   │   ├── test_mcp_server.py
│   │   └── test_api_endpoints.py
│   └── evaluation/
│       ├── eval_questions.json  # 50+ real domain questions
│       ├── eval_runner.py       # Automated evaluation
│       └── eval_metrics.py      # Correctness, faithfulness, citation accuracy
│
├── data/
│   └── sources/                 # Mount point for source documents to ingest
│       ├── README.md            # Instructions for adding sources
│       └── .gitkeep
│
└── scripts/
    ├── seed_initial_sources.py  # Auto-ingest known Odyssey sources
    ├── run_evaluation.py        # Run eval set and report
    └── export_chunks.py         # Debug: export all chunks to JSON
```

---

## 7. Source Types & Metadata Taxonomy

### 7.1 Source Types

| `source_type` | Extensions | Parser | Example Sources |
|---------------|-----------|--------|-----------------|
| `annex_b_spec` | `.md` | MarkdownParser | `IPS_Annex_B_Message_Specifications.md` |
| `tech_doc` | `.md` | MarkdownParser | `BIMPAY_TECHNICAL_DOC.md`, `BIMPAY_INFRASTRUCTURE_DOC.md` |
| `claude_context` | `.md` | MarkdownParser | `CLAUDE.md`, `IA SKILLS/CLAUDE.md` |
| `php_code` | `.php` | PhpCodeParser | `Bimpay/Messages/*.php`, `Bimpay/Validators/*.php` |
| `xml_example` | `.xml` | XmlExampleParser | `IPS Messages Examples/pacs.008/*.xml` |
| `postman_collection` | `.json` | PostmanParser | `BIMPAY POC.postman_collection.json` |
| `pdf_doc` | `.pdf` | PdfParser | Future IPS documentation PDFs |
| `generic_text` | `.txt`, `.md` | GenericTextParser | Fallback for unclassified files |

### 7.2 Metadata Fields

| Field | Type | Indexed | Description |
|-------|------|---------|-------------|
| `source_type` | `varchar(50)` | GIN | One of the source types above |
| `message_type` | `varchar(20)` | btree | ISO message ID: `pacs.008`, `camt.056`, etc. |
| `iso_version` | `varchar(30)` | btree | Full version: `pacs.008.001.12` |
| `module_path` | `varchar(255)` | btree | `Bimpay/Messages/Pacs008CreditTransfer.php` |
| `php_class` | `varchar(100)` | btree | `Pacs008CreditTransfer` |
| `php_symbol` | `varchar(100)` | btree | `toXml`, `validate`, `parse` |
| `field_xpath` | `varchar(255)` | GIN | `GrpHdr/MsgId`, `CdtTrfTxInf/Amt/InstdAmt` |
| `rule_status` | `varchar(1)` | btree | `M`, `O`, `C`, `R` (Annex B) |
| `section` | `varchar(255)` | btree | Document section heading |
| `subsection` | `varchar(255)` | btree | Subsection heading |
| `doc_version` | `varchar(20)` | btree | Version of the source document |
| `is_current` | `boolean` | btree | `true` = active version, `false` = superseded |

---

## 8. Extensibility Design

### 8.1 Adding New Document Types

New integrations or features are added by:

1. **Drop files** into `data/sources/` (or call `POST /api/v1/ingest`)
2. **Register a parser** if the file type is new (implement `BaseParser`)
3. **Register a chunker** if the content structure is unique (implement `BaseChunker`)
4. The ingestion pipeline auto-detects source type and routes accordingly

### 8.2 Adding New MCP Tools

New tools for future integrations follow the pattern:

1. Create `src/odyssey_rag/mcp_server/tools/new_tool.py`
2. Implement the tool function with typed input/output schemas
3. Register in `server.py`
4. Add tests in `tests/unit/test_mcp_tools/`

### 8.3 Adding New LLM/Embedding Providers

Providers implement the abstract interface:

```python
class BaseEmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    
    @abstractmethod
    def dimension(self) -> int: ...
```

New provider = new file in `embeddings/` + config entry. Zero changes to existing code.

---

## 9. Network & Security Model

```
┌───────────────────────────────────────────────┐
│           Docker Compose Network (rag_net)     │
│                                               │
│  postgres:5432 ◄──── rag-api:8080 ◄──── mcp-server:8081
│       │                    │                   │
│  (internal only       (internal +          (exposed:
│   unless debug)        optional expose)     main entry)
└───────────────────────────────────────────────┘

External access:
  - MCP clients → :8081 (HTTP/SSE + API key)
  - stdio mode  → direct process invocation (no network)
  - API debug   → :8080 (optional, disabled in prod)
  - DB debug    → :5432 (optional, disabled in prod)
```

**Auth**: API key in `MCP_API_KEY` env var. HTTP requests require `Authorization: Bearer <key>`. stdio mode is inherently local (no auth needed).

---

## 10. Revision & Quality Gates

| Checkpoint | Agent | Trigger |
|-----------|-------|---------|
| **Task execution** | Sonnet 4.6 | Every task in PLAN.md |
| **Phase review** | Opus 4.6 | After every 5-8 completed tasks |
| **Security review** | Opus 4.6 | After auth, secrets, and DB access implemented |
| **Architecture review** | Opus 4.6 | After core pipeline (ingest + retrieve) working |
| **Final review** | Opus 4.6 | Before v1.0 release |

Reviews check: code coherence with ARCHITECTURE.md, test coverage, security posture, convention compliance, and task plan accuracy.
