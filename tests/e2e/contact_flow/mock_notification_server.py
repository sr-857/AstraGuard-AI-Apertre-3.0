"""
Mock Notification Server for E2E Testing

Provides a lightweight HTTP server for:
- Capturing webhook/email notification payloads
- Simulating failures for retry testing
- Thread-safe request inspection
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass
class NotificationRecord:
    """Record of a captured notification."""
    endpoint: str
    method: str
    headers: Dict[str, str]
    body: Any
    timestamp: float
    
    def __post_init__(self):
        import time
        if self.timestamp is None:
            self.timestamp = time.time()


class NotificationInspector:
    """Thread-safe notification capture and inspection."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._notifications: List[NotificationRecord] = []
        self._failure_config: Dict[str, int] = {}
        self._failure_counts: Dict[str, int] = {}
    
    def reset(self):
        """Reset all captured data and failure configurations."""
        with self._lock:
            self._notifications = []
            self._failure_config = {}
            self._failure_counts = {}
    
    def set_failure_mode(self, endpoint: str, num_failures: int = 1):
        """Configure endpoint to fail for a number of requests."""
        with self._lock:
            self._failure_config[endpoint] = num_failures
            self._failure_counts[endpoint] = 0
    
    def should_fail(self, endpoint: str) -> bool:
        """Check if endpoint should simulate failure."""
        with self._lock:
            if endpoint not in self._failure_config:
                return False
            
            max_failures = self._failure_config[endpoint]
            current_failures = self._failure_counts.get(endpoint, 0)
            
            if current_failures < max_failures:
                self._failure_counts[endpoint] = current_failures + 1
                return True
            return False
    
    def capture(self, record: NotificationRecord):
        """Capture a notification record."""
        with self._lock:
            self._notifications.append(record)
    
    @property
    def notifications(self) -> List[NotificationRecord]:
        """Get all captured notifications."""
        with self._lock:
            return list(self._notifications)
    
    def get_by_endpoint(self, endpoint: str) -> List[NotificationRecord]:
        """Get notifications for a specific endpoint."""
        with self._lock:
            return [n for n in self._notifications if n.endpoint == endpoint]
    
    def count(self, endpoint: Optional[str] = None) -> int:
        """Count notifications, optionally filtered by endpoint."""
        with self._lock:
            if endpoint:
                return len([n for n in self._notifications if n.endpoint == endpoint])
            return len(self._notifications)
    
    def last(self) -> Optional[NotificationRecord]:
        """Get the most recent notification."""
        with self._lock:
            return self._notifications[-1] if self._notifications else None


# Global inspector instance
_inspector = NotificationInspector()


class MockNotificationHandler(BaseHTTPRequestHandler):
    """HTTP handler for mock notification server."""
    
    def log_message(self, format, *args):
        """Suppress server logging."""
        pass
    
    def _get_body(self) -> Any:
        """Read and parse request body."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return None
        
        raw_body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return {"raw": raw_body}
    
    def _capture_request(self, method: str):
        """Capture request details."""
        import time
        
        headers = {k: v for k, v in self.headers.items()}
        body = self._get_body() if method in ('POST', 'PUT', 'PATCH') else None
        
        record = NotificationRecord(
            endpoint=self.path,
            method=method,
            headers=headers,
            body=body,
            timestamp=time.time()
        )
        
        _inspector.capture(record)
        return record
    
    def _send_response(self, status: int, body: Dict[str, Any]):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests."""
        self._capture_request('GET')
        
        if _inspector.should_fail(self.path):
            self._send_response(500, {"error": "simulated failure"})
        else:
            self._send_response(200, {"status": "ok", "endpoint": self.path})
    
    def do_POST(self):
        """Handle POST requests (notifications)."""
        self._capture_request('POST')
        
        if _inspector.should_fail(self.path):
            self._send_response(500, {"error": "simulated failure"})
        else:
            self._send_response(200, {"status": "ok", "endpoint": self.path})
    
    def do_PUT(self):
        """Handle PUT requests."""
        self._capture_request('PUT')
        
        if _inspector.should_fail(self.path):
            self._send_response(500, {"error": "simulated failure"})
        else:
            self._send_response(200, {"status": "ok"})
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        self._capture_request('DELETE')
        
        if _inspector.should_fail(self.path):
            self._send_response(500, {"error": "simulated failure"})
        else:
            self._send_response(200, {"status": "ok"})


class MockNotificationServer:
    """Mock notification server for E2E testing."""
    
    def __init__(self, port: int = 0):
        """
        Initialize mock server.
        
        Args:
            port: Port to bind to. Use 0 for automatic port assignment.
        """
        self.server = HTTPServer(('localhost', port), MockNotificationHandler)
        self.port = self.server.server_address[1]
        self._thread: Optional[threading.Thread] = None
    
    @property
    def base_url(self) -> str:
        """Get the base URL of the server."""
        return f"http://localhost:{self.port}"
    
    @property
    def inspector(self) -> NotificationInspector:
        """Get the notification inspector."""
        return _inspector
    
    def start(self):
        """Start the server in a background thread."""
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the server."""
        self.server.shutdown()
        if self._thread:
            self._thread.join(timeout=5)
    
    def reset(self):
        """Reset the inspector."""
        _inspector.reset()


@contextmanager
def run_mock_notification_server(port: int = 0):
    """
    Context manager for running a mock notification server.
    
    Usage:
        with run_mock_notification_server() as server:
            # server.base_url contains the URL
            # server.inspector contains captured notifications
            pass
    """
    server = MockNotificationServer(port)
    server.start()
    try:
        yield server
    finally:
        server.stop()


if __name__ == "__main__":
    # Demo usage
    import time
    import requests
    
    with run_mock_notification_server(8888) as server:
        print(f"Mock server running at {server.base_url}")
        
        # Send some test requests
        requests.post(f"{server.base_url}/notify", json={"test": "data"})
        requests.post(f"{server.base_url}/webhook", json={"event": "contact_form"})
        
        # Check captured notifications
        print(f"Captured {server.inspector.count()} notifications")
        for n in server.inspector.notifications:
            print(f"  - {n.method} {n.endpoint}: {n.body}")
        
        print("\nPress Ctrl+C to stop...")
        try:
            time.sleep(30)
        except KeyboardInterrupt:
            pass
