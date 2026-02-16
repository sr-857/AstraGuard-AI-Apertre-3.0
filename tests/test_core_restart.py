import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock, patch
from src.core.restart import RestartManager, get_restart_manager

@pytest.fixture
def restart_manager():
    # Reset singleton
    RestartManager._instance = None
    return get_restart_manager()

@pytest.mark.asyncio
async def test_restart_manager_singleton():
    rm1 = get_restart_manager()
    rm2 = get_restart_manager()
    assert rm1 is rm2

@pytest.mark.asyncio
async def test_trigger_restart_flow(restart_manager):
    # Mock dependencies
    mock_shutdown = AsyncMock()
    restart_manager.shutdown_manager = mock_shutdown
    
    with patch('os.execv') as mock_execv:
        # Trigger restart
        await restart_manager.trigger_restart()
        
        # Verify cleanup was called
        mock_shutdown.execute_cleanup.assert_called_once()
        
        # Verify execv was called
        # args should be [sys.executable, sys.executable, *sys.argv]
        # Wait, the code is: os.execv(python, [python] + sys.argv)
        python = sys.executable
        expected_args = [python] + sys.argv
        mock_execv.assert_called_once_with(python, expected_args)

@pytest.mark.asyncio
async def test_restart_cleanup_failure_still_restarts(restart_manager):
    # Mock cleanup failure
    mock_shutdown = AsyncMock()
    mock_shutdown.execute_cleanup.side_effect = Exception("Cleanup failed")
    restart_manager.shutdown_manager = mock_shutdown
    
    with patch('os.execv') as mock_execv:
        # Trigger restart
        await restart_manager.trigger_restart()
        
        # Verify cleanup called
        mock_shutdown.execute_cleanup.assert_called_once()
        
        # Verify execv still called despite cleanup error
        mock_execv.assert_called_once()

@pytest.mark.asyncio
async def test_execv_failure_exits(restart_manager):
    mock_shutdown = AsyncMock()
    restart_manager.shutdown_manager = mock_shutdown
    
    # Mock sys.exit to prevent test runner death if our code calls it
    with patch('os.execv', side_effect=OSError("Exec failed")), \
         patch('sys.exit') as mock_exit:
         
        await restart_manager.trigger_restart()
        
        mock_exit.assert_called_once_with(1)
