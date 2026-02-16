"""
End-to-End Tests for Contact Form Submission Flow

Tests the complete contact flow:
API → Backend → Storage → Notifications

Scenarios covered:
1. Happy path: Submit → Persist → Notify
2. Retry and fallback: Notification failure handling
3. Idempotency: Duplicate submission handling
4. Partial failure: Database error handling
5. Rate limiting: E2E rate limit verification
"""

import pytest
import sqlite3
import time
import json
from pathlib import Path
from typing import Dict, Any

# Mark E2E tests as slow due to full stack operations
pytestmark = [pytest.mark.slow, pytest.mark.timeout(90)]

from fastapi.testclient import TestClient


# Mark all tests in this module as e2e tests
pytestmark = pytest.mark.e2e


class TestContactHappyPath:
    """Happy path E2E tests for contact form submission."""
    
    def test_submit_contact_returns_201(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str]
    ):
        """Test successful form submission returns 201 Created."""
        response = e2e_client.post("/api/contact", json=valid_contact_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "submission_id" in data
        assert data["submission_id"] is not None
    
    def test_submission_persisted_to_database(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        db_connection: sqlite3.Connection
    ):
        """Test submission is correctly persisted to database."""
        # Submit contact form
        response = e2e_client.post("/api/contact", json=valid_contact_data)
        assert response.status_code == 201
        
        submission_id = response.json()["submission_id"]
        
        # Verify database record
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT * FROM contact_submissions WHERE id = ?",
            (submission_id,)
        )
        row = cursor.fetchone()
        
        assert row is not None
        assert row["name"] == valid_contact_data["name"]
        assert row["email"] == valid_contact_data["email"].lower()
        assert row["subject"] == valid_contact_data["subject"]
        assert row["message"] == valid_contact_data["message"]
        assert row["status"] == "pending"
    
    def test_notification_logged(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        tmp_path: Path
    ):
        """Test notification is logged when email is not configured."""
        response = e2e_client.post("/api/contact", json=valid_contact_data)
        assert response.status_code == 201
        
        # Check notification log exists
        notification_log = tmp_path / "data" / "contact_notifications.log"
        assert notification_log.exists()
        
        # Verify log content
        with open(notification_log, "r") as f:
            log_content = f.read()
        
        assert valid_contact_data["name"] in log_content
        assert valid_contact_data["subject"] in log_content
    
    def test_minimal_submission_succeeds(
        self,
        e2e_client: TestClient,
        minimal_contact_data: Dict[str, str]
    ):
        """Test submission with only required fields succeeds."""
        response = e2e_client.post("/api/contact", json=minimal_contact_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
    
    def test_email_normalized_to_lowercase(
        self,
        e2e_client: TestClient,
        db_connection: sqlite3.Connection
    ):
        """Test email is normalized to lowercase in database."""
        contact_data = {
            "name": "Test User",
            "email": "TEST.User@EXAMPLE.COM",
            "subject": "Email Normalization Test",
            "message": "Testing email normalization to lowercase."
        }
        
        response = e2e_client.post("/api/contact", json=contact_data)
        assert response.status_code == 201
        
        submission_id = response.json()["submission_id"]
        
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT email FROM contact_submissions WHERE id = ?",
            (submission_id,)
        )
        row = cursor.fetchone()
        
        assert row["email"] == "test.user@example.com"


