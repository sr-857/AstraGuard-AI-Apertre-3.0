"""
AstraGuard AI - Main FastAPI Application Entry Point.

This module serves as the primary entry point for production deployments using
Uvicorn. It imports the initialized `app` from `api.service` and configures
the server settings (host, port) for standalone execution.
"""

import sys
import os
import signal
import logging
import time
from typing import Any, NoReturn, Optional
from types import FrameType

start_time = time.perf_counter()

logger: logging.Logger = logging.getLogger(__name__)

# Import application with error handling
try:
    from api.service import app
except ImportError as e:
    logger.critical(
        f"Failed to import application - missing dependencies: {e}",
        exc_info=True
    )
    logger.info("Ensure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    logger.critical(
        f"Application initialization failed: {e}",
        exc_info=True
    )
    sys.exit(1)

def signal_handler(sig: int, frame: Optional[FrameType]) -> NoReturn:
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig}, shutting down gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        import uvicorn
        
        # Configuration from environment variables with validation
        host = os.getenv("APP_HOST", "0.0.0.0")
        port_str = os.getenv("APP_PORT", "8002")
        log_level = os.getenv("LOG_LEVEL", "info").lower()
        
        # Validate port
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError(f"Port must be between 1-65535, got {port}")
        except ValueError as e:
            logger.error(f"Invalid APP_PORT configuration: {e}")
            sys.exit(1)
        
        # Validate log level
        valid_log_levels = ["critical", "error", "warning", "info", "debug"]
        if log_level not in valid_log_levels:
            logger.warning(
                f"Invalid LOG_LEVEL '{log_level}', using 'info'. "
                f"Valid levels: {', '.join(valid_log_levels)}"
            )
            log_level = "info"
        
        print(f"Starting AstraGuard AI server on {host}:{port}")
        print(f"Log level: {log_level}")
        
        end_time = time.perf_counter()
        print(f"Startup Time: {end_time - start_time:.2f} seconds")

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=log_level
        )
        
    except ImportError:
        logger.critical(
            "uvicorn not installed. Install with: pip install uvicorn"
        )
        sys.exit(1)
    except OSError as e:
        if e.errno in (48, 98):  # EADDRINUSE - Address already in use
            logger.error(
                f"Port {port} already in use. "
                f"Set APP_PORT environment variable to use a different port."
            )
        elif e.errno == 13:  # EACCES - Permission denied
            logger.error(
                f"Permission denied to bind to {host}:{port}. "
                f"Ports below 1024 require root privileges."
            )
        else:
            logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(
            f"Unexpected server error: {e}",
            exc_info=True
        )
        sys.exit(1)
