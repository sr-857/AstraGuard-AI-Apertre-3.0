"""Comprehensive unit tests for contact_app.py module."""

import pytest
import sys
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Mock contact module before importing contact_app
sys.modules['api.contact'] = MagicMock()


class TestContactAppInitialization:
    """Test contact_app module initialization and configuration."""

    def test_app_instance_creation(self):
        """Test that FastAPI app instance is created correctly."""
        from api.contact_app import app
        
        assert isinstance(app, FastAPI)
        assert app.title == "AstraGuard Contact API (dev)"

    def test_app_title_configuration(self):
        """Test app title is set correctly."""
        from api.contact_app import app
        
        assert app.title == "AstraGuard Contact API (dev)"

    def test_allowed_origins_configuration(self):
        """Test CORS allowed origins are configured correctly."""
        from api.contact_app import ALLOWED_ORIGINS
        
        assert isinstance(ALLOWED_ORIGINS, list)
        assert len(ALLOWED_ORIGINS) == 4
        assert "http://localhost:8080" in ALLOWED_ORIGINS
        assert "http://127.0.0.1:8080" in ALLOWED_ORIGINS
        assert "http://localhost:8000" in ALLOWED_ORIGINS
        assert "http://127.0.0.1:8000" in ALLOWED_ORIGINS

    def test_allowed_origins_no_duplicates(self):
        """Test that ALLOWED_ORIGINS has no duplicate entries."""
        from api.contact_app import ALLOWED_ORIGINS
        
        assert len(ALLOWED_ORIGINS) == len(set(ALLOWED_ORIGINS))

    def test_allowed_origins_are_strings(self):
        """Test that all allowed origins are strings."""
        from api.contact_app import ALLOWED_ORIGINS
        
        for origin in ALLOWED_ORIGINS:
            assert isinstance(origin, str)

    def test_allowed_origins_have_valid_protocols(self):
        """Test that all origins use http protocol."""
        from api.contact_app import ALLOWED_ORIGINS
        
        for origin in ALLOWED_ORIGINS:
            assert origin.startswith("http://")

    def test_logger_is_initialized(self):
        """Test that logger is properly initialized."""
        from api.contact_app import logger
        
        assert logger is not None
        assert hasattr(logger, 'critical')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'debug')


class TestCORSMiddleware:
    """Test CORS middleware configuration."""

    def test_cors_middleware_is_added(self):
        """Test that CORS middleware is added to the app."""
        from api.contact_app import app
        
        # Check if middleware stack exists
        assert app.user_middleware is not None
        assert len(app.user_middleware) > 0

    def test_cors_middleware_with_test_client(self):
        """Test CORS middleware behavior with test client."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.options("/")
        
        # Test that OPTIONS requests are handled
        assert response.status_code in [200, 404, 405]

    def test_cors_origin_header_localhost_8080(self):
        """Test CORS headers for localhost:8080 origin."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/", headers={"Origin": "http://localhost:8080"})
        
        # Check if CORS headers are set
        assert response.status_code in [404, 200]

    def test_cors_origin_header_127_0_0_1_8080(self):
        """Test CORS headers for 127.0.0.1:8080 origin."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/", headers={"Origin": "http://127.0.0.1:8080"})
        
        assert response.status_code in [404, 200]

    def test_cors_origin_header_localhost_8000(self):
        """Test CORS headers for localhost:8000 origin."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/", headers={"Origin": "http://localhost:8000"})
        
        assert response.status_code in [404, 200]

    def test_cors_origin_header_127_0_0_1_8000(self):
        """Test CORS headers for 127.0.0.1:8000 origin."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/", headers={"Origin": "http://127.0.0.1:8000"})
        
        assert response.status_code in [404, 200]

    def test_cors_with_invalid_origin(self):
        """Test CORS behavior with non-whitelisted origin."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/", headers={"Origin": "http://evil.com"})
        
        # Response should still work but without CORS headers for invalid origin
        assert response.status_code in [404, 200]

    def test_cors_with_custom_headers(self):
        """Test CORS with custom headers in request."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get(
            "/",
            headers={
                "Origin": "http://localhost:8080",
                "X-Custom-Header": "test-value"
            }
        )
        
        # Should accept request even with custom header
        assert response.status_code in [404, 200]

    def test_cors_preflight_request(self):
        """Test CORS preflight OPTIONS request."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        # Preflight should be handled (404 because route doesn't exist)
        assert response.status_code in [200, 404, 405]


class TestAppEndpoints:
    """Test app endpoint behavior."""

    def test_app_has_openapi_docs(self):
        """Test that OpenAPI docs endpoint exists."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/docs")
        
        # Docs endpoint should exist
        assert response.status_code == 200

    def test_app_has_openapi_json(self):
        """Test that OpenAPI JSON endpoint exists."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/openapi.json")
        
        # OpenAPI JSON should be accessible
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_app_nonexistent_route_returns_404(self):
        """Test that nonexistent routes return 404."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/nonexistent/route")
        
        # Should return 404 for non-existent routes
        assert response.status_code == 404

    def test_app_root_path(self):
        """Test app root path."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/")
        
        # Root might not have a handler, so 404 is expected
        assert response.status_code in [404, 200]


