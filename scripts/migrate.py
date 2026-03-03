"""Run pending database migrations.

Applies all numbered SQL migration files in db/migrations/
that haven't been applied yet.

Usage:
    python scripts/migrate.py
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def main() -> None:
    """Run pending migrations — placeholder for Phase 7."""
    logger.info("migrate.placeholder", message="Migration script not yet implemented")


if __name__ == "__main__":
    main()
