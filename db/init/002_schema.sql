-- db/init/002_schema.sql
-- Full schema for Odyssey RAG
-- Ref: DATA_MODEL.md §4

-- ────────────────────────────────────────────────────────
-- 4.1 document — Indexed source files
-- ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_path     VARCHAR(500)  NOT NULL,
    source_type     VARCHAR(50)   NOT NULL,
    file_hash       VARCHAR(64)   NOT NULL,
    doc_version     VARCHAR(20),
    integration     VARCHAR(100)  DEFAULT 'bimpay',
    is_current      BOOLEAN       DEFAULT TRUE,
    metadata_json   JSONB         DEFAULT '{}',
    total_chunks    INTEGER       DEFAULT 0,
    created_at      TIMESTAMPTZ   DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   DEFAULT NOW(),

    CONSTRAINT uq_document_path_hash UNIQUE (source_path, file_hash)
);

CREATE INDEX IF NOT EXISTS idx_document_source_type  ON document (source_type);
CREATE INDEX IF NOT EXISTS idx_document_integration  ON document (integration);
CREATE INDEX IF NOT EXISTS idx_document_is_current   ON document (is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_document_file_hash    ON document (file_hash);

-- ────────────────────────────────────────────────────────
-- 4.2 chunk — Text fragments with full-text search
-- ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chunk (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id       UUID          NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    content           TEXT          NOT NULL,
    token_count       INTEGER       NOT NULL DEFAULT 0,
    chunk_index       INTEGER       NOT NULL DEFAULT 0,
    section           VARCHAR(255),
    subsection        VARCHAR(255),
    metadata_json     JSONB         DEFAULT '{}',
    tsvector_content  TSVECTOR,
    created_at        TIMESTAMPTZ   DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunk_document_id   ON chunk (document_id);
CREATE INDEX IF NOT EXISTS idx_chunk_section       ON chunk (section);
CREATE INDEX IF NOT EXISTS idx_chunk_tsvector      ON chunk USING GIN (tsvector_content);
CREATE INDEX IF NOT EXISTS idx_chunk_metadata_json ON chunk USING GIN (metadata_json);

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

DROP TRIGGER IF EXISTS trg_chunk_tsvector ON chunk;
CREATE TRIGGER trg_chunk_tsvector
    BEFORE INSERT OR UPDATE OF content, section, subsection
    ON chunk
    FOR EACH ROW
    EXECUTE FUNCTION chunk_tsvector_trigger();

-- ────────────────────────────────────────────────────────
-- 4.3 chunk_embedding — Vector embeddings (1:1 with chunk)
-- ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chunk_embedding (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id    UUID         NOT NULL REFERENCES chunk(id) ON DELETE CASCADE,
    embedding   VECTOR(768)  NOT NULL,
    model_name  VARCHAR(100) NOT NULL DEFAULT 'nomic-embed-text-v1.5',
    created_at  TIMESTAMPTZ  DEFAULT NOW(),

    CONSTRAINT uq_chunk_embedding_chunk UNIQUE (chunk_id)
);

-- HNSW index for fast approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS idx_chunk_embedding_vector
    ON chunk_embedding
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

-- ────────────────────────────────────────────────────────
-- 4.4 chunk_metadata — Structured metadata for filtering
-- ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chunk_metadata (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id      UUID         NOT NULL REFERENCES chunk(id) ON DELETE CASCADE,

    -- ISO 20022 domain fields
    message_type  VARCHAR(20),
    iso_version   VARCHAR(30),
    field_xpath   VARCHAR(255),
    rule_status   VARCHAR(1),
    data_type     VARCHAR(50),

    -- Odyssey code domain
    module_path   VARCHAR(255),
    php_class     VARCHAR(100),
    php_symbol    VARCHAR(100),

    -- Source classification
    source_type   VARCHAR(50) NOT NULL,

    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cm_chunk_id      ON chunk_metadata (chunk_id);
CREATE INDEX IF NOT EXISTS idx_cm_message_type  ON chunk_metadata (message_type);
CREATE INDEX IF NOT EXISTS idx_cm_iso_version   ON chunk_metadata (iso_version);
CREATE INDEX IF NOT EXISTS idx_cm_source_type   ON chunk_metadata (source_type);
CREATE INDEX IF NOT EXISTS idx_cm_rule_status   ON chunk_metadata (rule_status);
CREATE INDEX IF NOT EXISTS idx_cm_php_class     ON chunk_metadata (php_class);
CREATE INDEX IF NOT EXISTS idx_cm_module_path   ON chunk_metadata (module_path);
CREATE INDEX IF NOT EXISTS idx_cm_field_xpath   ON chunk_metadata USING GIN (field_xpath gin_trgm_ops);

-- ────────────────────────────────────────────────────────
-- 4.5 ingest_job — Ingestion tracking
-- ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingest_job (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_path     VARCHAR(500)  NOT NULL,
    source_type     VARCHAR(50)   NOT NULL,
    status          VARCHAR(20)   NOT NULL DEFAULT 'pending',
    chunks_created  INTEGER       DEFAULT 0,
    error_message   TEXT,
    metadata_json   JSONB         DEFAULT '{}',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingest_job_status     ON ingest_job (status);
CREATE INDEX IF NOT EXISTS idx_ingest_job_created_at ON ingest_job (created_at DESC);

-- ────────────────────────────────────────────────────────
-- 4.6 feedback — User/agent feedback for quality improvement
-- ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query           TEXT          NOT NULL,
    chunk_ids       UUID[]        NOT NULL,
    response_text   TEXT,
    tool_name       VARCHAR(100),
    rating          SMALLINT      CHECK (rating BETWEEN -1 AND 1),
    comment         TEXT,
    created_at      TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_rating    ON feedback (rating);
CREATE INDEX IF NOT EXISTS idx_feedback_tool      ON feedback (tool_name);
CREATE INDEX IF NOT EXISTS idx_feedback_created   ON feedback (created_at DESC);
