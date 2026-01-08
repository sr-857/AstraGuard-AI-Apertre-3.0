"""
Unit tests for core/circuit_breaker.py

Tests circuit breaker functionality including state transitions,
failure handling, recovery mechanisms, and registry operations.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerMetrics,
    CircuitState,
    CircuitOpenError,
    CircuitBreakerRegistry,
    register_circuit_breaker,
    get_circuit_breaker,
    get_all_circuit_breakers,
)


class TestCircuitBreakerMetrics:
    """Test CircuitBreakerMetrics dataclass"""

    def test_initialization(self):
        """Test metrics initialization"""
        metrics = CircuitBreakerMetrics()
        assert metrics.state == CircuitState.CLOSED
        assert metrics.failures_total == 0
        assert metrics.successes_total == 0
        assert metrics.trips_total == 0
        assert metrics.last_failure_time is None
        assert isinstance(metrics.state_change_time, datetime)
        assert metrics.consecutive_successes == 0
        assert metrics.consecutive_failures == 0


class TestCircuitBreaker:
    """Test CircuitBreaker class functionality"""

    @pytest.fixture
    def breaker(self):
        """Create a test circuit breaker"""
        return CircuitBreaker(
            name="test_breaker",
            failure_threshold=3,
            success_threshold=2,
            recovery_timeout=1,
        )

    def test_initialization(self, breaker):
        """Test circuit breaker initialization"""
        assert breaker.name == "test_breaker"
        assert breaker.failure_threshold == 3
        assert breaker.success_threshold == 2
        assert breaker.recovery_timeout == 1
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open

    @pytest.mark.asyncio
    async def test_successful_call(self, breaker):
        """Test successful function call"""
        mock_func = AsyncMock(return_value="success")

        result = await breaker.call(mock_func, "arg1", kwarg="value")
        assert result == "success"
        assert breaker.is_closed

        metrics = breaker.get_metrics()
        assert metrics.successes_total == 1
        assert metrics.consecutive_successes == 1
        assert metrics.consecutive_failures == 0

        mock_func.assert_called_once_with("arg1", kwarg="value")

    @pytest.mark.asyncio
    async def test_failed_call_triggers_open(self, breaker):
        """Test that consecutive failures trigger OPEN state"""
        mock_func = AsyncMock(side_effect=Exception("test error"))

        # First failure
        with pytest.raises(Exception):
            await breaker.call(mock_func)
        assert breaker.is_closed

        # Second failure
        with pytest.raises(Exception):
            await breaker.call(mock_func)
        assert breaker.is_closed

        # Third failure triggers OPEN
        with pytest.raises(Exception):
            await breaker.call(mock_func)
        assert breaker.is_open

        metrics = breaker.get_metrics()
        assert metrics.failures_total == 3
        assert metrics.consecutive_failures == 3
        assert metrics.trips_total == 1

    @pytest.mark.asyncio
    async def test_open_circuit_fails_fast(self, breaker):
        """Test that OPEN circuit fails fast without calling function"""
        # Force circuit to OPEN
        breaker._transition_to_open()

        mock_func = AsyncMock(return_value="should_not_call")

        with pytest.raises(CircuitOpenError) as exc_info:
            await breaker.call(mock_func)

        assert exc_info.value.state == CircuitState.OPEN
        mock_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_open_circuit_uses_fallback(self, breaker):
        """Test that OPEN circuit uses fallback function"""
        # Force circuit to OPEN
        breaker._transition_to_open()

        mock_func = AsyncMock(return_value="should_not_call")
        mock_fallback = AsyncMock(return_value="fallback_result")

        result = await breaker.call(mock_func, fallback=mock_fallback)

        assert result == "fallback_result"
        mock_func.assert_not_called()
        mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_recovery_timeout_transition_to_half_open(self, breaker):
        """Test transition from OPEN to HALF_OPEN after recovery timeout"""
        # Force circuit to OPEN
        breaker._transition_to_open()
        breaker.metrics.last_failure_time = datetime.now()
        assert breaker.is_open

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        mock_func = AsyncMock(return_value="success")

        # Should transition to HALF_OPEN and succeed
        result = await breaker.call(mock_func)
        assert result == "success"
        assert breaker.is_half_open

    @pytest.mark.asyncio
    async def test_half_open_success_recovery(self, breaker):
        """Test successful recovery from HALF_OPEN state"""
        # Force to HALF_OPEN
        breaker._transition_to_half_open()
        assert breaker.is_half_open

        mock_func = AsyncMock(return_value="success")

        # First success
        await breaker.call(mock_func)
        assert breaker.is_half_open

        # Second success triggers CLOSED
        await breaker.call(mock_func)
        assert breaker.is_closed

        metrics = breaker.get_metrics()
        assert metrics.consecutive_successes == 0
        assert metrics.successes_total >= 2

    @pytest.mark.asyncio
    async def test_half_open_failure_back_to_open(self, breaker):
        """Test that any failure in HALF_OPEN returns to OPEN"""
        # Force to HALF_OPEN
        breaker._transition_to_half_open()
        assert breaker.is_half_open

        mock_func = AsyncMock(side_effect=Exception("test error"))

        with pytest.raises(Exception):
            await breaker.call(mock_func)

        assert breaker.is_open

    def test_reset_functionality(self, breaker):
        """Test manual reset to CLOSED state"""
        # Force to OPEN
        breaker._transition_to_open()
        assert breaker.is_open

        breaker.reset()
        assert breaker.is_closed

        metrics = breaker.get_metrics()
        assert metrics.failures_total == 0
        assert metrics.successes_total == 0
        assert metrics.trips_total == 0

    @pytest.mark.asyncio
    async def test_expected_exceptions_only(self, breaker):
        """Test that only expected exceptions count as failures"""
        # Custom exception that's not expected
        class CustomError(Exception):
            pass

        breaker.expected_exceptions = (ValueError,)

        mock_func_success = AsyncMock(return_value="success")
        mock_func_custom = AsyncMock(side_effect=CustomError("custom"))
        mock_func_value = AsyncMock(side_effect=ValueError("value"))

        # Custom error should not count as failure
        with pytest.raises(CustomError):
            await breaker.call(mock_func_custom)
        assert breaker.is_closed

        # ValueError should count as failure
        with pytest.raises(ValueError):
            await breaker.call(mock_func_value)
        assert breaker.is_closed  # Still closed after one failure

    def test_get_metrics_snapshot(self, breaker):
        """Test that get_metrics returns a snapshot"""
        # Modify metrics
        breaker._record_success()
        breaker._record_failure()

        metrics = breaker.get_metrics()

        # Modify breaker again
        breaker._record_success()

        # Original metrics should be unchanged
        assert metrics.successes_total == 1
        assert metrics.failures_total == 1

        # Current breaker should have updated values
        current_metrics = breaker.get_metrics()
        assert current_metrics.successes_total == 2
        assert current_metrics.failures_total == 1


class TestCircuitBreakerRegistry:
    """Test CircuitBreakerRegistry functionality"""

    @pytest.fixture
    def registry(self):
        """Create a test registry"""
        return CircuitBreakerRegistry()

    @pytest.fixture
    def breaker1(self):
        """Create test breaker 1"""
        return CircuitBreaker(name="breaker1")

    @pytest.fixture
    def breaker2(self):
        """Create test breaker 2"""
        return CircuitBreaker(name="breaker2")

    def test_register_and_get(self, registry, breaker1):
        """Test registering and retrieving breakers"""
        registry.register(breaker1)

        retrieved = registry.get("breaker1")
        assert retrieved is breaker1

        # Non-existent breaker
        assert registry.get("nonexistent") is None

    def test_get_all(self, registry, breaker1, breaker2):
        """Test getting all registered breakers"""
        registry.register(breaker1)
        registry.register(breaker2)

        all_breakers = registry.get_all()
        assert len(all_breakers) == 2
        assert all_breakers["breaker1"] is breaker1
        assert all_breakers["breaker2"] is breaker2

    def test_get_metrics_all(self, registry, breaker1, breaker2):
        """Test getting metrics for all breakers"""
        registry.register(breaker1)
        registry.register(breaker2)

        # Record some activity
        breaker1._record_success()
        breaker2._record_failure()

        all_metrics = registry.get_metrics()
        assert len(all_metrics) == 2
        assert all_metrics["breaker1"].successes_total == 1
        assert all_metrics["breaker2"].failures_total == 1


class TestGlobalRegistry:
    """Test global registry functions"""

    def test_global_register_and_get(self):
        """Test global registry functions"""
        breaker = CircuitBreaker(name="global_test")

        # Register globally
        register_circuit_breaker(breaker)

        # Retrieve globally
        retrieved = get_circuit_breaker("global_test")
        assert retrieved is breaker

        # Get all
        all_breakers = get_all_circuit_breakers()
        assert "global_test" in all_breakers


class TestCircuitOpenError:
    """Test CircuitOpenError exception"""

    def test_error_initialization(self):
        """Test error initialization with state"""
        error = CircuitOpenError("Circuit is open", CircuitState.OPEN)
        assert str(error) == "Circuit is open"
        assert error.state == CircuitState.OPEN

    def test_error_default_state(self):
        """Test error with default state"""
        error = CircuitOpenError("Default state")
        assert error.state == CircuitState.OPEN


class TestConcurrentCalls:
    """Test concurrent circuit breaker calls"""

    @pytest.mark.asyncio
    async def test_concurrent_calls_thread_safety(self):
        """Test that concurrent calls are thread-safe"""
        breaker = CircuitBreaker(name="concurrent_test", failure_threshold=5)

        async def failing_func():
            await asyncio.sleep(0.01)  # Small delay to increase concurrency
            raise Exception("Concurrent failure")

        # Launch multiple concurrent failing calls
        tasks = [breaker.call(failing_func) for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should fail with exceptions
        assert all(isinstance(r, Exception) for r in results)

        # Circuit should eventually open
        # (may not be exactly at failure_threshold due to timing)
        assert breaker.metrics.failures_total == 10
