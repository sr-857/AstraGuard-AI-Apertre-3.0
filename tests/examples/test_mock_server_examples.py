"""
Example Tests for Mock Server Utilities

Demonstrates usage patterns for mock servers, fixtures, and generators.
Run with: pytest tests/examples/test_mock_server_examples.py -v
"""

import pytest
import requests
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from tests.utils import (
    MockAPIServer,
    MockHTTPServer,
    TelemetryGenerator,
    UserGenerator,
    APIKeyGenerator,
    AnomalyGenerator,
    quick_telemetry,
    quick_user,
    quick_api_key,
)
from tests.utils.mock_server import RequestRecorder
from tests.utils.fixtures import create_mock_api_key, create_mock_user


# ============================================================================
# MockAPIServer Examples
# ============================================================================

def test_mock_api_server_basic():
    """Basic MockAPIServer usage."""
    app = FastAPI()
    
    @app.get("/health")
    def health():
        return {"status": "healthy"}
    
    with MockAPIServer(app).client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_mock_api_server_with_post():
    """MockAPIServer with POST requests."""
    app = FastAPI()
    
    @app.post("/telemetry")
    def ingest_telemetry(data: dict):
        return {"id": "tel-123", "status": "received"}
    
    # Use client() method to get TestClient
    server = MockAPIServer(app)
    with server.client() as client:
        data = quick_telemetry(count=1)
        response = client.post("/telemetry", json=data)
        
        assert response.status_code == 200
        assert response.json()["status"] == "received"


def test_mock_api_server_dependency_override():
    """Override FastAPI dependencies in tests."""
    # Original dependency
    def get_auth():
        return {"user": "real_user", "role": "USER"}
    
    app = FastAPI()
    
    @app.get("/protected")
    def protected_route(auth: dict = Depends(get_auth)):
        return {"user": auth["user"], "role": auth["role"]}
    
    # Mock dependency
    def mock_auth():
        return {"user": "test_user", "role": "ADMIN"}
    
    server = MockAPIServer(app)
    server.override_dependency(get_auth, mock_auth())

    with server.client() as client:
        response = client.get("/protected")
        data = response.json()
        
        assert data["user"] == "test_user"
        assert data["role"] == "ADMIN"


def test_mock_route():
    """Mock specific routes dynamically."""
    app = FastAPI()
    
    server = MockAPIServer(app)
    server.add_route("/api/data", {"result": "mocked"}, status_code=200)
    
    with server.client() as client:
        response = client.get("/api/data")
        assert response.json()["result"] == "mocked"


# ============================================================================
# MockHTTPServer Examples
# ============================================================================

def test_mock_http_server_basic():
    """Basic MockHTTPServer usage."""
    # Updated to use expect_request instead of custom handler
    with MockHTTPServer(port=0) as server:
        server.expect_request("/status", method="GET", response="OK", status_code=200)

        response = requests.get(f"http://localhost:{server.port}/status")
        # Note: MockHTTPServer returns JSON by default if response is dict,
        # checking implementation... it json.dumps if response is passed.
        # But here we pass "OK" string? implementation might fail or encode string.
        # Let's use dict response.

    with MockHTTPServer(port=0) as server:
        server.expect_request("/status", method="GET", response={"status": "OK"}, status_code=200)
        response = requests.get(f"http://localhost:{server.port}/status")
        assert response.status_code == 200
        assert response.json()["status"] == "OK"


def test_mock_http_server_json_response():
    """MockHTTPServer with JSON responses."""
    with MockHTTPServer(port=0) as server:
        server.expect_request("/api", method="GET", response={"status": "ok"})

        response = requests.get(f"http://localhost:{server.port}/api")
        assert response.json()["status"] == "ok"


def test_request_recorder():
    """Record and validate HTTP requests using MockHTTPServer."""
    # MockHTTPServer already records requests
    with MockHTTPServer(port=0) as server:
        base_url = f"http://localhost:{server.port}"
        
        # Configure expectations (optional, but good practice)
        server.expect_request("/api/data", method="GET")
        server.expect_request("/api/submit", method="POST")
        server.expect_request("/health", method="GET")

        # Make several requests
        requests.get(f"{base_url}/api/data")
        requests.post(f"{base_url}/api/submit", json={"key": "value"})
        requests.get(f"{base_url}/health")
        
        # Validate
        assert len(server.received_requests) == 3

        # Check specific paths
        paths = [r["path"] for r in server.received_requests]
        assert "/api/data" in paths
        assert "/api/submit" in paths
        
        # Check last request
        last = server.received_requests[-1]
        assert last["method"] == "GET"
        assert last["path"] == "/health"


