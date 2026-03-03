"""Run pending database migrations.

Applies all numbered SQL migration files in db/migrations/ that haven't
been applied yet, tracked via a ``schema_migrations`` table.

The ``db/init/`` scripts run automatically on first ``docker compose up``
(via Postgres init directory).  This script handles incremental migrations
added after initial deploy.

Usage:
    # From the RAG/ directory:
    PYTHONPATH=src python scripts/migrate.py

    # List applied / pending migrations without executing:
    PYTHONPATH=src python scripts/migrate.py --list
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"

_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT        PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def _get_applied(session: AsyncSession) -> set[str]:
    """Return filenames of already-applied migrations."""
    result = await session.execute(text("SELECT filename FROM schema_migrations"))
    return {row[0] for row in result.fetchall()}


async def _record_migration(session: AsyncSession, filename: str) -> None:
    await session.execute(
        text("INSERT INTO schema_migrations (filename) VALUES (:f)"),
        {"f": filename},
    )


async def _run_migrations(list_only: bool) -> None:
    from odyssey_rag.db.session import get_session_factory

    factory = get_session_factory()

    async with factory() as session:
        # Ensure tracking table exists
        await session.execute(text(_CREATE_MIGRATIONS_TABLE))
        await session.commit()

        applied = await _get_applied(session)

        sql_files = sorted(MIGRATIONS_DIR.glob("*.sql")) if MIGRATIONS_DIR.is_dir() else []

        pending = [f for f in sql_files if f.name not in applied]

        if list_only:
            for f in sql_files:
                status = "applied" if f.name in applied else "PENDING"
                print(f"  [{status:7s}] {f.name}")
            return

        if not pending:
            logger.info("migrate.no_pending_migrations")
            return

        for sql_file in pending:
            log = logger.bind(migration=sql_file.name)
            log.info("migrate.applying")
            try:
                sql = sql_file.read_text(encoding="utf-8")
                await session.execute(text(sql))
                await _record_migration(session, sql_file.name)
                await session.commit()
                log.info("migrate.applied")
            except Exception as exc:
                await session.rollback()
                log.error("migrate.failed", error=str(exc))
                sys.exit(1)

        logger.info("migrate.done", applied=len(pending))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply pending SQL migrations to the Odyssey RAG database.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="List applied and pending migrations without executing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    logger.info("migrate.starting", migrations_dir=str(MIGRATIONS_DIR))
    asyncio.run(_run_migrations(list_only=args.list))


if __name__ == "__main__":
    main()
