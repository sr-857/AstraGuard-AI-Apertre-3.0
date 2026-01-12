"""
Self-Healing Retry Logic with Exponential Backoff + Full Jitter
Implements automatic retry with exponential backoff before circuit breaker engagement.
"""
import asyncio
import random
import time
from functools import wraps
from typing import Callable, Any, Tuple, Optional
from datetime import datetime
import logging

from prometheus_client import Counter, Histogram, Gauge

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================

RETRY_ATTEMPTS_TOTAL = Counter(
    'astra_retry_attempts_total',
    'Total retry attempts',
    ['outcome']  # success, failed
)

RETRY_DELAYS_SECONDS = Histogram(
    'astra_retry_delays_seconds',
    'Retry delay durations in seconds',
    buckets=(0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
)

RETRY_EXHAUSTIONS_TOTAL = Counter(
    'astra_retry_exhaustions_total',
    'Number of times retry limit exhausted',
    ['function']
)

RETRY_BACKOFF_LEVEL = Gauge(
    'astra_retry_backoff_level',
    'Current backoff level (attempt number)',
    ['function']
)


# ============================================================================
# RETRY DECORATOR
# ============================================================================

class Retry:
    """
    Exponential backoff retry decorator with full jitter.
    
    Implements the retry pattern before circuit breaker engagement:
    1. Immediate attempt (attempt 0)
    2. Exponential backoff with jitter on retries
    3. Exhaustion after max_attempts
    
    Features:
    - Configurable exception filtering
    - Full jitter to prevent thundering herd
    - Prometheus metrics integration
    - Async/await compatible
    
    Example:
        @Retry(max_attempts=3, base_delay=0.5)
        async def fetch_data():
            return await api.call()
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        allowed_exceptions: Optional[Tuple] = None,
        jitter_type: str = "full"
    ):
        """
        Initialize retry decorator.
        
        Args:
            max_attempts: Maximum number of attempts (including first)
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay cap in seconds
            allowed_exceptions: Tuple of exception types to retry on
                               (default: TimeoutError, ConnectionError)
            jitter_type: Type of jitter - "full" (default), "equal", "decorrelated"
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.allowed_exceptions = allowed_exceptions or (
            TimeoutError,
            ConnectionError,
            OSError,
            asyncio.TimeoutError,
        )
        self.jitter_type = jitter_type
        self.last_exception: Optional[Exception] = None
    
    def __call__(self, func: Callable) -> Callable:
        """Decorate async function with retry logic."""
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await self._execute_with_retry(func, args, kwargs)
        
        # Also support sync functions
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return self._execute_with_retry_sync(func, args, kwargs)
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    async def _execute_with_retry(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict
    ) -> Any:
        """Execute async function with retry logic."""
        func_name = getattr(func, '__name__', 'unknown')
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                # Execute function
                result = await func(*args, **kwargs)
                
                # Success
                RETRY_ATTEMPTS_TOTAL.labels(outcome='success').inc()
                if attempt > 0:
                    logger.debug(
                        f"Retry successful for {func_name} "
                        f"after {attempt} retries"
                    )
                return result
            
            except self.allowed_exceptions as e:
                last_exception = e
                RETRY_ATTEMPTS_TOTAL.labels(outcome='failed').inc()
                
                # Check if this is the last attempt
                if attempt == self.max_attempts - 1:
                    RETRY_EXHAUSTIONS_TOTAL.labels(function=func_name).inc()
                    logger.error(
                        f"Retry exhausted for {func_name} after "
                        f"{self.max_attempts} attempts: {str(e)}"
                    )
                    raise
                
                # Calculate backoff delay
                delay = self._calculate_delay(attempt)
                RETRY_BACKOFF_LEVEL.labels(function=func_name).set(attempt + 1)
                RETRY_DELAYS_SECONDS.observe(delay)
                
                logger.warning(
                    f"Retry {attempt + 1}/{self.max_attempts} for {func_name} "
                    f"after {delay:.3f}s: {str(e)}"
                )
                
                # Sleep before retry
                await asyncio.sleep(delay)
            
            except Exception as e:
                # Non-retryable exception
                logger.error(
                    f"Non-retryable exception in {func_name}: {type(e).__name__}"
                )
                raise
        
        # Should not reach here, but raise if we do
        if last_exception:
            raise last_exception
        raise RuntimeError(f"Unexpected retry exhaustion for {func_name}")
    
    def _execute_with_retry_sync(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict
    ) -> Any:
        """Execute sync function with retry logic."""
        func_name = getattr(func, '__name__', 'unknown')
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Success
                RETRY_ATTEMPTS_TOTAL.labels(outcome='success').inc()
                if attempt > 0:
                    logger.debug(
                        f"Retry successful for {func_name} "
                        f"after {attempt} retries"
                    )
                return result
            
            except self.allowed_exceptions as e:
                last_exception = e
                RETRY_ATTEMPTS_TOTAL.labels(outcome='failed').inc()
                
                # Check if this is the last attempt
                if attempt == self.max_attempts - 1:
                    RETRY_EXHAUSTIONS_TOTAL.labels(function=func_name).inc()
                    logger.error(
                        f"Retry exhausted for {func_name} after "
                        f"{self.max_attempts} attempts: {str(e)}"
                    )
                    raise
                
                # Calculate backoff delay
                delay = self._calculate_delay(attempt)
                RETRY_BACKOFF_LEVEL.labels(function=func_name).set(attempt + 1)
                RETRY_DELAYS_SECONDS.observe(delay)
                
                logger.warning(
                    f"Retry {attempt + 1}/{self.max_attempts} for {func_name} "
                    f"after {delay:.3f}s: {str(e)}"
                )
                
                # Sleep before retry
                time.sleep(delay)
            
            except Exception as e:
                # Non-retryable exception
                logger.error(
                    f"Non-retryable exception in {func_name}: {type(e).__name__}"
                )
                raise
        
        # Should not reach here, but raise if we do
        if last_exception:
            raise last_exception
        raise RuntimeError(f"Unexpected retry exhaustion for {func_name}")
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff with jitter.
        
        Formula:
            exponential: base_delay * 2^attempt
            capped: min(exponential, max_delay)
            jittered: capped * random_jitter_factor
        
        Jitter types:
            - full: delay * uniform(0.5, 1.5)
            - equal: delay / 2 + uniform(0, delay / 2)
            - decorrelated: min(max_delay, delay * uniform(0, 3))
        """
        # Exponential backoff: 0.5 * 2^attempt
        exponential = self.base_delay * (2 ** attempt)
        
        # Cap at max_delay
        capped = min(exponential, self.max_delay)
        
        # Apply jitter
        if self.jitter_type == "full":
            # Full jitter: uniformly distributed between 0 and 2x delay
            jittered = capped * random.uniform(0.5, 1.5)
        elif self.jitter_type == "equal":
            # Equal jitter: delay/2 + uniform random
            jittered = (capped / 2) + (capped / 2) * random.random()
        elif self.jitter_type == "decorrelated":
            # Decorrelated jitter: recommended for general use
            jittered = min(self.max_delay, capped * random.uniform(0, 3))
        else:
            jittered = capped
        
        return jittered
    
    @staticmethod
    def reset_metrics() -> None:
        """Reset all metrics (for testing)."""
        RETRY_ATTEMPTS_TOTAL._metrics.clear()
        RETRY_EXHAUSTIONS_TOTAL._metrics.clear()


# ============================================================================
# EXPONENTIAL BACKOFF UTILITIES
# ============================================================================

def calculate_backoff_delays(
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0
) -> list:
    """
    Calculate expected backoff schedule (without jitter).
    
    Useful for documentation and testing.
    
    Returns:
        List of delays for each retry attempt
    """
    delays = [0]  # First attempt has no delay
    for attempt in range(1, max_attempts):
        delay = base_delay * (2 ** (attempt - 1))
        delay = min(delay, max_delay)
        delays.append(delay)
    return delays


def get_retry_metrics() -> dict:
    """Get current retry metrics snapshot."""
    return {
        'attempts_total': RETRY_ATTEMPTS_TOTAL._metrics,
        'exhaustions_total': RETRY_EXHAUSTIONS_TOTAL._metrics,
    }

# merge coflicts

