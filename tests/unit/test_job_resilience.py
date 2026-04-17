"""Tests for S7 — job resilience: startup recovery, watchdog, graceful shutdown."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odyssey_rag.job_resilience import (
    IngestTaskRegistry,
    recover_interrupted_jobs,
    start_watchdog,
    stop_watchdog,
)

# ── IngestTaskRegistry ────────────────────────────────────────────────────────


class TestIngestTaskRegistry:
    """Tests for the in-memory task tracker."""

    def setup_method(self):
        IngestTaskRegistry._tasks.clear()

    def test_register_tracks_task(self):
        job_id = uuid.uuid4()
        loop = asyncio.new_event_loop()
        task = loop.create_task(asyncio.sleep(100))
        IngestTaskRegistry.register(job_id, task)

        assert IngestTaskRegistry.active_count() == 1
        task.cancel()
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()

    def test_done_callback_removes_task(self):
        """When a task finishes, the done callback should unregister it."""
        job_id = uuid.uuid4()

        async def _run():
            t = asyncio.create_task(asyncio.sleep(0))
            IngestTaskRegistry.register(job_id, t)
            assert IngestTaskRegistry.active_count() == 1
            await t
            # Give the event loop a tick for the callback
            await asyncio.sleep(0)
            assert IngestTaskRegistry.active_count() == 0

        asyncio.run(_run())

    @pytest.mark.asyncio
    async def test_cancel_all_cancels_tasks(self):
        """cancel_all should cancel running tasks and mark DB jobs."""
        job1 = uuid.uuid4()
        job2 = uuid.uuid4()

        task1 = asyncio.create_task(asyncio.sleep(999))
        task2 = asyncio.create_task(asyncio.sleep(999))

        IngestTaskRegistry.register(job1, task1)
        IngestTaskRegistry.register(job2, task2)
        assert IngestTaskRegistry.active_count() == 2

        mock_repo = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("odyssey_rag.job_resilience.db_session", return_value=mock_session),
            patch("odyssey_rag.job_resilience.IngestJobRepository", return_value=mock_repo),
        ):
            count = await IngestTaskRegistry.cancel_all()

        assert count == 2
        assert task1.cancelled() or task1.done()
        assert task2.cancelled() or task2.done()
        assert mock_repo.mark_cancelled.call_count == 2

    @pytest.mark.asyncio
    async def test_cancel_all_empty_returns_zero(self):
        count = await IngestTaskRegistry.cancel_all()
        assert count == 0


# ── Startup recovery ──────────────────────────────────────────────────────────


class TestStartupRecovery:
    @pytest.mark.asyncio
    async def test_recover_calls_repo(self):
        mock_repo = AsyncMock()
        mock_repo.recover_interrupted_jobs.return_value = 3

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("odyssey_rag.job_resilience.db_session", return_value=mock_session),
            patch("odyssey_rag.job_resilience.IngestJobRepository", return_value=mock_repo),
        ):
            count = await recover_interrupted_jobs()

        assert count == 3
        mock_repo.recover_interrupted_jobs.assert_called_once()

    @pytest.mark.asyncio
    async def test_recover_zero_is_fine(self):
        mock_repo = AsyncMock()
        mock_repo.recover_interrupted_jobs.return_value = 0

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("odyssey_rag.job_resilience.db_session", return_value=mock_session),
            patch("odyssey_rag.job_resilience.IngestJobRepository", return_value=mock_repo),
        ):
            count = await recover_interrupted_jobs()

        assert count == 0


# ── Watchdog ──────────────────────────────────────────────────────────────────


class TestWatchdog:
    @pytest.mark.asyncio
    async def test_start_and_stop_watchdog(self):
        with patch("odyssey_rag.job_resilience.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                job_watchdog_interval=1,
                job_timeout_minutes=30,
            )
            task = start_watchdog()
            assert not task.done()

            await stop_watchdog()
            # After stop, the task should be done
            assert task.done()


# ── Repository resilience methods ─────────────────────────────────────────────


class TestIngestJobRepoResilience:
    """Tests for the new repository methods added in S7."""

    @pytest.mark.asyncio
    async def test_recover_interrupted_jobs_updates_running(self):
        """recover_interrupted_jobs marks running→failed."""
        mock_result = MagicMock()
        mock_result.rowcount = 2

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from odyssey_rag.db.repositories.ingest_jobs import IngestJobRepository
        repo = IngestJobRepository(mock_session)
        count = await repo.recover_interrupted_jobs()

        assert count == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_fail_stale_jobs_uses_cutoff(self):
        """fail_stale_jobs should target jobs older than timeout."""
        mock_result = MagicMock()
        mock_result.rowcount = 1

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from odyssey_rag.db.repositories.ingest_jobs import IngestJobRepository
        repo = IngestJobRepository(mock_session)
        count = await repo.fail_stale_jobs(timeout_minutes=30)

        assert count == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_by_status(self):
        """count_by_status returns a dict of status → count."""
        mock_result = MagicMock()
        mock_result.all.return_value = [("pending", 5), ("running", 2), ("completed", 10)]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from odyssey_rag.db.repositories.ingest_jobs import IngestJobRepository
        repo = IngestJobRepository(mock_session)
        counts = await repo.count_by_status()

        assert counts == {"pending": 5, "running": 2, "completed": 10}
