"""
AstraGuard AI - FastAPI Application Entry Point.

This module serves as the primary entry point for Vercel and production deployments.
It securely imports the main `app` instance from `api.service`, handling potential
import errors gracefully with detailed logging for debugging deployment issues.
"""
import logging
from typing import List

logger: logging.Logger = logging.getLogger(__name__)
try:
    from api.service import app
except ModuleNotFoundError as e:
    _log_import_error(e, "ModuleNotFoundError")
    _import_errors.append(("ModuleNotFoundError", str(e)))
    raise
except ImportError as e:
    # Distinguish between different types of ImportError
    if "httpx" in str(e) or "fastapi" in str(e).lower():
        _log_import_error(e, "MissingHTTPDependency")
    elif "pydantic" in str(e).lower():
        _log_import_error(e, "MissingPydanticDependency")
    else:
        _log_import_error(e, "ImportError")
    _import_errors.append(("ImportError", str(e)))
    raise
except AttributeError as e:
    # Handle case where module exists but doesn't have 'app' attribute
    logger.critical(
        "Module 'api.service' found but 'app' attribute is missing. "
        f"Verify that api.service module exports 'app' correctly. Error: {e} | "
        f"Python version: {sys.version}",
        exc_info=True,
    )
    _import_errors.append(("AttributeError", str(e)))
    raise
except Exception as e:
    # Catch-all for unexpected errors during import
    logger.critical(
        f"Unexpected error during import of 'api.service.app': {type(e).__name__} - {e} | "
        f"This may indicate a configuration or environment issue. | "
        f"Python version: {sys.version}",
        exc_info=True,
    )
    _import_errors.append((type(e).__name__, str(e)))
    raise

__all__: List[str] = ["app"]
