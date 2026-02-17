"""AstraGuard Structured Logging Module.

JSON-based structured logging for enterprise observability (Azure Monitor compatible).
"""

import logging
import json
import sys
import os
from datetime import datetime
from types import TracebackType
from typing import Any, Optional, Type
import structlog
from pythonjsonlogger import jsonlogger
from core.secrets import get_secret
from functools import lru_cache
import asyncio

# Cache secret retrieval to avoid repeated I/O
@lru_cache(maxsize=32)
def _cached_get_secret(key: str, default=None):
    """Cached wrapper for get_secret to reduce I/O overhead."""
    try:
        return get_secret(key, default)
    except (KeyError, ValueError, OSError, IOError) as e:
        # Log the specific error for debugging
        print(
            f"Warning: Failed to retrieve secret '{key}' ({type(e).__name__}): {e}. Using default value.",
            file=sys.stderr
        )
        return default
    except Exception as e:
        # Catch truly unexpected errors and log them prominently
        print(
            f"Error: Unexpected error retrieving secret '{key}' ({type(e).__name__}): {e}. Using default value.",
            file=sys.stderr
        )
        return default

# ============================================================================
# STRUCTURED LOGGING CONFIGURATION
# ============================================================================

def setup_json_logging(
    log_level: str = "INFO",
    service_name: str = "astra-guard",
    environment: Optional[str] = None
) -> None:
    """Sets up structured logging (JSON or Console).

    Configures structlog and the root logger.
    - If ASTRA_CONSOLE_LOGGING is true: Uses ConsoleRenderer for human-readable output.
    - Otherwise: Uses JSONRenderer for machine-readable output (Azure Monitor etc).

    Args:
        log_level: The logging level.
        service_name: The name of the service.
        environment: The environment name.
    """
    # Use cached secret retrieval to avoid repeated I/O
    if environment is None:
        environment = _cached_get_secret("environment", "development")
    try:
        # Use cached secret retrieval for consistency
        if environment is None:
            environment = _cached_get_secret("environment", "development")
        
        # Validate log_level
        if not hasattr(logging, log_level.upper()):
            raise ValueError(f"Invalid log level: {log_level}")

        force_console = os.getenv("ASTRA_CONSOLE_LOGGING", "").lower() == "true"
        
        # Common processors
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
        ]
        
        # Renderer selection
        if force_console:
            # Human-readable console renderer
            processors.append(structlog.dev.ConsoleRenderer(colors=True))
        else:
            # JSON renderer for production/ingestion
            processors.append(structlog.processors.JSONRenderer())

        # Configure structlog
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Configure Python standard logging
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))
        root_logger.handlers.clear()
        
        stream_handler = logging.StreamHandler(sys.stdout)
        
        if force_console:
            # Standard text formatter for console
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        else:
            # JSON formatter for standard logging
            formatter = jsonlogger.JsonFormatter(
                fmt='%(timestamp)s %(level)s %(name)s %(message)s',
                timestamp=True
            )
            
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

        # Add global context
        try:
            app_version = get_secret("app_version", "1.0.0")
        except (KeyError, ValueError, OSError, IOError) as e:
            app_version = "1.0.0"
            print(
                f"Warning: Failed to retrieve app_version secret ({type(e).__name__}): {e}. Using default '1.0.0'.",
                file=sys.stderr
            )
            
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

        # Add global context with cached secret retrieval
        app_version = _cached_get_secret("app_version", "1.0.0")

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            service=service_name,
            environment=environment,
            version=app_version
        )

    except (AttributeError, ImportError, ValueError) as e:
        print(f"Warning: Logging setup failed ({type(e).__name__}): {e}. Falling back to basic.", file=sys.stderr)
        logging.basicConfig(level=logging.INFO)
    except Exception as e:
        print(f"Error: Unexpected error during logging setup: {e}", file=sys.stderr)
        logging.basicConfig(level=logging.INFO)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Gets a structured logger instance.

    Args:
        name: Logger name (typically `__name__`).

    Returns:
        A bound structlog logger instance.
    """
    return structlog.get_logger(name)


# ============================================================================
# LOGGING CONTEXT MANAGERS
# ============================================================================

class LogContext:
    """Context manager for scoped logging context.

    Provides a context in which additional key-value pairs are added to each log message.
    """
    
    def __init__(self, logger: structlog.BoundLogger, **context: Any) -> None:
        """Initializes the LogContext.

        Args:
            logger: The structlog logger instance.
            **context: Additional key-value pairs to add to the logging context.
        """
        self.logger = logger
        self.context = context
    
    def __enter__(self) -> structlog.BoundLogger:
        """Enters the logging context.

        Binds the logger with the specified context.

        Returns:
            The bound logger instance.
        """
        self.logger = self.logger.bind(**self.context)
        return self.logger
    
    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> None:
        """Exits the logging context.

        Logs an error if an exception occurred within the context.

        Args:
            exc_type: The type of the exception, if any.
            exc_val: The exception instance, if any.
            exc_tb: The traceback, if any.

        Returns:
            None.
        """
        if exc_type is not None:
            self.logger.error(
                "context_error",
                error_type=exc_type.__name__,
                error_message=str(exc_val)
            )


def log_request(
    logger: structlog.BoundLogger,
    method: str,
    endpoint: str,
    status: int,
    duration_ms: float,
    **extra: Any
) -> None:
    """Logs an HTTP request with structured data.

    Args:
        logger: The structlog logger instance.
        method: The HTTP method (e.g., "GET", "POST").
        endpoint: The request endpoint.
        status: The HTTP status code.
        duration_ms: The request duration in milliseconds.
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.info(
        "http_request",
        method=method,
        endpoint=endpoint,
        status=status,
        duration_ms=round(duration_ms, 2),
        **extra
    )