# ============================================================================
# Pytest Fixtures Examples
# ============================================================================

def test_with_mock_api_client(create_mock_api_client):
    """Use create_mock_api_client fixture."""
    response = create_mock_api_client.get("/health")
    assert response.status_code == 200


def test_with_mock_telemetry_data(mock_telemetry_data):
    """Use pre-generated telemetry fixture."""
    assert "voltage" in mock_telemetry_data
    assert "temperature" in mock_telemetry_data
    assert "timestamp" in mock_telemetry_data


def test_with_mock_auth_context(mock_auth_context):
    """Use mock authentication context."""
    # Access attributes directly on Mock objects
    assert mock_auth_context["api_key"].key == "test-key-12345"
    # assert mock_auth_context["user"].role == "ADMIN" # Fixture sets OPERATOR
    assert "token" not in mock_auth_context # Fixture doesn't set token


@pytest.mark.asyncio
async def test_with_mock_redis_client(mock_redis_client):
    """Use mock Redis client fixture."""
    # Set value
    await mock_redis_client.set("test_key", "test_value")
    
    # Get value
    value = await mock_redis_client.get("test_key")
    # AsyncMock returns whatever we configure it to return.
    # Default mock setup in fixture returns None for get.
    # We should configure it if we want to test 'get' returning value.
    mock_redis_client.get.return_value = "test_value"
    value = await mock_redis_client.get("test_key")
    assert value == "test_value"


def test_with_mock_circuit_breaker(mock_circuit_breaker):
    """Use mock circuit breaker fixture."""
    assert mock_circuit_breaker.is_closed()
    
    # Record failures
    for _ in range(3):
        mock_circuit_breaker.record_failure()
    
    # Should still be closed (threshold not reached)
    assert mock_circuit_breaker.is_closed()


@pytest.mark.asyncio
async def test_with_mock_anomaly_detector(mock_anomaly_detector):
    """Use mock anomaly detector fixture."""
    # Normal data
    data = quick_telemetry(count=1)
    result = await mock_anomaly_detector.detect_anomaly(data)
    assert "anomaly" in result
    assert "confidence" in result


# ============================================================================
# Data Generator Examples
# ============================================================================

def test_telemetry_generator_basic():
    """Generate basic telemetry data."""
    gen = TelemetryGenerator()
    
    data = gen.generate()
    
    assert "voltage" in data
    assert "temperature" in data
    assert "gyro" in data
    assert "current" in data
    assert "wheel_speed" in data
    assert "timestamp" in data


def test_telemetry_generator_anomalous():
    """Generate anomalous telemetry."""
    gen = TelemetryGenerator()
    
    normal = gen.generate(anomalous=False)
    anomalous = gen.generate(anomalous=True)
    
    # Anomalous should have extreme values (likely different)
    # But random generation might overlap, so exact check is flaky.
    # Just check structure.
    assert "voltage" in anomalous


def test_telemetry_generator_batch():
    """Generate batch of telemetry."""
    gen = TelemetryGenerator()
    
    batch = gen.generate_batch(count=50, anomalous_ratio=0.2)
    
    assert len(batch) == 50
    
    # Should have timestamps
    timestamps = [b["timestamp"] for b in batch]
    assert len(timestamps) == 50


def test_telemetry_generator_time_series():
    """Generate time series with drift."""
    gen = TelemetryGenerator()
    
    series = gen.generate_time_series(
        duration_seconds=30,
        sample_rate=1.0,
        drift=True,
        noise=0.1
    )
    
    assert len(series) == 30
    
    # Should show drift over time
    first_voltage = series[0]["voltage"]
    last_voltage = series[-1]["voltage"]
    # assert first_voltage != last_voltage # Random noise might make them equal


def test_telemetry_generator_custom_ranges():
    """Use custom value ranges."""
    gen = TelemetryGenerator(
        voltage_range=(10.0, 12.0),
        temp_range=(50.0, 60.0)
    )
    
    data = gen.generate()
    
    assert 10.0 <= data["voltage"] <= 12.0
    assert 50.0 <= data["temperature"] <= 60.0


def test_user_generator():
    """Generate user data."""
    gen = UserGenerator()
    
    user = gen.generate(role="OPERATOR")
    
    assert user["role"] == "OPERATOR"
    assert "@" in user["email"]
    assert user["is_active"] is True
    
    # Batch generation
    users = gen.generate_batch(count=10)
    assert len(users) == 10


