# Cache & Performance Optimizations

This document describes the caching layer introduced in the `backend/cache` package.

## Quick Start

```python
from backend.cache import InMemoryLRUCache, cached, create_cache

# Option 1: Create cache directly
cache = InMemoryLRUCache(maxsize=1024, default_ttl=60)

# Option 2: Use configuration (respects environment variables)
cache = create_cache()

# Cache function results with decorator
@cached(cache=cache, key_fn=lambda user_id: f"user:{user_id}")
async def get_user(user_id: str) -> dict:
    return await database.fetch_user(user_id)
```

## Configuration

The cache is **disabled by default** and controlled via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_ENABLED` | `false` | Enable/disable caching |
| `CACHE_BACKEND` | `memory` | Backend: `memory` or `redis` |
| `CACHE_MAXSIZE` | `1024` | Max entries (memory cache) |
| `CACHE_TTL_SECONDS` | `60` | Default TTL in seconds |
| `CACHE_REDIS_URL` | `redis://localhost:6379` | Redis URL |
| `CACHE_KEY_PREFIX` | `astra:cache:` | Key prefix |

## Cache Implementations

### InMemoryLRUCache

Thread-safe LRU cache with O(1) operations. Best for:
- Local development
- Staging environments  
- Single-instance deployments

```python
cache = InMemoryLRUCache(
    maxsize=1024,      # Max entries before eviction
    default_ttl=60,    # Default TTL in seconds
    metrics_sink=sink  # Optional: emit metrics
)

await cache.set("key", {"data": "value"}, ttl=30)
result = await cache.get("key")
await cache.invalidate("key")
```

### RedisCache

Redis-backed cache for distributed deployments. Best for:
- Production multi-instance deployments
- Shared cache across services

```python
from backend.cache import RedisCache

cache = RedisCache(
    redis_url="redis://localhost:6379",
    default_ttl=60,
    key_prefix="myapp:cache:"
)
```

## Decorators

### @cached

Cache function results automatically:

```python
from backend.cache import cached

@cached(
    cache=my_cache,     # Cache instance (optional, uses default)
    key_fn=lambda x: f"item:{x}",  # Key generator (optional)
    ttl=300,            # TTL override (optional)
    prefix="api"        # Key prefix (optional)
)
async def fetch_item(item_id: str) -> dict:
    return await db.get_item(item_id)
```

### @cache_invalidate

Invalidate cache after writes:

```python
from backend.cache.decorators import cache_invalidate

@cache_invalidate(
    cache=my_cache,
    key_fn=lambda user_id, _: f"user:{user_id}"
)
async def update_user(user_id: str, data: dict) -> bool:
    await db.update(user_id, data)
    return True
```

## Invalidation Strategies

### Single Key

```python
await cache.invalidate("user:123")
```

### Clear All

```python
await cache.clear()  # Use during migrations
```

## Metrics

When a `MetricsSink` is provided, the cache emits:

| Metric | Type | Description |
|--------|------|-------------|
| `cache_hits_total` | Counter | Cache hit count |
| `cache_misses_total` | Counter | Cache miss count |
| `cache_evictions_total` | Counter | LRU eviction count |
| `cache_latency_ms` | Histogram | Operation latency |

### Stats API

```python
stats = cache.stats()
print(f"Hit rate: {stats.hit_rate():.1%}")
print(f"Size: {stats.size}")
```

## Performance Tuning

### Memory Cache Sizing

Set `CACHE_MAXSIZE` based on:
- Available memory
- Average entry size
- Expected working set

### TTL Selection

- Short TTL (5-30s): Frequently changing data
- Medium TTL (60-300s): Semi-static data
- Long TTL (600-3600s): Configuration, lookups

## Testing

Run cache tests:

```bash
python -m pytest tests/backend/cache/ -v
```

Run benchmarks:

```bash
python benchmarks/cache_benchmarks.py
```
