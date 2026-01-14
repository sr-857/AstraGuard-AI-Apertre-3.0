"""
Standalone test script for storage abstraction layer.
Run directly without pytest to avoid conftest.py issues.
"""

import asyncio
import time
from backend.storage import Storage, RedisAdapter, MemoryStorage


async def test_memory_storage():
    """Test MemoryStorage implementation."""
    print("Testing MemoryStorage...")
    
    storage = MemoryStorage()
    await storage.connect()
    
    # Test set and get
    await storage.set("test:key1", "value1")
    value = await storage.get("test:key1")
    assert value == "value1", f"Expected 'value1', got {value}"
    print("✓ Set and get works")
    
    # Test dict storage
    data = {"name": "test", "value": 42}
    await storage.set("test:dict", data)
    retrieved = await storage.get("test:dict")
    assert retrieved == data, f"Expected {data}, got {retrieved}"
    print("✓ Dictionary storage works")
    
    # Test delete
    await storage.delete("test:key1")
    value = await storage.get("test:key1")
    assert value is None, f"Expected None after delete, got {value}"
    print("✓ Delete works")
    
    # Test exists
    await storage.set("test:key2", "value2")
    exists = await storage.exists("test:key2")
    assert exists is True, "Expected key to exist"
    await storage.delete("test:key2")
    exists = await storage.exists("test:key2")
    assert exists is False, "Expected key to not exist"
    print("✓ Exists works")
    
    # Test expiration
    await storage.set("test:expire", "value", expire=1)
    value = await storage.get("test:expire")
    assert value == "value", "Expected value before expiration"
    await asyncio.sleep(1.1)
    value = await storage.get("test:expire")
    assert value is None, "Expected None after expiration"
    print("✓ Expiration works")
    
    # Test scan keys
    await storage.set("user:1", "alice")
    await storage.set("user:2", "bob")
    await storage.set("product:1", "widget")
    keys = await storage.scan_keys("user:*")
    assert set(keys) == {"user:1", "user:2"}, f"Expected user keys, got {keys}"
    print("✓ Scan keys works")
    
    # Test health check
    healthy = await storage.health_check()
    assert healthy is True, "Expected storage to be healthy"
    print("✓ Health check works")
    
    await storage.close()
    print("✅ All MemoryStorage tests passed!\n")


async def test_redis_adapter_interface():
    """Test RedisAdapter interface (without connecting to Redis)."""
    print("Testing RedisAdapter interface...")
    
    # Test from_config
    config = {
        "redis_url": "redis://localhost:6379",
        "timeout": 3.0,
        "max_retries": 5
    }
    adapter = RedisAdapter.from_config(config)
    assert adapter.redis_url == "redis://localhost:6379"
    assert adapter.timeout == 3.0
    assert adapter.max_retries == 5
    print("✓ from_config works")
    
    # Test that all interface methods exist
    assert hasattr(adapter, 'get')
    assert hasattr(adapter, 'set')
    assert hasattr(adapter, 'delete')
    assert hasattr(adapter, 'scan_keys')
    assert hasattr(adapter, 'expire')
    assert hasattr(adapter, 'exists')
    assert hasattr(adapter, 'health_check')
    assert hasattr(adapter, 'connect')
    assert hasattr(adapter, 'close')
    print("✓ All interface methods exist")
    
    print("✅ RedisAdapter interface tests passed!\n")


def test_imports():
    """Test that imports work correctly."""
    print("Testing imports...")
    
    # Test main package import
    from backend.storage import Storage, RedisAdapter, MemoryStorage
    assert Storage is not None
    assert RedisAdapter is not None
    assert MemoryStorage is not None
    print("✓ Main package imports work")
    
    # Test individual module imports
    from backend.storage.interface import Storage as IStorage
    from backend.storage.redis_adapter import RedisAdapter as RRedisAdapter
    from backend.storage.memory import MemoryStorage as MMemoryStorage
    assert IStorage is not None
    assert RRedisAdapter is not None
    assert MMemoryStorage is not None
    print("✓ Individual module imports work")
    
    print("✅ All import tests passed!\n")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Storage Abstraction Layer Tests")
    print("=" * 60)
    print()
    
    test_imports()
    await test_memory_storage()
    await test_redis_adapter_interface()
    
    print("=" * 60)
    print("🎉 All tests passed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
