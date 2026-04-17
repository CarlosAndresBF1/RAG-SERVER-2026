# Odyssey RAG — Ingestion Pipeline

> **Version**: 1.1.0  
> **Date**: 2026-03-18  
> **Status**: Implemented  
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md) §3.1, [DATA_MODEL.md](DATA_MODEL.md) §4

---

## 1. Pipeline Overview

The ingestion pipeline transforms raw source files into searchable, embedded chunks stored in PostgreSQL.

```
Input File → Detect Type → Parse → Chunk → Extract Metadata → Embed → Store
```

### 1.1 Entry Points

| Entry | Trigger |
|-------|---------|
| `POST /api/v1/ingest` | HTTP API call (async — returns job_id immediately) |
| `POST /api/v1/ingest/batch` | Batch HTTP API call (async — returns job IDs) |
| `odyssey_rag.ingest` | MCP tool call from VS Code |
| `scripts/seed_initial_sources.py` | One-time initial seeding |

### 1.2 Async Processing Model

Ingestion is **fire-and-forget**. The API endpoint:
1. Creates an `IngestJob` record with `status="pending"`
2. Launches `asyncio.create_task(_run_ingest_background(...))`
3. Returns `{ job_id, status: "pending" }` immediately

The pipeline running in background will:
- Re-use the existing pending `IngestJob` via `find_pending_by_path()`
- Transition: `pending` → `running` → `completed|failed`
- Check for cancellation at key stages (before parse, before embed, before store)
- Client polls `GET /api/v1/jobs/{id}` for progress

### 1.3 Job Lifecycle

```
pending ──→ running ──→ completed
   │           │
   │           ├──→ failed
   │           │
   ├──→ cancelled (user action)
   │           │
   └───────────┘
```

- **Cancel**: `POST /api/v1/jobs/{id}/cancel` — marks the job as `cancelled`. The background pipeline checks status at each major step and aborts via `IngestCancelledError`.
- **Delete**: `DELETE /api/v1/jobs/{id}` — removes the job record (only for finished jobs: completed, failed, or cancelled).

### 1.2 Pipeline Steps

```python
# ingestion/pipeline.py — orchestration pseudocode
async def ingest(source_path: str, overrides: dict | None = None) -> IngestResult:
    # 1. Detect source type
    source_type = detect_source_type(source_path, overrides)
    
    # 2. Check for duplicates (file hash)
    file_hash = compute_sha256(source_path)
    if already_ingested(source_path, file_hash):
        return IngestResult(status="skipped", reason="unchanged")
    
    # 3. Parse to structured text
    parser = get_parser(source_type)
    parsed_sections = parser.parse(source_path)
    
    # 4. Chunk into fragments
    chunker = get_chunker(source_type)
    chunks = chunker.chunk(parsed_sections)
    
    # 5. Extract metadata per chunk
    metadata = extract_metadata(chunks, source_type, overrides)
    
    # 6. Generate embeddings
    embeddings = await embed_chunks([c.content for c in chunks])
    
    # 7. Store in PostgreSQL (document + chunks + embeddings + metadata)
    await store(source_path, source_type, file_hash, chunks, embeddings, metadata)
    
    return IngestResult(status="completed", chunks_created=len(chunks))
```

---

## 2. Source Type Detection

```python
# ingestion/pipeline.py
SOURCE_TYPE_RULES = [
    # ── BimPay / IPS integration ──────────────────────────────────────
    (r"IPS_Annex_B.*\.md$",                "annex_b_spec"),
    (r"BIMPAY_(TECHNICAL|INFRASTRUCTURE).*\.md$", "tech_doc"),
    (r"CLAUDE\.md$",                        "claude_context"),
    # ── General Odyssey documentation ─────────────────────────────
    (r"[Aa]nnex[_\s]?[Aa]",                  "annex_a_spec"),
    (r"[Aa]nnex[_\s]?[Cc]",                  "annex_c_spec"),
    (r"(?i)alias",                           "alias_doc"),
    (r"(?i)qr|codigo.?qr",                  "qr_doc"),
    (r"(?i)home.?banking|banca.?electronica","banking_doc"),
    (r"(?i)integration|integraci[oó]n",      "integration_doc"),
    # ── Code & data sources ───────────────────────────────────────
    (r"\.php$",                             "php_code"),
    (r"\.xml$",                             "xml_example"),
    (r"\.postman_collection\.json$",        "postman_collection"),
    (r"\.pdf$",                             "pdf_doc"),
    (r"\.docx?$",                            "word_doc"),
    (r"\.(md|txt|rst)$",                    "generic_text"),
]

def detect_source_type(path: str, overrides: dict | None = None) -> str:
    """Auto-detect source type from filename. Override takes priority."""
    if overrides and "source_type" in overrides:
        return overrides["source_type"]
    for pattern, source_type in SOURCE_TYPE_RULES:
        if re.search(pattern, path, re.IGNORECASE):
            return source_type
    return "generic_text"
```

