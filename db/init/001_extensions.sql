-- db/init/001_extensions.sql
-- Required PostgreSQL extensions for Odyssey RAG

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "vector";           -- pgvector: vector similarity search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";          -- Trigram text similarity
