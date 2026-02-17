"""
Comprehensive tests for storage abstraction layer.

Tests both MemoryStorage and compatibility shim imports.
For RedisAdapter, we test the interface but skip live Redis tests
unless explicitly enabled with REDIS_TEST_URL environment variable.
"""

import pytest
import asyncio
import time
import os
from typing import Type
from unittest.mock import MagicMock, patch

from backend.storage import Storage, MemoryStorage
from backend.storage.redis_adapter import RedisAdapter

# Configure pytest-asyncio to handle async fixtures and tests
pytest_plugins = ('pytest_asyncio',)


class TestMemoryStorage:
    """Test suite for in-memory storage implementation."""

    @pytest.fixture
    async def storage(self):
        """Create and cleanup memory storage."""
        store = MemoryStorage()
        await store.connect()
        yield store
        await store.close()

    @pytest.mark.asyncio
    async def test_connect(self, storage):
        """Test connection always succeeds for memory storage."""
        assert storage.connected is True
        assert await storage.health_check() is True

    @pytest.mark.asyncio
    async def test_set_and_get(self, storage):
        """Test basic set and get operations."""
        # Set a string value
        result = await storage.set("test:key", "test_value")
        assert result is True

        # Get the value back
        value = await storage.get("test:key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_set_and_get_dict(self, storage):
        """Test storing and retrieving dictionary values."""
        data = {"name": "test", "value": 42, "nested": {"key": "value"}}
        
        result = await storage.set("test:dict", data)
        assert result is True

        retrieved = await storage.get("test:dict")
        assert retrieved == data

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, storage):
        """Test getting a key that doesn't exist."""
        value = await storage.get("nonexistent:key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, storage):
        """Test deleting an existing key."""
        await storage.set("test:key", "value")
        
        result = await storage.delete("test:key")
        assert result is True

        # Verify key is gone
        value = await storage.get("test:key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, storage):
        """Test deleting a key that doesn't exist."""
        result = await storage.delete("nonexistent:key")
        assert result is False

    @pytest.mark.asyncio
    async def test_expire_on_set(self, storage):
        """Test setting expiration when storing a key."""
        # Set with 1 second expiry
        result = await storage.set("test:expire", "value", expire=1)
        assert result is True

        # Should exist immediately
        value = await storage.get("test:expire")
        assert value == "value"

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be gone
        value = await storage.get("test:expire")
        assert value is None

    @pytest.mark.asyncio
    async def test_expire_existing_key(self, storage):
        """Test setting expiration on an existing key."""
        # Set without expiration
        await storage.set("test:key", "value")

        # Set expiration
        result = await storage.expire("test:key", 1)
        assert result is True

        # Should exist immediately
        value = await storage.get("test:key")
        assert value == "value"

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be gone
        value = await storage.get("test:key")
        assert value is None

    @pytest.mark.asyncio
    async def test_expire_nonexistent_key(self, storage):
        """Test setting expiration on a nonexistent key."""
        result = await storage.expire("nonexistent:key", 60)
        assert result is False

    @pytest.mark.asyncio
    async def test_exists(self, storage):
        """Test checking key existence."""
        # Non-existent key
        exists = await storage.exists("test:key")
        assert exists is False

        # Create key
        await storage.set("test:key", "value")
        exists = await storage.exists("test:key")
        assert exists is True

        # Delete key
        await storage.delete("test:key")
        exists = await storage.exists("test:key")
        assert exists is False

    @pytest.mark.asyncio
    async def test_scan_keys_simple(self, storage):
        """Test scanning for keys with simple pattern."""
        # Set multiple keys
        await storage.set("user:1", "alice")
        await storage.set("user:2", "bob")
        await storage.set("product:1", "widget")
        await storage.set("product:2", "gadget")

        # Scan for user keys
        user_keys = await storage.scan_keys("user:*")
        assert set(user_keys) == {"user:1", "user:2"}

        # Scan for product keys
        product_keys = await storage.scan_keys("product:*")
        assert set(product_keys) == {"product:1", "product:2"}

    @pytest.mark.asyncio
    async def test_scan_keys_with_expiry(self, storage):
        """Test that scan excludes expired keys."""
        # Set keys with different expiry
        await storage.set("temp:1", "value1", expire=1)
        await storage.set("temp:2", "value2")  # No expiry

        # Should find both initially
        keys = await storage.scan_keys("temp:*")
        assert set(keys) == {"temp:1", "temp:2"}

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should only find non-expired key
        keys = await storage.scan_keys("temp:*")
        assert keys == ["temp:2"]

    @pytest.mark.asyncio
    async def test_scan_keys_no_matches(self, storage):
        """Test scanning with pattern that matches nothing."""
        await storage.set("user:1", "alice")
        
        keys = await storage.scan_keys("product:*")
        assert keys == []

    @pytest.mark.asyncio
    async def test_health_check(self, storage):
        """Test health check returns True when connected."""
        assert await storage.health_check() is True

        # Close and check again
        await storage.close()
        assert await storage.health_check() is False

    @pytest.mark.asyncio
    async def test_clear_all(self, storage):
        """Test clearing all data."""
        # Set multiple keys
        await storage.set("key1", "value1")
        await storage.set("key2", "value2")
        await storage.set("key3", "value3")

        # Clear all
        await storage.clear_all()

        # Verify all gone
        assert await storage.get("key1") is None
        assert await storage.get("key2") is None
        assert await storage.get("key3") is None

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, storage):
        """Test concurrent access to storage."""
        # Run multiple set/get operations concurrently
        async def set_get(key: str, value: str):
            await storage.set(key, value)
            result = await storage.get(key)
            assert result == value

        # Execute 10 concurrent operations
        tasks = [
            set_get(f"concurrent:{i}", f"value_{i}")
            for i in range(10)
        ]
        await asyncio.gather(*tasks)

        # Verify all keys exist
        keys = await storage.scan_keys("concurrent:*")
        assert len(keys) == 10


class TestRedisAdapterUnit:
    """Unit tests for RedisAdapter using mocks."""

    @pytest.mark.asyncio
    async def test_from_url_success(self):
        """Test from_url succeeds when connect succeeds."""
        with patch.object(RedisAdapter, 'connect', new_callable=MagicMock) as mock_connect:
            # Mock connect to return an awaitable that returns True
            f = asyncio.Future()
            f.set_result(True)
            mock_connect.return_value = f

            adapter = await RedisAdapter.from_url("redis://localhost:6379")

            assert isinstance(adapter, RedisAdapter)
            assert adapter.redis_url == "redis://localhost:6379"
            assert mock_connect.called
            assert mock_connect.call_count == 1

    @pytest.mark.asyncio
    async def test_from_url_retry_success(self):
        """Test from_url retries and eventually succeeds."""
        with patch.object(RedisAdapter, 'connect', new_callable=MagicMock) as mock_connect:
            with patch('asyncio.sleep', new_callable=MagicMock) as mock_sleep:
                # Mock sleep to return immediately
                f_sleep = asyncio.Future()
                f_sleep.set_result(None)
                mock_sleep.return_value = f_sleep

                # Mock connect to fail twice then succeed
                f_fail = asyncio.Future()
                f_fail.set_result(False)
                f_success = asyncio.Future()
                f_success.set_result(True)

                mock_connect.side_effect = [f_fail, f_fail, f_success]

                adapter = await RedisAdapter.from_url("redis://localhost:6379", max_retries=5, retry_delay=0.1)

                assert isinstance(adapter, RedisAdapter)
                assert mock_connect.call_count == 3

    @pytest.mark.asyncio
    async def test_from_url_failure(self):
        """Test from_url fails after max retries."""
        with patch.object(RedisAdapter, 'connect', new_callable=MagicMock) as mock_connect:
            with patch('asyncio.sleep', new_callable=MagicMock) as mock_sleep:
                f_sleep = asyncio.Future()
                f_sleep.set_result(None)
                mock_sleep.return_value = f_sleep

                f_fail = asyncio.Future()
                f_fail.set_result(False)
                mock_connect.return_value = f_fail

                with pytest.raises(RuntimeError) as excinfo:
                    await RedisAdapter.from_url("redis://localhost:6379", max_retries=3, retry_delay=0.1)

                assert "Failed to connect to Redis" in str(excinfo.value)
                assert mock_connect.call_count == 3


class TestRedisAdapter:
    """Test suite for Redis adapter (interface tests only)."""

    @pytest.fixture
    def redis_url(self):
        """Get Redis URL from environment or skip tests."""
        url = os.getenv("REDIS_TEST_URL")
        if not url:
            pytest.skip("REDIS_TEST_URL not set, skipping Redis integration tests")
        return url

    @pytest.fixture
    async def storage(self, redis_url):
        """Create and cleanup Redis adapter."""
        adapter = RedisAdapter(redis_url=redis_url, timeout=2.0)
        connected = await adapter.connect()
        if not connected:
            pytest.skip("Could not connect to Redis")
        yield adapter
        # Cleanup test keys
        keys = await adapter.scan_keys("test:*")
        for key in keys:
            await adapter.delete(key)
        await adapter.close()

    @pytest.mark.asyncio
    async def test_from_config(self):
        """Test creating adapter from config dict."""
        config = {
            "redis_url": "redis://localhost:6379",
            "timeout": 3.0,
            "max_retries": 5,
            "retry_delay": 1.0
        }
        adapter = RedisAdapter.from_config(config)
        assert adapter.redis_url == "redis://localhost:6379"
        assert adapter.timeout == 3.0
        assert adapter.max_retries == 5
        assert adapter.retry_delay == 1.0

    @pytest.mark.asyncio
    async def test_serialization(self, storage):
        """Test JSON serialization of complex types."""
        data = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"key": "value"}
        }
        
        await storage.set("test:json", data)
        retrieved = await storage.get("test:json")
        assert retrieved == data

    @pytest.mark.asyncio
    async def test_basic_operations(self, storage):
        """Test basic get/set/delete operations."""
        # Set
        result = await storage.set("test:key", "test_value")
        assert result is True

        # Get
        value = await storage.get("test:key")
        assert value == "test_value"

        # Delete
        result = await storage.delete("test:key")
        assert result is True

        # Verify deleted
        value = await storage.get("test:key")
        assert value is None


