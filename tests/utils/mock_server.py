"""
Mock API Server Utilities for Testing

Provides reusable mock servers and testing utilities for AstraGuard projects.
"""

import asyncio
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Callable, Optional, Any
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock


class MockAPIServer:
    """
    Reusable FastAPI test server with common mocks and utilities.
    
    Example:
        >>> server = MockAPIServer()
        >>> server.add_route("/test", {"status": "ok"})
        >>> with server.client() as client:
        ...     response = client.get("/test")
        ...     assert response.status_code == 200
    """
    
    def __init__(self, title: str = "Test API"):
        """Initialize mock API server."""
        self.app = FastAPI(title=title)
        self.routes: Dict[str, Dict[str, Any]] = {}
        self._setup_default_routes()
    
    def _setup_default_routes(self):
        """Setup default test routes."""
        @self.app.get("/")
        async def root():
            return {"status": "ok", "message": "Test API is running"}
        
        @self.app.get("/health")
        async def health():
            return {"status": "healthy"}
    
    def add_route(
        self,
        path: str,
        response: Dict[str, Any],
        method: str = "GET",
        status_code: int = 200
    ):
        """
        Add a simple mock route that returns JSON.
        
        Args:
            path: Route path (e.g., "/api/test")
            response: JSON response dict
            method: HTTP method (GET, POST, etc.)
            status_code: Response status code
            
        Example:
            >>> server.add_route("/api/users", {"users": []})
        """
        if method == "GET":
            @self.app.get(path, status_code=status_code)
            async def route():
                return response
        elif method == "POST":
            @self.app.post(path, status_code=status_code)
            async def route():
                return response
        elif method == "PUT":
            @self.app.put(path, status_code=status_code)
            async def route():
                return response
        elif method == "DELETE":
            @self.app.delete(path, status_code=status_code)
            async def route():
                return response
        
        self.routes[f"{method}:{path}"] = {
            "response": response,
            "status_code": status_code
        }
    
    def add_dynamic_route(
        self,
        path: str,
        handler: Callable,
        method: str = "GET"
    ):
        """
        Add a route with custom handler function.
        
        Args:
            path: Route path
            handler: Async function to handle requests
            method: HTTP method
            
        Example:
            >>> async def handler():
            ...     return {"dynamic": True}
            >>> server.add_dynamic_route("/dynamic", handler)
        """
        if method == "GET":
            self.app.get(path)(handler)
        elif method == "POST":
            self.app.post(path)(handler)
    
    def override_dependency(self, dependency: Callable, mock: Any):
        """
        Override FastAPI dependency injection.
        
        Args:
            dependency: Original dependency function
            mock: Mock object or function to use instead
            
        Example:
            >>> from api.auth import get_api_key
            >>> mock_key = Mock()
            >>> server.override_dependency(get_api_key, lambda: mock_key)
        """
        self.app.dependency_overrides[dependency] = lambda: mock
    
    def client(self) -> TestClient:
        """
        Get FastAPI TestClient for this server.
        
        Returns:
            TestClient instance
            
        Example:
            >>> with server.client() as client:
            ...     response = client.get("/health")
        """
        return TestClient(self.app)


