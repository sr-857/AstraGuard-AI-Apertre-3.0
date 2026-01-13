"""
Tests for InMemoryLRUCache implementation.

Tests cover:
- Basic get/set operations
- TTL expiration
- LRU eviction
- Thread-safety
- Statistics accuracy
"""

import pytest
import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor

from backend.cache.in_memory import InMemoryLRUCache
from backend.cache.interface import CacheStats


# ============================================================================
# BASIC OPERATIONS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_set_and_get():
    """Test basic set and get operations."""
    cache = InMemoryLRUCache(maxsize=10)
    
    await cache.set("key1", "value1")
    result = await cache.get("key1")
    
    assert result == "value1"


@pytest.mark.asyncio
async def test_get_missing_key():
    """Test get returns None for missing key."""
    cache = InMemoryLRUCache(maxsize=10)
    
    result = await cache.get("nonexistent")
    
    assert result is None


@pytest.mark.asyncio
async def test_set_overwrites_existing():
    """Test set overwrites existing value."""
    cache = InMemoryLRUCache(maxsize=10)
    
    await cache.set("key", "value1")
    await cache.set("key", "value2")
    result = await cache.get("key")
    
    assert result == "value2"


@pytest.mark.asyncio
async def test_set_complex_values():
    """Test caching complex data types."""
    cache = InMemoryLRUCache(maxsize=10)
    
    # Dictionary
    await cache.set("dict", {"nested": {"data": [1, 2, 3]}})
    assert await cache.get("dict") == {"nested": {"data": [1, 2, 3]}}
    
    # List
    await cache.set("list", [1, "two", 3.0])
    assert await cache.get("list") == [1, "two", 3.0]
    
    # Tuple
    await cache.set("tuple", (1, 2, 3))
    assert await cache.get("tuple") == (1, 2, 3)


@pytest.mark.asyncio
async def test_invalidate():
    """Test invalidating a cache entry."""
    cache = InMemoryLRUCache(maxsize=10)
    
    await cache.set("key", "value")
    assert await cache.get("key") == "value"
    
    result = await cache.invalidate("key")
    assert result is True
    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_invalidate_missing_key():
    """Test invalidating non-existent key returns False."""
    cache = InMemoryLRUCache(maxsize=10)
    
    result = await cache.invalidate("nonexistent")
    
    assert result is False


@pytest.mark.asyncio
async def test_clear():
    """Test clearing all cache entries."""
    cache = InMemoryLRUCache(maxsize=10)
    
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")
    
    count = await cache.clear()
    
    assert count == 3
    assert await cache.get("key1") is None
    assert await cache.get("key2") is None
    assert await cache.get("key3") is None


# ============================================================================
# TTL TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_ttl_expiration():
    """Test entries expire after TTL."""
    cache = InMemoryLRUCache(maxsize=10, default_ttl=1)
    
    await cache.set("key", "value")
    assert await cache.get("key") == "value"
    
    # Wait for expiration
    await asyncio.sleep(1.1)
    
    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_per_key_ttl():
    """Test per-key TTL overrides default."""
    cache = InMemoryLRUCache(maxsize=10, default_ttl=10)
    
    await cache.set("short", "value", ttl=1)
    await cache.set("long", "value", ttl=10)
    
    await asyncio.sleep(1.1)
    
    assert await cache.get("short") is None
    assert await cache.get("long") == "value"


@pytest.mark.asyncio
async def test_no_ttl():
    """Test entries without TTL don't expire."""
    cache = InMemoryLRUCache(maxsize=10)  # No default TTL
    
    await cache.set("key", "value")
    
    # Get multiple times
    for _ in range(10):
        assert await cache.get("key") == "value"


@pytest.mark.asyncio
async def test_cleanup_expired():
    """Test manual cleanup of expired entries."""
    cache = InMemoryLRUCache(maxsize=10, default_ttl=1)
    
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    
    await asyncio.sleep(1.1)
    
    removed = await cache.cleanup_expired()
    
    assert removed == 2


# ============================================================================
# LRU EVICTION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_lru_eviction():
    """Test LRU eviction when maxsize is reached."""
    cache = InMemoryLRUCache(maxsize=3)
    
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")
    
    # Access key1 to make it recently used
    await cache.get("key1")
    
    # Add key4, should evict key2 (least recently used)
    await cache.set("key4", "value4")
    
    assert await cache.get("key1") == "value1"  # Still present
    assert await cache.get("key2") is None       # Evicted
    assert await cache.get("key3") == "value3"  # Still present
    assert await cache.get("key4") == "value4"  # New entry


@pytest.mark.asyncio
async def test_eviction_order():
    """Test eviction follows LRU order."""
    cache = InMemoryLRUCache(maxsize=3)
    
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.set("c", 3)
    
    # Access in order: b, a (c is now LRU)
    await cache.get("b")
    await cache.get("a")
    
    # Add d, should evict c
    await cache.set("d", 4)
    
    assert await cache.get("c") is None
    assert await cache.get("a") == 1
    assert await cache.get("b") == 2
    assert await cache.get("d") == 4


