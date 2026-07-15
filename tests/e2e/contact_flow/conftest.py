"""
Pytest fixtures for contact flow end-to-end tests.

Provides:
- Test app with isolated database
- Mock notification endpoints
- Rate limiter reset
- Seeded test data
"""

import pytest
import tempfile
import sqlite3
import json
import os
from pathlib import Path
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Generator, Dict, List, Any
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import the contact router and related functions
from api.contact import (
    router as contact_router,
    init_database,
    InMemoryRateLimiter,
    _in_memory_limiter,
    get_admin_user,
)


# ============================================================================
# NOTIFICATION MOCK SERVER
# ============================================================================

class NotificationCapture:
    """Thread-safe notification capture for assertions."""
    
    def __init__(self):
        self.notifications: List[Dict[str, Any]] = []
        self.should_fail: bool = False
        self.fail_count: int = 0
        self.max_failures: int = 0
    
    def reset(self):
        """Reset captured notifications and failure state."""
        self.notifications = []
        self.should_fail = False
        self.fail_count = 0
        self.max_failures = 0
    
    def set_failure_mode(self, num_failures: int = 1):
        """Configure server to fail for a number of requests."""
        self.should_fail = True
        self.max_failures = num_failures
        self.fail_count = 0
    
    def capture(self, notification: Dict[str, Any]) -> bool:
        """Capture notification and return success/failure status."""
        if self.should_fail and self.fail_count < self.max_failures:
            self.fail_count += 1
            return False
        self.notifications.append(notification)
        return True


# Global notification capture instance
notification_capture = NotificationCapture()


class MockNotificationHandler(BaseHTTPRequestHandler):
    """HTTP handler for mock notification server."""
    
    def log_message(self, format, *args):
        """Suppress server logging."""
        pass
    
    def do_POST(self):
        """Handle POST requests (notifications)."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            notification = json.loads(body)
        except json.JSONDecodeError:
            notification = {"raw": body}
        
        if notification_capture.capture(notification):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error": "simulated failure"}')


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def mock_notification_server():
    """Start a mock notification server for the test module."""
    server = HTTPServer(('localhost', 0), MockNotificationHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{port}"
    server.shutdown()


@pytest.fixture
def notification_inspector():
    """Provide access to captured notifications."""
    notification_capture.reset()
    yield notification_capture
    notification_capture.reset()


@pytest.fixture
def temp_database(tmp_path: Path) -> Generator[Path, None, None]:
    """Create temporary database for test isolation."""
    db_path = tmp_path / "test_contact.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    
    yield db_path


@pytest.fixture
def e2e_test_app(temp_database: Path, tmp_path: Path) -> FastAPI:
    """Create FastAPI test app with isolated database."""
    app = FastAPI(title="AstraGuard Contact API (E2E Test)")
    app.include_router(contact_router)
    
    # Override admin dependency to bypass auth and simulating a logged-in admin
    app.dependency_overrides[get_admin_user] = lambda: MagicMock(username="admin", role="admin")
    
    return app


@pytest.fixture
def e2e_client(e2e_test_app: FastAPI, tmp_path: Path, monkeypatch) -> Generator[TestClient, None, None]:
    """Create test client with isolated database and reset rate limiter."""
    # Create isolated data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / "contact_submissions.db"
    notification_log = data_dir / "contact_notifications.log"
    
    # Patch the database path and notification log
    monkeypatch.setattr("api.contact.DATA_DIR", data_dir)
    monkeypatch.setattr("api.contact.DB_PATH", db_path)
    monkeypatch.setattr("api.contact.NOTIFICATION_LOG", notification_log)
    
    # Initialize fresh database
    init_database()
    
    # Reset rate limiter
    _in_memory_limiter.requests.clear()
    
    with TestClient(e2e_test_app) as client:
        yield client
    
    # Cleanup
    _in_memory_limiter.requests.clear()


@pytest.fixture
def valid_contact_data() -> Dict[str, str]:
    """Valid contact form submission data."""
    return {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1-555-123-4567",
        "subject": "Test Inquiry",
        "message": "This is a test message for the contact form E2E tests."
    }


@pytest.fixture
def minimal_contact_data() -> Dict[str, str]:
    """Minimal valid contact form data (required fields only)."""
    return {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "subject": "Minimal Test",
        "message": "Minimal test message content."
    }


@pytest.fixture
def db_connection(tmp_path: Path, e2e_client) -> Generator[sqlite3.Connection, None, None]:
    """Provide database connection for assertions."""
    db_path = tmp_path / "data" / "contact_submissions.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def reset_rate_limiter():
    """Reset the rate limiter before and after test."""
    _in_memory_limiter.requests.clear()
    yield
    _in_memory_limiter.requests.clear()


# ============================================================================
# PYTEST MARKERS
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow-running"
    )
