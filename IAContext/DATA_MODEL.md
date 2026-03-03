# Odyssey RAG — Data Model

> **Version**: 1.0.0  
> **Date**: 2026-03-02  
> **Status**: Planning  
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md) §2.4, §7

---

## 1. Overview

All data lives in a single **PostgreSQL 16 + pgvector** instance. The schema supports:

- Document and chunk storage with hierarchical metadata
- Vector embeddings for semantic search (pgvector)
- Full-text search indexes for keyword/BM25-like retrieval (tsvector + pg_trgm)
- Ingestion job tracking
- User feedback collection for quality improvement

---

## 2. Extensions Required

```sql
-- db/init/001_extensions.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pgvector";         -- Vector similarity search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";          -- Trigram text similarity
```

---

## 3. Schema Diagram (Entity Relationship)

```
┌─────────────────────┐          ┌──────────────────────────────┐
│     document         │          │          chunk                │
├─────────────────────┤          ├──────────────────────────────┤
│ id (PK, UUID)        │ 1────*  │ id (PK, UUID)                │
│ source_path          │          │ document_id (FK → document)  │
│ source_type          │          │ content (TEXT)               │
│ file_hash (SHA-256)  │          │ token_count (INT)            │
│ doc_version          │          │ chunk_index (INT)            │
│ integration          │          │ section (VARCHAR)            │
│ is_current           │          │ subsection (VARCHAR)         │
│ metadata_json        │          │ metadata_json (JSONB)        │
│ total_chunks         │          │ tsvector_content (TSVECTOR)  │
│ created_at           │          │ created_at                   │
│ updated_at           │          │ updated_at                   │
└─────────────────────┘          └──────────┬───────────────────┘
                                             │ 1
                                             │
                                             │ 1
                                 ┌───────────┴──────────────────┐
                                 │        chunk_embedding        │
                                 ├──────────────────────────────┤
                                 │ id (PK, UUID)                │
                                 │ chunk_id (FK → chunk, UNIQUE)│
                                 │ embedding (VECTOR(768))      │
                                 │ model_name (VARCHAR)         │
                                 │ created_at                   │
                                 └──────────────────────────────┘

┌─────────────────────┐          ┌──────────────────────────────┐
│    chunk_metadata    │          │        ingest_job            │
├─────────────────────┤          ├──────────────────────────────┤
│ id (PK, UUID)        │          │ id (PK, UUID)                │
│ chunk_id (FK→chunk)  │          │ source_path (VARCHAR)        │
│ message_type         │          │ source_type (VARCHAR)        │
│ iso_version          │          │ status (VARCHAR)             │
│ module_path          │          │ chunks_created (INT)         │
│ php_class            │          │ error_message (TEXT)         │
│ php_symbol           │          │ started_at (TIMESTAMPTZ)     │
│ field_xpath          │          │ completed_at (TIMESTAMPTZ)   │
│ rule_status          │          │ created_at                   │
│ data_type            │          └──────────────────────────────┘
│ source_type          │
│ created_at           │          ┌──────────────────────────────┐
└─────────────────────┘          │        feedback              │
                                 ├──────────────────────────────┤
                                 │ id (PK, UUID)                │
                                 │ query (TEXT)                 │
                                 │ chunk_ids (UUID[])           │
                                 │ response_text (TEXT)         │
                                 │ tool_name (VARCHAR)          │
                                 │ rating (SMALLINT) -1/0/1    │
                                 │ comment (TEXT)               │
                                 │ created_at                   │
                                 └──────────────────────────────┘
```

---

## 4. Full Schema DDL

### 4.1 `document` — Indexed source files

```sql
-- db/init/002_schema.sql

CREATE TABLE IF NOT EXISTS document (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_path     VARCHAR(500)  NOT NULL,           -- Original file path
    source_type     VARCHAR(50)   NOT NULL,           -- annex_b_spec, php_code, xml_example, etc.
    file_hash       VARCHAR(64)   NOT NULL,           -- SHA-256 of file content (dedup/change detect)
    doc_version     VARCHAR(20),                       -- Document version (e.g. "1.0", "v3")
    integration     VARCHAR(100)  DEFAULT 'bimpay',   -- Integration name (bimpay, future ones)
    is_current      BOOLEAN       DEFAULT TRUE,       -- Active version flag
    metadata_json   JSONB         DEFAULT '{}',       -- Additional unstructured metadata
    total_chunks    INTEGER       DEFAULT 0,          -- Count of chunks for this doc
    created_at      TIMESTAMPTZ   DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   DEFAULT NOW(),
    
    CONSTRAINT uq_document_path_hash UNIQUE (source_path, file_hash)
);

CREATE INDEX idx_document_source_type  ON document (source_type);
CREATE INDEX idx_document_integration  ON document (integration);
CREATE INDEX idx_document_is_current   ON document (is_current) WHERE is_current = TRUE;
CREATE INDEX idx_document_file_hash    ON document (file_hash);
```

