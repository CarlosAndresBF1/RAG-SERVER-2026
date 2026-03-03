# Odyssey RAG — Retrieval Engine

> **Version**: 1.0.0  
> **Date**: 2026-03-02  
> **Status**: Planning  
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md) §3.2, [DATA_MODEL.md](DATA_MODEL.md) §5, [MCP_TOOLS.md](MCP_TOOLS.md)

---

## 1. Overview

The retrieval engine receives a user query (from API or MCP tool), finds the most relevant chunks, reranks them, and assembles a structured response with evidence, gaps, and followup suggestions.

```
Query → Parse & Expand → Hybrid Search (Vector + BM25) → RRF Merge → Rerank → Format Response
```

---

## 2. Query Pipeline

### 2.1 Query Preprocessing

```python
# retrieval/query_processor.py
from dataclasses import dataclass

@dataclass
class ProcessedQuery:
    """Processed version of the user's raw query."""
    raw: str                                # Original query text
    normalized: str                         # Lowercase, trimmed
    detected_message_type: str | None       # e.g. "pacs.008"
    detected_intent: str | None             # message_type | business_rule | module | error | general
    bm25_query: str                         # Optimized for full-text search
    vector_query: str                       # Optimized for semantic search
    metadata_filters: dict[str, str]        # Filters to apply (message_type, source_type, etc.)

class QueryProcessor:
    """Transform raw MCP tool input into search-ready queries."""
    
    def process(self, raw_query: str, tool_context: dict | None = None) -> ProcessedQuery:
        """
        Process a raw query into optimized search forms.
        
        Args:
            raw_query: The user's text query.
            tool_context: Parameters from MCP tool (message_type, focus, etc.)
        """
        normalized = raw_query.strip().lower()
        
        # Detect message type from query text (if not in tool_context)
        msg_type = (tool_context or {}).get("message_type") or self._detect_message_type(normalized)
        
        # Detect intent
        intent = (tool_context or {}).get("intent") or self._detect_intent(normalized)
        
        # Build BM25 query (expand abbreviations, add synonyms)
        bm25_query = self._build_bm25_query(normalized, msg_type)
        
        # Build vector query (more natural language, include context)
        vector_query = self._build_vector_query(raw_query, msg_type, intent)
        
        # Build metadata filters
        filters = self._build_filters(tool_context, msg_type)
        
        return ProcessedQuery(
            raw=raw_query,
            normalized=normalized,
            detected_message_type=msg_type,
            detected_intent=intent,
            bm25_query=bm25_query,
            vector_query=vector_query,
            metadata_filters=filters,
        )
```

### 2.2 Query Expansion

```python
# Abbreviation expansion for BM25
EXPANSIONS = {
    "pacs": "payment clearing and settlement",
    "camt": "cash management",
    "pain": "payment initiation",
    "acmt": "account management",
    "GrpHdr": "Group Header",
    "CdtTrfTxInf": "Credit Transfer Transaction Information",
    "SttlmInf": "Settlement Information",
    "RsltnOfInvstgtn": "Resolution of Investigation",
    "BIC": "Business Identifier Code",
    "IBAN": "International Bank Account Number",
    "M": "Mandatory",
    "O": "Optional",
    "C": "Conditional",
}

def _build_bm25_query(self, normalized: str, msg_type: str | None) -> str:
    """Expand abbreviations and add synonyms for BM25 search."""
    expanded = normalized
    for abbr, full in EXPANSIONS.items():
        if abbr.lower() in expanded:
            expanded = f"{expanded} {full}"
    if msg_type:
        expanded = f"{msg_type} {expanded}"
    return expanded
```

---

## 3. Hybrid Search

Two parallel retrieval paths run concurrently, then results are merged.

### 3.1 Vector Similarity Search

