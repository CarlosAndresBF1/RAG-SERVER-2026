# Odyssey RAG — API Reference

> **Version**: 1.1.0  
> **Date**: 2026-03-15  
> **Status**: Implemented  
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md) §3.2, [CONVENTIONS.md](CONVENTIONS.md) §5

---

## 1. Base Configuration

| Setting | Value |
|---------|-------|
| Base URL | `http://localhost:8080` (Docker internal) / `http://localhost:8089` (host) |
| API Prefix | `/api/v1` |
| Docs | `http://localhost:8080/docs` (Swagger UI) |
| ReDoc | `http://localhost:8080/redoc` |
| Content-Type | `application/json` |
| Auth | API Key via `X-API-Key` header (optional in dev) |

---

## 2. Endpoints

### 2.1 Health Check

```
GET /health
```

**Response** `200 OK`:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "database": "ok",
    "embedding_model": "ok",
    "reranker": "ok"
  }
}
```

**Response** `503 Service Unavailable`:
```json
{
  "status": "degraded",
  "version": "0.1.0",
  "services": {
    "database": "ok",
    "embedding_model": "error",
    "reranker": "ok"
  }
}
```

---

### 2.2 Search

```
POST /api/v1/search
```

**Request Body**:
```json
{
  "query": "pacs.008 group header fields",
  "message_type": "pacs.008",
  "source_type": "annex_b_spec",
  "focus": "fields",
  "top_k": 10
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | yes | — | Search query text |
| `message_type` | string | no | null | ISO message type filter (e.g. `pacs.008`) |
| `source_type` | string | no | null | Source type filter (e.g. `annex_b_spec`, `php_code`) |
| `focus` | string | no | null | Focus area: `overview`, `fields`, `builder`, `parser`, `validator`, `examples`, `envelope` |
| `top_k` | integer | no | 10 | Number of results (1-20) |

**Response** `200 OK`:
```json
{
  "query": "pacs.008 group header fields",
  "evidence": [
    {
      "text": "## pacs.008 > ### Group Header\n\n| XPath | Tag | Mult | Status...",
      "relevance": 0.92,
      "citations": [
        {
          "source_path": "md/IPS_Annex_B_Message_Specifications.md",
          "section": "pacs.008.001.12",
          "chunk_index": 3
        }
      ],
      "message_type": "pacs.008",
      "source_type": "annex_b_spec"
    }
  ],
  "gaps": [],
  "followups": [
    "Find business rules for pacs.008",
    "Find PHP module implementing pacs.008"
  ],
  "metadata": {
    "total_candidates": 45,
    "search_time_ms": 320
  }
}
```

**Response** `400 Bad Request`:
```json
{
  "detail": "query must not be empty"
}
```

---

### 2.3 Ingest

```
POST /api/v1/ingest
```

**Request Body**:
```json
{
  "source_path": "/app/sources/md/IPS_Annex_B_Message_Specifications.md",
  "source_type": "annex_b_spec",
  "metadata_overrides": {
    "message_type": "pacs.008"
  },
  "replace_existing": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `source_path` | string | yes | — | Absolute path to file (within container) |
| `source_type` | string | no | auto-detect | Override source type detection |
| `metadata_overrides` | object | no | null | Force specific metadata on all chunks |
| `replace_existing` | boolean | no | false | Delete existing version before ingesting |

**Response** `200 OK`:
```json
{
  "status": "completed",
  "document_id": 42,
  "source_path": "/app/sources/md/IPS_Annex_B_Message_Specifications.md",
  "source_type": "annex_b_spec",
  "chunks_created": 87,
  "file_hash": "a1b2c3d4...",
  "duration_ms": 4500
}
```

**Response** `200 OK` (skipped):
```json
{
  "status": "skipped",
  "reason": "unchanged",
  "source_path": "/app/sources/md/IPS_Annex_B_Message_Specifications.md",
  "file_hash": "a1b2c3d4..."
}
```

**Response** `200 OK` (failed):
```json
{
  "status": "failed",
  "error": "Parse error: invalid XML at line 42",
  "source_path": "/app/sources/bad_file.xml"
}
```

---

### 2.4 Batch Ingest

```
POST /api/v1/ingest/batch
```

**Request Body**:
```json
{
  "sources": [
    {"source_path": "/app/sources/Bimpay/Messages/Pacs008CreditTransfer.php"},
    {"source_path": "/app/sources/Bimpay/Messages/Camt056RecallMessage.php"},
    {"source_path": "/app/sources/md/IPS_Annex_B_Message_Specifications.md", "source_type": "annex_b_spec"}
  ],
  "replace_existing": false
}
```

**Response** `200 OK`:
```json
{
  "total": 3,
  "completed": 2,
  "skipped": 1,
  "failed": 0,
  "results": [
    {"source_path": "...Pacs008CreditTransfer.php", "status": "completed", "chunks_created": 8},
    {"source_path": "...Camt056RecallMessage.php", "status": "completed", "chunks_created": 6},
    {"source_path": "...IPS_Annex_B.md", "status": "skipped", "reason": "unchanged"}
  ],
  "duration_ms": 12000
}
```

---

### 2.5 List Sources

```
GET /api/v1/sources
```

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `source_type` | string | null | Filter by source type |
| `is_current` | boolean | true | Show active versions only |
| `page` | integer | 1 | Page number |
| `page_size` | integer | 50 | Items per page |

**Response** `200 OK`:
```json
{
  "items": [
    {
      "id": 1,
      "source_path": "md/IPS_Annex_B_Message_Specifications.md",
      "source_type": "annex_b_spec",
      "file_hash": "a1b2c3d4...",
      "total_chunks": 87,
      "is_current": true,
      "ingested_at": "2026-03-02T10:30:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 50
}
```

---

### 2.6 Get Source Detail

```
GET /api/v1/sources/{document_id}
```

**Response** `200 OK`:
```json
{
  "id": 1,
  "source_path": "md/IPS_Annex_B_Message_Specifications.md",
  "source_type": "annex_b_spec",
  "file_hash": "a1b2c3d4...",
  "total_chunks": 87,
  "is_current": true,
  "ingested_at": "2026-03-02T10:30:00Z",
  "chunks": [
    {
      "id": 101,
      "chunk_index": 0,
      "content": "## pacs.008.001.12\n\n...",
      "token_count": 340,
      "section": "pacs.008.001.12",
      "subsection": null,
      "metadata": {
        "message_type": "pacs.008",
        "iso_version": "pacs.008.001.12",
        "source_type": "annex_b_spec"
      }
    }
  ]
}
```

---

### 2.7 Delete Source

```
DELETE /api/v1/sources/{document_id}
```

**Response** `200 OK`:
```json
{
  "deleted": true,
  "document_id": 1,
  "chunks_deleted": 87
}
```

---

### 2.8 Get Chunks

```
GET /api/v1/chunks
```

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `document_id` | integer | null | Filter by document |
| `message_type` | string | null | Filter by ISO message type |
| `source_type` | string | null | Filter by source type |
| `section` | string | null | Filter by section name |
| `page` | integer | 1 | Page number |
| `page_size` | integer | 50 | Items per page |

---

### 2.9 Feedback

```
POST /api/v1/feedback
```

**Request Body**:
```json
{
  "query": "pacs.008 group header fields",
  "chunk_id": 101,
  "rating": 1,
  "comment": "Exactly what I needed"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | The original query |
| `chunk_id` | integer | yes | The chunk being rated |
| `rating` | integer | yes | -1 (bad), 0 (neutral), 1 (good) |
| `comment` | string | no | Free-text feedback |

---

### 2.10 Stats — Feedback (Expanded)

```
GET /api/v1/stats/feedback
```

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | integer | 1 | Page for per-query rows |
| `page_size` | integer | 20 | Rows per page |

**Response** `200 OK`:
```json
{
  "total_feedback": 89,
  "positive_pct": 76.4,
  "negative_pct": 15.7,
  "neutral_pct": 7.9,
  "trend": [
    {"date": "2026-03-14", "count": 12, "avg_rating": 0.67}
  ],
  "rows": [
    {"query": "pacs.008 fields", "rating": 1, "tool_name": "find_message_type", "created_at": "...", "chunk_count": 5}
  ],
  "page": 1,
  "page_size": 20
}
```

---

### 2.11 Stats — Database

```
GET /api/v1/stats/db
```

**Response** `200 OK`:
```json
{
  "database_size": "22 MB",
  "row_counts": {"document": 137, "chunk": 1255, "feedback": 89},
  "table_sizes": {"chunk": "15 MB", "document": "2 MB"}
}
```

---

### 2.12 Jobs List

```
GET /api/v1/jobs
```

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Items per page |
| `status` | string | null | Filter: `pending`, `running`, `completed`, `failed` |

---

### 2.13 Admin Users

```
GET /api/v1/admin/users
POST /api/v1/admin/users
DELETE /api/v1/admin/users/{id}
```

**POST Body**:
```json
{
  "email": "dev@odyssey.local",
  "password": "securepass",
  "display_name": "Developer",
  "role": "admin"
}
```

---

### 2.14 Audit Log

```
GET /api/v1/audit
```

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `page_size` | integer | 50 | Items per page |
| `action` | string | null | Filter by action type |

---

### 2.15 Auth Verify

```
POST /api/v1/auth/verify
```

**Request Body**:
```json
{
  "email": "admin@odyssey.local",
  "password": "admin"
}
```

**Response** `200 OK`:
```json
{
  "id": "uuid",
  "email": "admin@odyssey.local",
  "display_name": "Admin",
  "role": "admin"
}
```

---

### 2.16 MCP Tokens

```
GET /api/v1/tokens
POST /api/v1/tokens
DELETE /api/v1/tokens/{id}
GET /api/v1/tokens/{id}/audit
```

---

### 2.17 File Upload

```
POST /api/v1/upload
```

Multipart file upload. File is saved to `data/sources/` and can be ingested.

---

## 3. Pydantic Schemas

```python
# api/schemas.py

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    message_type: str | None = Field(None, pattern=r"^(pacs|camt|pain|acmt)\.\d{3}$")
    source_type: str | None = None
    focus: str | None = Field(None, pattern=r"^(overview|fields|builder|parser|validator|examples|envelope)$")
    top_k: int = Field(10, ge=1, le=20)

class Citation(BaseModel):
    source_path: str
    section: str | None
    chunk_index: int

class EvidenceItem(BaseModel):
    text: str
    relevance: float = Field(..., ge=0.0, le=1.0)
    citations: list[Citation]
    message_type: str | None
    source_type: str

class SearchResponse(BaseModel):
    query: str
    evidence: list[EvidenceItem]
    gaps: list[str]
    followups: list[str]
    metadata: dict[str, int | float]

class IngestRequest(BaseModel):
    source_path: str = Field(..., min_length=1)
    source_type: str | None = None
    metadata_overrides: dict[str, str] | None = None
    replace_existing: bool = False

class IngestResponse(BaseModel):
    status: str  # completed | skipped | failed
    document_id: int | None = None
    source_path: str
    source_type: str | None = None
    chunks_created: int | None = None
    file_hash: str | None = None
    duration_ms: int | None = None
    reason: str | None = None
    error: str | None = None

class FeedbackRequest(BaseModel):
    query: str
    chunk_id: int
    rating: int = Field(..., ge=-1, le=1)
    comment: str | None = None
```

---

## 4. Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message",
  "error_code": "VALIDATION_ERROR",
  "context": {}
}
```

| HTTP Status | Error Code | When |
|-------------|-----------|------|
| 400 | `VALIDATION_ERROR` | Invalid request body or params |
| 404 | `NOT_FOUND` | Document/chunk not found |
| 409 | `CONFLICT` | Duplicate ingest with `replace_existing=false` |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `SERVICE_UNAVAILABLE` | Embedding model or DB down |

---

## 5. FastAPI App Structure

```python
# api/main.py
from fastapi import FastAPI
from odyssey_rag.api.routes import search, ingest, sources, chunks, feedback

app = FastAPI(
    title="Odyssey RAG API",
    version="0.1.0",
    description="RAG system for Odyssey project knowledge — ISO 20022 / Bimpay domain",
)

app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
app.include_router(sources.router, prefix="/api/v1", tags=["sources"])
app.include_router(chunks.router, prefix="/api/v1", tags=["chunks"])
app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])

@app.get("/health")
async def health():
    ...
```
