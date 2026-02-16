import pytest
from unittest.mock import MagicMock, AsyncMock, patch
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
def mock_restart_manager():
    # Mock the singleton getter
    with patch("src.api.service.get_restart_manager") as mock_get:
        mock_rm = AsyncMock()
        mock_get.return_value = mock_rm
        yield mock_rm

def test_restart_endpoint_success(mock_restart_manager, admin_user):
    # Override auth dependency
    app.dependency_overrides[require_admin] = lambda: admin_user
    
    try:
        response = client.post("/api/v1/system/restart")
        
        # Verify response
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "restarting"
        assert "timestamp" in data
        assert "message" in data
        
        # Verify restart was triggered
        mock_restart_manager.trigger_restart.assert_called_once()
        
    finally:
        # Clean up overrides
        app.dependency_overrides = {}

def test_restart_endpoint_unauthorized():
    # No auth override, should fail
    response = client.post("/api/v1/system/restart")
    assert response.status_code in [401, 403]
