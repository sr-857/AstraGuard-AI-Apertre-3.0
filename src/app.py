# """
# AstraGuard AI - Main FastAPI Application Entry Point.

# This module serves as the primary entry point for production deployments using
# Uvicorn. It imports the initialized `app` from `api.service` and configures
# the server settings (host, port, workers) for standalone execution.
# """

# import os
# import sys
# import signal
# import logging

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
# )
# logger: logging.Logger = logging.getLogger(__name__)

# try:
#     from api.service import app
# except ImportError as e:
#     logger.critical("Failed to import application – missing dependencies: %s", e, exc_info=True)
#     logger.info("Ensure all dependencies are installed: pip install -r requirements.txt")
#     sys.exit(1)
# except Exception as e:
#     logger.critical("Application initialization failed: %s", e, exc_info=True)
#     sys.exit(1)

# VALID_LOG_LEVELS: frozenset[str] = frozenset(
#     {"critical", "error", "warning", "info", "debug", "trace"}
# )

# _EADDRINUSE: frozenset[int] = frozenset({48, 98})
# _EACCES: int = 13

# def _parse_port(value: str) -> int:
#     """Parse and validate a port number string.

#     Raises:
#         SystemExit: if the value is not a valid port number.
#     """
#     try:
#         port = int(value)
#     except ValueError:
#         logger.error("APP_PORT must be an integer, got: %r", value)
#         sys.exit(1)

#     if not (1 <= port <= 65535):
#         logger.error("APP_PORT must be between 1 and 65535, got: %d", port)
#         sys.exit(1)

#     return port

# def _parse_workers(value: str) -> int:
#     """Parse and validate the worker-count string.

#     Raises:
#         SystemExit: if the value is not a positive integer.
#     """
#     try:
#         workers = int(value)
#     except ValueError:
#         logger.error("APP_WORKERS must be an integer, got: %r", value)
#         sys.exit(1)

#     if workers < 1:
#         logger.error("APP_WORKERS must be >= 1, got: %d", workers)
#         sys.exit(1)

#     return workers

# def _parse_log_level(value: str) -> str:
#     """Normalise and validate a log-level string.

#     Falls back to "info" with a warning rather than hard-exiting, so a
#     misconfigured LOG_LEVEL never prevents the server from starting.
#     """
#     normalised = value.strip().lower()
#     if normalised not in VALID_LOG_LEVELS:
#         logger.warning(
#             "Invalid LOG_LEVEL %r – falling back to 'info'. "
#             "Valid levels: %s",
#             value,
#             ", ".join(sorted(VALID_LOG_LEVELS)),
#         )
#         return "info"
#     return normalised

# def signal_handler(sig: int, _frame: object) -> None:
#     """Handle SIGINT / SIGTERM for a clean shutdown.

#     Exposed as a public name so it can be referenced or patched by tests
#     and external tooling.  Registered internally via :func:`main`.
#     """
#     logger.info("Received signal %d – shutting down gracefully.", sig)
#     sys.exit(0)

# def main() -> None:
#     """Configure and start the Uvicorn server."""
#     host = os.environ.get("APP_HOST", "0.0.0.0")
#     port = _parse_port(os.environ.get("APP_PORT", "8002"))
#     workers = _parse_workers(os.environ.get("APP_WORKERS", "1"))
#     log_level = _parse_log_level(os.environ.get("LOG_LEVEL", "info"))

#     signal.signal(signal.SIGINT, signal_handler)
#     signal.signal(signal.SIGTERM, signal_handler)

#     logger.info(
#         "Starting AstraGuard AI on %s:%d (workers=%d, log_level=%s)",
#         host, port, workers, log_level,
#     )

#     try:
#         import uvicorn
#     except ImportError:
#         logger.critical("uvicorn is not installed.  Run: pip install uvicorn[standard]")
#         sys.exit(1)

#     try:
#         uvicorn.run(
#             "api.service:app" if workers > 1 else app,
#             host=host,
#             port=port,
#             workers=workers if workers > 1 else None,
#             log_level=log_level,
#             access_log=True,
#             server_header=False,
#             date_header=True,
#         )
#     except OSError as e:
#         if e.errno in _EADDRINUSE:
#             logger.error(
#                 "Port %d is already in use.  "
#                 "Set APP_PORT to a different port and retry.",
#                 port,
#             )
#         elif e.errno == _EACCES:
#             logger.error(
#                 "Permission denied binding to %s:%d.  "
#                 "Ports below 1024 require elevated privileges.",
#                 host, port,
#             )
#         else:
#             logger.error("Failed to start server: %s", e, exc_info=True)
#         sys.exit(1)
#     except KeyboardInterrupt:
#         logger.info("Server shutdown requested by user.")
#         sys.exit(0)
#     except Exception as e:  # noqa: BLE001
#         logger.critical("Unexpected server error: %s", e, exc_info=True)
#         sys.exit(1)


# if __name__ == "__main__":
#     main()




"""
AstraGuard AI - Main FastAPI Application Entry Point.

Serves as the primary entry point for production deployments using Uvicorn.
Imports the initialized `app` from `api.service` and configures server
settings from environment variables for standalone execution.
"""