---

## 3. Parsers

Each parser implements the `BaseParser` interface and returns a list of `ParsedSection` objects.

### 3.1 Interface

```python
# ingestion/parsers/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ParsedSection:
    """A logical section extracted from a source file."""
    content: str                        # The text content
    section: str | None = None          # Top-level heading (e.g. "pacs.008")
    subsection: str | None = None       # Sub-heading (e.g. "Group Header Fields")
    metadata: dict[str, str] = None     # Parser-specific metadata hints
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class BaseParser(ABC):
    """Abstract base for all document parsers."""
    
    @abstractmethod
    def parse(self, file_path: str) -> list[ParsedSection]:
        """Parse a file into structured sections."""
        ...
    
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles."""
        ...
```

### 3.2 MarkdownParser (`annex_b_spec`, `annex_a_spec`, `annex_c_spec`, `tech_doc`, `claude_context`, `generic_text`, `alias_doc`, `qr_doc`, `banking_doc`, `integration_doc`)

**Strategy**: Split by heading hierarchy (H1 → H2 → H3). Each section preserves its heading lineage.

```python
# ingestion/parsers/markdown.py
class MarkdownParser(BaseParser):
    """Parse Markdown files by heading structure.
    
    Splits content at heading boundaries (# → ## → ###).
    Each ParsedSection gets:
      - section: H1 or H2 text
      - subsection: H3 text (if applicable)
      - content: full text under that heading
    
    For Annex B, this naturally groups by:
      - Message type (e.g. "## pacs.008.001.12")
      - Field group (e.g. "### Group Header")
      - Individual fields (within content)
    """
```

**Annex B-specific behavior**: When the source_type is `annex_b_spec`, the parser also:
- Detects field definition tables (XPath | Tag | Mult | Status | Type | Desc)
- Extracts each field row as metadata hints: `field_xpath`, `rule_status`, `data_type`
- Preserves table structure in content (for LLM readability)

**Output example** for Annex B:
```python
ParsedSection(
    content="| GrpHdr/MsgId | <MsgId> | [1..1] | M | Max35Text | Unique message ID...",
    section="pacs.008.001.12",
    subsection="Group Header (GrpHdr)",
    metadata={
        "message_type": "pacs.008",
        "iso_version": "pacs.008.001.12",
        "fields_in_section": "MsgId,CreDtTm,NbOfTxs,SttlmInf"
    }
)
```

### 3.3 PhpCodeParser (`php_code`)

**Strategy**: Parse PHP source into semantic units: class declaration, individual methods, constants/properties.

```python
# ingestion/parsers/php_code.py
class PhpCodeParser(BaseParser):
    """Parse PHP files into class/method-level sections.
    
    Strategy:
    1. Extract class-level docblock + class declaration → one section ("overview")
    2. Each public/protected method → one section (docblock + signature + body)
    3. Constants and properties → grouped into one section
    
    Uses regex-based extraction (no PHP AST needed for this scope):
    - /class\s+(\w+)/ for class name
    - /(public|protected|private)\s+function\s+(\w+)/ for methods
    - /const\s+(\w+)/ for constants
    
    Metadata extracted:
    - php_class: class name
    - php_symbol: method name
    - module_path: relative file path
    """
```

**Output example** for `Pacs008CreditTransfer.php`:
```python
[
    ParsedSection(
        content="class Pacs008CreditTransfer extends BaseMessage {\n  // ..class overview...",
        section="Pacs008CreditTransfer",
        subsection="class_overview",
        metadata={"php_class": "Pacs008CreditTransfer", "module_path": "Bimpay/Messages/Pacs008CreditTransfer.php"}
    ),
    ParsedSection(
        content="public function buildDocument(XmlBuilder $xml, array $data): void {\n  ...",
        section="Pacs008CreditTransfer",
        subsection="buildDocument",
        metadata={"php_class": "Pacs008CreditTransfer", "php_symbol": "buildDocument"}
    ),
    # ... one per method
]
```

