---
name: odyssey-rag-patterns
description: "Odyssey RAG project-specific patterns, anti-patterns, and implementation guides. Use when working on the Odyssey RAG retrieval system, ingestion pipeline, MCP server, or any component of the knowledge retrieval platform."
---

# Odyssey RAG — Project Patterns & Learnings

Project-specific patterns discovered during comprehensive audit and implementation (2026-04-17).

## When to Use This Skill

- Working on the Odyssey RAG retrieval pipeline (hybrid search, reranker, fusion)
- Modifying the ingestion pipeline (parsers, chunkers, source type detection)
- Adding/modifying MCP tools or MCP server behavior
- Working with the PostgreSQL/pgvector database layer
- Implementing new integrations (Paysset, Blite, etc.)

## Critical Rules

1. **NEVER** change embedding dimensions (768) without re-indexing all documents
2. **NEVER** modify the MCP server name `"odyssey-rag"` — it is the canonical contract name
3. **ALWAYS** use `c.tsvector_content` for BM25 queries (not `to_tsvector()`)
4. **ALWAYS** use `run_in_executor` for CPU-bound ML inference (reranker, embeddings)
5. **ALWAYS** filter `WHERE d.is_current = TRUE` in all retrieval queries
6. **ALWAYS** use the nullable filter SQL pattern for optional filters

## Proven Patterns

### Pattern 1: Nullable Filter SQL
When adding optional filters to SQL queries, use the CAST/IS NULL pattern:
```sql
AND (CAST(:param AS TEXT) IS NULL OR d.column = CAST(:param AS TEXT))
```
Pass `None` for unset filters. The clause evaluates to `TRUE` and is skipped.
Used in: `vector_search.py`, `bm25_search.py`

### Pattern 2: Pre-computed tsvector for BM25
PostgreSQL maintains `tsvector_content` via DB trigger with weighted sections:
- Section title → weight A
- Subsection → weight B  
- Content → weight C
Always use `c.tsvector_content` with the GIN index `idx_chunk_tsvector`.
**Anti-pattern:** `to_tsvector('english', c.content)` bypasses the index entirely.

### Pattern 3: Async Executor for ML Inference
```python
loop = asyncio.get_running_loop()
scores = await loop.run_in_executor(None, self._model.predict, pairs)
```
When changing sync → async:
1. Update the method signature
2. Grep ALL callers (add `await`)
3. Check interface siblings (e.g., `PassthroughReranker`)

### Pattern 4: Source Type Detection Chain
`SOURCE_TYPE_RULES` is an ordered list of `(regex, type)` tuples. First match wins.
- Specific patterns (e.g., `IPS_Annex_B`) come first
- General patterns (e.g., `\.md$`) come last
- When adding multi-brand detection, handle variant spellings: `payss?ett?` for "Payset/Paysett/Paysset"

### Pattern 5: Integration Filter Passthrough
When adding a new filter parameter, wire it through the full stack:
```
MCP tool (@mcp.tool) → handler (tools/search.py) → engine (tool_context) → 
  all_filters dict → vector_search() AND bm25_search()
```
Both search paths MUST receive the filter. Missing one creates silent inconsistency.

### Pattern 6: Health Endpoint Before Auth
For HTTP services with auth middleware, insert health routes BEFORE the middleware:
```python
routes = [Route("/health", health_handler)] + existing_routes
```
Docker healthcheck pattern: `httpx.get("http://localhost:PORT/health")`

### Pattern 7: Document Versioning (Supersede)
- New version: `supersede(source_path)` marks old `is_current=False`, then inserts new doc
- Change detection: SHA-256 file hash comparison
- **Caution:** Different filenames = treated as separate documents (duplicate risk)
- Old chunks/embeddings are NOT deleted — requires garbage collection (S1)

## Tool Strategy Pattern
Tool-specific retrieval behavior is defined in `tool_strategies.py`:
```python
@dataclass
class ToolStrategy:
    metadata_filters: dict[str, str]
    source_type_boosts: dict[str, float]
    require_source_types: list[str]
    focus_filters: dict[str, dict[str, str]]
    bm25_boost_terms: list[str]
```
Strategies are data-driven, not if/else chains. Add new strategies as dataclass instances.

## Database Schema Quick Reference

| Table | Key Columns | Notes |
|-------|-------------|-------|
| document | id, source_path, source_type, integration, is_current, file_hash | One row per version |
| chunk | id, document_id, content, tsvector_content, section, subsection | GIN index on tsvector |
| chunk_embedding | chunk_id, embedding (Vector 768) | HNSW index |
| chunk_metadata | chunk_id, message_type, source_type, module_path | Domain-specific filtering |
| ingest_job | id, source_path, status, chunks_created | Pipeline tracking |
| feedback | id, query, chunk_ids, rating | Quality feedback |

## Testing Patterns

- Tests: `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/ -x`
- Lint: `.venv/bin/ruff check src/ tests/`
- Docker: `docker compose build && docker compose up -d`
- All external I/O must be mocked in unit tests
- Current baseline: 204+ unit tests passing

## Common Pitfalls

1. **Forgetting both search paths:** When adding a filter, add to BOTH `vector_search.py` AND `bm25_search.py`
2. **Regex spelling variants:** Use `payss?ett?` not `paysett?` for brands with spelling variants
3. **Sync ML in async context:** Always check if ML libraries return synchronous results
4. **Dead fields:** If adding a DB column, ensure it's used in at least one query path
5. **Scribe tool limit:** Scribe agent spawns may fail if too many tools (>128). Use gpt-5-mini or gpt-4.1 for Scribe.

## Architecture Overview

```
User/AI → MCP Server (stdio/HTTP) → RetrievalEngine
                                        ├→ QueryProcessor
                                        ├→ Vector Search (pgvector HNSW)
                                        ├→ BM25 Search (PostgreSQL tsvector GIN)
                                        ├→ RRF Fusion (k=60)
                                        ├→ Tool Strategy (boosts/filters)
                                        ├→ Cross-Encoder Reranker
                                        └→ ResponseBuilder → {evidence, gaps, followups}

Admin → FastAPI API → Ingestion Pipeline → DB
```

---

*Created: 2026-04-17 | Last updated: 2026-04-17*
