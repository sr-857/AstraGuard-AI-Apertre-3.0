"""Quick smoke test for fallback refactor"""
import asyncio
from backend.fallback import FallbackManager, FallbackMode, parse_condition, evaluate
from backend.storage import MemoryStorage


async def test_condition_parser():
    """Test condition parser"""
    print("Testing condition parser...")
    
    # Test always
    cond = parse_condition("always")
    assert evaluate(cond, {}) is True
    print("  ✓ 'always' works")
    
    # Test simple comparison
    cond = parse_condition("severity >= 0.8")
    assert evaluate(cond, {"severity": 0.9}) is True
    assert evaluate(cond, {"severity": 0.7}) is False
    print("  ✓ Simple comparisons work")
    
    # Test AND logic
    cond = parse_condition("severity >= 0.8 and recurrence_count >= 2")
    assert evaluate(cond, {"severity": 0.9, "recurrence_count": 3}) is True
    assert evaluate(cond, {"severity": 0.7, "recurrence_count": 3}) is False
    print("  ✓ AND logic works")
    
    # Test OR logic
    cond = parse_condition("severity >= 0.9 or recurrence_count >= 5")
    assert evaluate(cond, {"severity": 0.95, "recurrence_count": 1}) is True
    assert evaluate(cond, {"severity": 0.5, "recurrence_count": 6}) is True
    print("  ✓ OR logic works")
    
    print("✅ Condition parser tests passed!\n")


async def test_manager():
    """Test fallback manager"""
    print("Testing fallback manager...")
    
    storage = MemoryStorage()
    manager = FallbackManager(storage=storage)
    
    # Test initial mode
    assert manager.get_current_mode() == FallbackMode.PRIMARY
    print("  ✓ Initializes in PRIMARY mode")
    
    # Test mode switching
    await manager.set_mode("heuristic")
    assert manager.get_current_mode() == FallbackMode.HEURISTIC
    assert manager.is_degraded() is True
    print("  ✓ Can switch to HEURISTIC mode")
    
    await manager.set_mode("safe")
    assert manager.is_safe_mode() is True
    print("  ✓ Can switch to SAFE mode")
    
    # Test cascade
    health_state = {
        "circuit_breaker": {"state": "CLOSED"},
        "retry": {"failures_1h": 0},
        "system": {"failed_components": 0},
    }
    mode = await manager.cascade(health_state)
    assert mode == FallbackMode.PRIMARY
    print("  ✓ Cascade to PRIMARY works")
    
    # Test cascade to SAFE
    health_state["system"]["failed_components"] = 2
    mode = await manager.cascade(health_state)
    assert mode == FallbackMode.SAFE
    print("  ✓ Cascade to SAFE works")
    
    # Test metrics
    metrics = await manager.get_metrics()
    assert "current_mode" in metrics
    assert "is_degraded" in metrics
    print("  ✓ Metrics retrieval works")
    
    print("✅ Manager tests passed!\n")


async def test_storage():
    """Test storage interface"""
    print("Testing storage...")
    
    storage = MemoryStorage()
    
    # Test set/get
    await storage.set("test_key", "test_value")
    value = await storage.get("test_key")
    assert value == "test_value"
    print("  ✓ Set/Get works")
    
    # Test exists
    assert await storage.exists("test_key") is True
    assert await storage.exists("nonexistent") is False
    print("  ✓ Exists works")
    
    # Test delete
    await storage.delete("test_key")
    assert await storage.get("test_key") is None
    print("  ✓ Delete works")
    
    # Test TTL
    await storage.set("expiring_key", "value", ttl=1)
    assert await storage.exists("expiring_key") is True
    await asyncio.sleep(1.1)
    assert await storage.get("expiring_key") is None
    print("  ✓ TTL expiration works")
    
    # Test keys pattern matching
    await storage.set("prefix:key1", "value1")
    await storage.set("prefix:key2", "value2")
    await storage.set("other:key", "value")
    keys = await storage.keys("prefix:*")
    assert len(keys) == 2
    print("  ✓ Pattern matching works")
    
    print("✅ Storage tests passed!\n")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Running Fallback Refactor Smoke Tests")
    print("=" * 60 + "\n")
    
    try:
        await test_condition_parser()
        await test_storage()
        await test_manager()
        
        print("=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
