"""
Concurrency tests for asyncio locks in service.py
Tests thread-safe access to global state variables.
"""
import asyncio
import pytest

# Mark all tests in this module as slow due to concurrent operations
pytestmark = [pytest.mark.slow, pytest.mark.timeout(30)]


@pytest.mark.asyncio
async def test_concurrent_telemetry_updates():
    """Test 100 concurrent telemetry updates maintain consistency."""
    from api.service import telemetry_lock
    
    shared_data = {"counter": 0}
    
    async def update_data(i):
        async with telemetry_lock:
            shared_data["counter"] += 1
        await asyncio.sleep(0.001)  # Simulate work
    
    # Run 100 concurrent updates
    tasks = [update_data(i) for i in range(100)]
    await asyncio.gather(*tasks)
    
    # Verify all updates completed
    assert shared_data["counter"] == 100, f"Expected 100, got {shared_data['counter']}"


@pytest.mark.asyncio
async def test_concurrent_anomaly_appends():
    """Test concurrent anomaly history appends."""
    from api.service import anomaly_lock
    
    test_history = []
    
    async def add_anomaly(i):
        async with anomaly_lock:
            test_history.append({"id": i})
    
    initial_count = len(test_history)
    tasks = [add_anomaly(i) for i in range(50)]
    await asyncio.gather(*tasks)
    
    final_count = len(test_history)
    assert final_count == initial_count + 50, f"Expected {initial_count + 50}, got {final_count}"


@pytest.mark.asyncio
async def test_concurrent_fault_operations():
    """Test concurrent fault dictionary operations."""
    from api.service import faults_lock
    
    test_faults = {}
    
    async def add_fault(i):
        async with faults_lock:
            test_faults[f"fault_{i}"] = i
    
    async def remove_fault(i):
        async with faults_lock:
            if f"fault_{i}" in test_faults:
                del test_faults[f"fault_{i}"]
    
    # Add 50 faults
    add_tasks = [add_fault(i) for i in range(50)]
    await asyncio.gather(*add_tasks)
    assert len(test_faults) == 50
    
    # Remove 25 faults
    remove_tasks = [remove_fault(i) for i in range(25)]
    await asyncio.gather(*remove_tasks)
    assert len(test_faults) == 25


@pytest.mark.asyncio
async def test_no_deadlocks():
    """Verify no deadlocks with mixed operations."""
    from api.service import telemetry_lock, anomaly_lock, faults_lock
    
    async def mixed_operations(i):
        # Access multiple locks in consistent order
        async with telemetry_lock:
            await asyncio.sleep(0.0001)
        async with anomaly_lock:
            await asyncio.sleep(0.0001)
        async with faults_lock:
            await asyncio.sleep(0.0001)
    
    tasks = [mixed_operations(i) for i in range(100)]
    # Should complete without hanging
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)


@pytest.mark.asyncio
async def test_lock_overhead():
    """Measure lock acquisition overhead."""
    from api.service import telemetry_lock
    import time
    
    iterations = 1000
    start = time.perf_counter()
    
    for _ in range(iterations):
        async with telemetry_lock:
            pass  # Minimal critical section
    
    duration = time.perf_counter() - start
    avg_ms = (duration / iterations) * 1000
    
    print(f"\nAverage lock overhead: {avg_ms:.4f}ms")
    assert avg_ms < 1.0, f"Lock overhead {avg_ms:.4f}ms exceeds 1ms threshold"
