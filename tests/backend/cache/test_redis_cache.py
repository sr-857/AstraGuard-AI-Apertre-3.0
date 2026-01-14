"""
Tests for RedisCache implementation.

Tests use mocked Redis to avoid external dependencies.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.cache.redis_cache import RedisCache


# ============================================================================
# MOCK FIXTURES
# ============================================================================


@pytest.fixture
def mock_storage():
    """Create mock storage for Redis cache tests."""
    storage = AsyncMock()
    storage.get = AsyncMock(return_value=None)
    storage.set = AsyncMock(return_value=True)
    storage.delete = AsyncMock(return_value=True)
    storage.keys = AsyncMock(return_value=[])
    return storage


@pytest.fixture
def cache_with_mock(mock_storage):
    """Create RedisCache with mocked storage."""
    cache = RedisCache(storage=mock_storage, default_ttl=60)
    return cache


# ============================================================================
# BASIC OPERATIONS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_set_and_get(cache_with_mock, mock_storage):
    """Test basic set and get operations."""
    mock_storage.get.return_value = '{"data": "value"}'
    
    await cache_with_mock.set("key", {"data": "value"})
    result = await cache_with_mock.get("key")
    
    assert result == {"data": "value"}
    mock_storage.set.assert_called_once()
    mock_storage.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_missing_key(cache_with_mock, mock_storage):
    """Test get returns None for missing key."""
    mock_storage.get.return_value = None
    
    result = await cache_with_mock.get("nonexistent")
    
    assert result is None


@pytest.mark.asyncio
async def test_set_with_ttl(cache_with_mock, mock_storage):
    """Test set with custom TTL."""
    await cache_with_mock.set("key", "value", ttl=30)
    
    # Verify TTL was passed to storage
    mock_storage.set.assert_called_once()
    call_kwargs = mock_storage.set.call_args
    assert call_kwargs[1]["ttl"] == 30


@pytest.mark.asyncio
async def test_set_uses_default_ttl(cache_with_mock, mock_storage):
    """Test set uses default TTL when not specified."""
    cache_with_mock._default_ttl = 120
    
    await cache_with_mock.set("key", "value")
    
    call_kwargs = mock_storage.set.call_args
    assert call_kwargs[1]["ttl"] == 120


@pytest.mark.asyncio
async def test_invalidate(cache_with_mock, mock_storage):
    """Test invalidating a cache entry."""
    mock_storage.delete.return_value = True
    
    result = await cache_with_mock.invalidate("key")
    
    assert result is True
    mock_storage.delete.assert_called_once()


@pytest.mark.asyncio
async def test_invalidate_missing_key(cache_with_mock, mock_storage):
    """Test invalidating non-existent key."""
    mock_storage.delete.return_value = False
    
    result = await cache_with_mock.invalidate("nonexistent")
    
    assert result is False


@pytest.mark.asyncio
async def test_clear(cache_with_mock, mock_storage):
    """Test clearing all cache entries."""
    mock_storage.keys.return_value = [
        "astra:cache:key1",
        "astra:cache:key2",
        "astra:cache:key3",
    ]
    mock_storage.delete.return_value = True
    
    count = await cache_with_mock.clear()
    
    assert count == 3
    assert mock_storage.delete.call_count == 3


@pytest.mark.asyncio
async def test_clear_empty(cache_with_mock, mock_storage):
    """Test clearing when cache is empty."""
    mock_storage.keys.return_value = []
    
    count = await cache_with_mock.clear()
    
    assert count == 0


# ============================================================================
# SERIALIZATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_serialization_dict(cache_with_mock, mock_storage):
    """Test dictionary serialization."""
    test_data = {"key": "value", "nested": {"a": 1}}
    mock_storage.get.return_value = '{"key": "value", "nested": {"a": 1}}'
    
    await cache_with_mock.set("key", test_data)
    result = await cache_with_mock.get("key")
    
    assert result == test_data


@pytest.mark.asyncio
async def test_serialization_list(cache_with_mock, mock_storage):
    """Test list serialization."""
    test_data = [1, 2, "three", {"four": 4}]
    mock_storage.get.return_value = '[1, 2, "three", {"four": 4}]'
    
    await cache_with_mock.set("key", test_data)
    result = await cache_with_mock.get("key")
    
    assert result == test_data


@pytest.mark.asyncio
async def test_deserialization_error(cache_with_mock, mock_storage):
    """Test handling of deserialization errors."""
    mock_storage.get.return_value = "not valid json"
    
    result = await cache_with_mock.get("key")
    
    assert result is None


@pytest.mark.asyncio
async def test_serialization_error(cache_with_mock, mock_storage):
    """Test handling of non-serializable values."""
    class NonSerializable:
        pass
    
    result = await cache_with_mock.set("key", NonSerializable())
    
    assert result is False


# ============================================================================
# KEY PREFIX TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_key_prefix(mock_storage):
    """Test keys are prefixed correctly."""
    cache = RedisCache(
        storage=mock_storage, 
        key_prefix="custom:prefix:"
    )
    
    await cache.set("mykey", "value")
    
    # Verify key was prefixed
    call_args = mock_storage.set.call_args[0]
    assert call_args[0] == "custom:prefix:mykey"


@pytest.mark.asyncio
async def test_default_key_prefix(mock_storage):
    """Test default key prefix."""
    cache = RedisCache(storage=mock_storage)
    
    await cache.set("mykey", "value")
    
    call_args = mock_storage.set.call_args[0]
    assert call_args[0].startswith("astra:cache:")


# ============================================================================
# STATISTICS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_stats_hits(cache_with_mock, mock_storage):
    """Test hit counting."""
    mock_storage.get.return_value = '"cached"'
    
    await cache_with_mock.get("key")
    await cache_with_mock.get("key")
    
    stats = cache_with_mock.stats()
    assert stats.hits == 2


@pytest.mark.asyncio
async def test_stats_misses(cache_with_mock, mock_storage):
    """Test miss counting."""
    mock_storage.get.return_value = None
    
    await cache_with_mock.get("key1")
    await cache_with_mock.get("key2")
    
    stats = cache_with_mock.stats()
    assert stats.misses == 2


@pytest.mark.asyncio
async def test_reset_stats(cache_with_mock, mock_storage):
    """Test resetting statistics."""
    mock_storage.get.return_value = '"value"'
    
    await cache_with_mock.get("key")
    cache_with_mock.reset_stats()
    
    stats = cache_with_mock.stats()
    assert stats.hits == 0
    assert stats.misses == 0


@pytest.mark.asyncio
async def test_get_size(cache_with_mock, mock_storage):
    """Test getting cache size."""
    mock_storage.keys.return_value = [
        "astra:cache:a",
        "astra:cache:b",
        "astra:cache:c",
    ]
    
    size = await cache_with_mock.get_size()
    
    assert size == 3


# ============================================================================
# CONNECTION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_not_connected(mock_storage):
    """Test behavior when not connected."""
    cache = RedisCache(storage=None, redis_url="redis://invalid")
    cache._connected = False
    
    # Mock connect to fail
    with patch.object(cache, 'connect', new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = False
        
        result = await cache.get("key")
        
        assert result is None
        assert cache.stats().misses == 1


@pytest.mark.asyncio
async def test_connection_error_handling(cache_with_mock, mock_storage):
    """Test graceful handling of connection errors."""
    mock_storage.get.side_effect = ConnectionError("Redis unavailable")
    
    result = await cache_with_mock.get("key")
    
    assert result is None


# ============================================================================
# METRICS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_metrics_emission_on_hit(mock_storage):
    """Test metrics are emitted on cache hit."""
    mock_sink = MagicMock()
    cache = RedisCache(storage=mock_storage, metrics_sink=mock_sink)
    mock_storage.get.return_value = '"value"'
    
    await cache.get("key")
    
    mock_sink.emit_counter.assert_called_once()
    mock_sink.emit_histogram.assert_called_once()


@pytest.mark.asyncio
async def test_metrics_emission_on_miss(mock_storage):
    """Test metrics are emitted on cache miss."""
    mock_sink = MagicMock()
    cache = RedisCache(storage=mock_storage, metrics_sink=mock_sink)
    mock_storage.get.return_value = None
    
    await cache.get("key")
    
    mock_sink.emit_counter.assert_called()
    assert any(
        "cache_misses" in str(call) 
        for call in mock_sink.emit_counter.call_args_list
    )
