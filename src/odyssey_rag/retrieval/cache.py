"""In-memory TTL cache for retrieval query results.

Avoids re-executing the full pipeline (embed → search → fuse → rerank)
for identical queries within the TTL window.

Thread-safe via ``cachetools.TTLCache`` internal locking.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import structlog
from cachetools import TTLCache

logger = structlog.get_logger(__name__)


def _make_cache_key(query: str, tool_name: str, tool_context: dict[str, str] | None) -> str:
    """Build a deterministic cache key from query parameters.

    Args:
        query:        Raw query string.
        tool_name:    MCP tool name.
        tool_context: Optional tool parameters (frozen for hashing).

    Returns:
        SHA-256 hex digest of the combined inputs.
    """
    ctx = json.dumps(tool_context or {}, sort_keys=True)
    raw = f"{query}|{tool_name}|{ctx}"
    return hashlib.sha256(raw.encode()).hexdigest()


class QueryCache:
    """TTL-bounded in-memory cache for retrieval results.

    Args:
        max_size: Maximum number of cached entries.
        ttl:      Time-to-live in seconds for each entry.
        enabled:  Whether caching is active. When ``False``, all
                  operations are no-ops.
    """

    def __init__(
        self,
        max_size: int = 256,
        ttl: int = 300,
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=max_size, ttl=ttl)

    @property
    def enabled(self) -> bool:
        """Whether the cache is active."""
        return self._enabled

    def get(
        self,
        query: str,
        tool_name: str,
        tool_context: dict[str, str] | None,
    ) -> Any | None:
        """Look up a cached result.

        Args:
            query:        Raw query string.
            tool_name:    MCP tool name.
            tool_context: Optional tool parameters.

        Returns:
            Cached result or ``None`` on miss / disabled.
        """
        if not self._enabled:
            return None
        key = _make_cache_key(query, tool_name, tool_context)
        result = self._cache.get(key)
        if result is not None:
            logger.debug("cache.hit", key=key[:12])
        return result

    def put(
        self,
        query: str,
        tool_name: str,
        tool_context: dict[str, str] | None,
        result: Any,
    ) -> None:
        """Store a result in the cache.

        Args:
            query:        Raw query string.
            tool_name:    MCP tool name.
            tool_context: Optional tool parameters.
            result:       The retrieval result to cache.
        """
        if not self._enabled:
            return
        key = _make_cache_key(query, tool_name, tool_context)
        self._cache[key] = result
        logger.debug("cache.put", key=key[:12])

    def invalidate(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        logger.info("cache.invalidated")

    @property
    def size(self) -> int:
        """Current number of entries in the cache."""
        return len(self._cache)
