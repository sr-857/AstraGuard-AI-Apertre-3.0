"""
Tests for System-Level Resilience Layer

Verifies:
- Standardized error format (JSON schema)
- Trace ID propagation
- Circuit breaker behavior (fail-fast)
- Retry logic (exponential backoff)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.error_handlers import add_exception_handlers, ApiError
from api.logging_middleware import RequestLoggingMiddleware
from core.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from core.retry import Retry
from backend.redis_client import RedisClient

# ============================================================================
# 1. Error Format & Trace ID Tests
# ============================================================================

def test_error_format_and_trace_id():
    """Test standard error response format and trace ID."""
    app = FastAPI()
    add_exception_handlers(app)
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/error")
    async def trigger_error():
        raise ApiError(code="TEST_001", message="Test Error", status_code=400)

    client = TestClient(app)
    response = client.get("/error")

    assert response.status_code == 400
    data = response.json()

    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] == "TEST_001"
    assert data["error"]["message"] == "Test Error"
    assert "trace_id" in data["error"]
    assert response.headers["X-Trace-ID"] == data["error"]["trace_id"]


def test_validation_error_format():
    """Test Pydantic validation error format."""
    from pydantic import BaseModel

    class Item(BaseModel):
        name: str

    app = FastAPI()
    add_exception_handlers(app)

    @app.post("/items")
    async def create_item(item: Item):
        return item

    client = TestClient(app)
    response = client.post("/items", json={})  # Missing 'name'

    assert response.status_code == 400
    data = response.json()

    assert data["success"] is False
    assert data["error"]["code"] == "VAL_001"
    assert "details" in data["error"]
    assert len(data["error"]["details"]["errors"]) > 0


# ============================================================================
# 2. Circuit Breaker Tests
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_open():
    """Test circuit breaker opens after threshold failures."""
    cb = CircuitBreaker(name="test_cb", failure_threshold=2, recovery_timeout=1)

    mock_func = AsyncMock(side_effect=Exception("Fail"))

    # Fail 1
    with pytest.raises(Exception):
        await cb.call(mock_func)
    assert cb.state == CircuitState.CLOSED

    # Fail 2 (Threshold reached)
    with pytest.raises(Exception):
        await cb.call(mock_func)

    # Circuit should now be OPEN
    assert cb.state == CircuitState.OPEN

    # Fail Fast (No call to mock_func)
    with pytest.raises(CircuitOpenError):
        await cb.call(mock_func)

    # Ensure func was called exactly twice (for the 2 failures)
    assert mock_func.call_count == 2


@pytest.mark.asyncio
async def test_circuit_breaker_recovery():
    """Test circuit breaker recovers after timeout."""
    cb = CircuitBreaker(name="test_cb_recovery", failure_threshold=1, recovery_timeout=0.1, success_threshold=1)

    mock_func = AsyncMock(side_effect=Exception("Fail"))

    # Trip circuit
    with pytest.raises(Exception):
        await cb.call(mock_func)
    assert cb.state == CircuitState.OPEN

    # Wait for recovery timeout
    await asyncio.sleep(0.2)

    # Next call should be allowed (HALF-OPEN)
    mock_func.side_effect = None  # Succeed now
    mock_func.return_value = "Success"

    result = await cb.call(mock_func)
    assert result == "Success"
    assert cb.state == CircuitState.CLOSED  # Should close after success


# ============================================================================
# 3. Retry Logic Tests
# ============================================================================

@pytest.mark.asyncio
async def test_retry_logic():
    """Test retry decorator retries on failure."""
    mock_func = AsyncMock(side_effect=[ValueError("Fail 1"), ValueError("Fail 2"), "Success"])

    @Retry(max_attempts=3, base_delay=0.01, allowed_exceptions=(ValueError,))
    async def risky_operation():
        return await mock_func()

    result = await risky_operation()

    assert result == "Success"
    assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_retry_exhaustion():
    """Test retry raises exception after max attempts."""
    mock_func = AsyncMock(side_effect=ValueError("Persistent Fail"))

    @Retry(max_attempts=2, base_delay=0.01, allowed_exceptions=(ValueError,))
    async def risky_operation():
        return await mock_func()

    with pytest.raises(ValueError):
        await risky_operation()

    assert mock_func.call_count == 2


# ============================================================================
# 4. Redis Client Integration Test
# ============================================================================

@pytest.mark.asyncio
async def test_redis_client_resilience():
    """Test Redis client integration with circuit breaker."""
    redis_client = RedisClient(redis_url="redis://localhost:6379")
    redis_client.connected = True  # Simulate connected state

    # Mock internal redis instance to simulate connection failure
    # We mock _execute_safe logic or the circuit breaker inside it?
    # Actually, we can just mock the circuit breaker call

    redis_client.circuit_breaker.call = AsyncMock(side_effect=CircuitOpenError("Circuit Open"))

    # Should raise CircuitOpenError or handle it gracefully?
    # In our implementation: except CircuitOpenError -> raise

    with pytest.raises(CircuitOpenError):
        await redis_client.get_leader()
