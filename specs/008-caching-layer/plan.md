# Implementation Plan: Multi-Tier Caching Layer & Performance Optimization

## Architecture & Components

1. **`app/core/cache.py`**:
   - `TTLCache`: In-memory thread-safe dictionary with TTL expiration, maxsize eviction policy, and hit/miss metrics tracking.
   - Global cache instances:
     - `graph_cache` (TTL: 1800s, maxsize: 500)
     - `vector_cache` (TTL: 1800s, maxsize: 500)
     - `general_cache` (TTL: 3600s, maxsize: 1000)
   - Decorator `@cached`: Handles automatic key generation using SHA256 digest of serialized arguments and supports sync/async functions.

2. **Integration Points**:
   - `app/graph/neighborhood.py`: Caching graph neighborhood queries per equipment tag.
   - `app/retrieval/vector_store.py`: Caching vector similarity search results.

3. **Validation & Testing**:
   - `tests/test_cache.py`: Unit testing for `TTLCache`, decorator, TTL expiration, maxsize eviction, and stats accuracy.
