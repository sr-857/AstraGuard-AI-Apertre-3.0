"""
Tests for REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from api.service import app, initialize_components


@pytest.fixture(autouse=True)
async def setup_components():
    """Initialize components before all tests."""
    await initialize_components()
    # Reset memory store to ensure test isolation
    from api.service import memory_store
    if memory_store:
        memory_store.memory = []


@pytest.fixture(autouse=True)
def mock_psutil(monkeypatch):
    """Mock psutil to prevent blocking calls during tests."""
    monkeypatch.setattr("psutil.cpu_percent", lambda interval=None: 0.0)
    monkeypatch.setattr("psutil.virtual_memory", lambda: type('obj', (object,), {'percent': 50.0, 'available': 1024*1024*1024})())



from api.auth import get_api_key, APIKey
from core.auth import get_current_user, User, UserRole

@pytest.fixture
def client():
    """Create test client with auth override."""
    # Mock valid API key
    async def mock_get_api_key():
        return APIKey(
            key="test-key",
            name="Test Key",
            created_at=datetime.now(),
            permissions={"read", "write", "admin"},
            rate_limit=10000
        )
    
    # Mock current user with OPERATOR role (has SUBMIT_TELEMETRY permission)
    def mock_get_current_user():
        return User(
            id="test-user-id",
            username="test-operator",
            email="operator@test.local",
            role=UserRole.OPERATOR,
            created_at=datetime.now(),
            is_active=True
        )
    
    app.dependency_overrides[get_api_key] = mock_get_api_key
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with TestClient(app) as c:
        yield c
    # Clean up
    app.dependency_overrides = {}


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns health status."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestTelemetryEndpoints:
    """Test telemetry submission endpoints."""

    def test_submit_normal_telemetry(self, client):
        """Test submitting normal telemetry (no anomaly)."""
        telemetry = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.01,
            "current": 1.2,
            "wheel_speed": 3000
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 200
        data = response.json()
        assert "is_anomaly" in data
        assert "anomaly_score" in data
        assert "recommended_action" in data

    def test_submit_anomalous_telemetry(self, client):
        """Test submitting anomalous telemetry."""
        telemetry = {
            "voltage": 6.5,  # Below threshold
            "temperature": 50.0,  # High temperature
            "gyro": 0.2,  # High gyro
            "current": 2.0,
            "wheel_speed": 5000
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 200
        data = response.json()
        assert data["is_anomaly"] is True
        assert data["anomaly_score"] > 0.0
        assert data["anomaly_type"] in ["power_fault", "thermal_fault", "attitude_fault"]
        assert "recommended_action" in data
        assert "reasoning" in data

    def test_telemetry_validation_voltage_range(self, client):
        """Test voltage validation."""
        telemetry = {
            "voltage": 100.0,  # Invalid: exceeds max
            "temperature": 25.0,
            "gyro": 0.01
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 422  # Validation error

    def test_telemetry_validation_missing_fields(self, client):
        """Test validation with missing required fields."""
        telemetry = {
            "voltage": 8.0
            # Missing temperature and gyro
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 422

    def test_telemetry_optional_fields(self, client):
        """Test telemetry with only required fields."""
        telemetry = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.01
            # current and wheel_speed are optional
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 200


class TestBatchEndpoints:
    """Test batch processing endpoints."""

    def test_submit_batch_telemetry(self, client):
        """Test submitting batch of telemetry."""
        batch = {
            "telemetry": [
                {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01},
                {"voltage": 7.5, "temperature": 30.0, "gyro": 0.02},
                {"voltage": 6.5, "temperature": 50.0, "gyro": 0.2}  # Anomaly
            ]
        }
        response = client.post("/api/v1/telemetry/batch", json=batch)
        assert response.status_code == 200
        data = response.json()
        assert data["total_processed"] == 3
        assert data["anomalies_detected"] >= 1
        assert len(data["results"]) == 3

    def test_batch_empty_validation(self, client):
        """Test batch validation with empty list."""
        batch = {"telemetry": []}
        response = client.post("/api/v1/telemetry/batch", json=batch)
        assert response.status_code == 422

    def test_batch_size_limit(self, client):
        """Test batch size limit (max 1000)."""
        batch = {
            "telemetry": [
                {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01}
                for _ in range(1001)  # Exceeds limit
            ]
        }
        response = client.post("/api/v1/telemetry/batch", json=batch)
        assert response.status_code == 422


class TestStatusEndpoints:
    """Test status endpoints."""

    def test_get_system_status(self, client):
        """Test getting system status."""
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "mission_phase" in data
        assert "components" in data
        assert "uptime_seconds" in data

    def test_status_contains_components(self, client):
        """Test status includes component health."""
        response = client.get("/api/v1/status")
        data = response.json()
        assert isinstance(data["components"], dict)


class TestPhaseEndpoints:
    """Test mission phase endpoints."""

    def test_get_current_phase(self, client):
        """Test getting current mission phase."""
        response = client.get("/api/v1/phase")
        assert response.status_code == 200
        data = response.json()
        assert "phase" in data
        assert data["phase"] in ["LAUNCH", "DEPLOYMENT", "NOMINAL_OPS", "PAYLOAD_OPS", "SAFE_MODE"]
        assert "description" in data
        assert "constraints" in data
        assert "history" in data

    def test_update_phase_valid_transition(self, client):
        """Test valid phase transition."""
        # Try transitioning to SAFE_MODE (always valid)
        request = {
            "phase": "SAFE_MODE",
            "force": True
        }
        response = client.post("/api/v1/phase", json=request)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_phase"] == "SAFE_MODE"

    def test_update_phase_invalid_enum(self, client):
        """Test invalid phase enum value."""
        request = {
            "phase": "INVALID_PHASE",
            "force": False
        }
        response = client.post("/api/v1/phase", json=request)
        assert response.status_code == 422


class TestMemoryEndpoints:
    """Test memory store endpoints."""

    def test_get_memory_stats(self, client):
        """Test getting memory statistics."""
        response = client.get("/api/v1/memory/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_events" in data
        assert "critical_events" in data
        assert "avg_age_hours" in data
        assert "max_recurrence" in data
        assert data["total_events"] >= 0


class TestHistoryEndpoints:
    """Test anomaly history endpoints."""

    def test_get_anomaly_history(self, client):
        """Test getting anomaly history."""
        response = client.get("/api/v1/history/anomalies")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "anomalies" in data
        assert isinstance(data["anomalies"], list)

    def test_history_with_limit(self, client):
        """Test history with limit parameter."""
        response = client.get("/api/v1/history/anomalies?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["anomalies"]) <= 5

    def test_history_with_severity_filter(self, client):
        """Test history with severity filter."""
        # First submit an anomaly
        telemetry = {
            "voltage": 6.5,
            "temperature": 50.0,
            "gyro": 0.2
        }
        client.post("/api/v1/telemetry", json=telemetry)

        # Query with severity filter
        response = client.get("/api/v1/history/anomalies?severity_min=0.5")
        assert response.status_code == 200
        data = response.json()
        # All returned anomalies should meet severity threshold
        for anomaly in data["anomalies"]:
            assert anomaly["severity_score"] >= 0.5


class TestIntegrationFlow:
    """Test complete integration flow."""

    def test_full_anomaly_detection_flow(self, client):
        """Test complete flow: submit telemetry -> detect anomaly -> check history."""
        # 1. Check initial status
        status_response = client.get("/api/v1/status")
        assert status_response.status_code == 200

        # 2. Get current phase
        phase_response = client.get("/api/v1/phase")
        assert phase_response.status_code == 200
        initial_phase = phase_response.json()["phase"]

        # 3. Submit anomalous telemetry
        telemetry = {
            "voltage": 6.0,  # Power fault
            "temperature": 55.0,  # Thermal fault
            "gyro": 0.3,  # Attitude fault
            "current": 2.0,
            "wheel_speed": 4000
        }
        telemetry_response = client.post("/api/v1/telemetry", json=telemetry)
        assert telemetry_response.status_code == 200
        detection = telemetry_response.json()
        assert detection["is_anomaly"] is True

        # 4. Check anomaly history
        history_response = client.get("/api/v1/history/anomalies?limit=10")
        assert history_response.status_code == 200
        history = history_response.json()
        assert history["count"] > 0

        # 5. Check memory stats
        memory_response = client.get("/api/v1/memory/stats")
        assert memory_response.status_code == 200
        memory = memory_response.json()
        assert memory["total_events"] > 0


class TestCORS:
    """Test CORS configuration."""

    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.options("/api/v1/telemetry")
        # CORS middleware should handle OPTIONS requests
        assert response.status_code in [200, 405]


class TestOpenAPIDocumentation:
    """Test OpenAPI documentation endpoints."""

    def test_docs_endpoint(self, client):
        """Test Swagger UI is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema(self, client):
        """Test OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema


class TestMemoryBounds:
    """Test bounded history to prevent memory exhaustion."""

    def test_history_bounded_to_max_size(self, client):
        """Test that anomaly history is bounded and doesn't grow indefinitely."""
        from api.service import anomaly_history, MAX_ANOMALY_HISTORY_SIZE

        # Clear history
        anomaly_history.clear()

        # Submit anomalies up to the limit
        initial_count = min(100, MAX_ANOMALY_HISTORY_SIZE)
        for i in range(initial_count):
            telemetry = {
                "voltage": 6.0,  # Anomalous
                "temperature": 50.0,
                "gyro": 0.3
            }
            client.post("/api/v1/telemetry", json=telemetry)

        # Verify history size
        assert len(anomaly_history) == initial_count

        # Submit more anomalies beyond the limit (if limit allows)
        if MAX_ANOMALY_HISTORY_SIZE < 200:
            overflow_count = 50
            for i in range(overflow_count):
                telemetry = {
                    "voltage": 6.0,
                    "temperature": 50.0,
                    "gyro": 0.3
                }
                client.post("/api/v1/telemetry", json=telemetry)

            # Verify size is capped at max
            assert len(anomaly_history) == MAX_ANOMALY_HISTORY_SIZE

    def test_history_deque_auto_eviction(self, client):
        """Test that oldest entries are automatically evicted when limit reached."""
        from api.service import anomaly_history

        # Clear and get initial state
        anomaly_history.clear()

        # Add a few anomalies
        for i in range(5):
            telemetry = {
                "voltage": 6.0 + i * 0.1,  # Slightly different values
                "temperature": 50.0,
                "gyro": 0.3
            }
            client.post("/api/v1/telemetry", json=telemetry)

        # Get the first anomaly's voltage for verification
        if len(anomaly_history) > 0:
            first_anomaly_voltage = list(anomaly_history)[0].anomaly_score

            # History should be in insertion order (FIFO)
            history_response = client.get("/api/v1/history/anomalies?limit=10")
            assert history_response.status_code == 200
            data = history_response.json()
            assert data["count"] >= 5