```python
# retrieval/vector_search.py
async def vector_search(
    query_embedding: list[float],
    filters: dict[str, str],
    limit: int = 30,
) -> list[SearchResult]:
    """Search by cosine similarity using pgvector HNSW index.
    
    SQL (simplified):
        SELECT c.id, c.content, c.section, c.subsection,
               1 - (ce.embedding <=> :query_embedding) AS score
        FROM chunk c
        JOIN chunk_embedding ce ON c.id = ce.chunk_id
        JOIN document d ON c.document_id = d.id
        LEFT JOIN chunk_metadata cm ON c.id = cm.chunk_id
        WHERE d.is_current = TRUE
          AND (:msg_type IS NULL OR cm.message_type = :msg_type)
          AND (:source_type IS NULL OR cm.source_type = :source_type)
        ORDER BY ce.embedding <=> :query_embedding
        LIMIT :limit;
    
    Performance notes:
    - HNSW index: ef_search=100 (set via SET hnsw.ef_search=100)
    - ~0.5ms per query on <10K chunks
    - Cosine distance operator: <=>
    """
```

### 3.2 BM25 Full-Text Search

```python
# retrieval/bm25_search.py
async def bm25_search(
    query: str,
    filters: dict[str, str],
    limit: int = 30,
) -> list[SearchResult]:
    """Full-text search using PostgreSQL tsvector + ts_rank_cd.
    
    SQL (simplified):
        SELECT c.id, c.content, c.section, c.subsection,
               ts_rank_cd(c.content_tsvector, websearch_to_tsquery('english', :query)) AS score
        FROM chunk c
        JOIN document d ON c.document_id = d.id
        LEFT JOIN chunk_metadata cm ON c.id = cm.chunk_id
        WHERE d.is_current = TRUE
          AND c.content_tsvector @@ websearch_to_tsquery('english', :query)
          AND (:msg_type IS NULL OR cm.message_type = :msg_type)
        ORDER BY score DESC
        LIMIT :limit;
    
    Notes:
    - Weighted tsvector: title (A), heading (B), body (C)
    - websearch_to_tsquery supports natural language: "pacs 008 group header"
    - ts_rank_cd uses cover density ranking (better than ts_rank for longer texts)
    """
```

### 3.3 Reciprocal Rank Fusion (RRF)

```python
# retrieval/fusion.py
from collections import defaultdict

def reciprocal_rank_fusion(
    *result_lists: list[SearchResult],
    k: int = 60,
    top_n: int = 20,
) -> list[SearchResult]:
    """Merge multiple ranked result lists using RRF.
    
    Formula: RRF_score(d) = Σ  1 / (k + rank_i(d))
    
    Where:
    - k: smoothing constant (60 is standard)
    - rank_i(d): rank of document d in result list i (1-based)
    - Sum over all lists where d appears
    
    This produces a balanced merge regardless of score magnitude differences
    between vector and BM25 results.
    """
    rrf_scores: dict[int, float] = defaultdict(float)
    result_map: dict[int, SearchResult] = {}
    
    for results in result_lists:
        for rank, result in enumerate(results, start=1):
            rrf_scores[result.chunk_id] += 1.0 / (k + rank)
            result_map[result.chunk_id] = result
    
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    merged = []
    for chunk_id in sorted_ids[:top_n]:
        result = result_map[chunk_id]
        result.rrf_score = rrf_scores[chunk_id]
        merged.append(result)
    
    return merged
```

---

## 4. Cross-Encoder Reranking

After RRF merge, the top-N candidates are reranked using a cross-encoder for higher precision.

```python
# retrieval/reranker.py
from sentence_transformers import CrossEncoder

class CrossEncoderReranker:
    """Rerank candidates with cross-encoder for precision.
    
    Model: cross-encoder/ms-marco-MiniLM-L-6-v2
    - 22M parameters, fast inference (~10ms per pair on CPU)
    - Trained on MS MARCO passage ranking
    - Input: (query, candidate_text) pairs
    - Output: relevance score [-10, 10]
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)
    
    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Rerank candidates by cross-encoder relevance score.
        
        Args:
            query: The original query text.
            candidates: Pre-filtered candidates from RRF fusion (typically 20).
            top_k: Number of final results to return.
        
        Returns:
            Top-k results sorted by cross-encoder score.
        """
        if not candidates:
            return []
        
        pairs = [(query, c.content) for c in candidates]
        scores = self.model.predict(pairs)
        
        for candidate, score in zip(candidates, scores):
            candidate.rerank_score = float(score)
        
        candidates.sort(key=lambda x: x.rerank_score, reverse=True)
        return candidates[:top_k]
```

