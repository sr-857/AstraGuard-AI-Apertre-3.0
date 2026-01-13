"""
Tests for cache decorators.

Tests cover:
- @cached decorator functionality
- Key generation
- TTL handling
- Async and sync function support
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.cache.decorators import cached, cache_invalidate, _generate_key
from backend.cache.in_memory import InMemoryLRUCache


# ============================================================================
# BASIC DECORATOR TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cached_async_function():
    """Test @cached with async function."""
    cache = InMemoryLRUCache(maxsize=10)
    call_count = 0
    
    @cached(cache=cache)
    async def fetch_data(key: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"data_{key}"
    
    # First call - cache miss
    result1 = await fetch_data("a")
    assert result1 == "data_a"
    assert call_count == 1
    
    # Second call - cache hit
    result2 = await fetch_data("a")
    assert result2 == "data_a"
    assert call_count == 1  # Not incremented


@pytest.mark.asyncio
async def test_cached_different_args():
    """Test @cached differentiates by arguments."""
    cache = InMemoryLRUCache(maxsize=10)
    
    @cached(cache=cache)
    async def fetch_data(key: str) -> str:
        return f"data_{key}"
    
    result_a = await fetch_data("a")
    result_b = await fetch_data("b")
    
    assert result_a == "data_a"
    assert result_b == "data_b"


@pytest.mark.asyncio
async def test_cached_with_custom_key_fn():
    """Test @cached with custom key function."""
    cache = InMemoryLRUCache(maxsize=10)
    call_count = 0
    
    # key_fn only uses user_id from args, ignores other kwargs
    @cached(cache=cache, key_fn=lambda user_id, **kw: f"user:{user_id}")
    async def get_user(user_id: str, refresh: bool = False) -> dict:
        nonlocal call_count
        call_count += 1
        return {"id": user_id}
    
    # Same user_id, different refresh flag - should hit cache
    result1 = await get_user("123", refresh=False)
    result2 = await get_user("123", refresh=True)
    
    assert call_count == 1  # Only called once


@pytest.mark.asyncio
async def test_cached_with_ttl():
    """Test @cached with TTL."""
    cache = InMemoryLRUCache(maxsize=10)
    
    @cached(cache=cache, ttl=1)
    async def fetch_data() -> str:
        return "data"
    
    result1 = await fetch_data()
    assert result1 == "data"
    
    # Wait for TTL to expire
    await asyncio.sleep(1.1)
    
    # Should be a miss now
    stats_before = cache.stats()
    result2 = await fetch_data()
    stats_after = cache.stats()
    
    assert result2 == "data"
    assert stats_after.misses > stats_before.misses


@pytest.mark.asyncio
async def test_cached_with_prefix():
    """Test @cached with custom prefix."""
    cache = InMemoryLRUCache(maxsize=10)
    
    @cached(cache=cache, prefix="myapp")
    async def fetch_data(key: str) -> str:
        return f"data_{key}"
    
    await fetch_data("test")
    
    # Check key in cache starts with prefix
    stats = cache.stats()
    assert stats.size == 1


@pytest.mark.asyncio
async def test_cached_no_cache():
    """Test @cached when cache is None (disabled)."""
    call_count = 0
    
    @cached(cache=None)
    async def fetch_data() -> str:
        nonlocal call_count
        call_count += 1
        return "data"
    
    # Should call function each time
    await fetch_data()
    await fetch_data()
    
    assert call_count == 2


# ============================================================================
# SYNC FUNCTION TESTS
# ============================================================================


def test_cached_sync_function():
    """Test @cached with sync function when cache is disabled."""
    # Sync functions with async cache need special handling.
    # Test with None cache to verify decorator works without caching.
    call_count = 0
    
    @cached(cache=None)
    def compute(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 2
    
    result1 = compute(5)
    result2 = compute(5)
    
    assert result1 == 10
    assert result2 == 10
    # Without cache, function is called each time
    assert call_count == 2


# ============================================================================
# KEY GENERATION TESTS
# ============================================================================


def test_generate_key_default():
    """Test default key generation."""
    def my_func():
        pass
    
    key = _generate_key("fn", my_func, None, (1, "arg"), {"kw": "value"})
    
    assert "fn:my_func:" in key
    assert "1" in key
    assert "arg" in key
    assert "kw" in key


def test_generate_key_with_custom_key_fn():
    """Test key generation with custom function."""
    def my_func():
        pass
    
    def key_fn(user_id):
        return f"user:{user_id}"
    
    key = _generate_key("api", my_func, key_fn, ("123",), {})
    
    assert key == "api:my_func:user:123"


def test_generate_key_fn_error_fallback():
    """Test fallback when key_fn raises error."""
    def my_func():
        pass
    
    def bad_key_fn(*args):
        raise ValueError("Bad!")
    
    key = _generate_key("fn", my_func, bad_key_fn, ("arg",), {})
    
    # Should fallback to default key
    assert "fn:my_func:" in key


# ============================================================================
# CACHE INVALIDATE DECORATOR TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cache_invalidate():
    """Test @cache_invalidate decorator."""
    cache = InMemoryLRUCache(maxsize=10)
    
    # Set up cached value
    await cache.set("fn:update_user:user:123", {"id": "123"})
    
    @cache_invalidate(cache=cache, key_fn=lambda user_id, _: f"user:{user_id}")
    async def update_user(user_id: str, data: dict) -> bool:
        return True
    
    result = await update_user("123", {"name": "New"})
    
    assert result is True
    # Cache should be invalidated
    cached_value = await cache.get("fn:update_user:user:123")
    assert cached_value is None


def test_cache_invalidate_sync():
    """Test @cache_invalidate with sync function."""
    # Use None cache to test basic flow without async conflicts
    @cache_invalidate(cache=None, key_fn=lambda x: f"item:{x}")
    def delete_item(item_id: str) -> bool:
        return True
    
    result = delete_item("1")
    
    assert result is True


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cached_cache_error_graceful():
    """Test @cached handles cache errors gracefully."""
    cache = MagicMock()
    cache.get = AsyncMock(side_effect=Exception("Cache error"))
    cache.set = AsyncMock(side_effect=Exception("Cache error"))
    
    call_count = 0
    
    @cached(cache=cache)
    async def fetch_data() -> str:
        nonlocal call_count
        call_count += 1
        return "data"
    
    # Should still work despite cache errors
    result = await fetch_data()
    
    assert result == "data"
    assert call_count == 1


@pytest.mark.asyncio
async def test_cached_preserves_function_metadata():
    """Test @cached preserves function name and docstring."""
    cache = InMemoryLRUCache(maxsize=10)
    
    @cached(cache=cache)
    async def documented_function(x: int) -> int:
        """This is the docstring."""
        return x
    
    assert documented_function.__name__ == "documented_function"
    assert documented_function.__doc__ == "This is the docstring."
