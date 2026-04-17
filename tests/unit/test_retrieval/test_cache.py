"""Unit tests for the query result cache."""

from __future__ import annotations



from odyssey_rag.retrieval.cache import QueryCache, _make_cache_key


class TestMakeCacheKey:
    """Tests for the _make_cache_key helper."""

    def test_same_inputs_produce_same_key(self) -> None:
        """Identical inputs produce the same cache key."""
        k1 = _make_cache_key("query", "tool", {"a": "1"})
        k2 = _make_cache_key("query", "tool", {"a": "1"})
        assert k1 == k2

    def test_different_queries_produce_different_keys(self) -> None:
        """Different query strings produce different keys."""
        k1 = _make_cache_key("query A", "tool", None)
        k2 = _make_cache_key("query B", "tool", None)
        assert k1 != k2

    def test_different_tools_produce_different_keys(self) -> None:
        """Different tool names produce different keys."""
        k1 = _make_cache_key("query", "tool_a", None)
        k2 = _make_cache_key("query", "tool_b", None)
        assert k1 != k2

    def test_different_context_produce_different_keys(self) -> None:
        """Different tool contexts produce different keys."""
        k1 = _make_cache_key("query", "tool", {"a": "1"})
        k2 = _make_cache_key("query", "tool", {"a": "2"})
        assert k1 != k2

    def test_none_context_equals_empty_dict(self) -> None:
        """None context and empty dict produce the same key."""
        k1 = _make_cache_key("query", "tool", None)
        k2 = _make_cache_key("query", "tool", {})
        assert k1 == k2

    def test_dict_order_invariant(self) -> None:
        """Key is the same regardless of dict insertion order."""
        k1 = _make_cache_key("query", "tool", {"a": "1", "b": "2"})
        k2 = _make_cache_key("query", "tool", {"b": "2", "a": "1"})
        assert k1 == k2

    def test_key_is_hex_string(self) -> None:
        """Cache key is a 64-char hex string (SHA-256)."""
        key = _make_cache_key("query", "tool", None)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestQueryCache:
    """Tests for the QueryCache class."""

    def test_get_returns_none_on_miss(self) -> None:
        """get() returns None for an uncached query."""
        cache = QueryCache(max_size=10, ttl=60)
        result = cache.get("query", "tool", None)
        assert result is None

    def test_put_and_get_roundtrip(self) -> None:
        """put() stores a result that get() can retrieve."""
        cache = QueryCache(max_size=10, ttl=60)
        sentinel = {"evidence": [1, 2, 3]}
        cache.put("query", "tool", None, sentinel)
        result = cache.get("query", "tool", None)
        assert result is sentinel

    def test_different_queries_are_separate(self) -> None:
        """Different queries are stored independently."""
        cache = QueryCache(max_size=10, ttl=60)
        cache.put("query_a", "tool", None, "result_a")
        cache.put("query_b", "tool", None, "result_b")
        assert cache.get("query_a", "tool", None) == "result_a"
        assert cache.get("query_b", "tool", None) == "result_b"

    def test_disabled_cache_always_misses(self) -> None:
        """When disabled, get() always returns None."""
        cache = QueryCache(enabled=False)
        cache.put("query", "tool", None, "result")
        assert cache.get("query", "tool", None) is None

    def test_disabled_cache_put_is_noop(self) -> None:
        """When disabled, put() does not store anything."""
        cache = QueryCache(enabled=False)
        cache.put("query", "tool", None, "result")
        assert cache.size == 0

    def test_invalidate_clears_cache(self) -> None:
        """invalidate() removes all entries."""
        cache = QueryCache(max_size=10, ttl=300)
        cache.put("q1", "t", None, "r1")
        cache.put("q2", "t", None, "r2")
        assert cache.size == 2
        cache.invalidate()
        assert cache.size == 0
        assert cache.get("q1", "t", None) is None

    def test_max_size_eviction(self) -> None:
        """Cache evicts oldest entries when max_size is exceeded."""
        cache = QueryCache(max_size=2, ttl=300)
        cache.put("q1", "t", None, "r1")
        cache.put("q2", "t", None, "r2")
        cache.put("q3", "t", None, "r3")
        # q1 should have been evicted
        assert cache.size == 2
        assert cache.get("q3", "t", None) == "r3"

    def test_size_property(self) -> None:
        """size returns the current entry count."""
        cache = QueryCache(max_size=10, ttl=300)
        assert cache.size == 0
        cache.put("q1", "t", None, "r1")
        assert cache.size == 1

    def test_enabled_property(self) -> None:
        """enabled reflects the initialization flag."""
        assert QueryCache(enabled=True).enabled is True
        assert QueryCache(enabled=False).enabled is False

    def test_with_tool_context(self) -> None:
        """Caching works correctly with tool_context dict."""
        cache = QueryCache(max_size=10, ttl=300)
        ctx = {"message_type": "pacs.008", "focus": "fields"}
        cache.put("query", "find_message_type", ctx, "result_ctx")
        assert cache.get("query", "find_message_type", ctx) == "result_ctx"
        # Different context = miss
        assert cache.get("query", "find_message_type", {"message_type": "camt.053"}) is None
