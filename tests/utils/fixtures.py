"""
Reusable Pytest Fixtures for AstraGuard Testing

Common test fixtures that can be imported and used across all test files.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from unittest.mock import Mock, MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_api_client() -> TestClient:
    """
    Create a basic FastAPI TestClient with minimal setup.
    
    Example:
        def test_endpoint(mock_api_client):
            response = mock_api_client.get("/health")
            assert response.status_code == 200
    """
    app = FastAPI()
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    return TestClient(app)


@pytest.fixture
def mock_telemetry_data() -> Dict[str, Any]:
    """
    Generate sample telemetry data for testing.
    
    Returns:
        Dict with standard telemetry fields
        
    Example:
        def test_telemetry(mock_telemetry_data):
            assert "voltage" in mock_telemetry_data
            assert mock_telemetry_data["temperature"] > 0
    """
    return {
        "voltage": 8.0,
        "temperature": 25.0,
        "gyro": 0.1,
        "current": 1.5,
        "wheel_speed": 5.0,
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def mock_batch_telemetry_data() -> list:
    """Generate batch of telemetry data."""
    return [
        {
            "voltage": 7.5 + i * 0.1,
            "temperature": 20.0 + i * 2,
            "gyro": 0.05 * i,
            "current": 1.0 + i * 0.1,
            "wheel_speed": 4.0 + i * 0.5,
            "timestamp": (datetime.now() + timedelta(seconds=i)).isoformat()
        }
        for i in range(10)
    ]


@pytest.fixture
def mock_auth_context():
    """
    Create mock authentication context with API key and user.
    
    Returns:
        Dict with 'api_key' and 'user' mocks
        
    Example:
        def test_protected_endpoint(mock_auth_context):
            api_key = mock_auth_context['api_key']
            assert api_key.key == "test-key-12345"
    """
    api_key = Mock()
    api_key.key = "test-key-12345"
    api_key.name = "Test Key"
    api_key.permissions = {"read", "write", "admin"}
    api_key.created_at = datetime.now()
    api_key.expires_at = None
    
    user = Mock()
    user.id = "test-user-id"
    user.username = "test-user"
    user.email = "test@example.com"
    user.role = "OPERATOR"
    user.is_active = True
    user.created_at = datetime.now()
    
    return {
        "api_key": api_key,
        "user": user
    }


@pytest.fixture
def mock_health_monitor():
    """
    Create mock health monitor for testing.
    
    Returns:
        Mock health monitor with common methods
        
    Example:
        def test_health_check(mock_health_monitor):
            health = mock_health_monitor.get_comprehensive_state()
            assert health["status"] == "healthy"
    """
    monitor = MagicMock()
    
    monitor.get_comprehensive_state.return_value = {
        "status": "healthy",
        "circuit_state": "CLOSED",
        "fallback_mode": "PRIMARY",
        "health_score": 0.95,
        "timestamp": datetime.now().isoformat(),
        "components": {
            "anomaly_detector": {"status": "HEALTHY"},
            "memory_store": {"status": "HEALTHY"},
            "state_machine": {"status": "HEALTHY"}
        }
    }
    
    monitor.get_all_health.return_value = {
        "component1": {"status": "HEALTHY", "timestamp": datetime.now()},
        "component2": {"status": "HEALTHY", "timestamp": datetime.now()}
    }
    
    monitor.mark_healthy = MagicMock()
    monitor.mark_degraded = MagicMock()
    monitor.mark_unhealthy = MagicMock()
    
    return monitor


@pytest.fixture
async def mock_redis_client():
    """
    Create mock Redis client for async testing.
    
    Returns:
        AsyncMock Redis client
        
    Example:
        @pytest.mark.asyncio
        async def test_cache(mock_redis_client):
            await mock_redis_client.set("key", "value")
            mock_redis_client.set.assert_called_once()
    """
    redis = AsyncMock()
    redis.connected = True
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_circuit_breaker():
    """
    Create mock circuit breaker for testing.
    
    Returns:
        Mock circuit breaker
        
    Example:
        def test_circuit(mock_circuit_breaker):
            mock_circuit_breaker.is_open.return_value = False
            assert not mock_circuit_breaker.is_open()
    """
    breaker = MagicMock()
    breaker.is_open.return_value = False
    breaker.is_closed.return_value = True
    breaker.is_half_open.return_value = False
    breaker.record_success = MagicMock()
    breaker.record_failure = MagicMock()
    breaker.trip = MagicMock()
    breaker.reset = MagicMock()
    return breaker


@pytest.fixture
def mock_state_machine():
    """
    Create mock state machine for testing.
    
    Returns:
        Mock state machine
        
    Example:
        def test_phase(mock_state_machine):
            phase = mock_state_machine.get_current_phase()
            assert phase.value == "NOMINAL_OPS"
    """
    machine = MagicMock()
    
    phase = Mock()
    phase.value = "NOMINAL_OPS"
    phase.name = "Nominal Operations"
    
    machine.get_current_phase.return_value = phase
    machine.get_phase_description.return_value = "Normal satellite operations"
    machine.get_phase_history.return_value = []
    machine.transition_to = MagicMock()
    
    return machine


@pytest.fixture
def mock_anomaly_detector():
    """
    Create mock anomaly detector for testing.
    
    Returns:
        AsyncMock anomaly detector
        
    Example:
        @pytest.mark.asyncio
        async def test_detection(mock_anomaly_detector):
            result = await mock_anomaly_detector.detect_anomaly(data)
            assert result["anomaly"] == False
    """
    detector = AsyncMock()
    detector.detect_anomaly.return_value = {
        "anomaly": False,
        "confidence": 0.95,
        "model": "primary",
        "scores": {}
    }
    detector.is_loaded.return_value = True
    detector.load_model = AsyncMock()
    return detector


@pytest.fixture
def mock_memory_store():
    """
    Create mock memory store for testing.
    
    Returns:
        Mock memory store
        
    Example:
        def test_memory(mock_memory_store):
            stats = mock_memory_store.get_stats()
            assert stats["total_events"] == 0
    """
    store = MagicMock()
    store.memory = []
    
    store.get_stats.return_value = {
        "total_events": 0,
        "critical_events": 0,
        "avg_age_hours": 0.0,
        "max_recurrence": 0
    }
    
    store.add_event = MagicMock()
    store.get_events = MagicMock(return_value=[])
    store.clear = MagicMock()
    
    return store


@pytest.fixture
def mock_fastapi_request():
    """
    Create mock FastAPI Request object.
    
    Returns:
        Mock Request
        
    Example:
        def test_endpoint(mock_fastapi_request):
            ip = mock_fastapi_request.client.host
            assert ip == "192.168.1.100"
    """
    request = Mock()
    request.headers = {
        "User-Agent": "Mozilla/5.0 Test",
        "Content-Type": "application/json"
    }
    request.client = Mock()
    request.client.host = "192.168.1.100"
    request.method = "GET"
    request.url = Mock()
    request.url.path = "/test"
    return request


@pytest.fixture
def temp_database(tmp_path):
    """
    Create temporary SQLite database for testing.
    
    Args:
        tmp_path: Pytest temp directory fixture
        
    Returns:
        Path to temporary database
        
    Example:
        def test_db(temp_database):
            import sqlite3
            conn = sqlite3.connect(temp_database)
            # Use database
            conn.close()
    """
    db_path = tmp_path / "test.db"
    yield db_path
    # Cleanup handled by tmp_path


@pytest.fixture(autouse=True)
def reset_global_state():
    """
    Auto-used fixture to reset global state between tests.
    
    Prevents test pollution by cleaning up between runs.
    """
    # Setup
    yield
    # Teardown - add any global cleanup here
    pass


@pytest.fixture
def mock_datetime():
    """
    Create mock datetime for deterministic time testing.
    
    Returns:
        Fixed datetime object
        
    Example:
        def test_timestamp(mock_datetime):
            assert mock_datetime.year == 2026
    """
    return datetime(2026, 2, 15, 12, 0, 0)


@pytest.fixture
async def async_mock():
    """
    Create a basic AsyncMock for async testing.
    
    Returns:
        AsyncMock instance
        
    Example:
        @pytest.mark.asyncio
        async def test_async_func(async_mock):
            async_mock.return_value = "result"
            result = await async_mock()
            assert result == "result"
    """
    return AsyncMock()


# Convenience function for creating custom mocks

def create_mock_api_key(
    key: str = "test-key",
    permissions: Optional[set] = None,
    expires_at: Optional[datetime] = None
):
    """
    Create a mock API key for testing.
    
    Args:
        key: API key string
        permissions: Set of permissions
        expires_at: Optional expiration datetime
        
    Returns:
        Mock APIKey object
        
    Example:
        >>> api_key = create_mock_api_key(permissions={"read", "write"})
        >>> assert "read" in api_key.permissions
    """
    mock_key = Mock()
    mock_key.key = key
    mock_key.name = f"Test Key: {key}"
    mock_key.permissions = permissions or {"read"}
    mock_key.created_at = datetime.now()
    mock_key.expires_at = expires_at
    mock_key.is_expired = expires_at and datetime.now() > expires_at
    return mock_key


def create_mock_user(
    username: str = "testuser",
    role: str = "OPERATOR",
    email: Optional[str] = None
):
    """
    Create a mock user for testing.
    
    Args:
        username: Username
        role: User role
        email: Optional email
        
    Returns:
        Mock User object
        
    Example:
        >>> user = create_mock_user(role="ADMIN")
        >>> assert user.role == "ADMIN"
    """
    mock_user = Mock()
    mock_user.id = f"user-{username}"
    mock_user.username = username
    mock_user.email = email or f"{username}@test.local"
    mock_user.role = role
    mock_user.is_active = True
    mock_user.created_at = datetime.now()
    return mock_user
