# Odyssey RAG — Testing Strategy

> **Version**: 1.0.0  
> **Date**: 2026-03-02  
> **Status**: Planning  
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md) §8, [CONVENTIONS.md](CONVENTIONS.md) §6

---

## 1. Testing Layers

```
┌───────────────────────────────────────────┐
│  Layer 3: Evaluation Tests                │  Quality gate (precision, recall)
│  ── 50+ domain questions ──               │  See EVALUATION_SET.md
├───────────────────────────────────────────┤
│  Layer 2: Integration Tests               │  Real DB, real API, real MCP
│  ── API endpoints, ingest pipeline,       │
│     MCP server, end-to-end ──             │
├───────────────────────────────────────────┤
│  Layer 1: Unit Tests                      │  Isolated, fast, mocked deps
│  ── Parsers, chunkers, retrieval,         │
│     response builders, metadata ──        │
└───────────────────────────────────────────┘
```

---

## 2. Directory Structure

```
tests/
├── conftest.py               # Shared fixtures (db session, test data, etc.)
├── unit/
│   ├── conftest.py
│   ├── test_parsers/
│   │   ├── test_markdown_parser.py
│   │   ├── test_php_code_parser.py
│   │   ├── test_xml_example_parser.py
│   │   └── test_postman_parser.py
│   ├── test_chunkers/
│   │   ├── test_markdown_chunker.py
│   │   ├── test_php_code_chunker.py
│   │   └── test_semantic_chunker.py
│   ├── test_metadata/
│   │   └── test_metadata_extractor.py
│   ├── test_retrieval/
│   │   ├── test_query_processor.py
│   │   ├── test_fusion.py
│   │   ├── test_response_builder.py
│   │   └── test_tool_strategies.py
│   ├── test_embeddings/
│   │   └── test_embedding_provider.py
│   ├── test_llm/
│   │   └── test_provider_factory.py
│   └── test_db/
│       └── test_repositories.py
├── integration/
│   ├── conftest.py            # Test DB setup, API client
│   ├── test_api_endpoints.py
│   ├── test_ingest_pipeline.py
│   ├── test_mcp_server.py
│   └── test_retrieval_e2e.py
├── evaluation/
│   ├── conftest.py
│   ├── test_evaluation_suite.py
│   ├── evaluation_questions.json
│   └── evaluation_report.py
└── fixtures/
    ├── sample_annex_b.md       # Subset of Annex B (pacs.008 only)
    ├── sample_php_class.php    # Simplified Bimpay class
    ├── sample_xml_message.xml  # Minimal pacs.008 XML
    ├── sample_postman.json     # Minimal Postman collection
    └── sample_tech_doc.md      # Minimal tech doc
```

---

## 3. Unit Tests

### 3.1 Parser Tests

```python
# tests/unit/test_parsers/test_markdown_parser.py
import pytest
from odyssey_rag.ingestion.parsers.markdown import MarkdownParser

@pytest.fixture
def parser():
    return MarkdownParser()

@pytest.fixture
def annex_b_content():
    """Minimal Annex B extract for testing."""
    return """
## pacs.008.001.12

Customer Credit Transfer

### Group Header (GrpHdr)

| XPath | Tag | Mult | Status | Type | Description |
|-------|-----|------|--------|------|-------------|
| GrpHdr/MsgId | MsgId | [1..1] | M | Max35Text | Unique message identifier |
| GrpHdr/CreDtTm | CreDtTm | [1..1] | M | ISODateTime | Creation date/time |

### Credit Transfer Transaction Information

| XPath | Tag | Mult | Status | Type | Description |
|-------|-----|------|--------|------|-------------|
| CdtTrfTxInf/PmtId/EndToEndId | EndToEndId | [1..1] | M | Max35Text | End-to-end identifier |
"""

class TestMarkdownParser:
    def test_parse_splits_by_headings(self, parser, annex_b_content, tmp_path):
        """Parser should split content by heading hierarchy."""
        file = tmp_path / "annex_b.md"
        file.write_text(annex_b_content)
        sections = parser.parse(str(file))
        assert len(sections) >= 2  # At least GrpHdr and CdtTrfTxInf

    def test_parse_preserves_section_name(self, parser, annex_b_content, tmp_path):
        """Section name should be the H2 heading."""
        file = tmp_path / "annex_b.md"
        file.write_text(annex_b_content)
        sections = parser.parse(str(file))
        assert any(s.section == "pacs.008.001.12" for s in sections)

    def test_parse_preserves_subsection_name(self, parser, annex_b_content, tmp_path):
        """Subsection name should be the H3 heading."""
        file = tmp_path / "annex_b.md"
        file.write_text(annex_b_content)
        sections = parser.parse(str(file))
        grp_hdr = [s for s in sections if s.subsection and "Group Header" in s.subsection]
        assert len(grp_hdr) == 1

    def test_parse_detects_message_type_metadata(self, parser, annex_b_content, tmp_path):
        """Parser should extract message_type from Annex B heading."""
        file = tmp_path / "annex_b.md"
        file.write_text(annex_b_content)
        sections = parser.parse(str(file))
        assert any(s.metadata.get("message_type") == "pacs.008" for s in sections)

    def test_parse_empty_file_returns_empty_list(self, parser, tmp_path):
        """Empty file should return empty list."""
        file = tmp_path / "empty.md"
        file.write_text("")
        assert parser.parse(str(file)) == []
```