### 3.4 XmlExampleParser (`xml_example`)

**Strategy**: Parse XML message examples preserving structure, message type identification, and key field values.

```python
# ingestion/parsers/xml_example.py
class XmlExampleParser(BaseParser):
    """Parse ISO 20022 XML example files.
    
    Strategy:
    1. Detect message type from namespace/root element
    2. Extract AppHdr fields (From/To BIC, MsgDefIdr, BizMsgIdr)
    3. Split document body into logical sections:
       - Group Header
       - Transaction info (per CdtTrfTxInf / TxInf block)
       - Full XML as one section (for literal matching)
    
    Metadata extracted:
    - message_type (from namespace)
    - iso_version (from MsgDefIdr)
    - from_bic, to_bic (from AppHdr)
    """
```

### 3.5 DocxParser (`word_doc`)

```python
# ingestion/parsers/docx.py
class DocxParser(BaseParser):
    """Parse Word documents (.doc / .docx) into heading-delimited sections.
    
    .docx strategy (python-docx):
    1. Iterate paragraphs detecting heading styles (Heading 1–3, Title)
    2. Group body paragraphs under their heading context
    3. Heading 1 / Title → section, Heading 2/3 → subsection
    4. Extract tables as Markdown-formatted rows with | separators
    5. Table content is appended as separate sections with subsection="Table"
    
    .doc strategy (legacy binary):
    1. Try antiword CLI tool for text extraction
    2. Fallback: raw byte decoding with printable-text filtering
    3. Entire document → single section (no heading structure)
    
    Dependencies: python-docx, antiword (system package for .doc)
    Chunker: SemanticChunker (paragraph-aware splitting)
    """
```

**Output example** for a structured .docx:
```python
[
    ParsedSection(
        content="This is the introduction paragraph...",
        section="Document Title",
        subsection=None,
    ),
    ParsedSection(
        content="Detailed content under section one...",
        section="Document Title",
        subsection="Section One",
    ),
    ParsedSection(
        content="| Field | Type | Description |\n| --- | --- | --- |\n| MsgId | string | ...",
        section="Document Title",
        subsection="Table",
    ),
]
```

### 3.6 PdfParser (`pdf_doc`) — Future

```python
# ingestion/parsers/pdf.py
class PdfParser(BaseParser):
    """Parse PDF documents preserving structure.
    
    Strategy:
    1. Detect if text-based or scanned (fallback to OCR)
    2. Extract pages with pdfplumber (preserves tables)
    3. Identify headings by font size/weight heuristics
    4. Split by detected headings (similar to Markdown parser)
    5. Extract tables as Markdown-formatted text
    
    Dependencies: pdfplumber, pypdf
    OCR fallback: pytesseract (only if needed)
    """
```

### 3.7 PostmanParser (`postman_collection`)

```python
# ingestion/parsers/postman.py
class PostmanParser(BaseParser):
    """Parse Postman collection JSON files.
    
    Strategy:
    1. Load JSON, iterate collection items
    2. Each request → one ParsedSection:
       - method + URL
       - headers summary
       - request body (formatted)
       - example responses (if present)
    3. Folder structure → section/subsection hierarchy
    
    Metadata: endpoint inferred from URL pattern
    """
```

---

## 4. Chunkers

Chunkers take parsed sections and split them into appropriately sized chunks.

### 4.1 Interface

```python
# ingestion/chunkers/base.py
@dataclass
class Chunk:
    """A chunk ready for embedding and storage."""
    content: str
    token_count: int
    section: str | None = None
    subsection: str | None = None
    chunk_index: int = 0
    metadata: dict[str, str] = None

class BaseChunker(ABC):
    """Abstract base for chunking strategies."""
    
    def __init__(self, max_tokens: int = 512, overlap_tokens: int = 64):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
    
    @abstractmethod
    def chunk(self, sections: list[ParsedSection]) -> list[Chunk]:
        """Split parsed sections into chunks."""
        ...
```

### 4.2 MarkdownChunker

**Strategy**: Heading-aware chunking that respects section boundaries.

