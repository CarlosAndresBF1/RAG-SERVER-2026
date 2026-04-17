# Odyssey RAG — Conventions & Standards

> **Version**: 1.0.0  
> **Date**: 2026-03-02  
> **Status**: Planning  
> **Applies to**: All code in the `RAG/` monorepo

---

## 1. Language & Runtime

| Item | Standard |
|------|----------|
| **Python version** | 3.11+ (type hints, `match` statements, `asyncio` improvements) |
| **Package manager** | `pip` with `pyproject.toml` (PEP 621). `requirements.txt` as pinned lockfile |
| **Virtual env** | Managed inside Docker. Local dev via `python -m venv .venv` |
| **Async** | All I/O-bound code is `async/await`. FastAPI routes are async |

---

## 2. Code Style

### 2.1 Formatting & Linting

| Tool | Purpose | Config |
|------|---------|--------|
| **ruff** | Linting + formatting (replaces flake8, isort, black) | `pyproject.toml` `[tool.ruff]` |
| **mypy** | Static type checking | `pyproject.toml` `[tool.mypy]` (strict mode) |

```toml
# pyproject.toml
[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "DTZ", "T20", "RET", "SIM"]
ignore = ["S101"]  # Allow assert in tests

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.ruff.isort]
known-first-party = ["odyssey_rag"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

### 2.2 Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| **Modules/files** | `snake_case.py` | `vector_search.py`, `php_code.py` |
| **Classes** | `PascalCase` | `PhpCodeParser`, `VectorSearchEngine` |
| **Functions/methods** | `snake_case` | `embed_chunks()`, `find_message_type()` |
| **Constants** | `UPPER_SNAKE_CASE` | `DEFAULT_CHUNK_SIZE`, `EMBEDDING_DIMENSION` |
| **Type aliases** | `PascalCase` | `ChunkList = list[Chunk]` |
| **Env vars** | `UPPER_SNAKE_CASE` | `DATABASE_URL`, `LLM_PROVIDER` |
| **API routes** | `lowercase-kebab` | `/api/v1/search`, `/api/v1/chunk/{id}` |
| **DB tables** | `snake_case` (singular) | `document`, `chunk`, `embedding` |
| **DB columns** | `snake_case` | `source_type`, `message_type`, `created_at` |
| **MCP tool names** | `namespace.verb_noun` | `odyssey_rag.find_message_type` |

### 2.3 Docstrings

All public classes, methods, and functions must have docstrings.

```python
def find_message_type(
    message_type: str,
    *,
    sources: list[SourceType] | None = None,
    top_k: int = 8,
) -> SearchResult:
    """Retrieve evidence for an ISO 20022 message type.

    Searches indexed sources (Annex B spec, PHP builders/parsers/validators,
    XML examples) filtered by message type identifier.

    Args:
        message_type: ISO message ID, e.g. 'pacs.008', 'camt.056'.
        sources: Restrict search to specific source types. None = all.
        top_k: Maximum number of evidence chunks to return.

    Returns:
        SearchResult containing evidence[], gaps[], and followups[].

    Raises:
        ValueError: If message_type is not a recognized ISO 20022 type.
    """
```

### 2.4 Type Hints

- **All** function signatures must have complete type annotations
- Use `from __future__ import annotations` in every module
- Prefer `list[str]` over `List[str]` (PEP 585)
- Use `X | None` over `Optional[X]` (PEP 604)
- Use `TypeAlias` for complex types

```python
from __future__ import annotations

from typing import TypeAlias

