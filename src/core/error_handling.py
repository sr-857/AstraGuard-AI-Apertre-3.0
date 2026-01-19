"""
Centralized Error Handling & Graceful Degradation

Provides custom exceptions, error classification, and safe execution
utilities that allow components to fail gracefully without cascading.
"""

import logging
import functools
import traceback
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exception Hierarchy
# ============================================================================

class AstraGuardException(Exception):
    """Base exception for all AstraGuard-specific errors."""
    
    def __init__(self, message: str, component: str = "unknown", 
                 context: Optional[Dict[str, Any]] = None):
        """Initialize AstraGuard exception with metadata.
        
        Args:
            message: Error message
            component: Component where error occurred
            context: Additional context data
        """
        self.message = message
        self.component = component
        self.context = context or {}
        self.timestamp = datetime.now()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to structured log format."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "component": self.component,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


class ModelLoadError(AstraGuardException):
    """Raised when model initialization/loading fails."""
    pass


class AnomalyEngineError(AstraGuardException):
    """Raised when anomaly detection computation fails."""
    pass


class PolicyEvaluationError(AstraGuardException):
    """Raised when policy engine evaluation fails."""
    pass


class StateTransitionError(AstraGuardException):
    """Raised when state machine transition fails."""
    pass


class MemoryEngineError(AstraGuardException):
    """Raised when memory store operations fail."""
    pass


class PredictiveMaintenanceError(AstraGuardException):
    """Raised when predictive maintenance operations fail."""
    pass


# ============================================================================
# Error Classification & Handling
# ============================================================================

@functools.total_ordering
class ErrorSeverity(Enum):
    """Severity levels for errors."""
    CRITICAL = "critical"      # System-level failure
    HIGH = "high"              # Component failure, fallback needed
    MEDIUM = "medium"          # Operation failure, retry recommended
    LOW = "low"                # Non-critical warning

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            order = {
                ErrorSeverity.LOW: 0,
                ErrorSeverity.MEDIUM: 1,
                ErrorSeverity.HIGH: 2,
                ErrorSeverity.CRITICAL: 3
            }
            return order[self] < order[other]
        return NotImplemented


@dataclass
class ErrorContext:
    """Structured representation of an error occurrence."""
    error_type: str
    component: str
    message: str
    severity: ErrorSeverity
    original_exception: Optional[Exception] = None
    context_data: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        """Initialize default values for ErrorContext."""
        if self.context_data is None:
            self.context_data = {}
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to structured log format."""
        return {
            "error_type": self.error_type,
            "component": self.component,
            "message": self.message,
            "severity": self.severity.value,
            "context": self.context_data,
            "timestamp": self.timestamp.isoformat(),
        }


def classify_error(exc: Exception, component: str, 
                  context: Optional[Dict[str, Any]] = None) -> ErrorContext:
    """
    Classify an exception and return structured error context.
    
    Args:
        exc: The exception to classify
        component: Name of the component where error occurred
        context: Optional context data about the error
    
    Returns:
        ErrorContext with classification and metadata
    """
    context = context or {}
    
    # Map exception types to severity
    severity_map = {
        ModelLoadError: ErrorSeverity.HIGH,
        AnomalyEngineError: ErrorSeverity.MEDIUM,
        PolicyEvaluationError: ErrorSeverity.MEDIUM,
        StateTransitionError: ErrorSeverity.HIGH,
        MemoryEngineError: ErrorSeverity.MEDIUM,
        ValueError: ErrorSeverity.MEDIUM,
        KeyError: ErrorSeverity.MEDIUM,
        Exception: ErrorSeverity.HIGH,
    }
    
    # Find matching severity
    severity = ErrorSeverity.HIGH  # Default
    for exc_type, sev in severity_map.items():
        if isinstance(exc, exc_type):
            severity = sev
            break
    
    return ErrorContext(
        error_type=exc.__class__.__name__,
        component=component,
        message=str(exc),
        severity=severity,
        original_exception=exc,
        context_data=context,
    )


def log_error(error_ctx: ErrorContext, logger_obj: Optional[logging.Logger] = None):
    """
    Log an error with structured format.
    
    Args:
        error_ctx: ErrorContext to log
        logger_obj: Logger instance (defaults to module logger)
    """
    if logger_obj is None:
        logger_obj = logger
    
    log_data = error_ctx.to_dict()
    # Remove 'message' from extra data to avoid logging conflict
    log_data_extra = {k: v for k, v in log_data.items() if k != 'message'}
    
    if error_ctx.severity == ErrorSeverity.CRITICAL:
        logger_obj.critical(f"CRITICAL ERROR in {error_ctx.component}: {error_ctx.message}", 
                           extra=log_data_extra)
    elif error_ctx.severity == ErrorSeverity.HIGH:
        logger_obj.error(f"ERROR in {error_ctx.component}: {error_ctx.message}", 
                        extra=log_data_extra)
    elif error_ctx.severity == ErrorSeverity.MEDIUM:
        logger_obj.warning(f"WARNING in {error_ctx.component}: {error_ctx.message}", 
                          extra=log_data_extra)
    else:
        logger_obj.info(f"INFO from {error_ctx.component}: {error_ctx.message}", 
                       extra=log_data_extra)


# ============================================================================
# Safe Execution Utilities
# ============================================================================

T = TypeVar('T')
FallbackT = TypeVar('FallbackT')


def handle_component_error(
    component: str,
    fallback_value: Optional[Any] = None,
    severity: Optional[ErrorSeverity] = None,
    log_traceback: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., Union[T, Any]]]:
    """
    Decorator to wrap component functions with centralized error handling.
    
    Usage:
        @handle_component_error("my_component", fallback_value=None)
        def risky_function():
            ...
    
    Args:
        component: Name of the component
        fallback_value: Value to return on error (defaults to None)
        severity: Error severity level
        log_traceback: Whether to log full traceback
    
    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Union[T, Any]]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Union[T, Any]:
            try:
                return func(*args, **kwargs)
            except AstraGuardException as e:
                # Already an AstraGuard exception
                e.component = component
                error_ctx = classify_error(e, component)
                # Apply severity override from decorator if cleaner than map
                if severity is not None:
                     error_ctx.severity = severity
                log_error(error_ctx)
                if log_traceback:
                    logger.debug(f"Traceback:\n{traceback.format_exc()}")
                return fallback_value
            except Exception as e:
                # Wrap other exceptions
                error_ctx = classify_error(e, component, {"function": func.__name__})
                # Apply severity override from decorator
                if severity is not None:
                     error_ctx.severity = severity
                log_error(error_ctx)
                if log_traceback:
                    logger.debug(f"Traceback:\n{traceback.format_exc()}")
                return fallback_value
        return wrapper
    return decorator