class TestContactRetryAndFallback:
    """Tests for retry and fallback behavior on notification failures."""
    
    def test_submission_succeeds_despite_notification_error(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        db_connection: sqlite3.Connection,
        monkeypatch
    ):
        """Test submission succeeds even if notification fails."""
        # Mock notification to fail
        def mock_notification_failure(*args, **kwargs):
            raise Exception("Simulated notification failure")
        
        monkeypatch.setattr(
            "api.contact.log_notification",
            mock_notification_failure
        )
        
        # Submission should still succeed
        response = e2e_client.post("/api/contact", json=valid_contact_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        
        # Verify record was persisted
        submission_id = data["submission_id"]
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT id FROM contact_submissions WHERE id = ?",
            (submission_id,)
        )
        assert cursor.fetchone() is not None
    
    def test_fallback_to_log_when_email_not_configured(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        tmp_path: Path,
        monkeypatch
    ):
        """Test fallback to file logging when SendGrid is not configured."""
        # Ensure SendGrid is not configured
        monkeypatch.setattr("api.contact.SENDGRID_API_KEY", None)
        
        response = e2e_client.post("/api/contact", json=valid_contact_data)
        assert response.status_code == 201
        
        # Verify notification was logged to file
        notification_log = tmp_path / "data" / "contact_notifications.log"
        assert notification_log.exists()


class TestContactIdempotency:
    """Tests for idempotency and duplicate submission handling."""
    
    def test_duplicate_submissions_create_separate_records(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        db_connection: sqlite3.Connection
    ):
        """Test duplicate submissions create separate database records."""
        # Submit same data twice
        response1 = e2e_client.post("/api/contact", json=valid_contact_data)
        response2 = e2e_client.post("/api/contact", json=valid_contact_data)
        
        assert response1.status_code == 201
        assert response2.status_code == 201
        
        # Verify different submission IDs
        id1 = response1.json()["submission_id"]
        id2 = response2.json()["submission_id"]
        assert id1 != id2
        
        # Verify both records exist
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM contact_submissions WHERE email = ?",
            (valid_contact_data["email"].lower(),)
        )
        count = cursor.fetchone()["count"]
        assert count == 2
    
    def test_unique_submission_ids(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str]
    ):
        """Test each submission gets a unique ID."""
        ids = set()
        
        for i in range(3):
            response = e2e_client.post("/api/contact", json=valid_contact_data)
            assert response.status_code == 201
            ids.add(response.json()["submission_id"])
        
        assert len(ids) == 3


class TestContactPartialFailure:
    """Tests for graceful degradation during partial failures."""
    
    def test_database_error_returns_500(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        monkeypatch
    ):
        """Test database failure returns 500 error."""
        def mock_db_failure(*args, **kwargs):
            raise sqlite3.DatabaseError("Simulated database failure")
        
        monkeypatch.setattr("api.contact.save_submission", mock_db_failure)
        
        response = e2e_client.post("/api/contact", json=valid_contact_data)
        
        assert response.status_code == 500
        assert "Failed to save submission" in response.json()["detail"]
    
    def test_validation_error_returns_422(
        self,
        e2e_client: TestClient
    ):
        """Test invalid data returns 422 validation error."""
        invalid_data = {
            "name": "J",  # Too short
            "email": "not-an-email",
            "subject": "T",  # Too short
            "message": "Short"  # Too short
        }
        
        response = e2e_client.post("/api/contact", json=invalid_data)
        
        assert response.status_code == 422
    
    def test_xss_sanitization(
        self,
        e2e_client: TestClient,
        db_connection: sqlite3.Connection
    ):
        """Test dangerous characters are sanitized to prevent XSS."""
        xss_data = {
            "name": "Test<script>alert('xss')</script>User",
            "email": "test@example.com",
            "subject": "XSS Test<img src=x onerror=alert(1)>",
            "message": "Testing XSS protection with <script> and 'quotes' and \"double-quotes\"."
        }
        
        response = e2e_client.post("/api/contact", json=xss_data)
        assert response.status_code == 201
        
        # Verify dangerous characters were removed
        submission_id = response.json()["submission_id"]
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT name, subject, message FROM contact_submissions WHERE id = ?",
            (submission_id,)
        )
        row = cursor.fetchone()
        
        assert "<script>" not in row["name"]
        assert "<" not in row["name"]
        assert ">" not in row["name"]
    
    def test_honeypot_protection(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        db_connection: sqlite3.Connection
    ):
        """Test honeypot field catches bots and doesn't persist."""
        honeypot_data = valid_contact_data.copy()
        honeypot_data["website"] = "http://spam-bot.com"
        
        response = e2e_client.post("/api/contact", json=honeypot_data)
        
        # Should return fake success
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        
        # But no submission_id in response (caught as spam)
        # The honeypot returns a fake success without persisting
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM contact_submissions WHERE email = ?",
            (valid_contact_data["email"].lower(),)
        )
        count = cursor.fetchone()["count"]
        assert count == 0