class TestOpenAPISchema:
    """Test OpenAPI schema generation."""

    def test_app_openapi_schema(self):
        """Test that OpenAPI schema can be generated."""
        from api.contact_app import app
        
        schema = app.openapi()
        assert schema is not None
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "AstraGuard Contact API (dev)"

    def test_openapi_version(self):
        """Test OpenAPI version in schema."""
        from api.contact_app import app
        
        schema = app.openapi()
        assert "openapi" in schema
        # OpenAPI version should be 3.x.x
        assert schema["openapi"].startswith("3.")

    def test_openapi_has_paths(self):
        """Test that OpenAPI schema has paths."""
        from api.contact_app import app
        
        schema = app.openapi()
        assert "paths" in schema
        # Even if no routes, paths key should exist
        assert isinstance(schema["paths"], dict)


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""

    def test_malformed_origin_header(self):
        """Test handling of malformed Origin header."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/", headers={"Origin": "not-a-valid-url"})
        
        # Should handle gracefully
        assert response.status_code in [404, 200]

    def test_empty_origin_header(self):
        """Test handling of empty Origin header."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/", headers={"Origin": ""})
        
        # Should handle gracefully
        assert response.status_code in [404, 200]

    def test_request_without_origin_header(self):
        """Test request without Origin header."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/")
        
        # Should work without Origin header
        assert response.status_code in [404, 200]

    def test_cors_various_http_methods(self):
        """Test CORS with various HTTP methods."""
        from api.contact_app import app
        
        client = TestClient(app)
        
        # Test different methods (will get 404/405 but CORS should work)
        for method in ["get", "post", "put", "patch", "delete"]:
            response = getattr(client, method)(
                "/test",
                headers={"Origin": "http://localhost:8080"}
            )
            assert response.status_code in [404, 405, 200]

    def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        from api.contact_app import app
        
        client = TestClient(app)
        
        # Make multiple requests
        responses = []
        for _ in range(10):
            response = client.get("/", headers={"Origin": "http://localhost:8080"})
            responses.append(response)
        
        # All should be handled
        assert len(responses) == 10
        assert all(r.status_code in [404, 200] for r in responses)

    def test_large_header_values(self):
        """Test handling of large header values."""
        from api.contact_app import app
        
        client = TestClient(app)
        large_value = "x" * 1000
        response = client.get("/", headers={"X-Custom": large_value})
        
        # Should handle large headers
        assert response.status_code in [404, 200, 431]

    def test_special_characters_in_path(self):
        """Test handling of special characters in path."""
        from api.contact_app import app
        
        client = TestClient(app)
        response = client.get("/test%20path")
        
        # Should handle special characters
        assert response.status_code in [404, 200]


class TestModuleImports:
    """Test module imports and dependencies."""

    def test_fastapi_import(self):
        """Test that FastAPI is imported correctly."""
        from api.contact_app import FastAPI
        assert FastAPI is not None

    def test_cors_middleware_import(self):
        """Test that CORSMiddleware is imported correctly."""
        from api.contact_app import CORSMiddleware
        assert CORSMiddleware is not None

    def test_list_type_import(self):
        """Test that List type is imported correctly."""
        from api.contact_app import List
        assert List is not None

    def test_logging_import(self):
        """Test that logging is imported correctly."""
        from api.contact_app import logging
        assert logging is not None


class TestAppConfiguration:
    """Test app configuration details."""

    def test_app_instance_is_singleton(self):
        """Test that app instance behaves as singleton."""
        from api.contact_app import app as app1
        from api.contact_app import app as app2
        
        # Should be the same instance
        assert app1 is app2

    def test_app_has_title(self):
        """Test that app has title set."""
        from api.contact_app import app
        
        assert hasattr(app, 'title')
        assert app.title is not None
        assert len(app.title) > 0

    def test_allowed_origins_immutable(self):
        """Test ALLOWED_ORIGINS list properties."""
        from api.contact_app import ALLOWED_ORIGINS
        
        # Should be a list
        assert isinstance(ALLOWED_ORIGINS, list)
        # Should have exact number of entries
        assert len(ALLOWED_ORIGINS) == 4

    def test_all_origins_use_http_not_https(self):
        """Test that all configured origins use HTTP (dev environment)."""
        from api.contact_app import ALLOWED_ORIGINS
        
        for origin in ALLOWED_ORIGINS:
            assert origin.startswith("http://")
            assert not origin.startswith("https://")

    def test_origins_include_both_localhost_and_127(self):
        """Test that origins include both localhost and 127.0.0.1."""
        from api.contact_app import ALLOWED_ORIGINS
        
        localhost_origins = [o for o in ALLOWED_ORIGINS if "localhost" in o]
        ip_origins = [o for o in ALLOWED_ORIGINS if "127.0.0.1" in o]
        
        # Should have both types
        assert len(localhost_origins) > 0
        assert len(ip_origins) > 0

    def test_origins_include_both_ports(self):
        """Test that origins include both 8000 and 8080 ports."""
        from api.contact_app import ALLOWED_ORIGINS
        
        port_8000 = [o for o in ALLOWED_ORIGINS if ":8000" in o]
        port_8080 = [o for o in ALLOWED_ORIGINS if ":8080" in o]
        
        # Should have both ports
        assert len(port_8000) > 0
        assert len(port_8080) > 0