---

## 5. Response Assembly

After reranking, results are structured into the MCP output contract.

### 5.1 Evidence Builder

```python
# retrieval/response_builder.py
@dataclass
class Citation:
    source_path: str
    section: str | None
    chunk_index: int

@dataclass
class Evidence:
    text: str                       # Relevant chunk content (may be trimmed)
    relevance: float                # 0.0-1.0 normalized score
    citations: list[Citation]       # Source references
    message_type: str | None        # ISO message type (if applicable)
    source_type: str                # annex_b_spec, php_code, etc.

@dataclass
class RetrievalResponse:
    query: str
    evidence: list[Evidence]        # Top relevant chunks
    gaps: list[str]                 # Identified knowledge gaps
    followups: list[str]            # Suggested follow-up queries

class ResponseBuilder:
    """Assemble retrieval results into structured MCP response."""
    
    def build(
        self,
        query: ProcessedQuery,
        reranked: list[SearchResult],
        threshold: float = 0.3,
    ) -> RetrievalResponse:
        """Build structured response from reranked results.
        
        Args:
            query: The processed query.
            reranked: Reranked search results.
            threshold: Minimum rerank score to include as evidence.
        """
        evidence = []
        for result in reranked:
            norm_score = self._normalize_score(result.rerank_score)
            if norm_score < threshold:
                continue
            evidence.append(Evidence(
                text=result.content,
                relevance=norm_score,
                citations=[Citation(
                    source_path=result.source_path,
                    section=result.section,
                    chunk_index=result.chunk_index,
                )],
                message_type=result.message_type,
                source_type=result.source_type,
            ))
        
        gaps = self._detect_gaps(query, evidence)
        followups = self._suggest_followups(query, evidence)
        
        return RetrievalResponse(
            query=query.raw,
            evidence=evidence,
            gaps=gaps,
            followups=followups,
        )
```

### 5.2 Gap Detection

```python
def _detect_gaps(self, query: ProcessedQuery, evidence: list[Evidence]) -> list[str]:
    """Identify knowledge gaps based on what was asked vs what was found."""
    gaps = []
    
    # No results at all
    if not evidence:
        gaps.append(f"No relevant documentation found for: {query.raw}")
        return gaps
    
    # Message type requested but no Annex B evidence
    if query.detected_message_type:
        annex_sources = [e for e in evidence if e.source_type == "annex_b_spec"]
        if not annex_sources:
            gaps.append(f"No Annex B specification found for {query.detected_message_type}")
    
    # Module intent but no PHP code evidence
    if query.detected_intent == "module":
        code_sources = [e for e in evidence if e.source_type == "php_code"]
        if not code_sources:
            gaps.append("No PHP implementation code found for this query")
    
    # Low confidence results
    if evidence and max(e.relevance for e in evidence) < 0.5:
        gaps.append("Results have low confidence — query may need refinement")
    
    return gaps
```

### 5.3 Follow-up Suggestions

```python
def _suggest_followups(self, query: ProcessedQuery, evidence: list[Evidence]) -> list[str]:
    """Suggest useful next queries based on results."""
    followups = []
    
    msg_type = query.detected_message_type
    intent = query.detected_intent
    
    if msg_type and intent == "message_type":
        followups.append(f"Find business rules for {msg_type}")
        followups.append(f"Find PHP module implementing {msg_type}")
    
    if intent == "business_rule":
        followups.append(f"Find the builder/parser for {msg_type}")
    
    if intent == "module":
        followups.append(f"Find tests for this module")
        followups.append(f"Find the Annex B specification for related message type")
    
    if intent == "error":
        followups.append("Search for similar error patterns in other message types")
    
    return followups[:3]  # Max 3 suggestions
```