EvidenceList: TypeAlias = list[Evidence]
MetadataDict: TypeAlias = dict[str, str | int | bool | None]
```

---

## 3. Project Structure Conventions

### 3.1 Module Organization

```
src/odyssey_rag/
├── api/           # HTTP layer only (routes, schemas, deps)
├── ingestion/     # Offline pipeline (parse, chunk, embed, store)
├── retrieval/     # Online pipeline (search, rerank, assemble)
├── embeddings/    # Embedding providers (nomic, openai, cohere)
├── llm/           # LLM providers (openai, anthropic, gemini)
├── mcp_server/    # MCP protocol layer (tools, auth, transport)
├── db/            # Database models, sessions, repositories
├── config.py      # Centralized settings (pydantic-settings)
└── main.py        # FastAPI app factory
```

### 3.2 Import Order (enforced by ruff)

1. Standard library
2. Third-party packages
3. First-party (`odyssey_rag`)
4. Local (relative imports within same package)

### 3.3 Dependency Injection

Use FastAPI's `Depends()` for all service dependencies:

```python
# api/dependencies.py
async def get_db_session() -> AsyncGenerator[AsyncSession, None]: ...
async def get_embedding_service() -> EmbeddingProvider: ...
async def get_retrieval_engine(
    session: AsyncSession = Depends(get_db_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_service),
) -> RetrievalEngine: ...
```

---

## 4. Configuration Management

### 4.1 Environment Variables

All config via env vars (12-factor). Centralized in `config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/odyssey_rag"
    
    # Embeddings
    embedding_provider: str = "nomic"  # nomic | openai | cohere
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768
    
    # LLM
    llm_provider: str = "openai"  # openai | anthropic | gemini
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    
    # MCP
    mcp_api_key: str = ""
    mcp_transport: str = "sse"  # stdio | sse
    mcp_port: int = 8081
    
    # Search
    default_top_k: int = 8
    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # Ingestion
    chunk_size: int = 512  # tokens
    chunk_overlap: int = 64  # tokens
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

### 4.2 .env.example Template

Every env var used must be documented in `.env.example` with defaults and descriptions:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://rag:changeme@localhost:5432/odyssey_rag
DB_PORT=5432

# LLM Provider (openai | anthropic | gemini)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...

# Embedding (nomic runs local, no key needed)
EMBEDDING_PROVIDER=nomic

# MCP Server
MCP_API_KEY=your-api-key-here
MCP_PORT=8081

# API
API_PORT=8080
```

---

## 5. Database Conventions

### 5.1 Schema Standards

- All tables have `id` (UUID v4, primary key), `created_at`, `updated_at`
- Use `TIMESTAMPTZ` for all timestamps (UTC)
- Foreign keys with `ON DELETE CASCADE` where ownership is clear
- Indexes: every column used in `WHERE`, `JOIN`, or `ORDER BY`
- `vector` columns use `pgvector` type with explicit dimension

### 5.2 Migrations

- Schema changes via numbered SQL files: `db/migrations/003_add_feedback_table.sql`
- Each migration file is idempotent (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`)
- Never modify a deployed migration. Always create a new one

### 5.3 Naming

| SQL Element | Convention | Example |
|-------------|-----------|---------|
| Tables | singular `snake_case` | `document`, `chunk`, `embedding` |
| Columns | `snake_case` | `source_type`, `created_at` |
| Indexes | `idx_{table}_{columns}` | `idx_chunk_message_type` |
| Constraints | `fk_{table}_{ref}`, `uq_{table}_{cols}` | `fk_chunk_document` |

---

## 6. API Conventions

### 6.1 URL Structure

```
/api/v1/{resource}          # Collection
/api/v1/{resource}/{id}     # Single item
/api/v1/search              # Action endpoints (verb)
/api/v1/ingest              # Action endpoints (verb)
/api/v1/health              # System endpoints
```

### 6.2 Request/Response Format

- All responses are JSON
- Success responses: `{"data": ..., "meta": {...}}`
- Error responses: `{"error": {"code": "...", "message": "...", "details": [...]}}`
- Pagination: `{"data": [...], "meta": {"total": 100, "offset": 0, "limit": 20}}`

### 6.3 HTTP Status Codes

| Code | Usage |
|------|-------|
| 200 | Successful retrieval/search |
| 201 | Document ingested successfully |
| 400 | Invalid input (bad query, unknown source type) |
| 401 | Missing/invalid API key |
| 404 | Chunk/document not found |
| 422 | Validation error (Pydantic) |
| 500 | Internal error |

---

## 7. Testing Conventions

### 7.1 Test File Structure

| Source file | Test file |
|------------|-----------|
| `src/odyssey_rag/ingestion/parsers/markdown.py` | `tests/unit/test_parsers/test_markdown.py` |
| `src/odyssey_rag/retrieval/engine.py` | `tests/unit/test_retrieval/test_engine.py` |
| `src/odyssey_rag/mcp_server/tools/find_message_type.py` | `tests/unit/test_mcp_tools/test_find_message_type.py` |

### 7.2 Test Naming

```python
# Pattern: test_{action}_{scenario}_{expected_result}
def test_parse_markdown_with_headings_returns_sections():
def test_search_pacs008_returns_builder_and_spec_evidence():
def test_find_error_with_unknown_code_returns_gaps():
def test_ingest_pdf_with_tables_preserves_structure():
```