@pytest.mark.asyncio
async def test_update_moves_to_mru():
    """Test updating a key moves it to most recently used."""
    cache = InMemoryLRUCache(maxsize=3)
    
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.set("c", 3)
    
    # Update a (moves to MRU)
    await cache.set("a", 10)
    
    # Add d, should evict b (LRU)
    await cache.set("d", 4)
    
    assert await cache.get("a") == 10
    assert await cache.get("b") is None
    assert await cache.get("c") == 3
    assert await cache.get("d") == 4


# ============================================================================
# STATISTICS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_stats_hits_and_misses():
    """Test hit and miss counting."""
    cache = InMemoryLRUCache(maxsize=10)
    
    await cache.set("key", "value")
    
    await cache.get("key")      # Hit
    await cache.get("key")      # Hit
    await cache.get("missing")  # Miss
    
    stats = cache.stats()
    
    assert stats.hits == 2
    assert stats.misses == 1


@pytest.mark.asyncio
async def test_stats_evictions():
    """Test eviction counting."""
    cache = InMemoryLRUCache(maxsize=2)
    
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.set("c", 3)  # Evicts a
    await cache.set("d", 4)  # Evicts b
    
    stats = cache.stats()
    
    assert stats.evictions == 2


@pytest.mark.asyncio
async def test_stats_size():
    """Test size reporting."""
    cache = InMemoryLRUCache(maxsize=10)
    
    assert cache.stats().size == 0
    
    await cache.set("a", 1)
    await cache.set("b", 2)
    
    assert cache.stats().size == 2
    
    await cache.invalidate("a")
    
    assert cache.stats().size == 1


@pytest.mark.asyncio
async def test_stats_hit_rate():
    """Test hit rate calculation."""
    cache = InMemoryLRUCache(maxsize=10)
    
    await cache.set("key", "value")
    
    await cache.get("key")      # Hit
    await cache.get("key")      # Hit
    await cache.get("key")      # Hit
    await cache.get("missing")  # Miss
    
    stats = cache.stats()
    
    assert stats.hit_rate() == 0.75


@pytest.mark.asyncio
async def test_reset_stats():
    """Test resetting statistics."""
    cache = InMemoryLRUCache(maxsize=10)
    
    await cache.set("key", "value")
    await cache.get("key")
    await cache.get("missing")
    
    cache.reset_stats()
    stats = cache.stats()
    
    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.evictions == 0
    assert stats.size == 1  # Size is not reset


# ============================================================================
# THREAD-SAFETY TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_access():
    """Test thread-safe concurrent access."""
    cache = InMemoryLRUCache(maxsize=100)
    errors = []
    
    async def writer(start: int):
        for i in range(start, start + 50):
            try:
                await cache.set(f"key{i}", f"value{i}")
            except Exception as e:
                errors.append(e)
    
    async def reader():
        for i in range(100):
            try:
                await cache.get(f"key{i}")
            except Exception as e:
                errors.append(e)
    
    # Run concurrent writers and readers
    tasks = [
        writer(0),
        writer(50),
        reader(),
        reader(),
    ]
    await asyncio.gather(*tasks)
    
    assert len(errors) == 0


def test_thread_safety_sync():
    """Test thread-safe access from multiple threads."""
    cache = InMemoryLRUCache(maxsize=100)
    errors = []
    
    def sync_set(key: str, value: str):
        try:
            asyncio.run(cache.set(key, value))
        except Exception as e:
            errors.append(e)
    
    def sync_get(key: str):
        try:
            asyncio.run(cache.get(key))
        except Exception as e:
            errors.append(e)
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(50):
            futures.append(executor.submit(sync_set, f"key{i}", f"value{i}"))
        for i in range(50):
            futures.append(executor.submit(sync_get, f"key{i}"))
        
        for future in futures:
            future.result()
    
    assert len(errors) == 0


# ============================================================================
# GET_OR_SET TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_or_set_miss():
    """Test get_or_set computes value on miss."""
    cache = InMemoryLRUCache(maxsize=10)
    call_count = 0
    
    async def factory():
        nonlocal call_count
        call_count += 1
        return "computed"
    
    result = await cache.get_or_set("key", factory)
    
    assert result == "computed"
    assert call_count == 1


@pytest.mark.asyncio
async def test_get_or_set_hit():
    """Test get_or_set returns cached value on hit."""
    cache = InMemoryLRUCache(maxsize=10)
    call_count = 0
    
    async def factory():
        nonlocal call_count
        call_count += 1
        return "computed"
    
    await cache.set("key", "cached")
    result = await cache.get_or_set("key", factory)
    
    assert result == "cached"
    assert call_count == 0  # Factory not called


@pytest.mark.asyncio
async def test_get_or_set_sync_factory():
    """Test get_or_set with sync factory function."""
    cache = InMemoryLRUCache(maxsize=10)
    
    def factory():
        return "sync_computed"
    
    result = await cache.get_or_set("key", factory)
    
    assert result == "sync_computed"
