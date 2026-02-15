"""
API Request/Response Logging Middleware

Provides comprehensive logging for all API requests and responses with:
- Request method, path, and headers (excluding sensitive data)
- Response status code and duration
- Correlation ID for request tracing
- Configurable log sampling for high-traffic endpoints
"""

import time
import uuid
from typing import Callable, Set, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog

logger = structlog.get_logger(__name__)

# Sensitive headers to exclude from logging
SENSITIVE_HEADERS: Set[str] = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "proxy-authorization",
    "www-authenticate",
}

# High-traffic endpoints for sampling
HIGH_TRAFFIC_ENDPOINTS: Set[str] = {
    "/health",
    "/health/live",
    "/health/ready",
    "/metrics",
}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging API requests and responses.
    
    Features:
    - Adds correlation ID to each request
    - Logs request method, path, and non-sensitive headers
    - Logs response status and duration
    - Supports log sampling for high-traffic endpoints
    """
    
    def __init__(
        self,
        app: ASGIApp,
        log_level: str = "INFO",
        sample_rate: float = 0.1,  # 10% sampling for high-traffic endpoints
    ):
        """
        Initialize the logging middleware.
        
        Args:
            app: The ASGI application
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            sample_rate: Sampling rate for high-traffic endpoints (0.0 to 1.0)
        """
        super().__init__(app)
        self.log_level = log_level.upper()
        self.sample_rate = max(0.0, min(1.0, sample_rate))  # Clamp between 0 and 1
        self._request_counter = 0
    
    def _should_log(self, path: str) -> bool:
        """
        Determine if request should be logged based on sampling rate.
        
        Args:
            path: Request path
            
        Returns:
            True if request should be logged
        """
        # Always log non-health-check endpoints
        if path not in HIGH_TRAFFIC_ENDPOINTS:
            return True
        
        # Sample high-traffic endpoints
        self._request_counter += 1
        return (self._request_counter % int(1 / self.sample_rate)) == 0
    
    def _filter_headers(self, headers: dict) -> dict:
        """
        Filter out sensitive headers from logging.
        
        Args:
            headers: Request headers
            
        Returns:
            Filtered headers dictionary
        """
        return {
            key: value
            for key, value in headers.items()
            if key.lower() not in SENSITIVE_HEADERS
        }
    
    def _generate_correlation_id(self) -> str:
        """
        Generate a unique correlation ID for request tracing.
        
        Returns:
            UUID-based correlation ID
        """
        return str(uuid.uuid4())
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and log details.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from the application
        """
        # Generate correlation ID
        correlation_id = self._generate_correlation_id()
        request.state.correlation_id = correlation_id
        
        # Record start time
        start_time = time.time()
        
        # Check if we should log this request
        should_log = self._should_log(request.url.path)
        
        # Log request details
        if should_log:
            filtered_headers = self._filter_headers(dict(request.headers))
            
            logger.info(
                "api_request",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                query_params=str(request.query_params) if request.query_params else None,
                client_host=request.client.host if request.client else None,
                headers=filtered_headers,
            )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            # Log response details
            if should_log:
                logger.info(
                    "api_response",
                    correlation_id=correlation_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round(duration_ms, 2),
                )
            
            return response
            
        except Exception as e:
            # Calculate duration even for errors
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                "api_error",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
            )
            
            # Re-raise the exception
            raise


def get_correlation_id(request: Request) -> Optional[str]:
    """
    Extract correlation ID from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Correlation ID if available, None otherwise
    """
    return getattr(request.state, "correlation_id", None)
