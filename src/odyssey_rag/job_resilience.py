"""S7 — Background ingest job resilience.

Provides three mechanisms to prevent zombie/stuck ingestion jobs:

1. **Startup recovery** — On application start, marks all ``running`` jobs
   as ``failed`` since they were interrupted by a process restart.

2. **Job watchdog** — A periodic asyncio task that detects jobs stuck in
   ``running`` state longer than the configured timeout and fails them.

3. **Graceful shutdown** — Cancels in-flight asyncio ingest tasks and marks
   their jobs as ``cancelled`` so nothing is left dangling.

The ``IngestTaskRegistry`` tracks live ``asyncio.Task`` objects so shutdown
can cancel them deterministically.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import ClassVar

import structlog

from odyssey_rag.config import get_settings
from odyssey_rag.db.repositories.ingest_jobs import IngestJobRepository
from odyssey_rag.db.session import db_session

logger = structlog.get_logger(__name__)


# ── Task registry ─────────────────────────────────────────────────────────────


class IngestTaskRegistry:
    """Tracks live asyncio ingest tasks for graceful shutdown.

    The ingest endpoint registers each ``asyncio.Task`` here on creation.
    During shutdown, ``cancel_all`` cancels every tracked task and marks the
    corresponding jobs as ``cancelled`` in the database.
    """

    _tasks: ClassVar[dict[uuid.UUID, asyncio.Task]] = {}

    @classmethod
    def register(cls, job_id: uuid.UUID, task: asyncio.Task) -> None:
        """Track a running ingest task."""
        cls._tasks[job_id] = task
        task.add_done_callback(lambda _t: cls._tasks.pop(job_id, None))

    @classmethod
    def active_count(cls) -> int:
        return len(cls._tasks)

    @classmethod
    async def cancel_all(cls) -> int:
        """Cancel all tracked tasks and mark their DB jobs as cancelled.

        Returns the number of tasks cancelled.
        """
        if not cls._tasks:
            return 0

        cancelled = 0
        job_ids = list(cls._tasks.keys())

        # Cancel asyncio tasks first
        for _job_id, task in list(cls._tasks.items()):
            if not task.done():
                task.cancel()
                cancelled += 1

        # Give tasks a moment to handle cancellation
        if cancelled:
            await asyncio.sleep(0.5)

        # Mark DB records as cancelled
        async with db_session() as session:
            repo = IngestJobRepository(session)
            for job_id in job_ids:
                await repo.mark_cancelled(job_id)

        cls._tasks.clear()
        logger.info("job_resilience.shutdown_cancelled", count=cancelled)
        return cancelled


# ── Startup recovery ──────────────────────────────────────────────────────────


async def recover_interrupted_jobs() -> int:
    """Mark all ``running`` jobs as ``failed`` on startup.

    Should be called once during the FastAPI lifespan startup phase.
    """
    async with db_session() as session:
        repo = IngestJobRepository(session)
        count = await repo.recover_interrupted_jobs()

    if count:
        logger.warning("job_resilience.startup_recovery", recovered=count)
    else:
        logger.info("job_resilience.startup_recovery", recovered=0)
    return count


# ── Watchdog ──────────────────────────────────────────────────────────────────


async def _watchdog_loop(interval: int, timeout_minutes: int) -> None:
    """Periodically scan for stale running jobs and fail them."""
    while True:
        try:
            await asyncio.sleep(interval)
            async with db_session() as session:
                repo = IngestJobRepository(session)
                timed_out = await repo.fail_stale_jobs(timeout_minutes)
                if timed_out:
                    logger.warning(
                        "job_resilience.watchdog_sweep",
                        timed_out=timed_out,
                        timeout_minutes=timeout_minutes,
                    )
        except asyncio.CancelledError:
            logger.info("job_resilience.watchdog_stopped")
            break
        except Exception:
            logger.exception("job_resilience.watchdog_error")


_watchdog_task: asyncio.Task | None = None


def start_watchdog() -> asyncio.Task:
    """Start the background job watchdog.

    Reads interval and timeout from application settings.
    Returns the watchdog asyncio.Task (kept for shutdown cancellation).
    """
    global _watchdog_task
    settings = get_settings()
    _watchdog_task = asyncio.create_task(
        _watchdog_loop(
            interval=settings.job_watchdog_interval,
            timeout_minutes=settings.job_timeout_minutes,
        ),
        name="job-watchdog",
    )
    logger.info(
        "job_resilience.watchdog_started",
        interval=settings.job_watchdog_interval,
        timeout_minutes=settings.job_timeout_minutes,
    )
    return _watchdog_task


async def stop_watchdog() -> None:
    """Stop the watchdog gracefully."""
    global _watchdog_task
    if _watchdog_task and not _watchdog_task.done():
        _watchdog_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _watchdog_task
    _watchdog_task = None
