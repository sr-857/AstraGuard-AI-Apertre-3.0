"""
API test fixtures and configuration for AstraGuard API testing.

Provides:
- FastAPI test client
- Mock services and dependencies
- API request/response fixtures
- Database fixtures
- Authentication fixtures
"""

import pytest
import asyncio
from typing import Generator, AsyncGenerator, Dict, Any, Optional
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import json

from fastapi.testclient import TestClient
from core.auth import APIKey, APIKeyManager
from api.service import create_app, get_app
from api.models import (
    TelemetryInput,
    TelemetryBatch,
    AnomalyResponse,
    SystemStatus,
    PhaseUpdateRequest,
    UserCreateRequest,
    APIKeyCreateRequest,
)


# ============================================================================
# FASTAPI TEST CLIENT FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def api_client() -> TestClient:
    """Create a FastAPI test client for API testing."""
    app = create_app()
    return TestClient(app)


@pytest.fixture(scope="function")
async def async_api_client():
    """Create an async test client for async endpoint testing."""
    from httpx import AsyncClient
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="function")
def mock_app():
    """Create a FastAPI app with mocked dependencies."""
    app = create_app()
    return app


# ============================================================================
# AUTHENTICATION FIXTURES
# ============================================================================

@pytest.fixture
def valid_api_key() -> str:
    """Generate a valid API key for testing."""
    return "ag-test-api-key-" + "a" * 32


@pytest.fixture
def invalid_api_key() -> str:
    """Generate an invalid API key."""
    return "invalid-key-12345"


@pytest.fixture
def api_key_manager() -> APIKeyManager:
    """Create a mock API key manager."""
    manager = Mock(spec=APIKeyManager)
    manager.validate_key = Mock(return_value=True)
    manager.get_permissions = Mock(return_value={"read", "write"})
    return manager


@pytest.fixture
def auth_headers(valid_api_key: str) -> Dict[str, str]:
    """Create authorization headers with valid API key."""
    return {"X-API-Key": valid_api_key}


@pytest.fixture
def basic_auth_headers() -> Dict[str, str]:
    """Create basic authorization headers."""
    import base64
    credentials = base64.b64encode(b"testuser:testpass").decode()
    return {"Authorization": f"Basic {credentials}"}


@pytest.fixture
def bearer_token_headers() -> Dict[str, str]:
    """Create bearer token authorization headers."""
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# TELEMETRY DATA FIXTURES
# ============================================================================

@pytest.fixture
def valid_telemetry_payload() -> TelemetryInput:
    """Create a valid telemetry input payload."""
    return TelemetryInput(
        timestamp=datetime.now().isoformat(),
        voltage=8.0,
        temperature=25.0,
        gyro=0.02,
        current=1.1,
        wheel_speed=5000,
        state_of_charge=85.0
    )


@pytest.fixture
def valid_telemetry_dict() -> Dict[str, Any]:
    """Create a valid telemetry payload as dictionary."""
    return {
        "timestamp": datetime.now().isoformat(),
        "voltage": 8.0,
        "temperature": 25.0,
        "gyro": 0.02,
        "current": 1.1,
        "wheel_speed": 5000,
        "state_of_charge": 85.0
    }


@pytest.fixture
def anomalous_telemetry_dict() -> Dict[str, Any]:
    """Create an anomalous telemetry payload."""
    return {
        "timestamp": datetime.now().isoformat(),
        "voltage": 3.5,  # Low voltage
        "temperature": 85.0,  # High temperature
        "gyro": 0.5,  # High angular velocity
        "current": 2.5,  # High current draw
        "wheel_speed": 8000,  # High wheel speed
        "state_of_charge": 15.0  # Low battery
    }


@pytest.fixture
def telemetry_batch() -> TelemetryBatch:
    """Create a batch of telemetry data."""
    return TelemetryBatch(
        batch_id="test-batch-001",
        timestamp=datetime.now().isoformat(),
        telemetry=[
            TelemetryInput(
                timestamp=datetime.now().isoformat(),
                voltage=8.0 + i * 0.1,
                temperature=25.0 + i * 0.5,
                gyro=0.02 + i * 0.01,
                current=1.1 + i * 0.05,
                wheel_speed=5000 + i * 100,
                state_of_charge=85.0 - i * 1.0
            )
            for i in range(5)
        ]
    )


@pytest.fixture
def invalid_telemetry_dict() -> Dict[str, Any]:
    """Create an invalid telemetry payload (missing required fields)."""
    return {
        "timestamp": datetime.now().isoformat(),
        "voltage": 8.0,
        # Missing other required fields
    }


@pytest.fixture
def telemetry_with_outliers() -> Dict[str, Any]:
    """Create telemetry with outliers for anomaly detection testing."""
    return {
        "timestamp": datetime.now().isoformat(),
        "voltage": 15.0,  # Extreme outlier
        "temperature": 150.0,  # Extreme outlier
        "gyro": 5.0,  # Extreme outlier
        "current": 10.0,  # Extreme outlier
        "wheel_speed": 20000,  # Extreme outlier
        "state_of_charge": 0.1  # Near zero
    }


# ============================================================================
# FEEDBACK FIXTURES
# ============================================================================

@pytest.fixture
def feedback_payload() -> Dict[str, Any]:
    """Create a feedback submission payload."""
    return {
        "anomaly_id": "test-anomaly-001",
        "label": "true_positive",
        "confidence": 0.95,
        "notes": "This was a real anomaly"
    }