```
Input: ParsedSection with heading hierarchy
       
Rules:
1. If section content ≤ max_tokens → one chunk (preserve whole section)
2. If > max_tokens → split at paragraph boundaries with overlap
3. Never split a field definition row across chunks
4. Preserve heading context as prefix:
   "## pacs.008 > ### Group Header\n\n{content}"
```

### 4.3 PhpCodeChunker

**Strategy**: Method-level chunks with class context.

```
Rules:
1. Each method → one chunk (most are < 512 tokens)
2. If method > max_tokens → split at logical blocks (foreach, if/else)  
3. Always prepend: "Class: Pacs008CreditTransfer\nFile: Bimpay/Messages/Pacs008CreditTransfer.php\n\n"
4. Class overview (docblock + properties + constants) → one chunk
5. Imports/requires → included in class overview chunk
```

### 4.4 XmlMessageChunker

**Strategy**: Message-section chunking.

```
Rules:
1. AppHdr → one chunk (always small)
2. Each major element group (GrpHdr, CdtTrfTxInf, TxInf) → one chunk
3. Full XML → one chunk (for literal search matching)
4. Prefix each chunk: "Message: pacs.008 | File: example_pacs008_credit_transfer.xml"
```

### 4.5 SemanticChunker (fallback)

For generic text and PDFs, use token-aware splitting:

```
Rules:
1. Split at paragraph boundaries (\n\n)
2. Target: max_tokens per chunk
3. Overlap: overlap_tokens from end of previous chunk
4. If single paragraph > max_tokens: split at sentence boundaries
5. Preserve section/subsection from ParsedSection
```

---

## 5. Metadata Extraction

After chunking, metadata is extracted and structured for filtering.

```python
# ingestion/metadata/extractor.py
class MetadataExtractor:
    """Extract structured metadata from chunks based on source type."""
    
    def extract(self, chunk: Chunk, source_type: str) -> ChunkMetadata:
        """Build ChunkMetadata from chunk content and parser hints."""
        base = ChunkMetadata(source_type=source_type)
        
        # Merge parser-provided hints
        if chunk.metadata:
            base.update_from_hints(chunk.metadata)
        
        # Auto-detect message type from content
        if not base.message_type:
            base.message_type = self._detect_message_type(chunk.content)
        
        # Auto-detect ISO version
        if not base.iso_version and base.message_type:
            base.iso_version = self._detect_iso_version(chunk.content, base.message_type)
        
        # Extract XPaths from Annex B table content
        if source_type == "annex_b_spec":
            base.field_xpath = self._extract_xpaths(chunk.content)
            base.rule_status = self._extract_rule_status(chunk.content)
            base.data_type = self._extract_data_type(chunk.content)
        
        return base
```

### 5.1 Message Type Detection

```python
# Patterns for auto-detecting message type from content
MESSAGE_TYPE_PATTERNS = {
    "pacs.008": [r"pacs\.008", r"FIToFICstmrCdtTrf", r"Pacs008", r"CreditTransfer"],
    "pacs.002": [r"pacs\.002", r"FIToFIPmtStsRpt", r"Pacs002", r"PaymentStatusReport"],
    "pacs.004": [r"pacs\.004", r"PmtRtr", r"Pacs004", r"CreditTransferReturn"],
    "pacs.028": [r"pacs\.028", r"FIToFIPmtStsReq", r"Pacs028", r"Investigation"],
    "camt.056": [r"camt\.056", r"FIToFIPmtCxlReq", r"Camt056", r"RecallMessage"],
    "camt.029": [r"camt\.029", r"RsltnOfInvstgtn", r"Camt029", r"NegativeAnswer"],
    "pain.001": [r"pain\.001", r"CstmrCdtTrfInitn", r"Pain001", r"PaymentInitiation"],
    "pain.002": [r"pain\.002", r"CstmrPmtStsRpt", r"Pain002", r"StatusReport"],
    "pain.013": [r"pain\.013", r"CdtrPmtActvtnReq", r"Pain013", r"RequestToPay"],
    "pain.014": [r"pain\.014", r"CdtrPmtActvtnReqStsRpt", r"Pain014", r"RequestToPayResponse"],
}
```

---

## 6. Embedding Step

