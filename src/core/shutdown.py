"""
Shutdown Manager Module

Centralized registry for cleanup tasks to ensure graceful application shutdown.
"""

import asyncio
import logging
import signal
from typing import List, Callable, Awaitable, Union

logger = logging.getLogger(__name__)

class ShutdownManager:
    """Manages graceful shutdown tasks."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShutdownManager, cls).__new__(cls)
            cls._instance._tasks = []
            cls._instance._shutdown_event = asyncio.Event()
        return cls._instance

    def register_cleanup_task(self, task: Union[Callable[[], None], Callable[[], Awaitable[None]]], name: str = "task"):
        """Register a cleanup task (sync or async)."""
        self._tasks.append((name, task))
        logger.debug(f"Registered cleanup task: {name}")

    async def execute_cleanup(self):
        """Execute all registered cleanup tasks."""
        logger.info("Executing shutdown cleanup tasks...")
        
        # Run in reverse order of registration
        for name, task in reversed(self._tasks):
            try:
                logger.info(f"Cleaning up: {name}")
                if asyncio.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Error during cleanup of {name}: {e}", exc_info=True)
                
        logger.info("Shutdown cleanup complete.")

    def trigger_shutdown(self):
        """Trigger the shutdown event."""
        logger.info("Shutdown triggered.")
        self._shutdown_event.set()

    async def wait_for_shutdown(self):
        """Wait for the shutdown event."""
        await self._shutdown_event.wait()

def get_shutdown_manager() -> ShutdownManager:
    """Get the singleton ShutdownManager instance."""
    return ShutdownManager()
