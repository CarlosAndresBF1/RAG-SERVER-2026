"""Handler for oddysey_rag.ingest MCP tool.

Ingests new documents into the Odyssey RAG knowledge base via the
standard ingestion pipeline.
"""

from __future__ import annotations

from odyssey_rag.ingestion.pipeline import ingest


async def ingest_handler(
    source: str,
    source_type: str | None = None,
    replace_existing: bool = False,
) -> dict:
    """Ingest a document and return status, chunks_created, and source_type_detected."""
    overrides: dict[str, str] | None = None
    if source_type:
        overrides = {"source_type": source_type}

    result = await ingest(
        source_path=source,
        overrides=overrides,
        replace_existing=replace_existing,
    )

    return {
        "status": result.status,
        "source": result.source_path,
        "chunks_created": result.chunks_created or 0,
        "source_type_detected": result.source_type,
        "errors": ([result.error] if result.error else []),
    }
