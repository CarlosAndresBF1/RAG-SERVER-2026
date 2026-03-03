"""Odyssey RAG exception hierarchy.

All custom exceptions inherit from OdysseyRagError for consistent
error handling at API and MCP boundaries.
"""

from __future__ import annotations


class OdysseyRagError(Exception):
    """Base exception for all RAG errors."""


class IngestionError(OdysseyRagError):
    """Failed to ingest/parse a document."""


class RetrievalError(OdysseyRagError):
    """Failed to execute search/retrieval."""


class EmbeddingError(OdysseyRagError):
    """Failed to generate embeddings."""


class ConfigError(OdysseyRagError):
    """Invalid or missing configuration."""
