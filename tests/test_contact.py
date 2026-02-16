"""
Tests for Contact Form API

Tests validation, rate limiting, spam protection, and database persistence.
"""

import pytest
import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import FastAPI
import tempfile
import shutil
import os

# Import the contact router
from api.contact import router, init_database, DB_PATH, DATA_DIR


# Test app setup
@pytest.fixture
def test_app():
    """Create a test FastAPI app with contact router"""
    app = FastAPI()
    app.include_router(router)
    
    # Override admin dependency to bypass auth
    from api.contact import get_admin_user
    app.dependency_overrides[get_admin_user] = lambda: {"username": "admin", "roles": ["admin"]}
    
    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Setup temporary database for tests"""
    test_data_dir = tmp_path / "data"
    test_data_dir.mkdir()
    test_db_path = test_data_dir / "contact_submissions.db"
    
    # Monkey patch the paths
    monkeypatch.setattr("api.contact.DATA_DIR", test_data_dir)
    monkeypatch.setattr("api.contact.DB_PATH", test_db_path)
    monkeypatch.setattr("api.contact.NOTIFICATION_LOG", test_data_dir / "contact_notifications.log")
    
    # Clear the in-memory rate limiter between tests
    from api.contact import _in_memory_limiter
    _in_memory_limiter.requests.clear()
    
    # Initialize database
    init_database()
    
    yield test_db_path
    
    # Cleanup
    if test_db_path.exists():
        test_db_path.unlink()


def test_submit_valid_contact_form(client):
    """Test successful form submission with valid data"""
    payload = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1-555-123-4567",
        "subject": "Feature Request",
        "message": "I would like to request a new feature for the security dashboard."
    }
    
    response = client.post("/api/contact", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "submission_id" in data
    assert "Thank you" in data["message"]


def test_submit_minimal_valid_form(client):
    """Test submission with only required fields"""
    payload = {
        "name": "Jane Smith",
        "email": "jane@company.com",
        "subject": "General Inquiry",
        "message": "This is a test message with minimum required length."
    }
    
    response = client.post("/api/contact", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True


def test_missing_required_field(client):
    """Test validation error when required field is missing"""
    payload = {
        "name": "John Doe",
        "email": "john@example.com",
        "subject": "Test"
        # Missing 'message' field
    }
    
    response = client.post("/api/contact", json=payload)
    
    assert response.status_code == 422  # Validation error


def test_invalid_email_format(client):
    """Test validation error for invalid email"""
    payload = {
        "name": "John Doe",
        "email": "not-an-email",
        "subject": "Test Subject",
        "message": "This is a test message."
    }
    
    response = client.post("/api/contact", json=payload)
    
    assert response.status_code == 422


def test_name_too_short(client):
    """Test validation error for name less than 2 characters"""
    payload = {
        "name": "A",
        "email": "test@example.com",
        "subject": "Test",
        "message": "This is a test message."
    }
    
    response = client.post("/api/contact", json=payload)
    
    assert response.status_code == 422


def test_message_too_short(client):
    """Test validation error for message less than 10 characters"""
    payload = {
        "name": "John Doe",
        "email": "john@example.com",
        "subject": "Test",
        "message": "Short"
    }
    
    response = client.post("/api/contact", json=payload)
    
    assert response.status_code == 422


def test_xss_sanitization(client, setup_test_db):
    """Test that dangerous characters are removed"""
    payload = {
        "name": "John<script>alert('xss')</script>Doe",
        "email": "john@example.com",
        "subject": "Test<script>",
        "message": "Message with <b>HTML</b> and 'quotes' and \"double quotes\""
    }
    
    response = client.post("/api/contact", json=payload)
    
    assert response.status_code == 201
    
    # Check database to verify sanitization
    conn = sqlite3.connect(setup_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name, subject, message FROM contact_submissions WHERE id = ?", 
                   (response.json()["submission_id"],))
    row = cursor.fetchone()
    conn.close()
    
    # Verify dangerous characters are removed
    assert "<script>" not in row[0]
    assert "<script>" not in row[1]
    assert "<b>" not in row[2]


def test_honeypot_spam_protection(client, setup_test_db):
    """Test that honeypot field catches bots"""
    payload = {
        "name": "Bot User",
        "email": "bot@spam.com",
        "subject": "Spam Message",
        "message": "This is spam content",
        "website": "http://spam.com"  # Honeypot field
    }
    
    response = client.post("/api/contact", json=payload)
    
    # Should return success but not save to database
    assert response.status_code == 201
    assert response.json()["success"] is True
    assert "submission_id" not in response.json()
    
    # Verify not saved to database
    conn = sqlite3.connect(setup_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM contact_submissions WHERE email = ?", 
                   ("bot@spam.com",))
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count == 0


def test_email_normalization(client, setup_test_db):
    """Test that email is normalized to lowercase"""
    payload = {
        "name": "John Doe",
        "email": "JOHN@EXAMPLE.COM",
        "subject": "Test",
        "message": "Test message content"
    }
    
    response = client.post("/api/contact", json=payload)
    
    assert response.status_code == 201
    submission_id = response.json()["submission_id"]
    
    # Check database
    conn = sqlite3.connect(setup_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM contact_submissions WHERE id = ?", (submission_id,))
    email = cursor.fetchone()[0]
    conn.close()
    
    assert email == "john@example.com"


def test_rate_limiting(client, monkeypatch):
    """Test rate limiting prevents excessive submissions"""
    # Mock IP address
    def mock_get_client_ip(request):
        return "192.168.1.100"
    
    monkeypatch.setattr("api.contact.get_client_ip", mock_get_client_ip)
    
    payload = {
        "name": "Rate Test User",
        "email": "ratetest@example.com",
        "subject": "Rate Limit Test",
        "message": "Testing rate limiting functionality"
    }
    
    # Submit 5 times (within limit)
    for i in range(5):
        response = client.post("/api/contact", json={**payload, "email": f"test{i}@example.com"})
        assert response.status_code == 201
    
    # 6th submission should be rate limited
    response = client.post("/api/contact", json=payload)
    assert response.status_code == 429
    assert "Too many submissions" in response.json()["detail"]


def test_database_persistence(client, setup_test_db):
    """Test that submissions are properly saved to database"""
    payload = {
        "name": "Database Test",
        "email": "dbtest@example.com",
        "phone": "+1-555-999-8888",
        "subject": "Persistence Test",
        "message": "Testing database persistence"
    }
    
    response = client.post("/api/contact", json=payload)
    assert response.status_code == 201
    submission_id = response.json()["submission_id"]
    
    # Verify in database
    conn = sqlite3.connect(setup_test_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contact_submissions WHERE id = ?", (submission_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row["name"] == payload["name"]
    assert row["email"] == payload["email"]
    assert row["phone"] == payload["phone"]
    assert row["subject"] == payload["subject"]
    assert row["message"] == payload["message"]
    assert row["status"] == "pending"


def test_get_submissions_admin(client, setup_test_db, monkeypatch):
    """Test admin endpoint for retrieving submissions"""
    # Mock admin auth (if AUTH_AVAILABLE)
    monkeypatch.setattr("api.contact.AUTH_AVAILABLE", False)
    
    # Create some test submissions
    for i in range(3):
        payload = {
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "subject": f"Subject {i}",
            "message": f"Message content for submission {i}"
        }
        client.post("/api/contact", json=payload)
    
    # Get submissions
    response = client.get("/api/contact/submissions")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["submissions"]) == 3
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_get_submissions_with_pagination(client, setup_test_db, monkeypatch):
    """Test pagination of submissions"""
    monkeypatch.setattr("api.contact.AUTH_AVAILABLE", False)
    monkeypatch.setattr("api.contact.RATE_LIMIT_SUBMISSIONS", 100)  # Increase rate limit for testing
    
    # Create 10 submissions
    for i in range(10):
        payload = {
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "subject": "Test",
            "message": "Test message content"
        }
        client.post("/api/contact", json=payload)
    
    # Get first page
    response = client.get("/api/contact/submissions?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 10
    assert len(data["submissions"]) == 5
    
    # Get second page
    response = client.get("/api/contact/submissions?limit=5&offset=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["submissions"]) == 5


def test_get_submissions_with_status_filter(client, setup_test_db, monkeypatch):
    """Test filtering submissions by status"""
    monkeypatch.setattr("api.contact.AUTH_AVAILABLE", False)
    
    # Create submission
    payload = {
        "name": "Filter Test",
        "email": "filter@example.com",
        "subject": "Test",
        "message": "Test message"
    }
    response = client.post("/api/contact", json=payload)
    submission_id = response.json()["submission_id"]
    
    # Update status
    conn = sqlite3.connect(setup_test_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE contact_submissions SET status = ? WHERE id = ?", ("resolved", submission_id))
    conn.commit()
    conn.close()
    
    # Filter by resolved
    response = client.get("/api/contact/submissions?status_filter=resolved")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["submissions"][0]["status"] == "resolved"


def test_update_submission_status(client, setup_test_db, monkeypatch):
    """Test updating submission status"""
    monkeypatch.setattr("api.contact.AUTH_AVAILABLE", False)
    
    # Create submission
    payload = {
        "name": "Status Test",
        "email": "status@example.com",
        "subject": "Test",
        "message": "Test message"
    }
    response = client.post("/api/contact", json=payload)
    submission_id = response.json()["submission_id"]
    
    # Update status
    response = client.patch(f"/api/contact/submissions/{submission_id}/status?status=resolved")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Verify in database
    conn = sqlite3.connect(setup_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM contact_submissions WHERE id = ?", (submission_id,))
    status = cursor.fetchone()[0]
    conn.close()
    
    assert status == "resolved"


def test_health_check(client):
    """Test contact service health check"""
    response = client.get("/api/contact/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert "total_submissions" in data
    assert "rate_limiter" in data


def test_long_message(client):
    """Test message at maximum length"""
    payload = {
        "name": "Long Message Test",
        "email": "long@example.com",
        "subject": "Testing long message",
        "message": "A" * 5000  # Maximum allowed length
    }
    
    response = client.post("/api/contact", json=payload)
    assert response.status_code == 201


def test_message_exceeds_max_length(client):
    """Test validation error for message exceeding max length"""
    payload = {
        "name": "Too Long",
        "email": "toolong@example.com",
        "subject": "Test",
        "message": "A" * 5001  # Exceeds maximum
    }
    
    response = client.post("/api/contact", json=payload)
    assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
