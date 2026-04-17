"""Dynamic source type categorization system.

Provides a multi-layer detection chain:
  1. API override (highest priority)
  2. Hardcoded SOURCE_TYPE_RULES (existing regex rules)
  3. DB custom rules (SourceTypeRule table, cached in-memory)
  4. Content-based keyword heuristic
  5. Fallback to ``"generic_text"``

Both sync and async interfaces are exposed so the ingestion pipeline
(which is sync-compatible) can use the cached rules without awaiting.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass

import structlog

from odyssey_rag.ingestion.pipeline import SOURCE_TYPE_RULES

logger = structlog.get_logger(__name__)


# ── Content-based keyword heuristic ──────────────────────────────────────────

CONTENT_KEYWORDS: dict[str, str] = {
    "annex": "annex_spec",
    "paysset": "paysett_doc",
    "paysett": "paysett_doc",
    "blite": "blite_doc",
    "blossom": "blite_doc",
    "bimpay": "tech_doc",
    "mimics": "mimics_doc",
    "qr": "qr_doc",
    "alias": "alias_doc",
    "home banking": "banking_doc",
    "runbook": "runbook",
    "architecture": "architecture_doc",
    "integration": "integration_doc",
}


@dataclass(frozen=True)
class CachedRule:
    """In-memory representation of a DB rule for fast sync access."""

    pattern: str
    source_type: str
    priority: int


class SourceTypeCategorizer:
    """Thread-safe categorizer with in-memory cache of DB rules.

    Call :meth:`refresh_cache` (async) on startup and periodically to
    reload rules from the database.  The sync method
    :meth:`detect_source_type_sync` reads only from the cache and never
    touches the database.
    """

    def __init__(self) -> None:
        self._cached_rules: list[CachedRule] = []
        self._lock = threading.Lock()
        self._last_refresh: float = 0.0
        self._refresh_interval: float = 300.0  # 5 minutes

    # ── Cache management ─────────────────────────────────────────────────

    async def refresh_cache(self) -> int:
        """Reload active DB rules into the in-memory cache.

        Returns the number of rules loaded.
        """
        from odyssey_rag.db.repositories.source_type_rules import SourceTypeRuleRepository
        from odyssey_rag.db.session import db_session

        try:
            async with db_session() as session:
                repo = SourceTypeRuleRepository(session)
                db_rules = await repo.list_active()

            new_cache = [
                CachedRule(
                    pattern=r.pattern,
                    source_type=r.source_type,
                    priority=r.priority,
                )
                for r in db_rules
            ]

            with self._lock:
                self._cached_rules = new_cache
                self._last_refresh = time.monotonic()

            logger.info("categorizer.cache_refreshed", rule_count=len(new_cache))
            return len(new_cache)
        except Exception:
            logger.warning("categorizer.cache_refresh_failed", exc_info=True)
            return len(self._cached_rules)

    def _get_cached_rules(self) -> list[CachedRule]:
        """Return current cached rules (thread-safe snapshot)."""
        with self._lock:
            return list(self._cached_rules)

    @property
    def cache_age_seconds(self) -> float:
        """Seconds since last successful cache refresh."""
        if self._last_refresh == 0.0:
            return float("inf")
        return time.monotonic() - self._last_refresh

    # ── Detection chain ──────────────────────────────────────────────────

    def detect_source_type_sync(
        self,
        path: str,
        overrides: dict[str, str] | None = None,
    ) -> str:
        """Synchronous source type detection using the full chain.

        Safe to call from sync code — uses only in-memory data.

        Args:
            path:      File path to classify.
            overrides: Optional mapping that may contain ``"source_type"``.

        Returns:
            Detected source type string.
        """
        # 1. API override (highest priority)
        if overrides and "source_type" in overrides:
            return overrides["source_type"]

        # 2. Hardcoded regex rules
        for pattern, source_type in SOURCE_TYPE_RULES:
            if re.search(pattern, path, re.IGNORECASE):
                return source_type

        # 3. DB custom rules (from cache)
        for rule in self._get_cached_rules():
            try:
                if re.search(rule.pattern, path, re.IGNORECASE):
                    return rule.source_type
            except re.error:
                logger.warning(
                    "categorizer.invalid_regex",
                    pattern=rule.pattern,
                    source_type=rule.source_type,
                )
                continue

        # 4. Content-based keyword heuristic
        result = _keyword_heuristic(path)
        if result is not None:
            return result

        # 5. Fallback
        return "generic_text"

    async def detect_source_type_async(
        self,
        path: str,
        overrides: dict[str, str] | None = None,
    ) -> str:
        """Async detection — refreshes cache if stale, then delegates to sync.

        Args:
            path:      File path to classify.
            overrides: Optional mapping that may contain ``"source_type"``.

        Returns:
            Detected source type string.
        """
        if self.cache_age_seconds > self._refresh_interval:
            await self.refresh_cache()

        return self.detect_source_type_sync(path, overrides)


def _keyword_heuristic(path: str) -> str | None:
    """Check filename against keyword map (case-insensitive).

    Returns the matching source type, or None if no keyword matched.
    """
    lower_path = path.lower()
    for keyword, source_type in CONTENT_KEYWORDS.items():
        if keyword in lower_path:
            return source_type
    return None


# ── Module-level singleton ───────────────────────────────────────────────────

_categorizer: SourceTypeCategorizer | None = None


def get_categorizer() -> SourceTypeCategorizer:
    """Get or create the module-level categorizer singleton."""
    global _categorizer  # noqa: PLW0603
    if _categorizer is None:
        _categorizer = SourceTypeCategorizer()
    return _categorizer


async def init_categorizer_cache() -> None:
    """Initialize the categorizer cache on application startup."""
    categorizer = get_categorizer()
    await categorizer.refresh_cache()