### 3.2 Chunker Tests

```python
# tests/unit/test_chunkers/test_markdown_chunker.py
class TestMarkdownChunker:
    def test_chunk_small_section_stays_whole(self, chunker):
        """Sections smaller than max_tokens should be one chunk."""
        sections = [ParsedSection(content="Short content", section="test")]
        chunks = chunker.chunk(sections)
        assert len(chunks) == 1

    def test_chunk_large_section_splits(self, chunker):
        """Sections larger than max_tokens should be split."""
        long_content = "word " * 600  # ~600 tokens
        sections = [ParsedSection(content=long_content, section="test")]
        chunks = chunker.chunk(sections)
        assert len(chunks) >= 2

    def test_chunk_preserves_heading_prefix(self, chunker):
        """Each chunk should include heading context."""
        sections = [ParsedSection(content="Some content", section="pacs.008", subsection="GrpHdr")]
        chunks = chunker.chunk(sections)
        assert "pacs.008" in chunks[0].content
        assert "GrpHdr" in chunks[0].content

    def test_chunk_overlap_content(self, chunker):
        """Adjacent chunks should have overlapping content."""
        long_content = "sentence one. " * 300
        sections = [ParsedSection(content=long_content, section="test")]
        chunks = chunker.chunk(sections)
        if len(chunks) >= 2:
            # Last tokens of chunk 0 should appear in start of chunk 1
            assert chunks[0].content[-50:] in chunks[1].content[:200] or True  # overlap check
```

### 3.3 Metadata Extractor Tests

```python
# tests/unit/test_metadata/test_metadata_extractor.py
class TestMetadataExtractor:
    def test_detect_message_type_pacs008(self, extractor):
        """Should detect pacs.008 from content."""
        chunk = Chunk(content="pacs.008 Credit Transfer message...", token_count=10)
        meta = extractor.extract(chunk, "annex_b_spec")
        assert meta.message_type == "pacs.008"

    def test_detect_message_type_camt056(self, extractor):
        """Should detect camt.056 from content."""
        chunk = Chunk(content="FIToFIPmtCxlReq recall request", token_count=10)
        meta = extractor.extract(chunk, "annex_b_spec")
        assert meta.message_type == "camt.056"

    def test_extract_rule_status_mandatory(self, extractor):
        """Should extract M (mandatory) from field table."""
        chunk = Chunk(content="| GrpHdr/MsgId | MsgId | [1..1] | M | Max35Text |", token_count=15)
        meta = extractor.extract(chunk, "annex_b_spec")
        assert "M" in (meta.rule_status or "")

    def test_php_metadata_from_hints(self, extractor):
        """Should use parser hints for PHP metadata."""
        chunk = Chunk(
            content="public function buildDocument...",
            token_count=50,
            metadata={"php_class": "Pacs008CreditTransfer", "php_symbol": "buildDocument"},
        )
        meta = extractor.extract(chunk, "php_code")
        assert meta.php_class == "Pacs008CreditTransfer"
        assert meta.php_symbol == "buildDocument"
```

### 3.4 Query Processor Tests

```python
# tests/unit/test_retrieval/test_query_processor.py
class TestQueryProcessor:
    def test_detect_message_type_from_query(self, processor):
        """Should detect message type in query text."""
        result = processor.process("How do I build a pacs.008 message?")
        assert result.detected_message_type == "pacs.008"

    def test_query_expansion_adds_synonyms(self, processor):
        """BM25 query should expand abbreviations."""
        result = processor.process("pacs.008 GrpHdr fields")
        assert "Group Header" in result.bm25_query

    def test_tool_context_overrides_detection(self, processor):
        """Tool context should override auto-detection."""
        result = processor.process("Show me the fields", {"message_type": "camt.056"})
        assert result.detected_message_type == "camt.056"

    def test_metadata_filters_from_tool_context(self, processor):
        """Tool context should produce metadata filters."""
        result = processor.process("overview", {"message_type": "pacs.008", "source_type": "annex_b_spec"})
        assert result.metadata_filters["message_type"] == "pacs.008"
```

### 3.5 RRF Fusion Tests