### 4.2 `chunk` — Text fragments with full-text search

```sql
CREATE TABLE IF NOT EXISTS chunk (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id       UUID          NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    content           TEXT          NOT NULL,           -- The actual chunk text
    token_count       INTEGER       NOT NULL DEFAULT 0, -- Approximate token count
    chunk_index       INTEGER       NOT NULL DEFAULT 0, -- Position within document
    section           VARCHAR(255),                      -- Top-level heading
    subsection        VARCHAR(255),                      -- Sub-heading
    metadata_json     JSONB         DEFAULT '{}',       -- Flexible extra metadata
    tsvector_content  TSVECTOR,                          -- Pre-computed full-text search vector
    created_at        TIMESTAMPTZ   DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX idx_chunk_document_id      ON chunk (document_id);
CREATE INDEX idx_chunk_section          ON chunk (section);
CREATE INDEX idx_chunk_tsvector         ON chunk USING GIN (tsvector_content);
CREATE INDEX idx_chunk_metadata_json    ON chunk USING GIN (metadata_json);

-- Auto-update tsvector on insert/update
CREATE OR REPLACE FUNCTION chunk_tsvector_trigger() RETURNS trigger AS $$
BEGIN
    NEW.tsvector_content := 
        setweight(to_tsvector('english', COALESCE(NEW.section, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.subsection, '')), 'B') ||
        setweight(to_tsvector('english', NEW.content), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_chunk_tsvector
    BEFORE INSERT OR UPDATE OF content, section, subsection
    ON chunk
    FOR EACH ROW
    EXECUTE FUNCTION chunk_tsvector_trigger();
```

### 4.3 `chunk_embedding` — Vector embeddings (1:1 with chunk)

```sql
CREATE TABLE IF NOT EXISTS chunk_embedding (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id    UUID         NOT NULL REFERENCES chunk(id) ON DELETE CASCADE,
    embedding   VECTOR(768)  NOT NULL,   -- nomic-embed-text dimension
    model_name  VARCHAR(100) NOT NULL DEFAULT 'nomic-embed-text-v1.5',
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    
    CONSTRAINT uq_chunk_embedding_chunk UNIQUE (chunk_id)
);

-- HNSW index for fast approximate nearest neighbor search
-- ef_construction=128 and m=16 are good defaults for ~100K chunks
CREATE INDEX idx_chunk_embedding_vector 
    ON chunk_embedding 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);
```

### 4.4 `chunk_metadata` — Structured metadata for filtering

```sql
CREATE TABLE IF NOT EXISTS chunk_metadata (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id      UUID         NOT NULL REFERENCES chunk(id) ON DELETE CASCADE,
    
    -- ISO 20022 domain fields
    message_type  VARCHAR(20),           -- pacs.008, camt.056, pain.013, etc.
    iso_version   VARCHAR(30),           -- pacs.008.001.12
    field_xpath   VARCHAR(255),          -- GrpHdr/MsgId, CdtTrfTxInf/Amt/InstdAmt
    rule_status   VARCHAR(1),            -- M, O, C, R
    data_type     VARCHAR(50),           -- Max35Text, ISODateTime, BIC, Amount
    
    -- Odyssey code domain
    module_path   VARCHAR(255),          -- Bimpay/Messages/Pacs008CreditTransfer.php
    php_class     VARCHAR(100),          -- Pacs008CreditTransfer
    php_symbol    VARCHAR(100),          -- toXml, validate, parse
    
    -- Source classification
    source_type   VARCHAR(50) NOT NULL,  -- annex_b_spec, php_code, xml_example, etc.
    
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cm_chunk_id      ON chunk_metadata (chunk_id);
CREATE INDEX idx_cm_message_type  ON chunk_metadata (message_type);
CREATE INDEX idx_cm_iso_version   ON chunk_metadata (iso_version);
CREATE INDEX idx_cm_source_type   ON chunk_metadata (source_type);
CREATE INDEX idx_cm_rule_status   ON chunk_metadata (rule_status);
CREATE INDEX idx_cm_php_class     ON chunk_metadata (php_class);
CREATE INDEX idx_cm_module_path   ON chunk_metadata (module_path);
CREATE INDEX idx_cm_field_xpath   ON chunk_metadata USING GIN (field_xpath gin_trgm_ops);
```

