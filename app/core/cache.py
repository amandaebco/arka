"""Central caching module for ARKA.

Provides TTL-based in-memory caching for GraphRAG queries, vector searches,
and heavy retrieval operations. Includes function decorators for both sync and
async functions, with cache hit/miss statistics.
"""

import asyncio
import functools
import hashlib
import json
import time
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    """Thread-safe In-Memory TTL Cache with statistics."""

    def __init__(self, default_ttl: int = 3600, maxsize: int = 1000):
        self.default_ttl = default_ttl
        self.maxsize = maxsize
        self._store: Dict[str, Tuple[Any, float]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expiry = self._store[key]
            if time.time() < expiry:
                self.hits += 1
                return value
            # Expired
            del self._store[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if len(self._store) >= self.maxsize:
            self._evict_expired_or_oldest()
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        self._store[key] = (value, expiry)

    def clear(self) -> None:
        self._store.clear()
        self.hits = 0
        self.misses = 0

    def size(self) -> int:
        self._cleanup_expired()
        return len(self._store)

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_ratio = (self.hits / total) if total > 0 else 0.0
        return {
            "size": self.size(),
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": round(hit_ratio, 4),
        }

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._store.items() if now >= exp]
        for k in expired_keys:
            del self._store[k]

    def _evict_expired_or_oldest(self) -> None:
        self._cleanup_expired()
        if len(self._store) >= self.maxsize:
            # Evict earliest expiring key
            oldest_key = min(self._store.keys(), key=lambda k: self._store[k][1])
            del self._store[oldest_key]


# Global cache instances
graph_cache = TTLCache(default_ttl=1800, maxsize=500)
vector_cache = TTLCache(default_ttl=1800, maxsize=500)
general_cache = TTLCache(default_ttl=3600, maxsize=1000)


def _make_key(prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    serialized = json.dumps(
        {"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}},
        sort_keys=True,
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{func_name}:{digest}" if prefix else f"{func_name}:{digest}"


def cached(cache_instance: Optional[TTLCache] = None, ttl: Optional[int] = None, prefix: str = ""):
    """Decorator to cache return values of sync and async functions."""
    target_cache = cache_instance or general_cache

    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = _make_key(prefix, func.__name__, args, kwargs)
                cached_val = target_cache.get(key)
                if cached_val is not None:
                    return cached_val
                result = await func(*args, **kwargs)
                target_cache.set(key, result, ttl=ttl)
                return result

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                key = _make_key(prefix, func.__name__, args, kwargs)
                cached_val = target_cache.get(key)
                if cached_val is not None:
                    return cached_val
                result = func(*args, **kwargs)
                target_cache.set(key, result, ttl=ttl)
                return result

            return sync_wrapper

    return decorator