class TestCompatibilityShim:
    """Test backward compatibility imports."""

    def test_import_from_redis_client(self):
        """Test that storage components can be imported from redis_client."""
        from backend.redis_client import Storage, RedisAdapter, MemoryStorage
        
        # Verify types are available
        assert Storage is not None
        assert RedisAdapter is not None
        assert MemoryStorage is not None

    def test_import_from_storage_package(self):
        """Test that storage components can be imported from storage package."""
        from backend.storage import Storage, RedisAdapter, MemoryStorage
        
        # Verify types are available
        assert Storage is not None
        assert RedisAdapter is not None
        assert MemoryStorage is not None

    def test_redis_client_still_available(self):
        """Test that RedisClient is still available for backward compatibility."""
        from backend.redis_client import RedisClient
        
        # Should still be importable
        assert RedisClient is not None


class TestStorageInterface:
    """Test that implementations conform to Storage protocol."""

    @pytest.mark.asyncio
    async def test_memory_storage_implements_interface(self):
        """Verify MemoryStorage implements Storage interface."""
        storage = MemoryStorage()
        
        # Check all required methods exist
        assert hasattr(storage, 'get')
        assert hasattr(storage, 'set')
        assert hasattr(storage, 'delete')
        assert hasattr(storage, 'scan_keys')
        assert hasattr(storage, 'expire')
        assert hasattr(storage, 'exists')
        assert hasattr(storage, 'health_check')

    def test_redis_adapter_implements_interface(self):
        """Verify RedisAdapter implements Storage interface."""
        adapter = RedisAdapter()
        
        # Check all required methods exist
        assert hasattr(adapter, 'get')
        assert hasattr(adapter, 'set')
        assert hasattr(adapter, 'delete')
        assert hasattr(adapter, 'scan_keys')
        assert hasattr(adapter, 'expire')
        assert hasattr(adapter, 'exists')
        assert hasattr(adapter, 'health_check')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
