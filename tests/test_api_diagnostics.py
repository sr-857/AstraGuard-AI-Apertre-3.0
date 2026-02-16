import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

# Import app and auth resources
from src.api.service import app, require_admin
from src.core.auth import User, UserRole

client = TestClient(app)

# Mock user for authentication
@pytest.fixture
def admin_user():
    return User(
        id="admin_123",
        username="admin_user",
        email="admin@astraguard.com",
        role=UserRole.ADMIN,
        created_at=datetime.now(),
        is_active=True
    )

@pytest.fixture
def mock_diagnostics():
    with patch("src.api.service.SystemDiagnostics") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        # Setup return value for run_full_diagnostics
        mock_instance.run_full_diagnostics.return_value = {
            "timestamp": datetime.now().isoformat(),
            "system_info": {"os": "TestOS"},
            "resources": {"cpu": 10},
            "network": {},
            "process": {},
            "application_health": {"status": "healthy"}
        }
        yield mock_instance

def test_diagnostics_endpoint_success(mock_diagnostics, admin_user):
    # Override auth dependency
    app.dependency_overrides[require_admin] = lambda: admin_user
    
    try:
        response = client.get("/api/v1/system/diagnostics")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "system_info" in data
        assert data["system_info"]["os"] == "TestOS"
        
        # Verify diagnostics was called
        mock_diagnostics.run_full_diagnostics.assert_called_once()
        
    finally:
        # Clean up overrides
        app.dependency_overrides = {}

def test_diagnostics_endpoint_unauthorized():
    # No auth override, should fail
    response = client.get("/api/v1/system/diagnostics")
    assert response.status_code in [401, 403]