### 4.5 `ingest_job` — Ingestion tracking

```sql
CREATE TABLE IF NOT EXISTS ingest_job (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_path     VARCHAR(500)  NOT NULL,
    source_type     VARCHAR(50)   NOT NULL,
    status          VARCHAR(20)   NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    chunks_created  INTEGER       DEFAULT 0,
    error_message   TEXT,
    metadata_json   JSONB         DEFAULT '{}',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX idx_ingest_job_status     ON ingest_job (status);
CREATE INDEX idx_ingest_job_created_at ON ingest_job (created_at DESC);
```

### 4.6 `feedback` — User/agent feedback for quality improvement

```sql
CREATE TABLE IF NOT EXISTS feedback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query           TEXT          NOT NULL,          -- The original user query
    chunk_ids       UUID[]        NOT NULL,          -- Which chunks were used
    response_text   TEXT,                             -- Generated response (if applicable)
    tool_name       VARCHAR(100),                     -- MCP tool that was called
    rating          SMALLINT      CHECK (rating BETWEEN -1 AND 1),  -- -1=bad, 0=neutral, 1=good
    comment         TEXT,                             -- Free-text feedback
    created_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX idx_feedback_rating    ON feedback (rating);
CREATE INDEX idx_feedback_tool      ON feedback (tool_name);
CREATE INDEX idx_feedback_created   ON feedback (created_at DESC);
```

---

## 5. Key Queries

### 5.1 Vector Similarity Search (Semantic)

```sql
-- Find top-K chunks most similar to a query embedding
SELECT 
    c.id,
    c.content,
    c.section,
    c.subsection,
    cm.message_type,
    cm.source_type,
    1 - (ce.embedding <=> $1::vector) AS similarity_score
FROM chunk_embedding ce
JOIN chunk c ON c.id = ce.chunk_id
JOIN chunk_metadata cm ON cm.chunk_id = c.id
JOIN document d ON d.id = c.document_id
WHERE d.is_current = TRUE
  AND ($2::varchar IS NULL OR cm.message_type = $2)      -- optional filter
  AND ($3::varchar IS NULL OR cm.source_type = $3)        -- optional filter
ORDER BY ce.embedding <=> $1::vector
LIMIT $4;  -- top_k
```

### 5.2 Full-Text Search (BM25-like)

```sql
-- Keyword search with ranking, weighted by section > subsection > content
SELECT 
    c.id,
    c.content,
    c.section,
    ts_rank_cd(c.tsvector_content, websearch_to_tsquery('english', $1)) AS text_score,
    cm.message_type,
    cm.source_type
FROM chunk c
JOIN chunk_metadata cm ON cm.chunk_id = c.id
JOIN document d ON d.id = c.document_id
WHERE d.is_current = TRUE
  AND c.tsvector_content @@ websearch_to_tsquery('english', $1)
  AND ($2::varchar IS NULL OR cm.message_type = $2)
  AND ($3::varchar IS NULL OR cm.source_type = $3)
ORDER BY text_score DESC
LIMIT $4;
```

### 5.3 Hybrid Merge (Reciprocal Rank Fusion)

```sql
-- Combine vector + text scores using RRF
-- This is typically done in application code:
-- 
-- For each chunk appearing in vector OR text results:
--   rrf_score = 1/(k + vector_rank) + 1/(k + text_rank)
--   where k = 60 (standard RRF constant)
--   ranks start from 1; use large rank if absent from one result set
```

### 5.4 Metadata-Filtered Search

```sql
-- Find all mandatory fields for a specific message type
SELECT c.content, cm.field_xpath, cm.data_type, cm.rule_status
FROM chunk c
JOIN chunk_metadata cm ON cm.chunk_id = c.id
WHERE cm.message_type = 'pacs.008'
  AND cm.rule_status = 'M'
  AND cm.source_type = 'annex_b_spec'
ORDER BY cm.field_xpath;
```

### 5.5 Change Detection (Re-ingestion)

