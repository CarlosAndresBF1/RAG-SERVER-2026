"""Ingestion pipeline orchestrator.

Entry point for the full ingestion flow:
    detect → parse → chunk → metadata → embed → store

Supports:
- SHA-256-based change detection (skip unchanged files)
- Automatic source-type detection from filename patterns
- All configured parsers and chunkers
- Batch embedding with configurable batch size
- Atomic DB storage in a single transaction (supersede + insert)
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

from odyssey_rag.config import get_settings
from odyssey_rag.db.models import (
    Chunk as ChunkModel,
)
from odyssey_rag.db.models import (
    ChunkEmbedding,
    ChunkMetadata as ChunkMetadataModel,
    Document,
    IngestJob,
)
from odyssey_rag.db.repositories.chunks import ChunkRepository
from odyssey_rag.db.repositories.documents import DocumentRepository
from odyssey_rag.db.repositories.embeddings import EmbeddingRepository
from odyssey_rag.db.repositories.ingest_jobs import IngestJobRepository
from odyssey_rag.db.session import db_session
from odyssey_rag.embeddings.factory import create_embedding_provider
from odyssey_rag.ingestion.chunkers.base import Chunk
from odyssey_rag.ingestion.chunkers.markdown import MarkdownChunker
from odyssey_rag.ingestion.chunkers.php_code import PhpCodeChunker
from odyssey_rag.ingestion.chunkers.semantic import SemanticChunker
from odyssey_rag.ingestion.metadata.extractor import ExtractedMetadata, MetadataExtractor
from odyssey_rag.ingestion.parsers.base import ParsedSection
from odyssey_rag.ingestion.parsers.markdown import MarkdownParser
from odyssey_rag.ingestion.parsers.php_code import PhpCodeParser
from odyssey_rag.ingestion.parsers.postman import PostmanParser
from odyssey_rag.ingestion.parsers.docx import DocxParser
from odyssey_rag.ingestion.parsers.xml_example import XmlExampleParser

logger = structlog.get_logger(__name__)

# ── Source type detection ─────────────────────────────────────────────────────

SOURCE_TYPE_RULES: list[tuple[str, str]] = [
    (r"IPS_Annex_B.*\.md$", "annex_b_spec"),
    (r"BIMPAY_(TECHNICAL|INFRASTRUCTURE).*\.md$", "tech_doc"),
    (r"CLAUDE\.md$", "claude_context"),
    (r"\.php$", "php_code"),
    (r"\.xml$", "xml_example"),
    (r"\.postman_collection\.json$", "postman_collection"),
    (r"\.pdf$", "pdf_doc"),
    (r"\.docx?$", "word_doc"),
    (r"\.(md|txt|rst)$", "generic_text"),
]


def detect_source_type(path: str, overrides: Optional[dict[str, str]] = None) -> str:
    """Auto-detect source type from filename, with optional override.

    Args:
        path:      File path to classify.
        overrides: Optional mapping that may contain ``"source_type"`` key.

    Returns:
        Source type string (e.g. ``"annex_b_spec"``).
    """
    if overrides and "source_type" in overrides:
        return overrides["source_type"]
    for pattern, source_type in SOURCE_TYPE_RULES:
        if re.search(pattern, path, re.IGNORECASE):
            return source_type
    return "generic_text"


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class IngestResult:
    """Result returned by the ingestion pipeline.

    Attributes:
        status:         ``"completed"``, ``"skipped"``, or ``"failed"``.
        source_path:    Path that was processed.
        source_type:    Detected (or overridden) source type.
        chunks_created: Number of chunks stored (0 for skipped/failed).
        document_id:    UUID of the stored Document row (None if skipped/failed).
        reason:         Human-readable reason string (for skipped/failed).
        error:          Exception message (for failed results).
    """

    status: str
    source_path: str
    source_type: str = ""
    chunks_created: int = 0
    document_id: Optional[uuid.UUID] = None
    reason: str = ""
    error: str = ""


# ── Utility functions ─────────────────────────────────────────────────────────

def compute_sha256(file_path: str) -> str:
    """Compute the SHA-256 hex digest of a file.

    Args:
        file_path: Path to the file.

    Returns:
        64-character lowercase hex string.
    """
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_parser(source_type: str):
    """Instantiate the appropriate parser for a source type."""
    if source_type in ("annex_b_spec", "tech_doc", "claude_context", "generic_text"):
        return MarkdownParser()
    if source_type == "php_code":
        return PhpCodeParser()
    if source_type == "xml_example":
        return XmlExampleParser()
    if source_type == "postman_collection":
        return PostmanParser()
    if source_type == "word_doc":
        return DocxParser()
    # Fallback
    return MarkdownParser()


def _get_chunker(source_type: str):
    """Instantiate the appropriate chunker for a source type."""
    settings = get_settings()
    max_tokens = settings.chunk_size
    overlap = settings.chunk_overlap

    if source_type in ("annex_b_spec", "tech_doc", "claude_context", "generic_text"):
        return MarkdownChunker(max_tokens=max_tokens, overlap_tokens=overlap)
    if source_type == "php_code":
        return PhpCodeChunker(max_tokens=max_tokens, overlap_tokens=overlap)
    if source_type in ("xml_example", "postman_collection", "word_doc"):
        return SemanticChunker(max_tokens=max_tokens, overlap_tokens=overlap)
    return SemanticChunker(max_tokens=max_tokens, overlap_tokens=overlap)


# ── Change detection ──────────────────────────────────────────────────────────

async def _is_unchanged(
    doc_repo: DocumentRepository,
    source_path: str,
    new_hash: str,
) -> bool:
    """Check whether the file has changed since last ingestion.

    Args:
        doc_repo:    DocumentRepository connected to the current session.
        source_path: Canonical source path.
        new_hash:    SHA-256 hash of the current file.

    Returns:
        ``True`` if an unchanged version is already stored.
    """
    existing = await doc_repo.get_current_by_path(source_path)
    if existing is None:
        return False
    return existing.file_hash == new_hash


# ── Batch embedding helper ────────────────────────────────────────────────────

async def _embed_chunks(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for all chunk texts in batches of 32.

    Args:
        texts: List of chunk content strings.

    Returns:
        Parallel list of 768-dimensional embedding vectors.
    """
    settings = get_settings()
    provider = create_embedding_provider(settings)
    embeddings: list[list[float]] = []
    batch_size = 32

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_embeddings = await provider.embed(batch)
        embeddings.extend(batch_embeddings)

    return embeddings


