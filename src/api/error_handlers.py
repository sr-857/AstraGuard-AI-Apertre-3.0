"""
Global Exception Handlers for AstraGuard API

Implements standardized error responses, unified error codes, and trace ID propagation.
Hooks into FastAPI to catch all exceptions and return consistent JSON format.
"""

import logging
import sqlite3
from typing import Union, Dict, Any
from uuid import uuid4

from fastapi import Request, FastAPI
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

# Import core error types
from core.error_handling import (
    ApiError,
    ValidationError,
    AuthError,
    RateLimitError,
    NotFoundError,
    ServerError,
    DependencyError,
    ErrorContext,
    ErrorSeverity,
    classify_error,
    log_error
)

# Import metrics
try:
    from prometheus_client import Counter
    ERROR_COUNTER = Counter(
        "api_errors_total",
        "Total API errors by code and type",
        ["code", "error_type"]
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


logger = logging.getLogger(__name__)


def _create_error_response(
    status_code: int,
    code: str,
    message: str,
    trace_id: str,
    details: Dict[str, Any] = None
) -> JSONResponse:
    """Helper to create standardized error response."""

    # Record metric if available
    if METRICS_AVAILABLE:
        ERROR_COUNTER.labels(code=code, error_type=code.split("_")[0]).inc()

    content = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "trace_id": trace_id,
        }
    }

    if details:
        content["error"]["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=content
    )


def get_trace_id(request: Request) -> str:
    """Extract trace ID from request state or generate new one."""
    if hasattr(request.state, "trace_id"):
        return request.state.trace_id
    # Fallback if middleware didn't run (e.g., early error)
    return str(uuid4())


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """Handle custom ApiError exceptions."""
    trace_id = get_trace_id(request)

    # Log the error
    error_ctx = classify_error(exc, component="api_handler")
    log_error(error_ctx)

    return _create_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        trace_id=trace_id,
        details=exc.details
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPExceptions (e.g., 404, 401)."""
    trace_id = get_trace_id(request)

    # Map status codes to error codes
    code_map = {
        400: "VAL_000",
        401: "AUTH_001",
        403: "AUTH_003",
        404: "RES_001",
        429: "RATE_001",
        500: "SRV_001",
        502: "DEP_001",
        503: "DEP_002",
    }
    code = code_map.get(exc.status_code, "SRV_000")

    return _create_error_response(
        status_code=exc.status_code,
        code=code,
        message=str(exc.detail),
        trace_id=trace_id
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    trace_id = get_trace_id(request)

    details = {"errors": exc.errors()}

    return _create_error_response(
        status_code=400,
        code="VAL_001",
        message="Request validation failed",
        trace_id=trace_id,
        details=details
    )


async def redis_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Redis errors (if caught at top level)."""
    # Note: We catch generic Exception here but register for specific Redis types if imported
    trace_id = get_trace_id(request)

    logger.error(f"Redis error: {exc}", exc_info=True)

    return _create_error_response(
        status_code=503,
        code="DEP_003",
        message="Service dependency unavailable",
        trace_id=trace_id
    )


async def db_error_handler(request: Request, exc: sqlite3.Error) -> JSONResponse:
    """Handle Database errors."""
    trace_id = get_trace_id(request)

    logger.error(f"Database error: {exc}", exc_info=True)

    return _create_error_response(
        status_code=500,
        code="SRV_005",
        message="Database operation failed",
        trace_id=trace_id
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected exceptions."""
    trace_id = get_trace_id(request)

    # Log unexpected error with stack trace
    logger.exception(f"Unexpected error: {exc}")

    return _create_error_response(
        status_code=500,
        code="SRV_999",
        message="Internal server error",
        trace_id=trace_id
    )


def add_exception_handlers(app: FastAPI):
    """Register all exception handlers with the FastAPI app."""

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(sqlite3.Error, db_error_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Try to import Redis exceptions and register if available
    try:
        from redis.exceptions import RedisError
        app.add_exception_handler(RedisError, redis_error_handler)
    except ImportError:
        pass
