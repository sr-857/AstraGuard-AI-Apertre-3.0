"""
Restart Manager Module

Handles safe application restart by ensuring graceful cleanup before re-execution.
"""

import sys
import os
import logging
import asyncio
from core.shutdown import get_shutdown_manager

logger = logging.getLogger(__name__)

class RestartManager:
    """Manages application restart."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RestartManager, cls).__new__(cls)
            cls._instance.shutdown_manager = get_shutdown_manager()
        return cls._instance

    async def trigger_restart(self):
        """
        Trigger a graceful restart of the application.
        
        1. Execute shutdown cleanup tasks.
        2. Re-execute the current process using os.execv.
        """
        logger.warning("Initiating system restart...")
        
        # 1. Graceful Cleanup
        try:
            await self.shutdown_manager.execute_cleanup()
        except Exception as e:
            logger.error(f"Error during pre-restart cleanup: {e}", exc_info=True)
            # Proceed with restart anyway to ensure recovery
            
        # 2. Re-execution
        logger.info("Re-spawning process...")
        try:
            # sys.executable is the python interpreter
            # sys.argv is the list of command line arguments passed to the script
            # We need to re-execute the same command
            python = sys.executable
            os.execv(python, [python] + sys.argv)
        except Exception as e:
            logger.critical(f"Failed to restart process: {e}", exc_info=True)
            sys.exit(1)

def get_restart_manager() -> RestartManager:
    """Get the singleton RestartManager instance."""
    return RestartManager()