class TestContactRateLimiting:
    """E2E tests for rate limiting behavior."""
    
    def test_rate_limit_exceeded_returns_429(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        reset_rate_limiter
    ):
        """Test rate limit exceeded returns 429 Too Many Requests."""
        # Make 5 successful submissions (rate limit is 5 per hour)
        for i in range(5):
            contact_data = valid_contact_data.copy()
            contact_data["email"] = f"test{i}@example.com"
            response = e2e_client.post("/api/contact", json=contact_data)
            assert response.status_code == 201
        
        # 6th submission should be rate limited
        response = e2e_client.post("/api/contact", json=valid_contact_data)
        
        assert response.status_code == 429
        response_data = response.json()
        assert "Too many submissions" in response_data["detail"]["message"]
    
    def test_rate_limit_applies_per_ip(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        reset_rate_limiter
    ):
        """Test rate limiting is applied per IP address."""
        # This test verifies the rate limiter key includes IP
        # Since TestClient uses testclient as the IP, all requests
        # from the same client share the same rate limit bucket
        
        # Make 5 submissions
        for i in range(5):
            contact_data = valid_contact_data.copy()
            contact_data["email"] = f"rate-test{i}@example.com"
            response = e2e_client.post("/api/contact", json=contact_data)
            assert response.status_code == 201
        
        # Verify rate limit is enforced
        response = e2e_client.post("/api/contact", json=valid_contact_data)
        assert response.status_code == 429


class TestContactHealthCheck:
    """E2E tests for health check endpoint."""
    
    def test_health_check_returns_healthy(
        self,
        e2e_client: TestClient
    ):
        """Test health check endpoint returns healthy status."""
        response = e2e_client.get("/api/contact/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "total_submissions" in data
        assert "rate_limiter" in data


class TestContactAdminEndpoints:
    """E2E tests for admin endpoints."""
    
    def test_get_submissions_returns_list(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str]
    ):
        """Test admin can retrieve submissions list."""
        # Create some submissions first
        for i in range(3):
            contact_data = valid_contact_data.copy()
            contact_data["email"] = f"admin-test{i}@example.com"
            e2e_client.post("/api/contact", json=contact_data)
        
        # Get submissions (auth not required when AUTH_AVAILABLE is False)
        response = e2e_client.get("/api/contact/submissions")
        
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "submissions" in data
        assert data["total"] >= 3
    
    def test_update_submission_status(
        self,
        e2e_client: TestClient,
        valid_contact_data: Dict[str, str],
        db_connection: sqlite3.Connection
    ):
        """Test admin can update submission status."""
        # Create a submission
        response = e2e_client.post("/api/contact", json=valid_contact_data)
        submission_id = response.json()["submission_id"]
        
        # Update status
        response = e2e_client.patch(
            f"/api/contact/submissions/{submission_id}/status",
            params={"status": "resolved"}
        )
        
        assert response.status_code == 200
        
        # Verify status was updated
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT status FROM contact_submissions WHERE id = ?",
            (submission_id,)
        )
        row = cursor.fetchone()
        assert row["status"] == "resolved"
    
    def test_update_nonexistent_submission_returns_404(
        self,
        e2e_client: TestClient
    ):
        """Test updating non-existent submission returns 404."""
        response = e2e_client.patch(
            "/api/contact/submissions/99999/status",
            params={"status": "resolved"}
        )
        
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