```sql
-- Check if a file has changed since last ingestion
SELECT id, file_hash, is_current 
FROM document 
WHERE source_path = $1 
ORDER BY created_at DESC 
LIMIT 1;

-- If file_hash differs: mark old as superseded, ingest new
UPDATE document SET is_current = FALSE, updated_at = NOW() 
WHERE source_path = $1 AND is_current = TRUE;
```

---

## 6. Index Strategy

| Index | Type | Purpose | When Used |
|-------|------|---------|-----------|
| `idx_chunk_embedding_vector` | HNSW (cosine) | Approximate nearest neighbor vector search | Every semantic query |
| `idx_chunk_tsvector` | GIN | Full-text search with ranking | Every keyword query |
| `idx_cm_message_type` | btree | Filter chunks by ISO message type | `find_message_type`, `find_business_rule` |
| `idx_cm_source_type` | btree | Filter by source type | All tools with `sources` filter |
| `idx_cm_rule_status` | btree | Filter by M/O/C/R | `find_business_rule` |
| `idx_cm_field_xpath` | GIN (trigram) | Partial match on XPath strings | `find_business_rule` with XPath |
| `idx_cm_php_class` | btree | Filter by PHP class name | `find_module` |
| `idx_document_is_current` | partial btree | Only active docs in search | All queries |
| `idx_chunk_metadata_json` | GIN | Query JSONB metadata | Flexible ad-hoc filters |

### 6.1 HNSW Tuning Notes

```sql
-- For ~100K chunks (adequate for Odyssey + Bimpay):
-- m=16: connections per node (higher = better recall, more memory)
-- ef_construction=128: build quality (higher = slower build, better index)
-- At query time, set ef_search for recall/speed tradeoff:
SET hnsw.ef_search = 100;  -- default 40; increase for better recall
```

---

## 7. Migration Strategy

### 7.1 Init Scripts (First Deploy)

Files in `db/init/` run automatically on first `docker compose up`:

```
db/init/
├── 001_extensions.sql    # pgvector, pg_trgm, uuid-ossp
└── 002_schema.sql        # Full schema from §4 above
```

### 7.2 Incremental Migrations

After initial deploy, changes go to `db/migrations/`:

```
db/migrations/
├── 003_add_integration_column.sql
├── 004_add_feedback_table.sql
└── ...
```

Rules:
- **Numbered sequentially** (003, 004, ...)
- **Idempotent** (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`)
- **Never modify** a deployed migration — always add new
- Applied by a startup script in the rag-api container

### 7.3 Migration Runner (Simple)

```python
# Applied on app startup before serving requests
async def run_migrations(session: AsyncSession):
    """Execute all pending migration SQL files in order."""
    migration_dir = Path("db/migrations")
    applied = await get_applied_migrations(session)  # from a migrations table
    for sql_file in sorted(migration_dir.glob("*.sql")):
        if sql_file.name not in applied:
            await session.execute(text(sql_file.read_text()))
            await record_migration(session, sql_file.name)
    await session.commit()
```

---

## 8. Data Volume Estimates

| Source | Est. Documents | Est. Chunks | Est. Storage |
|--------|---------------|-------------|-------------|
| Annex B Markdown (857 lines) | 1 | ~80–120 | ~0.5 MB |
| CLAUDE.md files (2) | 2 | ~40–60 | ~0.3 MB |
| Tech docs (2 Notion exports) | 2 | ~30–50 | ~0.2 MB |
| PHP Bimpay code (56 files) | 56 | ~200–400 | ~2 MB |
| XML examples (~30 files) | ~30 | ~60–120 | ~1 MB |
| Postman collections (2) | 2 | ~20–40 | ~0.2 MB |
| **Total (initial)** | **~93** | **~430–790** | **~4 MB** |
| Future PDFs (estimated) | ~10–50 | ~500–2000 | ~10–20 MB |

With pgvector HNSW index overhead and 768-dim embeddings:
- **Embedding storage**: ~790 chunks × 768 dims × 4 bytes = ~2.4 MB
- **HNSW index**: ~3× embedding size = ~7 MB
- **Total estimated DB size**: ~30–50 MB (initial), scalable to 100K+ chunks

---

## 9. Backup & Recovery

```bash
# Backup (run from host)
docker compose exec postgres pg_dump -U rag odyssey_rag > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres psql -U rag odyssey_rag < backup_20260302.sql
```

The Docker named volume `rag_pgdata` persists across container restarts. For production, consider adding automated pg_dump cron or WAL-based streaming replication.
