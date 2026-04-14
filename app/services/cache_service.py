"""
In-memory TTL cache for analytics endpoints.

Why cache analytics queries?
  Analytics queries aggregate thousands of rows (e.g. all results for a driver
  across 15 seasons = ~300 rows with GROUP BY). These are expensive to compute
  but the underlying data rarely changes (historical F1 data is static).

  Without caching:   every call recomputes the aggregation → slow, DB-heavy
  With TTL caching:  first call computes + stores, next calls return instantly

Implementation: cachetools.TTLCache
  - TTLCache is a dict-like container with a maximum size and a TTL (time-to-live)
  - Each entry automatically expires after `ttl` seconds
  - When the cache is full, the least-recently-used entry is evicted
  - Thread-safe when combined with a Lock

Design decision: why NOT Redis?
  Redis would be the production choice for distributed caching across multiple
  servers. For this single-server project, in-memory caching:
    1. Has zero infrastructure overhead (no extra service to deploy/monitor)
    2. Is faster than Redis (no network round-trip)
    3. Is sufficient — PythonAnywhere runs a single process
  The architecture is identical; switching to Redis later requires only changing
  the cache backend, not the business logic.

Cache key strategy:
  Each analytics function has a unique prefix + its parameters as the key.
  Example: "driver_performance:123:2010:2023"
  This ensures different queries never collide.
"""

from cachetools import TTLCache
from threading import Lock
from typing import Any, Optional
import json

# One cache per analytics category — different TTLs reflect how "stale" each can be
# driver/team aggregations change only when new races are imported → 10 min TTL
# season highlights are fully static → 30 min TTL
_analytics_cache: TTLCache = TTLCache(maxsize=256, ttl=600)   # 10 minutes
_season_cache: TTLCache = TTLCache(maxsize=100, ttl=1800)     # 30 minutes
_lock = Lock()


def _make_key(*args) -> str:
    """Build a deterministic cache key from any combination of arguments."""
    return ":".join(str(a) for a in args)


def cache_get(cache: TTLCache, *key_parts) -> Optional[Any]:
    """
    Retrieve a cached value. Returns None on miss.
    Uses a lock so concurrent requests don't get a race condition on the cache dict.
    """
    key = _make_key(*key_parts)
    with _lock:
        return cache.get(key)


def cache_set(cache: TTLCache, value: Any, *key_parts) -> None:
    """Store a value in the cache under the given key."""
    key = _make_key(*key_parts)
    with _lock:
        cache[key] = value


# Convenience accessors — callers use these rather than the raw cache objects
def get_analytics(key: str) -> Optional[Any]:
    return cache_get(_analytics_cache, key)


def set_analytics(key: str, value: Any) -> None:
    cache_set(_analytics_cache, value, key)


def get_season(key: str) -> Optional[Any]:
    return cache_get(_season_cache, key)


def set_season(key: str, value: Any) -> None:
    cache_set(_season_cache, value, key)