# ── Main ingestion function ───────────────────────────────────────────────────

async def ingest(
    source_path: str,
    overrides: Optional[dict[str, str]] = None,
    replace_existing: bool = False,
) -> IngestResult:
    """Run the full ingestion pipeline for a single file.

    Steps:
    1. Detect source type
    2. Compute file hash; skip if unchanged (unless ``replace_existing=True``)
    3. Parse to ParsedSections
    4. Chunk into token-bounded Chunks
    5. Extract structured metadata per chunk
    6. Generate embeddings (batched)
    7. Store in PostgreSQL atomically (supersede old, insert new)

    Args:
        source_path:      Absolute or relative path to the source file.
        overrides:        Optional dict with ``"source_type"`` or ``"integration"``
                          keys to override auto-detection.
        replace_existing: If ``True``, re-ingest even if the hash matches.

    Returns:
        IngestResult describing the outcome.
    """
    path = Path(source_path)
    log = logger.bind(source_path=source_path)

    # ── Validate file exists ──────────────────────────────────────────────────
    if not path.exists():
        log.warning("file_not_found")
        return IngestResult(
            status="failed",
            source_path=source_path,
            error=f"File not found: {source_path}",
        )

    source_type = detect_source_type(source_path, overrides)
    log = log.bind(source_type=source_type)

    # ── Compute file hash ─────────────────────────────────────────────────────
    file_hash = compute_sha256(source_path)

    # ── Check change detection via DB ─────────────────────────────────────────
    job_id = uuid.uuid4()

    async with db_session() as session:
        doc_repo = DocumentRepository(session)
        job_repo = IngestJobRepository(session)

        if not replace_existing:
            if await _is_unchanged(doc_repo, source_path, file_hash):
                log.info("skip_unchanged")
                return IngestResult(
                    status="skipped",
                    source_path=source_path,
                    source_type=source_type,
                    reason="unchanged",
                )

        # Create ingest job record
        job = IngestJob(
            id=job_id,
            source_path=source_path,
            source_type=source_type,
            status="pending",
        )
        await job_repo.insert(job)

    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        parser = _get_parser(source_type)
        parsed_sections: list[ParsedSection] = parser.parse(source_path)
        log.info("parsed", section_count=len(parsed_sections))
    except Exception as exc:
        log.error("parse_failed", error=str(exc))
        async with db_session() as session:
            await IngestJobRepository(session).mark_failed(job_id, str(exc))
        return IngestResult(
            status="failed",
            source_path=source_path,
            source_type=source_type,
            error=f"Parse failed: {exc}",
        )

    if not parsed_sections:
        log.warning("empty_parse_result")
        async with db_session() as session:
            await IngestJobRepository(session).mark_failed(
                job_id, "Parser returned no sections"
            )
        return IngestResult(
            status="failed",
            source_path=source_path,
            source_type=source_type,
            error="Parser returned no sections",
        )

    # ── Chunk ─────────────────────────────────────────────────────────────────
    try:
        chunker = _get_chunker(source_type)
        chunks: list[Chunk] = chunker.chunk(parsed_sections)
        log.info("chunked", chunk_count=len(chunks))
    except Exception as exc:
        log.error("chunk_failed", error=str(exc))
        async with db_session() as session:
            await IngestJobRepository(session).mark_failed(job_id, str(exc))
        return IngestResult(
            status="failed",
            source_path=source_path,
            source_type=source_type,
            error=f"Chunking failed: {exc}",
        )

    # ── Extract metadata ──────────────────────────────────────────────────────
    extractor = MetadataExtractor()
    all_metadata: list[ExtractedMetadata] = [
        extractor.extract(chunk, source_type) for chunk in chunks
    ]

    # ── Generate embeddings ───────────────────────────────────────────────────
    try:
        async with db_session() as session:
            await IngestJobRepository(session).mark_running(job_id)

        texts = [c.content for c in chunks]
        embeddings = await _embed_chunks(texts)
        log.info("embedded", embedding_count=len(embeddings))
    except Exception as exc:
        log.error("embed_failed", error=str(exc))
        async with db_session() as session:
            await IngestJobRepository(session).mark_failed(job_id, str(exc))
        return IngestResult(
            status="failed",
            source_path=source_path,
            source_type=source_type,
            error=f"Embedding failed: {exc}",
        )

    # ── Store atomically ──────────────────────────────────────────────────────
    integration = (overrides or {}).get("integration", "bimpay")
    doc_id: uuid.UUID

    try:
        async with db_session() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = ChunkRepository(session)
            emb_repo = EmbeddingRepository(session)
            job_repo = IngestJobRepository(session)

            # Supersede previous current version
            await doc_repo.supersede(source_path)

            # Create new document record
            doc = Document(
                id=uuid.uuid4(),
                source_path=source_path,
                source_type=source_type,
                file_hash=file_hash,
                integration=integration,
                is_current=True,
                total_chunks=len(chunks),
            )
            await doc_repo.insert(doc)
            doc_id = doc.id

            # Bulk insert chunks + embeddings + metadata
            for i, (chunk, embedding, meta) in enumerate(
                zip(chunks, embeddings, all_metadata)
            ):
                chunk_record = ChunkModel(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    chunk_index=i,
                    section=chunk.section,
                    subsection=chunk.subsection,
                    metadata_json=chunk.metadata,
                )
                await chunk_repo.insert(chunk_record)

                emb_record = ChunkEmbedding(
                    id=uuid.uuid4(),
                    chunk_id=chunk_record.id,
                    embedding=embedding,
                )
                await emb_repo.insert(emb_record)

                meta_record = ChunkMetadataModel(
                    id=uuid.uuid4(),
                    chunk_id=chunk_record.id,
                    source_type=source_type,
                    message_type=meta.message_type,
                    iso_version=meta.iso_version,
                    field_xpath=meta.field_xpath,
                    rule_status=meta.rule_status,
                    data_type=meta.data_type,
                    module_path=meta.module_path,
                    php_class=meta.php_class,
                    php_symbol=meta.php_symbol,
                )
                session.add(meta_record)

            await job_repo.mark_completed(job_id, chunks_created=len(chunks))
            log.info("stored", doc_id=str(doc_id), chunks=len(chunks))

    except Exception as exc:
        log.error("store_failed", error=str(exc))
        async with db_session() as session:
            await IngestJobRepository(session).mark_failed(job_id, str(exc))
        return IngestResult(
            status="failed",
            source_path=source_path,
            source_type=source_type,
            error=f"Storage failed: {exc}",
        )

    return IngestResult(
        status="completed",
        source_path=source_path,
        source_type=source_type,
        chunks_created=len(chunks),
        document_id=doc_id,
    )