```python
# ingestion/pipeline.py (within ingest function)
async def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for all chunk texts.
    
    Uses the configured embedding provider (default: nomic-embed-text).
    Batches requests for efficiency (batch_size=32).
    """
    provider = get_embedding_provider()  # from config
    embeddings = []
    for batch in batched(texts, 32):
        batch_embeddings = await provider.embed(batch)
        embeddings.extend(batch_embeddings)
    return embeddings
```

---

## 7. Storage Step

```python
# ingestion/pipeline.py (within ingest function)
async def store(
    source_path: str,
    source_type: str,
    file_hash: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    metadata: list[ChunkMetadata],
) -> None:
    """Persist document, chunks, embeddings, and metadata in a single transaction."""
    async with db_session() as session:
        # 1. Mark previous version as superseded (if exists)
        await session.execute(
            update(Document)
            .where(Document.source_path == source_path, Document.is_current == True)
            .values(is_current=False, updated_at=func.now())
        )
        
        # 2. Create document record
        doc = Document(
            source_path=source_path,
            source_type=source_type,
            file_hash=file_hash,
            total_chunks=len(chunks),
        )
        session.add(doc)
        await session.flush()  # Get doc.id
        
        # 3. Bulk insert chunks + embeddings + metadata
        for i, (chunk, embedding, meta) in enumerate(zip(chunks, embeddings, metadata)):
            chunk_record = ChunkModel(
                document_id=doc.id,
                content=chunk.content,
                token_count=chunk.token_count,
                chunk_index=i,
                section=chunk.section,
                subsection=chunk.subsection,
            )
            session.add(chunk_record)
            await session.flush()
            
            session.add(ChunkEmbedding(chunk_id=chunk_record.id, embedding=embedding))
            session.add(ChunkMetadataModel(chunk_id=chunk_record.id, **meta.to_dict()))
        
        await session.commit()
```

---

## 8. Re-ingestion & Deduplication

### 8.1 Change Detection

```python
def should_reingest(source_path: str, new_hash: str) -> bool:
    """Check if file has changed since last ingestion."""
    existing = db.query(Document).filter(
        Document.source_path == source_path,
        Document.is_current == True
    ).first()
    
    if existing is None:
        return True  # Never ingested
    return existing.file_hash != new_hash  # Changed
```

### 8.2 Replace Mode

When `replace_existing=True` in the ingest tool:
1. Delete all chunks/embeddings/metadata for the existing document
2. Mark document as `is_current=False`
3. Ingest fresh

When `replace_existing=False` (default):
1. If unchanged (same hash): skip
2. If changed: mark old as superseded, create new document + chunks

---

## 9. Initial Seed Sources

The `scripts/seed_initial_sources.py` script auto-ingests known project sources:

```python
INITIAL_SOURCES = [
    # Annex B specification
    {"path": "../../md/IPS_Annex_B_Message_Specifications.md", "type": "annex_b_spec"},
    
    # Technical documentation
    {"path": "../../notion/BIMPAY_TECHNICAL_DOC.md", "type": "tech_doc"},
    {"path": "../../notion/BIMPAY_INFRASTRUCTURE_DOC.md", "type": "tech_doc"},
    
    # Claude context files
    {"path": "../../odyssey/CLAUDE.md", "type": "claude_context"},
    {"path": "../../IA SKIILLS/CLAUDE.md", "type": "claude_context"},
    
    # PHP Bimpay code (56 files)
    {"path": "../../Bimpay Context Claude/Bimpay/", "type": "php_code", "recursive": True},
    
    # XML examples
    {"path": "../../IPS Messages Examples/", "type": "xml_example", "recursive": True,
     "extensions": [".xml"]},
    
    # Postman collections
    {"path": "../../IPS Messages Examples/BIMPAY POC.postman_collection.json", "type": "postman_collection"},
    {"path": "../../md/BIMPAY POC.postman_collection.json", "type": "postman_collection"},
]
```

---

## 10. Error Handling

| Error | Behavior |
|-------|----------|
| File not found | `IngestResult(status="failed", error="File not found: ...")` |
| Unsupported file type | Fall back to `generic_text` parser |
| .doc without antiword | Fallback to raw text extraction |
| Parse error (corrupt PDF, invalid XML) | Log error, record in `ingest_job`, skip file |
| Embedding service unavailable | Retry 3× with exponential backoff, then fail job |
| Database write failure | Rollback transaction, fail job |
| Duplicate (same hash) | Skip silently, return `status="skipped"` |