class MockHTTPServer:
    """
    Simple HTTP server for mocking external services.
    
    Useful for testing webhooks, external APIs, and notification endpoints.
    
    Example:
        >>> server = MockHTTPServer()
        >>> server.expect_request("/webhook", method="POST")
        >>> with server.run():
        ...     # Make requests to server.url
        ...     assert server.received_requests[0]["path"] == "/webhook"
    """
    
    def __init__(self, port: int = 0):
        """
        Initialize mock HTTP server.
        
        Args:
            port: Port to bind to (0 = random available port)
        """
        self.port = port
        self.received_requests: List[Dict[str, Any]] = []
        self.expected_requests: Dict[str, Dict[str, Any]] = {}
        self.response_overrides: Dict[str, Dict[str, Any]] = {}
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.url: Optional[str] = None
    
    def expect_request(
        self,
        path: str,
        method: str = "POST",
        response: Optional[Dict[str, Any]] = None,
        status_code: int = 200
    ):
        """
        Set up expected request and response.
        
        Args:
            path: Request path
            method: HTTP method
            response: JSON response dict
            status_code: Response status code
        """
        self.expected_requests[f"{method}:{path}"] = {
            "path": path,
            "method": method,
            "count": 0
        }
        
        if response:
            self.response_overrides[f"{method}:{path}"] = {
                "response": response,
                "status_code": status_code
            }
    
    def clear_requests(self):
        """Clear recorded requests."""
        self.received_requests.clear()
        for key in self.expected_requests:
            self.expected_requests[key]["count"] = 0
    
    def get_request_count(self, path: str, method: str = "POST") -> int:
        """
        Get number of requests received for path.
        
        Args:
            path: Request path
            method: HTTP method
            
        Returns:
            Number of matching requests
        """
        key = f"{method}:{path}"
        if key in self.expected_requests:
            return self.expected_requests[key]["count"]
        return sum(
            1 for req in self.received_requests
            if req["path"] == path and req["method"] == method
        )
    
    def _create_handler(self):
        """Create request handler class."""
        server_instance = self
        
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                """Suppress server logging."""
                pass
            
            def do_GET(self):
                self._handle_request("GET")
            
            def do_POST(self):
                self._handle_request("POST")
            
            def do_PUT(self):
                self._handle_request("PUT")
            
            def do_DELETE(self):
                self._handle_request("DELETE")
            
            def _handle_request(self, method: str):
                """Handle incoming request."""
                # Read body
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length) if content_length > 0 else b''
                
                try:
                    body_json = json.loads(body.decode('utf-8')) if body else {}
                except json.JSONDecodeError:
                    body_json = {"raw": body.decode('utf-8', errors='ignore')}
                
                # Record request
                request_data = {
                    "method": method,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": body_json
                }
                server_instance.received_requests.append(request_data)
                
                # Update expected request count
                key = f"{method}:{self.path}"
                if key in server_instance.expected_requests:
                    server_instance.expected_requests[key]["count"] += 1
                
                # Send response
                if key in server_instance.response_overrides:
                    override = server_instance.response_overrides[key]
                    self.send_response(override["status_code"])
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(override["response"]).encode())
                else:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "ok"}')
        
        return Handler
    
    def start(self):
        """Start the mock server in background thread."""
        handler_class = self._create_handler()
        self.server = HTTPServer(('localhost', self.port), handler_class)
        self.port = self.server.server_address[1]
        self.url = f"http://localhost:{self.port}"
        
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        return self.url
    
    def stop(self):
        """Stop the mock server."""
        if self.server:
            self.server.shutdown()
            self.server = None
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
    
    def run(self):
        """Context manager for running server."""
        return _MockServerContext(self)


class _MockServerContext:
    """Context manager for MockHTTPServer."""
    
    def __init__(self, server: MockHTTPServer):
        self.server = server
    
    def __enter__(self):
        self.server.start()
        return self.server
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.server.stop()


class RequestRecorder:
    """
    Records HTTP requests for testing and assertions.
    
    Example:
        >>> recorder = RequestRecorder()
        >>> recorder.record_request("/api/test", {"data": "value"})
        >>> assert recorder.get_request_count("/api/test") == 1
        >>> assert recorder.last_request["path"] == "/api/test"
    """
    
    def __init__(self):
        """Initialize request recorder."""
        self.requests: List[Dict[str, Any]] = []
    
    def record_request(
        self,
        path: str,
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
        method: str = "POST"
    ):
        """Record a request."""
        self.requests.append({
            "path": path,
            "body": body,
            "headers": headers or {},
            "method": method
        })
    
    def get_request_count(self, path: str) -> int:
        """Get number of requests to path."""
        return sum(1 for req in self.requests if req["path"] == path)
    
    def get_requests_to(self, path: str) -> List[Dict[str, Any]]:
        """Get all requests to specific path."""
        return [req for req in self.requests if req["path"] == path]
    
    @property
    def last_request(self) -> Optional[Dict[str, Any]]:
        """Get last recorded request."""
        return self.requests[-1] if self.requests else None
    
    def clear(self):
        """Clear all recorded requests."""
        self.requests.clear()


# Convenience functions

def create_mock_server(routes: Optional[Dict[str, Any]] = None) -> MockAPIServer:
    """
    Create a mock API server with optional routes.
    
    Args:
        routes: Dict of {path: response_data}
        
    Returns:
        MockAPIServer instance
        
    Example:
        >>> server = create_mock_server({
        ...     "/api/users": {"users": []},
        ...     "/api/status": {"status": "healthy"}
        ... })
    """
    server = MockAPIServer()
    if routes:
        for path, response in routes.items():
            server.add_route(path, response)
    return server


def create_http_mock(port: int = 0) -> MockHTTPServer:
    """
    Create a simple HTTP mock server.
    
    Args:
        port: Port to bind to (0 = random)
        
    Returns:
        MockHTTPServer instance
        
    Example:
        >>> mock = create_http_mock()
        >>> mock.expect_request("/webhook", response={"received": True})
        >>> with mock.run():
        ...     # Server is running at mock.url
        ...     pass
    """
    return MockHTTPServer(port=port)