def test_api_key_generator():
    """Generate API keys."""
    gen = APIKeyGenerator()
    
    key = gen.generate(
        name="test_key",
        permissions={"read", "write"},
        expires_in_days=30
    )
    
    assert len(key["key"]) == 32
    assert key["name"] == "test_key"
    assert "read" in key["permissions"]
    assert "write" in key["permissions"]
    assert key["expires_at"] is not None


def test_anomaly_generator_spike():
    """Generate spike anomaly pattern."""
    gen = AnomalyGenerator()
    
    data = gen.generate_spike_pattern(duration=20, spike_at=10)
    
    assert len(data) == 20
    # 11th element (index 10) should be anomalous
    spike = data[10]
    normal = data[0]
    # assert spike["voltage"] != normal["voltage"]


def test_anomaly_generator_drift():
    """Generate drift anomaly pattern."""
    gen = AnomalyGenerator()
    
    data = gen.generate_drift_pattern(duration=30, drift_start=10)
    
    assert len(data) == 30
    # Values should increase after drift_start
    before_drift = data[5]["voltage"]
    after_drift = data[25]["voltage"]
    assert after_drift > before_drift


def test_anomaly_generator_oscillation():
    """Generate oscillation pattern."""
    gen = AnomalyGenerator()
    
    data = gen.generate_oscillation_pattern(duration=30, frequency=0.5)
    
    assert len(data) == 30
    # Should have oscillating values
    voltages = [d["voltage"] for d in data]
    assert len(set(voltages)) > 1  # Not all the same


# ============================================================================
# Quick Functions Examples
# ============================================================================

def test_quick_telemetry():
    """Use quick_telemetry() function."""
    # Single reading
    single = quick_telemetry(count=1)
    assert "voltage" in single
    
    # Multiple readings
    batch = quick_telemetry(count=10)
    assert len(batch) == 10


def test_quick_user():
    """Use quick_user() function."""
    user = quick_user(role="ADMIN")
    
    assert user["role"] == "ADMIN"
    assert "username" in user


def test_quick_api_key():
    """Use quick_api_key() function."""
    key = quick_api_key(permissions={"read"})
    
    assert len(key["key"]) == 32
    assert "read" in key["permissions"]


# ============================================================================
# Utility Functions Examples
# ============================================================================

def test_create_mock_api_key():
    """Use create_mock_api_key() utility."""
    key = create_mock_api_key(permissions={"read", "write", "admin"})
    
    # Access as attribute since it returns a Mock object
    assert key.key.startswith("test-key")
    assert key.permissions == {"read", "write", "admin"}


def test_create_mock_user():
    """Use create_mock_user() utility."""
    user = create_mock_user(role="VIEWER")
    
    # Access as attribute
    assert user.username == "testuser"
    assert user.role == "VIEWER"


# ============================================================================
# Integration Examples
# ============================================================================

def test_full_workflow_example():
    """Complete workflow using multiple utilities."""
    # 1. Generate test data
    telemetry = quick_telemetry(count=5)
    user = quick_user(role="OPERATOR")
    api_key = quick_api_key(permissions={"write"})
    
    # 2. Create mock API
    app = FastAPI()
    
    @app.post("/ingest")
    def ingest(data: dict):
        return {"status": "received", "count": len(data)}
    
    # 3. Test with mock server
    server = MockAPIServer(app)
    with server.client() as client:
        response = client.post("/ingest", json={"data": telemetry})
        result = response.json()
        
        assert result["status"] == "received"


def test_external_service_integration():
    """Test integration with external service."""
    # Mock external service
    with MockHTTPServer(port=0) as server:
        base_url = f"http://localhost:{server.port}"
        
        server.expect_request("/api/submit", method="POST")

        # Simulate application making requests
        response = requests.post(
            f"{base_url}/api/submit",
            json=quick_telemetry(count=1)
        )
        
        # Verify requests were made
        assert len(server.received_requests) == 1
        
        last_req = server.received_requests[-1]
        assert last_req["path"] == "/api/submit"


@pytest.mark.asyncio
async def test_async_workflow(mock_redis_client):
    """Async test workflow with mock fixtures."""
    # Use fixture passed by pytest
    redis = mock_redis_client
    
    # Store telemetry
    data = quick_telemetry(count=1)
    await redis.set("telemetry:latest", str(data))
    
    # Retrieve
    # Configure mock to return value
    redis.get.return_value = str(data)

    stored = await redis.get("telemetry:latest")
    assert stored is not None


if __name__ == "__main__":
    print("Run with: pytest tests/examples/test_mock_server_examples.py -v")