def safe_execute(
    func: Callable[..., T],
    *args,
    component: str = "unknown",
    fallback_value: Optional[Any] = None,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Union[T, Any]:
    """
    Safely execute a function with centralized error handling.
    
    Usage:
        result = safe_execute(
            risky_function,
            arg1, arg2,
            component="my_component",
            fallback_value=None,
            context={"phase": "launch"}
        )
    
    Args:
        func: Function to execute
        *args: Positional arguments to function
        component: Component name for logging
        fallback_value: Value to return on error
        context: Additional context for logging
        **kwargs: Keyword arguments to function
    
    Returns:
        Function result or fallback_value on error
    """
    try:
        return func(*args, **kwargs)
    except AstraGuardException as e:
        e.component = component
        e.context.update(context or {})
        error_ctx = classify_error(e, component, context)
        log_error(error_ctx)
        logger.debug(f"Traceback:\n{traceback.format_exc()}")
        return fallback_value
    except Exception as e:
        context_data = {"function": func.__name__}
        if context:
            context_data.update(context)
        error_ctx = classify_error(e, component, context_data)
        log_error(error_ctx)
        logger.debug(f"Traceback:\n{traceback.format_exc()}")
        return fallback_value


class ErrorContext_ContextManager:
    """Context manager for handling errors in a code block.
    
    Ensures proper resource cleanup and error logging within a context.
    Automatically captures, classifies, and logs exceptions with structured metadata.
    
    Resource cleanup: Automatically cleans up via __exit__ method.
    Exception handling: All exceptions are logged with component context before processing.
    
    Usage:
        with ErrorContext_ContextManager("component_name", on_error=cleanup_fn) as ctx:
            # risky operation - resources automatically cleaned on exception or exit
            pass
    """
    
    def __init__(
        self,
        component: str,
        default_return: Any = None,
        on_error: Optional[Callable[[ErrorContext], Any]] = None,
        reraise: bool = False,
    ):
        """
        Initialize error context manager with resource cleanup support.
        
        Args:
            component: Component name for logging and context
            default_return: Value to return on error
            on_error: Optional callback for resource cleanup/alerting on error
            reraise: Whether to reraise exception after logging and cleanup
        
        Note:
            The on_error callback is invoked before resource cleanup in __exit__,
            allowing for graceful cleanup (file handles, connections, etc).
        """
        self.component = component
        self.default_return = default_return
        self.on_error = on_error
        self.reraise = reraise
        self.error_ctx: Optional[ErrorContext] = None
    
    def __enter__(self):
        """Enter the error context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the error context manager, handling any exceptions.
        
        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
            
        Returns:
            bool: True to suppress exception, False to propagate
        """
        if exc_type is None:
            return False  # No exception
        
        # Classify and log the error
        self.error_ctx = classify_error(exc_val, self.component)
        log_error(self.error_ctx)
        logger.debug(f"Traceback:\n{traceback.format_exc()}")
        
        # Call error callback if provided
        if self.on_error:
            self.on_error(self.error_ctx)
        
        # Return True to suppress exception (unless reraise=True)
        return not self.reraise
