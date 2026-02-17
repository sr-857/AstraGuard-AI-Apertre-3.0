import pytest
from fastapi.testclient import TestClient
from api.service import app
from api.auth import get_api_key
from core.auth import APIKey

# Mock dependency for authentication
async def mock_get_api_key():
    return APIKey(
        id="smoke-test-id",
        key="smoke-test-key",
        name="smoke-test",
        permissions=["read"],
        created_at="2023-01-01T00:00:00",
        expires_at=None
    )

@pytest.mark.smoke
def test_core_api_status():
    """Verify core API endpoint (/api/v1/status) is reachable."""
    # Override dependency to bypass authentication
    app.dependency_overrides[get_api_key] = mock_get_api_key

    # Use HTTPS base URL to bypass TLSMiddleware enforcement
    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/api/v1/status")

        # Should return 200 OK
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "uptime_seconds" in data

    # Clean up override
    app.dependency_overrides = {}
