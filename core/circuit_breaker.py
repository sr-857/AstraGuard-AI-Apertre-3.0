"""
Circuit Breaker Pattern Implementation

Prevents cascading failures by monitoring service health and failing fast
when a service becomes unavailable. Implements three-state pattern:
- CLOSED: Normal operation
- OPEN: Service unavailable, fail fast
- HALF_OPEN: Testing if service recovered

Follows Netflix Hystrix and AWS patterns for production reliability.
"""

import asyncio
import time
import logging
from typing import Callable, Any, Optional, Tuple, Set
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerMetrics:
    """Metrics collected by circuit breaker"""
    state: CircuitState = CircuitState.CLOSED
    failures_total: int = 0
    successes_total: int = 0
    trips_total: int = 0
    last_failure_time: Optional[datetime] = None
    state_change_time: datetime = field(default_factory=datetime.now)
    consecutive_successes: int = 0
    consecutive_failures: int = 0


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open"""
    def __init__(self, message: str, state: CircuitState = CircuitState.OPEN):
        self.state = state
        super().__init__(message)


class CircuitBreaker:
    """
    Production-grade circuit breaker for resilience.
    
    Protects against cascading failures by:
    1. Monitoring failure rates
    2. Failing fast when service is down
    3. Attempting recovery in HALF_OPEN state
    
    Thread-safe for concurrent async operations.
    """
    
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        success_threshold: int = 2,
        recovery_timeout: int = 30,
        expected_exceptions: Tuple[type, ...] = (Exception,),
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker identifier
            failure_threshold: Failures to trigger OPEN state
            success_threshold: Successes in HALF_OPEN to close
            recovery_timeout: Seconds before attempting recovery
            expected_exceptions: Exception types to count as failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        
        # State management with thread safety
        self._lock = threading.RLock()
        self.metrics = CircuitBreakerMetrics()
        
        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"threshold={failure_threshold}, recovery={recovery_timeout}s"
        )
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        with self._lock:
            return self.metrics.state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)"""
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)"""
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)"""
        return self.state == CircuitState.HALF_OPEN
    
    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self.metrics.last_failure_time is None:
            return False
        
        elapsed = time.time() - self.metrics.last_failure_time.timestamp()
        return elapsed >= self.recovery_timeout
    
    async def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Async function to call
            *args: Positional arguments
            fallback: Fallback function if circuit is open
            **kwargs: Keyword arguments
            
        Returns:
            Function result or fallback result
            
        Raises:
            CircuitOpenError: If circuit is open and no fallback provided
        """
        with self._lock:
            # Transition from OPEN to HALF_OPEN if recovery timeout exceeded
            if self.is_open and self._should_attempt_recovery():
                self._transition_to_half_open()
            
            # Fail fast if still open
            if self.is_open:
                if fallback:
                    logger.warning(
                        f"Circuit '{self.name}' is OPEN, using fallback"
                    )
                    return await fallback(*args, **kwargs)
                raise CircuitOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service recovery in ~{self.recovery_timeout}s",
                    state=CircuitState.OPEN
                )
        
        # Execute function
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result

        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            if isinstance(e, self.expected_exceptions):
                self._record_failure()
                raise
            else:
                raise
    
    def _record_success(self):
        """Record successful call"""
        with self._lock:
            self.metrics.successes_total += 1
            self.metrics.consecutive_successes += 1
            self.metrics.consecutive_failures = 0
            
            logger.debug(
                f"Circuit '{self.name}' success "
                f"(state={self.state}, successes={self.metrics.consecutive_successes})"
            )
            
            # HALF_OPEN -> CLOSED transition
            if self.is_half_open:
                if self.metrics.consecutive_successes >= self.success_threshold:
                    self._transition_to_closed()
            
            # CLOSED: reduce failure count (recovery from transient issues)
            elif self.is_closed:
                self.metrics.consecutive_failures = max(
                    0, self.metrics.consecutive_failures - 1
                )
    
    def _record_failure(self):
        """Record failed call"""
        with self._lock:
            self.metrics.failures_total += 1
            self.metrics.consecutive_failures += 1
            self.metrics.consecutive_successes = 0
            self.metrics.last_failure_time = datetime.now()
            
            logger.warning(
                f"Circuit '{self.name}' failure "
                f"(state={self.state}, failures={self.metrics.consecutive_failures}/{self.failure_threshold})"
            )
            
            # CLOSED -> OPEN transition
            if self.is_closed:
                if self.metrics.consecutive_failures >= self.failure_threshold:
                    self._transition_to_open()
            
            # HALF_OPEN -> OPEN transition (any failure fails recovery)
            elif self.is_half_open:
                self._transition_to_open()
    
    def _transition_to_open(self):
        """Transition circuit to OPEN state"""
        if self.metrics.state != CircuitState.OPEN:
            self.metrics.state = CircuitState.OPEN
            self.metrics.trips_total += 1
            self.metrics.state_change_time = datetime.now()
            logger.error(
                f"Circuit '{self.name}' OPENED after "
                f"{self.metrics.consecutive_failures} failures"
            )
    
    def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state"""
        self.metrics.state = CircuitState.HALF_OPEN
        self.metrics.consecutive_successes = 0
        self.metrics.consecutive_failures = 0
        self.metrics.state_change_time = datetime.now()
        logger.info(f"Circuit '{self.name}' -> HALF_OPEN (testing recovery)")
    
    def _transition_to_closed(self):
        """Transition circuit to CLOSED state"""
        self.metrics.state = CircuitState.CLOSED
        self.metrics.consecutive_failures = 0
        self.metrics.consecutive_successes = 0
        self.metrics.state_change_time = datetime.now()
        logger.info(f"Circuit '{self.name}' CLOSED (recovered)")
    
    def reset(self):
        """Reset circuit to CLOSED state (manual override)"""
        with self._lock:
            self.metrics = CircuitBreakerMetrics()
            logger.info(f"Circuit '{self.name}' manually reset to CLOSED")
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current metrics snapshot"""
        with self._lock:
            return CircuitBreakerMetrics(
                state=self.metrics.state,
                failures_total=self.metrics.failures_total,
                successes_total=self.metrics.successes_total,
                trips_total=self.metrics.trips_total,
                last_failure_time=self.metrics.last_failure_time,
                state_change_time=self.metrics.state_change_time,
                consecutive_successes=self.metrics.consecutive_successes,
                consecutive_failures=self.metrics.consecutive_failures,
            )


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    Useful for monitoring all circuit breakers in a system.
    """
    
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
    
    def register(self, breaker: CircuitBreaker) -> None:
        """Register a circuit breaker"""
        with self._lock:
            self._breakers[breaker.name] = breaker
            logger.debug(f"Registered circuit breaker: {breaker.name}")
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        with self._lock:
            return self._breakers.get(name)
    
    def get_all(self) -> dict[str, CircuitBreaker]:
        """Get all circuit breakers"""
        with self._lock:
            return dict(self._breakers)
    
    def get_metrics(self) -> dict[str, CircuitBreakerMetrics]:
        """Get metrics for all circuit breakers"""
        with self._lock:
            return {
                name: breaker.get_metrics()
                for name, breaker in self._breakers.items()
            }


# Global registry
_global_registry = CircuitBreakerRegistry()


def register_circuit_breaker(breaker: CircuitBreaker) -> CircuitBreaker:
    """Register a circuit breaker globally"""
    _global_registry.register(breaker)
    return breaker


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get registered circuit breaker by name"""
    return _global_registry.get(name)


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """Get all registered circuit breakers"""
    return _global_registry.get_all()
