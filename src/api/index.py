"""
AstraGuard AI - Vercel Serverless Function Entry Point.

This module adapts the AstraGuard AI FastAPI application for deployment on Vercel's
serverless platform. It handles environment setup, path resolution, and application
export required by the Vercel runtime.

The module performs the following critical initialization steps:
1.  Resolves the project root directory relative to this file.
2.  Adds the project root to `sys.path` to ensure absolute imports work correctly
    in the serverless environment where directory structure may differ from local development.
3.  Imports the main FastAPI application instance (`app`) from `api.service`.
4.  Exports the `app` object, which Vercel looks for to handle incoming HTTP requests.

Attributes:
    app (FastAPI): The main FastAPI application instance exported for Vercel.
"""

import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Resolve project root safely
try:
    project_root = Path(__file__).parent.parent
except NameError as e:
    logger.critical(
        "__file__ is not defined; cannot resolve project root in serverless environment",
        exc_info=True,
    )
    raise RuntimeError("Invalid runtime environment: __file__ is undefined") from e

project_root_str = str(project_root)

if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
    logger.debug(
        "Added project root to sys.path",
        extra={"project_root": project_root_str},
    )

# Import FastAPI application
try:
    from api.service import app
except ModuleNotFoundError as e:
    logger.critical(
        "Failed to import 'api.service.app' (module not found). "
        "Check project structure and PYTHONPATH.",
        exc_info=True,
    )
    raise
except ImportError as e:
    logger.critical(
        "ImportError while importing 'api.service.app'. "
        "This may be caused by import-time side effects or missing dependencies.",
        exc_info=True,
    )
    raise

# This exports the FastAPI app 
__all__ = ["app"]