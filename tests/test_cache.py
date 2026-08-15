import asyncio
import time

import pytest

from app.core.cache import TTLCache, cached


def test_ttl_cache_basic_get_set():
    cache = TTLCache(default_ttl=10, maxsize=10)
    cache.set("key1", "value1")

    assert cache.get("key1") == "value1"
    assert cache.get("key2") is None
    assert cache.size() == 1


def test_ttl_cache_expiration():
    cache = TTLCache(default_ttl=1, maxsize=10)
    cache.set("short_key", "short_val", ttl=1)

    assert cache.get("short_key") == "short_val"
    time.sleep(1.1)
    assert cache.get("short_key") is None


def test_ttl_cache_eviction_and_stats():
    cache = TTLCache(default_ttl=100, maxsize=2)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")  # Triggers eviction

    assert cache.size() <= 2
    stats = cache.stats()
    assert stats["hits"] == 0
    assert "hit_ratio" in stats


def test_sync_cached_decorator():
    cache = TTLCache(default_ttl=100)
    call_count = 0

    @cached(cache_instance=cache, prefix="test")
    def compute(a: int, b: int) -> int:
        nonlocal call_count
        call_count += 1
        return a + b

    val1 = compute(2, 3)
    val2 = compute(2, 3)

    assert val1 == 5
    assert val2 == 5
    assert call_count == 1  # Second call served from cache
    assert cache.stats()["hits"] == 1


@pytest.mark.asyncio
async def test_async_cached_decorator():
    cache = TTLCache(default_ttl=100)
    call_count = 0

    @cached(cache_instance=cache, prefix="async_test")
    async def async_compute(x: str) -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return x.upper()

    res1 = await async_compute("hello")
    res2 = await async_compute("hello")

    assert res1 == "HELLO"
    assert res2 == "HELLO"
    assert call_count == 1
    assert cache.stats()["hits"] == 1