def log_error(
    logger: structlog.BoundLogger,
    error: Exception,
    context: str,
    **extra: Any
) -> None:
    """Logs an error with full context and stack trace.

    Args:
        logger: The structlog logger instance.
        error: The exception instance.
        context: A description of the context in which the error occurred.
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.error(
        context,
        error_type=type(error).__name__,
        error_message=str(error),
        exc_info=True,
        **extra
    )


def log_detection(
    logger: structlog.BoundLogger,
    severity: str,
    detected_type: str,
    confidence: float,
    **extra: Any
) -> None:
    """Logs an anomaly/detection event.

    Args:
        logger: The structlog logger instance.
        severity: The severity level ("critical", "warning", "info").
        detected_type: The type of anomaly detected.
        confidence: The confidence score (0.0-1.0).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.info(
        "anomaly_detected",
        severity=severity,
        type=detected_type,
        confidence=round(confidence, 3),
        **extra
    )


def log_circuit_breaker_event(
    logger: structlog.BoundLogger,
    event: str,
    breaker_name: str,
    state: str,
    reason: Optional[str] = None,
    **extra: Any
) -> None:
    """Logs a circuit breaker state change event.

    Args:
        logger: The structlog logger instance.
        event: The event type ("opened", "closed", "reset", "half_open").
        breaker_name: The name of the circuit breaker.
        state: The current state of the circuit breaker.
        reason: The reason for the state change (optional).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.warning(
        "circuit_breaker_event",
        event=event,
        breaker=breaker_name,
        state=state,
        reason=reason,
        **extra
    )


def log_retry_event(
    logger: structlog.BoundLogger,
    endpoint: str,
    attempt: int,
    status: str,
    delay_ms: Optional[float] = None,
    **extra: Any
) -> None:
    """Logs a retry attempt.

    Args:
        logger: The structlog logger instance.
        endpoint: The endpoint being retried.
        attempt: The attempt number.
        status: The status of the retry ("retrying", "success", "exhausted").
        delay_ms: The delay before the next retry in milliseconds (optional).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    level = "info" if status == "retrying" else "warning"
    getattr(logger, level)(
        "retry_event",
        endpoint=endpoint,
        attempt=attempt,
        status=status,
        delay_ms=delay_ms,
        **extra
    )


