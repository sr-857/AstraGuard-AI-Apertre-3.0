"""
Timeout handling utilities for AstraGuard-AI.

Provides decorator-based timeout enforcement for both synchronous and
asynchronous operations to prevent hanging processes.

Features:
- @with_timeout decorator for sync functions
- @async_timeout decorator for async functions
- Cross-platform support (Windows, Linux, macOS)
- Graceful timeout exceptions with context
- Integration with circuit breaker and retry logic
"""

import asyncio
import threading
import functools
import logging
from typing import Callable, Any, Optional, TypeVar, cast
from datetime import datetime

# Import centralized secrets management
from core.secrets import get_secret

logger = logging.getLogger(__name__)

# Type variable for generic function returns
T = TypeVar('T')


class TimeoutError(Exception):
    """
    Raised when an operation exceeds its timeout limit.
    
    Attributes:
        operation: Name of the operation that timed out
        timeout_seconds: Timeout value that was exceeded
        start_time: When the operation started
    """
    
    def __init__(
        self, 
        operation: str, 
        timeout_seconds: float,
        start_time: Optional[datetime] = None
    ):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        self.start_time = start_time or datetime.now()
        
        msg = f"Operation '{operation}' exceeded timeout of {timeout_seconds}s"
        super().__init__(msg)


def with_timeout(seconds: float, operation_name: Optional[str] = None):
    """
    Decorator to enforce timeout on synchronous functions.
    
    Uses threading.Timer for cross-platform compatibility.
    When timeout is reached, raises TimeoutError.
    
    Args:
        seconds: Maximum execution time in seconds
        operation_name: Optional name for logging (defaults to function name)
    
    Returns:
        Decorated function that raises TimeoutError on timeout
    
    Example:
        @with_timeout(seconds=5.0)
        def load_model():
            # Will raise TimeoutError if exceeds 5 seconds
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            op_name = operation_name or func.__name__
            start_time = datetime.now()
            
            # Container to hold result or exception
            result_container: dict = {'exception': None, 'result': None, 'completed': False}
            timeout_triggered = threading.Event()
            
            def target():
                """Execute function in thread"""
                try:
                    result_container['result'] = func(*args, **kwargs)
                    result_container['completed'] = True
                except Exception as e:
                    result_container['exception'] = e
                    result_container['completed'] = True
            
            # Start function in separate thread
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            
            # Wait for completion or timeout
            thread.join(timeout=seconds)
            
            if not result_container['completed']:
                # Timeout occurred
                timeout_triggered.set()
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.warning(
                    f"Timeout: {op_name} exceeded {seconds}s (elapsed: {elapsed:.2f}s)"
                )
                raise TimeoutError(op_name, seconds, start_time)
            
            # Check for exception in thread
            if result_container['exception']:
                raise result_container['exception']
            
            return cast(T, result_container['result'])
        
        return wrapper
    
    return decorator


def async_timeout(seconds: float, operation_name: Optional[str] = None):
    """
    Decorator to enforce timeout on asynchronous functions.

    Uses custom implementation with asyncio.create_task and asyncio.wait for proper cancellation.
    When timeout is reached, raises TimeoutError.

    Args:
        seconds: Maximum execution time in seconds
        operation_name: Optional name for logging (defaults to function name)

    Returns:
        Decorated async function that raises TimeoutError on timeout

    Example:
        @async_timeout(seconds=5.0)
        async def fetch_data():
            # Will raise TimeoutError if exceeds 5 seconds
            pass
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            op_name = operation_name or func.__name__
            start_time = datetime.now()

            # Create task for the function
            task = asyncio.create_task(func(*args, **kwargs))

            # Create timeout task
            timeout_task = asyncio.create_task(asyncio.sleep(seconds))

            # Wait for first to complete
            done, pending = await asyncio.wait(
                {task, timeout_task}, return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            for p in pending:
                p.cancel()

            # Handle results
            if task in done:
                # Function completed
                try:
                    return task.result()
                except Exception as e:
                    raise e
            else:
                # Timeout occurred
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.warning(
                    f"Async timeout: {op_name} exceeded {seconds}s (elapsed: {elapsed:.2f}s)"
                )
                raise TimeoutError(op_name, seconds, start_time)

        return wrapper

    return decorator


class TimeoutContext:
    """
    Context manager for timeout enforcement.
    
    Useful for wrapping blocks of code with timeout protection.
    
    Example:
        with TimeoutContext(seconds=5.0, operation="data_processing"):
            # Code here will timeout after 5 seconds
            process_data()
    """
    
    def __init__(self, seconds: float, operation: str = "operation"):
        self.seconds = seconds
        self.operation = operation
        self.start_time: Optional[datetime] = None
        self._timer: Optional[threading.Timer] = None
        self._timed_out = False
    
    def __enter__(self):
        self.start_time = datetime.now()
        
        def timeout_handler():
            self._timed_out = True
            logger.warning(
                f"Context timeout: {self.operation} exceeded {self.seconds}s"
            )
        
        self._timer = threading.Timer(self.seconds, timeout_handler)
        self._timer.daemon = True
        self._timer.start()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._timer:
            self._timer.cancel()
        
        if self._timed_out and exc_type is None:
            # Timeout occurred but no exception was raised
            raise TimeoutError(self.operation, self.seconds, self.start_time)
        
        return False  # Don't suppress exceptions
    
    def check_timeout(self):
        """Manually check if timeout has been exceeded"""
        if self._timed_out:
            raise TimeoutError(self.operation, self.seconds, self.start_time)


# Singleton for global timeout configuration
class TimeoutConfig:
    """
    Global timeout configuration loaded from environment variables.
    
    Provides centralized timeout values for different operations.
    """
    
    def __init__(self):
        import os
        
        # Load from environment or use defaults
        self.model_load_timeout = float(get_secret('timeout_model_load', default='300') or '300')
        self.inference_timeout = float(get_secret('timeout_inference', default='60') or '60')
        self.redis_timeout = float(get_secret('timeout_redis', default='5') or '5')
        self.file_io_timeout = float(get_secret('timeout_file_io', default='30') or '30')
        
        logger.info(
            f"Timeout config loaded: model={self.model_load_timeout}s, "
            f"inference={self.inference_timeout}s, redis={self.redis_timeout}s, "
            f"file_io={self.file_io_timeout}s"
        )


# Global singleton instance
_timeout_config: Optional[TimeoutConfig] = None


def get_timeout_config() -> TimeoutConfig:
    """Get global timeout configuration singleton"""
    global _timeout_config
    if _timeout_config is None:
        _timeout_config = TimeoutConfig()
    return _timeout_config