@pytest.fixture
def invalid_feedback_payload() -> Dict[str, Any]:
    """Create an invalid feedback payload."""
    return {
        "anomaly_id": "test-anomaly-001",
        # Missing required 'label' field
        "confidence": 0.95
    }


# ============================================================================
# SYSTEM STATUS FIXTURES
# ============================================================================

@pytest.fixture
def mock_system_status() -> SystemStatus:
    """Create a mock system status."""
    return SystemStatus(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        uptime=3600.0,
        version="1.0.0",
        components={
            "anomaly_detector": "healthy",
            "memory_engine": "healthy",
            "policy_engine": "healthy"
        }
    )


# ============================================================================
# PHASE UPDATE FIXTURES
# ============================================================================

@pytest.fixture
def phase_update_payload() -> Dict[str, Any]:
    """Create a phase update request."""
    return {
        "new_phase": "THERMAL_REGULATION",
        "reason": "High temperature detected",
        "duration_seconds": 300
    }


@pytest.fixture
def invalid_phase_update_payload() -> Dict[str, Any]:
    """Create an invalid phase update request."""
    return {
        "new_phase": "INVALID_PHASE",  # Invalid phase
        "reason": "Test reason"
    }


# ============================================================================
# USER AND API KEY FIXTURES
# ============================================================================

@pytest.fixture
def user_create_payload() -> Dict[str, Any]:
    """Create a user creation payload."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePass123!",
        "permissions": ["read", "write"]
    }


@pytest.fixture
def apikey_create_payload() -> Dict[str, Any]:
    """Create an API key creation payload."""
    return {
        "name": "Test API Key",
        "description": "Key for testing",
        "permissions": ["read", "write", "execute"],
        "expires_in_days": 90
    }


# ============================================================================
# MOCK SERVICE FIXTURES
# ============================================================================

@pytest.fixture
def mock_anomaly_detector() -> AsyncMock:
    """Create a mock anomaly detector service."""
    detector = AsyncMock()
    detector.detect = AsyncMock(
        return_value={
            "is_anomaly": False,
            "confidence": 0.92,
            "anomaly_type": None,
            "severity": "NONE"
        }
    )
    detector.batch_detect = AsyncMock(
        return_value=[
            {
                "is_anomaly": False,
                "confidence": 0.92,
                "anomaly_type": None,
                "severity": "NONE"
            }
        ]
    )
    return detector


@pytest.fixture
def mock_policy_engine() -> AsyncMock:
    """Create a mock policy engine."""
    engine = AsyncMock()
    engine.get_policy_decision = AsyncMock(
        return_value={
            "mission_phase": "NOMINAL_OPS",
            "recommended_action": "CONTINUE",
            "severity": "NONE"
        }
    )
    return engine


@pytest.fixture
def mock_memory_engine() -> AsyncMock:
    """Create a mock memory engine."""
    engine = AsyncMock()
    engine.get_stats = AsyncMock(
        return_value={
            "total_events": 1000,
            "memory_usage": 1024000,
            "cache_hit_rate": 0.85
        }
    )
    return engine


@pytest.fixture
def mock_database() -> AsyncMock:
    """Create a mock database."""
    db = AsyncMock()
    db.save_telemetry = AsyncMock(return_value={"id": "test-001"})
    db.save_anomaly = AsyncMock(return_value={"id": "anomaly-001"})
    db.get_anomaly_history = AsyncMock(return_value=[])
    db.save_feedback = AsyncMock(return_value={"id": "feedback-001"})
    return db


# ============================================================================
# RESPONSE VALIDATION FIXTURES
# ============================================================================

@pytest.fixture
def expected_anomaly_response_schema() -> Dict[str, Any]:
    """Expected schema for anomaly response."""
    return {
        "type": "object",
        "properties": {
            "anomaly_id": {"type": "string"},
            "is_anomaly": {"type": "boolean"},
            "confidence": {"type": "number"},
            "severity": {"type": "string"},
            "anomaly_type": {"type": ["string", "null"]},
            "timestamp": {"type": "string"},
            "telemetry_id": {"type": "string"}
        },
        "required": ["anomaly_id", "is_anomaly", "confidence", "severity", "timestamp"]
    }


@pytest.fixture
def expected_health_response_schema() -> Dict[str, Any]:
    """Expected schema for health check response."""
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "timestamp": {"type": "string"},
            "version": {"type": "string"}
        },
        "required": ["status", "timestamp"]
    }


# ============================================================================
# PERFORMANCE TEST FIXTURES
# ============================================================================

@pytest.fixture
def performance_baseline() -> Dict[str, float]:
    """Performance baseline for benchmarking."""
    return {
        "telemetry_endpoint_p95": 0.1,  # 100ms
        "batch_endpoint_p95": 0.5,  # 500ms
        "health_endpoint_p95": 0.05,  # 50ms
        "auth_endpoint_p95": 0.15,  # 150ms
    }


@pytest.fixture
def load_test_config() -> Dict[str, Any]:
    """Configuration for load testing."""
    return {
        "concurrent_users": 10,
        "requests_per_user": 100,
        "think_time_ms": 100,
        "duration_seconds": 60,
        "ramp_up_seconds": 10
    }


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup():
    """Clean up after each test."""
    yield
    # Add cleanup code here if needed
    import gc
    gc.collect()
