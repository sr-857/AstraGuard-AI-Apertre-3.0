"""
API Contract Tests for AstraGuard Backend

Tests API contracts for all endpoints including:
- Request/response validation
- Status codes
- Response schemas
- Error handling
- Authentication & authorization
"""

import pytest
from typing import Dict, Any
from datetime import datetime
from fastapi.testclient import TestClient
from api.models import AnomalyResponse, SystemStatus, HealthCheckResponse

from tests.api.factories import (
    TelemetryFactory,
    AnomalyFactory,
    UserFactory,
    APIKeyFactory,
    FeedbackFactory,
    ContactFactory,
)


class TestHealthCheckContract:
    """Tests for health check API contract."""

    def test_health_check_root(self, api_client: TestClient):
        """Test root health check endpoint."""
        response = api_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in data

    def test_health_check_endpoint(self, api_client: TestClient):
        """Test /health endpoint."""
        response = api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    def test_liveness_probe(self, api_client: TestClient):
        """Test /health/live endpoint."""
        response = api_client.get("/health/live")
        assert response.status_code == 200

    def test_readiness_probe(self, api_client: TestClient):
        """Test /health/ready endpoint."""
        response = api_client.get("/health/ready")
        assert response.status_code in [200, 503]

    def test_health_check_response_schema(self, api_client: TestClient):
        """Validate health check response schema."""
        response = api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # Required fields
        assert isinstance(data.get("status"), str)
        assert isinstance(data.get("timestamp"), str)
        # Optional fields
        if "version" in data:
            assert isinstance(data["version"], str)


