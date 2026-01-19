"""
AstraGuard Structured Logging Module
JSON-based structured logging for enterprise observability (Azure Monitor compatible)
"""

import logging
import json
import sys
import os
from datetime import datetime
from typing import Any, Dict, Optional
import structlog
from pythonjsonlogger import jsonlogger
from core.secrets import get_secret

# ============================================================================
# STRUCTURED LOGGING CONFIGURATION
# ============================================================================

def setup_json_logging(
    log_level: str = "INFO",
    service_name: str = "astra-guard",
    environment: str = get_secret("environment", "development")
):
    """
    Setup JSON structured logging for production environments
    Compatible with Azure Monitor, ELK Stack, Splunk, etc.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service_name: Name of the service
        environment: Environment name (development, staging, production)
    """
    
    # Configure structlog for structured output
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure root logger with JSON handler
    json_handler = logging.StreamHandler(sys.stdout)
    json_formatter = jsonlogger.JsonFormatter(
        fmt='%(timestamp)s %(level)s %(name)s %(message)s',
        timestamp=True
    )
    json_handler.setFormatter(json_formatter)
    
    # Configure Python logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    root_logger.handlers.clear()
    root_logger.addHandler(json_handler)
    
    # Add global context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        service=service_name,
        environment=environment,
        version=get_secret("app_version", "1.0.0")
    )


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Bound structlog logger instance
    """
    return structlog.get_logger(name)


# ============================================================================
# LOGGING CONTEXT MANAGERS
# ============================================================================

class LogContext:
    """Context manager for scoped logging context"""
    
    def __init__(self, logger: structlog.BoundLogger, **context):
        self.logger = logger
        self.context = context
    
    def __enter__(self):
        self.logger = self.logger.bind(**self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
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
    **extra
):
    """
    Log HTTP request with structured data
    
    Args:
        logger: Structlog logger instance
        method: HTTP method
        endpoint: Request endpoint
        status: HTTP status code
        duration_ms: Request duration in milliseconds
        **extra: Additional context fields
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
    **extra
):
    """
    Log error with full context and stack trace
    
    Args:
        logger: Structlog logger instance
        error: Exception instance
        context: Context description
        **extra: Additional context fields
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
    **extra
):
    """
    Log anomaly/detection event
    
    Args:
        logger: Structlog logger instance
        severity: Severity level (critical, warning, info)
        detected_type: Type of anomaly detected
        confidence: Confidence score (0.0-1.0)
        **extra: Additional context fields
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
    **extra
):
    """
    Log circuit breaker state changes
    
    Args:
        logger: Structlog logger instance
        event: Event type (opened, closed, reset, half_open)
        breaker_name: Name of circuit breaker
        state: Current state
        reason: Reason for state change
        **extra: Additional context fields
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
    **extra
):
    """
    Log retry attempt
    
    Args:
        logger: Structlog logger instance
        endpoint: Endpoint being retried
        attempt: Attempt number
        status: Status (retrying, success, exhausted)
        delay_ms: Delay before next retry in milliseconds
        **extra: Additional context fields
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
    **extra
):
    """
    Log recovery/remediation action
    
    Args:
        logger: Structlog logger instance
        action_type: Type of recovery action
        status: Status (started, completed, failed)
        component: Component being recovered
        duration_ms: Duration of recovery in milliseconds
        **extra: Additional context fields
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
    **extra
):
    """
    Log performance metric
    
    Args:
        logger: Structlog logger instance
        metric_name: Name of metric
        value: Metric value
        unit: Unit of measurement
        threshold: SLO threshold for comparison
        **extra: Additional context fields
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
# FILTERING AND UTILITIES
# ============================================================================

def set_log_level(level: str):
    """Change logging level at runtime"""
    logging.getLogger().setLevel(getattr(logging, level))


def clear_context():
    """Clear all context variables"""
    structlog.contextvars.clear_contextvars()


def bind_context(**context):
    """Add context to all future log entries"""
    structlog.contextvars.bind_contextvars(**context)


def unbind_context(*keys):
    """Remove context variables"""
    structlog.contextvars.unbind_contextvars(*keys)


# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize on import
if get_secret("enable_json_logging", False):
    setup_json_logging()