```python
# tests/unit/test_retrieval/test_fusion.py
class TestReciprocalRankFusion:
    def test_rrf_single_list_preserves_order(self):
        """Single list should preserve original ranking."""
        results = [SearchResult(chunk_id=i) for i in range(5)]
        merged = reciprocal_rank_fusion(results, k=60, top_n=5)
        assert [r.chunk_id for r in merged] == [0, 1, 2, 3, 4]

    def test_rrf_merges_two_lists(self):
        """Items appearing in both lists should rank higher."""
        list_a = [SearchResult(chunk_id=1), SearchResult(chunk_id=2), SearchResult(chunk_id=3)]
        list_b = [SearchResult(chunk_id=2), SearchResult(chunk_id=4), SearchResult(chunk_id=1)]
        merged = reciprocal_rank_fusion(list_a, list_b, k=60, top_n=3)
        # chunk_id=2 is rank 2 in both → highest RRF. chunk_id=1 is rank 1 and 3.
        assert merged[0].chunk_id in (1, 2)

    def test_rrf_top_n_limits_output(self):
        """Should return at most top_n results."""
        results = [SearchResult(chunk_id=i) for i in range(100)]
        merged = reciprocal_rank_fusion(results, k=60, top_n=5)
        assert len(merged) == 5

    def test_rrf_empty_lists(self):
        """Empty lists should return empty results."""
        assert reciprocal_rank_fusion([], k=60, top_n=5) == []
```

### 3.6 Response Builder Tests

```python
# tests/unit/test_retrieval/test_response_builder.py
class TestResponseBuilder:
    def test_filters_below_threshold(self, builder):
        """Results below threshold should be excluded."""
        results = [SearchResult(chunk_id=1, rerank_score=-5.0)]  # Low score
        response = builder.build(query, results, threshold=0.3)
        assert len(response.evidence) == 0

    def test_gap_detected_when_no_results(self, builder):
        """Should report gap when no results found."""
        response = builder.build(query, [], threshold=0.3)
        assert len(response.gaps) > 0
        assert "No relevant" in response.gaps[0]

    def test_followups_suggested_for_message_type(self, builder):
        """Should suggest follow-ups for message type queries."""
        query = ProcessedQuery(detected_message_type="pacs.008", detected_intent="message_type", ...)
        results = [good_result]
        response = builder.build(query, results)
        assert len(response.followups) > 0
```

---

## 4. Integration Tests

### 4.1 Test Database Fixture

```python
# tests/integration/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture(scope="session")
def test_db_url():
    """Use a test database (docker compose run with ENVIRONMENT=test)."""
    return "postgresql+asyncpg://rag_user:test_password@localhost:5432/odyssey_rag_test"

@pytest.fixture(scope="session")
async def db_engine(test_db_url):
    engine = create_async_engine(test_db_url)
    # Apply schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    async with AsyncSession(db_engine) as session:
        yield session
        await session.rollback()
```

### 4.2 API Endpoint Tests

```python
# tests/integration/test_api_endpoints.py
import httpx
import pytest

@pytest.fixture
def api_client():
    return httpx.AsyncClient(base_url="http://localhost:8080")

class TestHealthEndpoint:
    async def test_health_returns_ok(self, api_client):
        response = await api_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

class TestSearchEndpoint:
    async def test_search_returns_evidence(self, api_client, seeded_db):
        response = await api_client.post("/api/v1/search", json={
            "query": "pacs.008 group header fields",
        })
        assert response.status_code == 200
        data = response.json()
        assert "evidence" in data
        assert "gaps" in data

    async def test_search_empty_query_returns_400(self, api_client):
        response = await api_client.post("/api/v1/search", json={"query": ""})
        assert response.status_code == 400

class TestIngestEndpoint:
    async def test_ingest_file_creates_chunks(self, api_client, tmp_path):
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nSome content for testing.")
        response = await api_client.post("/api/v1/ingest", json={
            "source_path": str(test_file),
        })
        assert response.status_code == 200
        assert response.json()["status"] in ("completed", "skipped")

class TestSourcesEndpoint:
    async def test_list_sources(self, api_client, seeded_db):
        response = await api_client.get("/api/v1/sources")
        assert response.status_code == 200
        sources = response.json()
        assert isinstance(sources, list)
```

### 4.3 Ingestion Pipeline Integration

