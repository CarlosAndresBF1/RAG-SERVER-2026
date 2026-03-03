"""Seed initial Odyssey sources into the RAG database.

Reads source documents from data/sources/ and runs
the ingestion pipeline for each one.

Usage:
    python scripts/seed_initial_sources.py
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def main() -> None:
    """Seed initial sources — placeholder for Phase 7."""
    logger.info("seed.placeholder", message="Seed script not yet implemented")


if __name__ == "__main__":
    main()