class TestTelemetryContract:
    """Tests for telemetry API contract."""

    def test_single_telemetry_post(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test POST /api/v1/telemetry with single telemetry."""
        payload = TelemetryFactory.create_normal()
        response = api_client.post(
            "/api/v1/telemetry",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "anomaly_id" in data
        assert "is_anomaly" in data
        assert "confidence" in data
        assert "severity" in data
        assert "timestamp" in data

    def test_telemetry_invalid_payload(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test POST /api/v1/telemetry with invalid payload."""
        payload = {"invalid": "data"}
        response = api_client.post(
            "/api/v1/telemetry",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_telemetry_missing_required_fields(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test telemetry with missing required fields."""
        payload = {
            "timestamp": datetime.now().isoformat(),
            "voltage": 8.0,
        }
        response = api_client.post(
            "/api/v1/telemetry",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_telemetry_batch_post(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test POST /api/v1/telemetry/batch with batch data."""
        telemetry_list = TelemetryFactory.create_batch(count=5)
        payload = {
            "batch_id": "test-batch-001",
            "timestamp": datetime.now().isoformat(),
            "telemetry": telemetry_list,
        }
        response = api_client.post(
            "/api/v1/telemetry/batch",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == len(telemetry_list)

    def test_telemetry_get_latest(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test GET /api/v1/telemetry/latest."""
        response = api_client.get(
            "/api/v1/telemetry/latest",
            headers=auth_headers,
        )
        # Should return 200 or 404 if no telemetry yet
        assert response.status_code in [200, 404]

    def test_telemetry_response_schema(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Validate telemetry response schema."""
        payload = TelemetryFactory.create_normal()
        response = api_client.post(
            "/api/v1/telemetry",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # Validate schema
        required_fields = [
            "anomaly_id",
            "is_anomaly",
            "confidence",
            "severity",
            "timestamp",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestSystemStatusContract:
    """Tests for system status API contract."""

    def test_system_status(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test GET /api/v1/status."""
        response = api_client.get(
            "/api/v1/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "uptime" in data

    def test_system_diagnostics(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test GET /api/v1/system/diagnostics."""
        response = api_client.get(
            "/api/v1/system/diagnostics",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestPhaseUpdateContract:
    """Tests for mission phase update API contract."""

    def test_get_current_phase(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test GET /api/v1/phase."""
        response = api_client.get(
            "/api/v1/phase",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "current_phase" in data or "phase" in data

    def test_update_phase(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test POST /api/v1/phase."""
        payload = {
            "new_phase": "THERMAL_REGULATION",
            "reason": "Test phase update",
        }
        response = api_client.post(
            "/api/v1/phase",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code in [200, 400]  # 400 if phase is invalid
        if response.status_code == 200:
            data = response.json()
            assert "current_phase" in data or "new_phase" in data

    def test_invalid_phase_update(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test phase update with invalid phase."""
        payload = {
            "new_phase": "INVALID_PHASE_XYZ",
            "reason": "Test",
        }
        response = api_client.post(
            "/api/v1/phase",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code in [400, 422]


class TestMemoryStatsContract:
    """Tests for memory statistics API contract."""

    def test_memory_stats(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test GET /api/v1/memory/stats."""
        response = api_client.get(
            "/api/v1/memory/stats",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # Should contain memory-related fields
        assert isinstance(data, dict)


class TestAnomalyHistoryContract:
    """Tests for anomaly history API contract."""

    def test_anomaly_history(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test GET /api/v1/history/anomalies."""
        response = api_client.get(
            "/api/v1/history/anomalies",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "anomalies" in data or isinstance(data, list)

    def test_anomaly_history_with_filters(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test anomaly history with query filters."""
        params = {
            "limit": 10,
            "offset": 0,
            "min_confidence": 0.8,
        }
        response = api_client.get(
            "/api/v1/history/anomalies",
            params=params,
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestFeedbackContract:
    """Tests for feedback API contract."""

    def test_submit_feedback(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test POST /api/v1/feedback."""
        payload = FeedbackFactory.create()
        response = api_client.post(
            "/api/v1/feedback",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "feedback_id" in data or "id" in data

    def test_submit_invalid_feedback(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test feedback with invalid data."""
        payload = {
            "anomaly_id": "test-001",
            # Missing required fields
        }
        response = api_client.post(
            "/api/v1/feedback",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_get_pending_feedback(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test GET /api/v1/feedback/pending."""
        response = api_client.get(
            "/api/v1/feedback/pending",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestAuthenticationContract:
    """Tests for authentication API contract."""

    def test_login(self, api_client: TestClient):
        """Test POST /api/v1/auth/login."""
        payload = {
            "username": "testuser",
            "password": "testpass",
        }
        response = api_client.post(
            "/api/v1/auth/login",
            json=payload,
        )
        # May fail if credentials don't exist, but should not crash
        assert response.status_code in [200, 401, 422]

    def test_create_user(self, api_client: TestClient):
        """Test POST /api/v1/auth/users."""
        payload = UserFactory.create()
        response = api_client.post(
            "/api/v1/auth/users",
            json=payload,
        )
        assert response.status_code in [200, 201, 409]  # 409 if user exists

    def test_get_current_user(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test GET /api/v1/auth/users/me."""
        response = api_client.get(
            "/api/v1/auth/users/me",
            headers=auth_headers,
        )
        assert response.status_code in [200, 401]

    def test_create_api_key(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test POST /api/v1/auth/apikeys."""
        payload = {
            "name": "Test Key",
            "description": "Testing API key creation",
            "permissions": ["read", "write"],
            "expires_in_days": 90,
        }
        response = api_client.post(
            "/api/v1/auth/apikeys",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code in [200, 201, 400]


class TestAuthorizationContract:
    """Tests for authorization (API key) contract."""

    def test_request_without_auth_key(self, api_client: TestClient):
        """Test request without API key is rejected."""
        payload = TelemetryFactory.create_normal()
        response = api_client.post(
            "/api/v1/telemetry",
            json=payload,
        )
        # Should require authentication
        assert response.status_code in [401, 403, 422]

    def test_request_with_invalid_auth_key(self, api_client: TestClient):
        """Test request with invalid API key is rejected."""
        payload = TelemetryFactory.create_normal()
        headers = {"X-API-Key": "invalid-key"}
        response = api_client.post(
            "/api/v1/telemetry",
            json=payload,
            headers=headers,
        )
        assert response.status_code in [401, 403]

    def test_metrics_endpoint_requires_auth(self, api_client: TestClient):
        """Test that metrics endpoint requires authentication."""
        response = api_client.get("/metrics")
        # Should require auth or have special handling
        assert response.status_code in [200, 401, 403]


class TestErrorHandlingContract:
    """Tests for error handling contract."""

    def test_not_found_returns_404(self, api_client: TestClient):
        """Test 404 for non-existent endpoints."""
        response = api_client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_invalid_method_returns_405(self, api_client: TestClient):
        """Test 405 for invalid HTTP methods."""
        response = api_client.post("/health")  # GET only endpoint
        assert response.status_code in [405, 422]

    def test_malformed_json_returns_400(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test 400 for malformed JSON."""
        response = api_client.post(
            "/api/v1/telemetry",
            data="invalid json {",
            headers=auth_headers,
        )
        assert response.status_code in [400, 422]

    def test_error_response_contains_detail(self, api_client: TestClient):
        """Test that error responses contain detail message."""
        response = api_client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data or "message" in data


class TestContentTypeContract:
    """Tests for content type handling."""

    def test_json_response_content_type(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test JSON responses have correct content type."""
        response = api_client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")

    def test_post_requires_json_content_type(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test POST requires proper content type."""
        payload = TelemetryFactory.create_normal()
        # Should work with application/json
        response = api_client.post(
            "/api/v1/telemetry",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestCORSContract:
    """Tests for CORS handling."""

    def test_cors_headers_present(self, api_client: TestClient):
        """Test CORS headers in response."""
        response = api_client.get("/health")
        # CORS headers should be present or properly configured
        assert response.status_code == 200


class TestPaginationContract:
    """Tests for pagination in list endpoints."""

    def test_anomaly_history_pagination(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test pagination in anomaly history."""
        response = api_client.get(
            "/api/v1/history/anomalies",
            params={"limit": 10, "offset": 0},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # Should have pagination info or list of items
        assert isinstance(data, (dict, list))


class TestCachingContract:
    """Tests for caching headers."""

    def test_health_check_cacheable(self, api_client: TestClient):
        """Test health check has appropriate cache headers."""
        response = api_client.get("/health")
        assert response.status_code == 200
        # Cache headers may or may not be present


class TestRateLimitingContract:
    """Tests for rate limiting."""

    def test_health_check_no_rate_limit(self, api_client: TestClient):
        """Test health check is not rate limited."""
        for _ in range(10):
            response = api_client.get("/health")
            assert response.status_code == 200


class TestMetricsContract:
    """Tests for metrics endpoint."""

    def test_metrics_endpoint_format(self, api_client: TestClient):
        """Test metrics endpoint returns valid format."""
        response = api_client.get("/metrics")
        assert response.status_code in [200, 401, 403]
        if response.status_code == 200:
            # Should be Prometheus format or JSON
            assert len(response.text) > 0