### 7.3 Fixtures & Mocks

- Shared fixtures in `tests/conftest.py`
- Database tests use a test PostgreSQL instance (Docker-based)
- Embedding tests mock the embedding model (deterministic vectors)
- MCP tool tests mock the RAG API responses

### 7.4 Coverage Target

| Category | Target |
|----------|--------|
| Unit tests | ≥ 85% line coverage |
| Integration tests | All API endpoints + MCP tools covered |
| Evaluation tests | 50+ domain questions, measured metrics |

---

## 8. Git & Commit Conventions

### 8.1 Branch Naming

```
main                          # Stable, reviewed
feat/{short-description}      # New feature
fix/{short-description}       # Bug fix
docs/{short-description}      # Documentation only
refactor/{short-description}  # Code restructuring
test/{short-description}      # Test additions
```

### 8.2 Commit Messages

Follow Conventional Commits:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`

Scopes: `ingestion`, `retrieval`, `mcp`, `api`, `db`, `docker`, `config`, `eval`

Examples:
```
feat(ingestion): add PHP code parser with class/function chunking
fix(retrieval): handle empty BM25 results in hybrid merge
test(mcp): add integration tests for find_message_type tool
docs(architecture): update data flow diagram with reranker step
chore(docker): pin pgvector image to 0.7.4
```

### 8.3 Agent Task Commits

When Sonnet executes a task from PLAN.md, the commit message must reference the task:

```
feat(ingestion): implement markdown parser [TASK-012]

Implements heading-based chunking for Annex B and technical docs.
Preserves section hierarchy in metadata.

Refs: PLAN.md task 012
```

---

## 9. Documentation Conventions

### 9.1 Inline Documentation

- Every module has a module-level docstring explaining its purpose
- Every public class/function has a docstring (Google style)
- Complex algorithms have inline comments explaining "why", not "what"

### 9.2 Architecture Decision Records (ADRs)

Significant decisions documented as comments in the relevant doc:

```markdown
<!-- ADR: Chose nomic-embed over OpenAI embeddings
     Date: 2026-03-02
     Reason: Zero API cost, runs local in Docker, 768-dim, 8K context
     Tradeoff: Slightly lower quality on non-English text
     Alternatives: OpenAI text-embedding-3-small (better quality, API cost)
-->
```

---

## 10. Error Handling

### 10.1 Exception Hierarchy

```python
class OdysseyRagError(Exception):
    """Base exception for all RAG errors."""

class IngestionError(OdysseyRagError):
    """Failed to ingest/parse a document."""

class RetrievalError(OdysseyRagError):
    """Failed to execute search/retrieval."""

class EmbeddingError(OdysseyRagError):
    """Failed to generate embeddings."""

class ConfigError(OdysseyRagError):
    """Invalid or missing configuration."""
```

### 10.2 Rules

- Never catch bare `Exception` (except at API boundary)
- Always log the full traceback at `error` level
- API routes translate exceptions to proper HTTP status codes via FastAPI exception handlers
- MCP tools return errors in `gaps[]` field, never raise to the client

---

## 11. Logging

### 11.1 Format

```python
import structlog

logger = structlog.get_logger(__name__)

# Usage
logger.info("ingestion.started", source_type="pdf_doc", file="annex_b.pdf")
logger.error("retrieval.failed", query=query, error=str(e))
```

### 11.2 Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Chunk details, embedding vectors (dev only) |
| `INFO` | Ingestion events, search queries, MCP tool calls |
| `WARNING` | Degraded service (fallback to different provider) |
| `ERROR` | Failed operations (parse error, DB connection lost) |

---

## 12. Makefile Targets

The project Makefile follows Odyssey's pattern:

```makefile
# Build
build:           # Build all Docker images
dev:             # Start with hot-reload + exposed ports

# Run
up:              # docker compose up -d
down:            # docker compose down
logs:            # docker compose logs -f

# Test
test:            # Run all tests in Docker
test-unit:       # Unit tests only
test-integration:# Integration tests only
test-eval:       # Run evaluation set

# Quality
lint:            # ruff check + mypy
format:          # ruff format
check:           # lint + test (CI gate)

# Data
seed:            # Ingest initial Odyssey sources
reset-db:        # Drop and recreate database

# Utilities
shell:           # Interactive shell in rag-api container
db-shell:        # psql into PostgreSQL
```
