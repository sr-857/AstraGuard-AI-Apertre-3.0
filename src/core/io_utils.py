import time
import functools
import logging
import asyncio
from typing import Optional, Callable, Any

# Try to import metrics, but don't fail if they aren't initialized yet (e.g. tests)
try:
    from astraguard.observability import IO_LATENCY, IO_BATCH_SIZE
except ImportError:
    IO_LATENCY = None
    IO_BATCH_SIZE = None

logger = logging.getLogger(__name__)

def measure_io(operation_type: str, storage_type: str):
    """
    Decorator to measure I/O latency and record it to Prometheus.

    Args:
        operation_type: Type of operation (e.g., 'write', 'read', 'serialize')
        storage_type: Type of storage (e.g., 'disk', 'memory', 'wal')
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = (time.perf_counter() - start) * 1000  # ms
                if IO_LATENCY:
                    try:
                        IO_LATENCY.labels(
                            operation_type=operation_type,
                            storage_type=storage_type
                        ).observe(duration)
                    except Exception as e:
                        logger.warning(f"Failed to record I/O metric: {e}")

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000  # ms
                if IO_LATENCY:
                    try:
                        IO_LATENCY.labels(
                            operation_type=operation_type,
                            storage_type=storage_type
                        ).observe(duration)
                    except Exception as e:
                        logger.warning(f"Failed to record I/O metric: {e}")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

def record_batch_size(size: int, operation_type: str, storage_type: str):
    """
    Helper to record batch size metric.
    """
    if IO_BATCH_SIZE:
        try:
            IO_BATCH_SIZE.labels(
                operation_type=operation_type,
                storage_type=storage_type
            ).observe(size)
        except Exception as e:
            logger.warning(f"Failed to record batch size metric: {e}")