def log_recovery_action(
    logger: structlog.BoundLogger,
    action_type: str,
    status: str,
    component: str,
    duration_ms: Optional[float] = None,
    **extra: Any
) -> None:
    """Logs a recovery/remediation action.

    Args:
        logger: The structlog logger instance.
        action_type: The type of recovery action.
        status: The status of the recovery action ("started", "completed", "failed").
        component: The component being recovered.
        duration_ms: The duration of the recovery action in milliseconds (optional).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.info(
        "recovery_action",
        action=action_type,
        status=status,
        component=component,
        duration_ms=duration_ms,
        **extra
    )


def log_performance_metric(
    logger: structlog.BoundLogger,
    metric_name: str,
    value: float,
    unit: str = "ms",
    threshold: Optional[float] = None,
    **extra: Any
) -> None:
    """Logs a performance metric.

    Args:
        logger: The structlog logger instance.
        metric_name: The name of the metric.
        value: The metric value.
        unit: The unit of measurement (default: "ms").
        threshold: An SLO threshold for comparison (optional).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    alert = False
    if threshold is not None and value > threshold:
        alert = True
        log_level = "warning"
    else: 
        log_level = "info"

    getattr(logger, log_level)(
        "performance_metric",
        metric=metric_name,
        value=round(value, 2),
        unit=unit,
        threshold=threshold,
        alert=alert,
        **extra
    )


# ============================================================================
# ASYNC LOGGING FUNCTIONS
# ============================================================================

async def async_log_request(
    logger: structlog.BoundLogger,
    method: str,
    endpoint: str,
    status: int,
    duration_ms: float,
    **extra
):
    """
    Async version of log_request to avoid blocking in async contexts.
    Optimized to execute directly without thread overhead since logging is fast.

    Args:
        logger: Structlog logger instance
        method: HTTP method
        endpoint: Request endpoint
        status: HTTP status code
        duration_ms: Request duration in milliseconds
        **extra: Additional context fields
    """
    # Logging is typically fast, execute directly to avoid thread spawn overhead
    log_request(logger, method, endpoint, status, duration_ms, **extra)


async def async_log_error(
    logger: structlog.BoundLogger,
    error: Exception,
    context: str,
    **extra
):
    """
    Async version of log_error.
    Optimized to execute directly without thread overhead since logging is fast.

    Args:
        logger: Structlog logger instance
        error: Exception instance
        context: Context description
        **extra: Additional context fields
    """
    # Logging is typically fast, execute directly to avoid thread spawn overhead
    log_error(logger, error, context, **extra)


async def async_log_detection(
    logger: structlog.BoundLogger,
    severity: str,
    detected_type: str,
    confidence: float,
    **extra
):
    """
    Async version of log_detection.
    Optimized to execute directly without thread overhead since logging is fast.

    Args:
        logger: Structlog logger instance
        severity: Severity level
        detected_type: Type of anomaly detected
        confidence: Confidence score
        **extra: Additional context fields
    """
    # Logging is typically fast, execute directly to avoid thread spawn overhead
    log_detection(logger, severity, detected_type, confidence, **extra)


# ============================================================================
# FILTERING AND UTILITIES
# ============================================================================

def set_log_level(level: str) -> None:
    """Changes the logging level at runtime.

    Args:
        level: The new logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").

    Returns:
        None.

    Raises:
        ValueError: If the provided level is not a valid logging level.
    """
    if not isinstance(level, str):
        raise TypeError(f"Log level must be a string, got {type(level).__name__}")
    
    level_upper = level.upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    
    if level_upper not in valid_levels:
        raise ValueError(
            f"Invalid log level: '{level}'. Must be one of {valid_levels}"
        )
    
    try:
        logging.getLogger().setLevel(getattr(logging, level_upper))
    except AttributeError as e:
        # This should not happen after validation, but handle it anyway
        raise ValueError(f"Failed to set log level '{level}': {e}") from e


def clear_context() -> None:
    """Clears all context variables.

    Returns:
        None.
    """
    structlog.contextvars.clear_contextvars()


def bind_context(**context: Any) -> None:
    """Adds context variables to all future log entries.

    Args:
        **context: Key-value pairs to add to the logging context.

    Returns:
        None.
    """
    structlog.contextvars.bind_contextvars(**context)


def unbind_context(*keys: str) -> None:
    """Removes context variables.

    Args:
        *keys: Variable number of keys to remove from the context.

    Returns:
        None.
    """
    structlog.contextvars.unbind_contextvars(*keys)


# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize on import with error handling
try:
    enable_json = _cached_get_secret("enable_json_logging", False)
    if enable_json:
        setup_json_logging()
except (KeyError, ValueError, OSError, IOError, TypeError) as e:
    print(
        f"Warning: Failed to initialize JSON logging on import ({type(e).__name__}): {e}. "
        f"Using default logging.",
        file=sys.stderr
    )
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )

