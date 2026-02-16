import pytest
from fastapi.testclient import TestClient
from api.service import app

# Use HTTPS base URL to bypass TLSMiddleware enforcement
client = TestClient(app, base_url="https://testserver")

@pytest.mark.smoke
def test_health_endpoint():
    """Verify that the health endpoint returns a valid status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
