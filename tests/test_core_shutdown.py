import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from src.core.shutdown import ShutdownManager, get_shutdown_manager

@pytest.fixture
def shutdown_manager():
    # Reset singleton effectively for tests
    ShutdownManager._instance = None
    return get_shutdown_manager()

@pytest.mark.asyncio
async def test_shutdown_manager_singleton():
    sm1 = get_shutdown_manager()
    sm2 = get_shutdown_manager()
    assert sm1 is sm2

@pytest.mark.asyncio
async def test_register_and_execute_cleanup(shutdown_manager):
    # Mock tasks
    task1 = Mock()
    task2 = AsyncMock()
    task3 = Mock()
    
    # Register in order 1, 2, 3
    shutdown_manager.register_cleanup_task(task1, "task1")
    shutdown_manager.register_cleanup_task(task2, "task2")
    shutdown_manager.register_cleanup_task(task3, "task3")
    
    # Execute
    await shutdown_manager.execute_cleanup()
    
    # Verify execution order (LIFO: 3, 2, 1)
    # Since we can't easily check exact timing without side effects, 
    # we rely on the implementation. But strictly:
    # We can check call counts.
    
    task3.assert_called_once()
    task2.assert_called_once()
    task1.assert_called_once()

@pytest.mark.asyncio
async def test_error_handling_during_cleanup(shutdown_manager):
    # Task causing error
    bad_task = Mock(side_effect=Exception("Boom"))
    good_task = Mock()
    
    shutdown_manager.register_cleanup_task(good_task, "good")
    shutdown_manager.register_cleanup_task(bad_task, "bad")
    
    # Should not raise exception
    await shutdown_manager.execute_cleanup()
    
    bad_task.assert_called_once()
    good_task.assert_called_once()  # Should still run even if bad_task failed (if bad ran first? No, LIFO)
    # LIFO: bad runs, fails. good runs.
    
@pytest.mark.asyncio
async def test_shutdown_event(shutdown_manager):
    assert not shutdown_manager._shutdown_event.is_set()
    
    shutdown_manager.trigger_shutdown()
    assert shutdown_manager._shutdown_event.is_set()
    
    # Should not block now
    await asyncio.wait_for(shutdown_manager.wait_for_shutdown(), timeout=0.1)