import sys
import os
import signal
import logging
from typing import NoReturn, Optional
from types import FrameType

logger: logging.Logger = logging.getLogger(__name__)


def _load_app():
    """
    Lazily import the application to avoid side effects on module import.

    Defers expensive initialization (DB connections, model loading, config
    parsing in api.service) until the server is actually starting. This
    prevents test runners, linters, and other tooling from triggering full
    app startup just by importing this module.
    """
    try:
        from api.service import app as _app
        return _app
    except ImportError as e:
        logger.critical(
            "Failed to import application - missing dependencies: %s", e,
            exc_info=True
        )
        logger.info("Ensure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.critical("Application initialization failed: %s", e, exc_info=True)
        sys.exit(1)


def _get_server_config() -> dict:
    """
    Read and validate all server configuration from environment variables.

    Centralizing config parsing here makes the configuration surface
    explicit and easy to audit, and ensures validation errors surface
    before uvicorn.run() is called.

    Returns a validated config dict ready to be unpacked into uvicorn.run().
    """
    host = os.getenv("APP_HOST", "0.0.0.0")  # nosec B104
    port_str = os.getenv("APP_PORT", "8002")
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    workers_str = os.getenv("APP_WORKERS", "1")
    graceful_timeout_str = os.getenv("APP_GRACEFUL_TIMEOUT", "30")

    # --- Port validation ---
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1-65535, got {port}")
    except ValueError as e:
        logger.error("Invalid APP_PORT configuration: %s", e)
        sys.exit(1)

    # --- Log level validation ---
    valid_log_levels = {"critical", "error", "warning", "info", "debug"}
    if log_level not in valid_log_levels:
        logger.warning(
            "Invalid LOG_LEVEL '%s', defaulting to 'info'. Valid: %s",
            log_level, ", ".join(sorted(valid_log_levels))
        )
        log_level = "info"

    # --- Workers validation ---
    try:
        workers = int(workers_str)
        if workers < 1:
            raise ValueError(f"Workers must be >= 1, got {workers}")
    except ValueError as e:
        logger.warning("Invalid APP_WORKERS '%s', defaulting to 1: %s", workers_str, e)
        workers = 1

    # --- Graceful shutdown timeout ---
    try:
        graceful_timeout = int(graceful_timeout_str)
        if graceful_timeout < 0:
            raise ValueError("Graceful timeout must be non-negative")
    except ValueError as e:
        logger.warning(
            "Invalid APP_GRACEFUL_TIMEOUT '%s', defaulting to 30s: %s",
            graceful_timeout_str, e
        )
        graceful_timeout = 30

    return {
        "host": host,
        "port": port,
        "log_level": log_level,
        "workers": workers,
        "timeout_graceful_shutdown": graceful_timeout,
    }


def _make_signal_handler(label: str):
    """
    Factory that returns a signal handler which logs and exits cleanly.

    Separating construction from registration keeps signal_handler's
    signature compatible with signal.signal() — (int, FrameType | None) -> None —
    while still being informative about which signal triggered shutdown.
    """
    def handler(sig: int, frame: Optional[FrameType]) -> None:
        logger.info("Received %s (signal %d), shutting down gracefully...", label, sig)
        sys.exit(0)
    return handler



if __name__ == "__main__":
    # Register signal handlers before anything else so the process is
    # always interruptible, even if app loading takes a while.
    signal.signal(signal.SIGINT, _make_signal_handler("SIGINT"))
    signal.signal(signal.SIGTERM, _make_signal_handler("SIGTERM"))

    try:
        import uvicorn
    except ImportError:
        logger.critical("uvicorn not installed. Install with: pip install uvicorn")
        sys.exit(1)

    config = _get_server_config()
    app = _load_app()

    logger.info(
        "Starting AstraGuard AI on %s:%d (workers=%d, log_level=%s)",
        config["host"], config["port"], config["workers"], config["log_level"],
    )

    try:
        # Pass the app as an import string when workers > 1 so uvicorn can
        # fork and initialize each worker process independently. With a direct
        # object reference, multi-worker mode silently falls back to 1 worker.
        app_target = "api.service:app" if config["workers"] > 1 else app

        uvicorn.run(
            app_target,
            host=config["host"],          # nosec B104
            port=config["port"],
            log_level=config["log_level"],
            workers=config["workers"],
            timeout_graceful_shutdown=config["timeout_graceful_shutdown"],
        )
    except OSError as e:
        if e.errno in (48, 98):  # EADDRINUSE
            logger.error(
                "Port %d already in use. Set APP_PORT to use a different port.",
                config["port"]
            )
        elif e.errno == 13:  # EACCES
            logger.error(
                "Permission denied binding to %s:%d. Ports < 1024 require root.",
                config["host"], config["port"]
            )
        else:
            logger.error("Failed to start server: %s", e, exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
        sys.exit(0)
    except Exception as e:
        logger.critical("Unexpected server error: %s", e, exc_info=True)
        sys.exit(1)