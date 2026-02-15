"""
Standalone concurrency tests for asyncio locks.
Tests lock behavior without importing service.py dependencies.
"""
import asyncio
import pytest
from asyncio import Lock

# Mark lock tests as slow due to concurrent operations
pytestmark = [pytest.mark.slow, pytest.mark.timeout(30)]


@pytest.mark.asyncio
async def test_lock_basic_functionality():
    """Test basic lock acquire/release."""
    lock = Lock()
    
    async with lock:
        assert lock.locked()
    
    assert not lock.locked()


@pytest.mark.asyncio
async def test_concurrent_counter_with_lock():
    """Test 100 concurrent increments with lock protection."""
    lock = Lock()
    counter = {"value": 0}
    
    async def increment():
        async with lock:
            counter["value"] += 1
        await asyncio.sleep(0.001)
    
    tasks = [increment() for _ in range(100)]
    await asyncio.gather(*tasks)
    
    assert counter["value"] == 100


@pytest.mark.asyncio
async def test_concurrent_list_appends_with_lock():
    """Test concurrent list appends with lock."""
    lock = Lock()
    data = []
    
    async def append_item(i):
        async with lock:
            data.append(i)
    
    tasks = [append_item(i) for i in range(50)]
    await asyncio.gather(*tasks)
    
    assert len(data) == 50
    assert set(data) == set(range(50))


@pytest.mark.asyncio
async def test_concurrent_dict_operations_with_lock():
    """Test concurrent dictionary operations with lock."""
    lock = Lock()
    data = {}
    
    async def add_item(i):
        async with lock:
            data[f"key_{i}"] = i
    
    async def remove_item(i):
        async with lock:
            if f"key_{i}" in data:
                del data[f"key_{i}"]
    
    # Add 50 items
    add_tasks = [add_item(i) for i in range(50)]
    await asyncio.gather(*add_tasks)
    assert len(data) == 50
    
    # Remove 25 items
    remove_tasks = [remove_item(i) for i in range(25)]
    await asyncio.gather(*remove_tasks)
    assert len(data) == 25


@pytest.mark.asyncio
async def test_no_deadlocks_multiple_locks():
    """Verify no deadlocks with multiple locks."""
    lock1 = Lock()
    lock2 = Lock()
    lock3 = Lock()
    
    async def use_locks(i):
        # Always acquire in same order to prevent deadlock and hold multiple locks concurrently
        async with lock1:
            await asyncio.sleep(0.0001)
            async with lock2:
                await asyncio.sleep(0.0001)
                async with lock3:
                    await asyncio.sleep(0.0001)
    
    tasks = [use_locks(i) for i in range(100)]
    # Should complete without hanging
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)


@pytest.mark.asyncio
async def test_lock_overhead():
    """Measure lock acquisition overhead."""
    import time
    
    lock = Lock()
    iterations = 1000
    start = time.perf_counter()
    
    for _ in range(iterations):
        async with lock:
            pass
    
    duration = time.perf_counter() - start
    avg_ms = (duration / iterations) * 1000
    
    # Diagnostic output only; do not assert on timing to avoid flaky tests on slow/contended CI.
    print(f"\nAverage lock overhead: {avg_ms:.4f}ms")


@pytest.mark.asyncio
async def test_lock_prevents_race_condition():
    """Demonstrate lock prevents race condition."""
    lock = Lock()
    shared_state = {"reads": 0, "writes": 0}
    
    async def read_write_with_lock():
        async with lock:
            # Read
            current = shared_state["reads"]
            await asyncio.sleep(0.001)  # Simulate work
            # Write
            shared_state["reads"] = current + 1
            shared_state["writes"] += 1
    
    tasks = [read_write_with_lock() for _ in range(100)]
    await asyncio.gather(*tasks)
    
    # With lock, reads and writes should match
    assert shared_state["reads"] == 100
    assert shared_state["writes"] == 100