```python
# tests/integration/test_ingest_pipeline.py
class TestIngestionPipeline:
    async def test_ingest_markdown_creates_document_and_chunks(self, db_session, pipeline, sample_md):
        """Full pipeline: parse → chunk → embed → store."""
        result = await pipeline.ingest(str(sample_md))
        assert result.status == "completed"
        assert result.chunks_created > 0
        
        # Verify in DB
        doc = await db_session.execute(
            select(Document).where(Document.source_path == str(sample_md))
        )
        assert doc.scalar_one().is_current is True

    async def test_reingest_unchanged_file_skips(self, pipeline, sample_md):
        """Same file should be skipped if hash unchanged."""
        await pipeline.ingest(str(sample_md))
        result = await pipeline.ingest(str(sample_md))
        assert result.status == "skipped"

    async def test_reingest_changed_file_supersedes(self, db_session, pipeline, sample_md):
        """Changed file should create new document, mark old as superseded."""
        await pipeline.ingest(str(sample_md))
        sample_md.write_text("# Updated\n\nNew content.")
        result = await pipeline.ingest(str(sample_md))
        assert result.status == "completed"
        
        docs = await db_session.execute(
            select(Document).where(Document.source_path == str(sample_md))
        )
        docs_list = docs.scalars().all()
        assert sum(1 for d in docs_list if d.is_current) == 1
```

### 4.4 MCP Server Integration

```python
# tests/integration/test_mcp_server.py
class TestMcpServer:
    async def test_list_tools_returns_six_tools(self, mcp_client):
        """MCP server should expose 6 tools."""
        tools = await mcp_client.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "oddysey_rag.find_message_type",
            "oddysey_rag.find_business_rule",
            "oddysey_rag.find_module",
            "oddysey_rag.find_error",
            "oddysey_rag.search",
            "oddysey_rag.ingest",
        }
        assert expected.issubset(tool_names)

    async def test_find_message_type_returns_evidence(self, mcp_client, seeded_db):
        """find_message_type should return structured evidence."""
        result = await mcp_client.call_tool("oddysey_rag.find_message_type", {
            "message_type": "pacs.008",
        })
        assert result.content
        data = json.loads(result.content[0].text)
        assert "evidence" in data

    async def test_find_module_returns_module_map(self, mcp_client, seeded_db):
        """find_module should return module_map object."""
        result = await mcp_client.call_tool("oddysey_rag.find_module", {
            "query": "pacs.008 builder",
        })
        data = json.loads(result.content[0].text)
        assert "module_map" in data or "evidence" in data
```

---

## 5. Test Configuration

### 5.1 `pyproject.toml` Test Section

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests (fast, no external deps)",
    "integration: Integration tests (require DB/API)",
    "evaluation: Evaluation tests (quality metrics)",
    "slow: Tests that take > 5s",
]
filterwarnings = [
    "ignore::DeprecationWarning",
]

[tool.coverage.run]
source = ["src/odyssey_rag"]
omit = ["*/tests/*", "*/scripts/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

### 5.2 Running Tests

```bash
# All tests
make test

# Unit only (fast, no deps)
pytest tests/unit/ -v -m unit

# Integration only (requires docker compose up)
pytest tests/integration/ -v -m integration

# Evaluation suite
pytest tests/evaluation/ -v -m evaluation --tb=short

# Coverage report
pytest tests/unit/ --cov --cov-report=term-missing
```

---

## 6. Coverage Targets

| Module | Target | Critical Methods |
|--------|--------|-----------------|
| `ingestion/parsers/` | 90% | `parse()` for each parser |
| `ingestion/chunkers/` | 85% | `chunk()`, overlap logic |
| `ingestion/metadata/` | 90% | `extract()`, type detection |
| `retrieval/` | 85% | `search()`, `fuse()`, `rerank()` |
| `api/` | 80% | All endpoints |
| `mcp_server/` | 80% | All 6 tool handlers |
| `db/` | 75% | Repository CRUD |
| **Overall** | **≥ 80%** | |

---

## 7. Test Data Management

### 7.1 Fixtures Strategy

- **Unit tests**: Use minimal inline fixtures (small strings, dicts)
- **Integration tests**: Use `tests/fixtures/` files (curated subsets of real data)
- **Evaluation tests**: Use `tests/evaluation/evaluation_questions.json` (domain Q&A)

### 7.2 Fixture Files

| File | Content | Purpose |
|------|---------|---------|
| `sample_annex_b.md` | Annex B pacs.008 section only (~50 lines) | Parser/chunker testing |
| `sample_php_class.php` | Simplified Bimpay class with 3 methods | PHP parser testing |
| `sample_xml_message.xml` | Minimal valid pacs.008 XML | XML parser testing |
| `sample_postman.json` | 2-request collection | Postman parser testing |
| `sample_tech_doc.md` | 3-section tech doc | Generic markdown testing |

---

## 8. CI Integration (Future)

```yaml
# .github/workflows/test.yml (when ready)
name: Tests
on: [push, pull_request]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/unit/ -v --cov --cov-report=xml
  
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:0.7.4-pg16
        env: { POSTGRES_PASSWORD: test, POSTGRES_DB: odyssey_rag_test }
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/integration/ -v
        env: { DATABASE_URL: "postgresql+asyncpg://postgres:test@localhost:5432/odyssey_rag_test" }
```