---

## 6. Tool-Specific Retrieval Strategies

Each MCP tool customizes the retrieval pipeline slightly.

### 6.1 `find_message_type`

```python
# Tool-specific overrides
{
    "metadata_filters": {"message_type": tool_params["message_type"]},
    "source_type_boost": {"annex_b_spec": 2.0, "xml_example": 1.5},
    "focus_filter": {
        "overview": {"subsection_pattern": "overview|introduction"},
        "fields": {"source_type": "annex_b_spec", "subsection_pattern": "field|xpath"},
        "builder": {"source_type": "php_code", "php_symbol_pattern": "build"},
        "parser": {"source_type": "php_code", "php_symbol_pattern": "parse"},
        "validator": {"source_type": "php_code", "php_symbol_pattern": "validat"},
        "examples": {"source_type": "xml_example"},
        "envelope": {"subsection_pattern": "AppHdr|envelope|header"},
    },
}
```

### 6.2 `find_business_rule`

```python
{
    "metadata_filters": {"message_type": tool_params.get("message_type")},
    "source_type_boost": {"annex_b_spec": 3.0},  # Heavily prefer spec
    "require_source_type": ["annex_b_spec"],       # Only Annex B results
    "bm25_boost_terms": ["M", "O", "C", "mandatory", "optional", "conditional"],
}
```

### 6.3 `find_module`

```python
{
    "source_type_boost": {"php_code": 3.0, "tech_doc": 1.5},
    "require_source_type": ["php_code", "tech_doc"],
    "response_transform": "module_map",  # Return ModuleMap object instead of flat evidence
}
```

### 6.4 `find_error`

```python
{
    "bm25_boost_terms": ["RJCT", "ACSP", "PDNG", "error", "reject", "reason", "code"],
    "source_type_boost": {"annex_b_spec": 2.0, "php_code": 1.5, "tech_doc": 1.0},
    "response_transform": "resolution",  # Return Resolution object
}
```

---

## 7. Configuration

```python
# config/settings.py (retrieval section)
class RetrievalSettings(BaseModel):
    """Retrieval engine configuration."""
    
    # Hybrid search
    vector_search_limit: int = 30           # Candidates from vector search
    bm25_search_limit: int = 30             # Candidates from BM25 search
    rrf_k: int = 60                         # RRF smoothing constant
    rrf_merge_limit: int = 20               # Candidates after RRF merge
    
    # Reranking
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_k: int = 10                # Final results after reranking
    reranker_enabled: bool = True           # Can disable for faster dev
    
    # Response
    evidence_threshold: float = 0.3         # Min score to include
    max_evidence_items: int = 8             # Max evidence in response
    max_followups: int = 3                  # Max followup suggestions
    
    # HNSW index
    hnsw_ef_search: int = 100               # Query-time ef parameter
```

---

## 8. Performance Targets

| Metric | Target | Measurement |
|--------|--------|------------|
| End-to-end latency (p50) | < 500ms | From query receipt to response |
| End-to-end latency (p95) | < 1500ms | Including reranker |
| Vector search | < 50ms | On <10K chunks with HNSW |
| BM25 search | < 30ms | With GIN index |
| Reranking (20 candidates) | < 200ms | Cross-encoder on CPU |
| Embedding generation | < 100ms | Single query embedding |
| Relevance (top-5 precision) | > 0.7 | Evaluated on EVALUATION_SET |

---

## 9. Module Structure

```
src/odyssey_rag/retrieval/
├── __init__.py
├── engine.py            # Main RetrievalEngine orchestration
├── query_processor.py   # Query parsing, expansion, filter building
├── vector_search.py     # pgvector similarity search
├── bm25_search.py       # PostgreSQL full-text search
├── fusion.py            # RRF merge
├── reranker.py          # Cross-encoder reranking
├── response_builder.py  # Evidence, gaps, followups assembly
└── tool_strategies.py   # Per-MCP-tool retrieval customization
```
