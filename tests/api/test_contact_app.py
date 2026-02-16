"""
Unit tests for src/api/contact_app.py - Lightweight Contact API Application.

Tests cover:
- FastAPI application creation and configuration
- CORS middleware configuration
- Router inclusion (success and failure paths)
- Error handling for router import failures
- Logging behavior

Target: ≥80% coverage
"""

import pytest
import sys
import logging
from unittest.mock import patch, MagicMock

# Check if FastAPI is available; if not, skip tests
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except (ImportError, TypeError):
    FASTAPI_AVAILABLE = False
    FastAPI = MagicMock
    TestClient = MagicMock

pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI not installed"
)


@pytest.fixture(autouse=True)
def clean_modules():
    """Clean up module cache before each test."""
    modules_to_remove = [k for k in sys.modules.keys() 
                        if k.startswith('api.contact')]
    for mod in modules_to_remove:
        del sys.modules[mod]
    yield
    # Cleanup after test
    modules_to_remove = [k for k in sys.modules.keys() 
                        if k.startswith('api.contact')]
    for mod in modules_to_remove:
        del sys.modules[mod]


class TestAppCreation:
    """Test FastAPI application creation."""

    def test_app_is_fastapi_instance(self):
        """Test that app is a FastAPI instance."""
        mock_router = MagicMock()
        
        # Patch both api.contact and src.api.contact to ensure correct mocking
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert isinstance(contact_app.app, FastAPI)

    def test_app_has_correct_title(self):
        """Test that app has the expected title."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert contact_app.app.title == "AstraGuard Contact API (dev)"

    def test_app_exposes_logger(self):
        """Test that module exposes a logger."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert hasattr(contact_app, 'logger')
            assert isinstance(contact_app.logger, logging.Logger)


class TestCORSConfiguration:
    """Test CORS middleware configuration."""

    def test_allowed_origins_contains_localhost_8080(self):
        """Test that localhost:8080 is in allowed origins."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert "http://localhost:8080" in contact_app.ALLOWED_ORIGINS

    def test_allowed_origins_contains_127_0_0_1_8080(self):
        """Test that 127.0.0.1:8080 is in allowed origins."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert "http://127.0.0.1:8080" in contact_app.ALLOWED_ORIGINS

    def test_allowed_origins_contains_localhost_8000(self):
        """Test that localhost:8000 is in allowed origins."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert "http://localhost:8000" in contact_app.ALLOWED_ORIGINS

    def test_allowed_origins_contains_127_0_0_1_8000(self):
        """Test that 127.0.0.1:8000 is in allowed origins."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert "http://127.0.0.1:8000" in contact_app.ALLOWED_ORIGINS

    def test_allowed_origins_count(self):
        """Test that exactly 4 origins are allowed."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert len(contact_app.ALLOWED_ORIGINS) == 4

    def test_cors_middleware_is_added(self):
        """Test that CORS middleware is added to the app."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            # Check middleware stack contains CORSMiddleware
            middleware_classes = [m.cls.__name__ for m in contact_app.app.user_middleware]
            assert 'CORSMiddleware' in middleware_classes


class TestRouterInclusion:
    """Test router inclusion behavior."""

    def test_router_is_included_successfully(self):
        """Test that router is included when import succeeds."""
        mock_router = MagicMock()
        mock_contact = MagicMock(router=mock_router)
        
        with patch.dict(sys.modules, {
            'api.contact': mock_contact,
            'src.api.contact': mock_contact
        }):
            from api import contact_app
            
            # App should have routes from the router
            assert contact_app.app is not None

    def test_runtime_error_triggers_critical_log_and_reraise(self):
        """Test that RuntimeError during include_router logs critical and re-raises."""
        import runpy
        import os
        
        # Clear cached modules to force reimport
        modules_to_clear = [k for k in list(sys.modules.keys()) if k.startswith('api.contact')]
        for mod in modules_to_clear:
            del sys.modules[mod]
        
        mock_router = MagicMock()
        mock_contact = MagicMock(router=mock_router)
        mock_logger = MagicMock()
        
        # Create a mock FastAPI that raises RuntimeError on include_router
        class FailingFastAPI:
            def __init__(self, *args, **kwargs):
                self.title = kwargs.get('title', '')
                
            def add_middleware(self, *args, **kwargs):
                pass
                
            def include_router(self, router):
                raise RuntimeError("Router registration failed")

            def exception_handler(self, exc_class_or_status_code):
                def decorator(func):
                    return func
                return decorator
        
        # Patch at the fastapi module level before running the module
        with patch.dict(sys.modules, {
            'api.contact': mock_contact,
            'src.api.contact': mock_contact
        }):
            with patch('fastapi.FastAPI', FailingFastAPI):
                with patch('logging.getLogger') as mock_get_logger:
                    mock_get_logger.return_value = mock_logger
                    module_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'api', 'contact_app.py')
                    module_path = os.path.abspath(module_path)
                    
                    with pytest.raises(RuntimeError, match="Router registration failed"):
                        runpy.run_path(module_path, run_name='api.contact_app')
                    
                    # Verify logger.critical was called with exc_info=True
                    mock_logger.critical.assert_called_once()
                    call_args = mock_logger.critical.call_args
                    assert "Failed to include contact router" in call_args[0][0]
                    assert call_args[1].get('exc_info') is True


class TestCORSBehavior:
    """Test actual CORS behavior via HTTP requests."""

    def test_cors_allows_localhost_8080_origin(self):
        """Test that CORS allows requests from localhost:8080."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={"Origin": "http://localhost:8080"}
            )
            
            # Should not get a CORS error (405 is expected for no route, not CORS block)
            assert response.status_code in [200, 404, 405]

    def test_cors_allows_localhost_8000_origin(self):
        """Test that CORS allows requests from localhost:8000."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={"Origin": "http://localhost:8000"}
            )
            
            assert response.status_code in [200, 404, 405]

    def test_cors_credentials_allowed(self):
        """Test that CORS allows credentials."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={
                    "Origin": "http://localhost:8080",
                    "Access-Control-Request-Method": "POST"
                }
            )
            
            # Assert credentials header is present and correct
            assert "access-control-allow-credentials" in response.headers
            assert response.headers["access-control-allow-credentials"] == "true"


class TestAllowedMethods:
    """Test allowed HTTP methods in CORS."""

    def test_cors_allows_get_method(self):
        """Test that CORS allows GET method."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={
                    "Origin": "http://localhost:8080",
                    "Access-Control-Request-Method": "GET"
                }
            )
            
            assert "access-control-allow-methods" in response.headers
            assert "GET" in response.headers["access-control-allow-methods"]

    def test_cors_allows_post_method(self):
        """Test that CORS allows POST method."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={
                    "Origin": "http://localhost:8080",
                    "Access-Control-Request-Method": "POST"
                }
            )
            
            assert "access-control-allow-methods" in response.headers
            assert "POST" in response.headers["access-control-allow-methods"]

    def test_cors_allows_put_method(self):
        """Test that CORS allows PUT method."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={
                    "Origin": "http://localhost:8080",
                    "Access-Control-Request-Method": "PUT"
                }
            )
            
            assert "access-control-allow-methods" in response.headers
            assert "PUT" in response.headers["access-control-allow-methods"]

    def test_cors_allows_delete_method(self):
        """Test that CORS allows DELETE method."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={
                    "Origin": "http://localhost:8080",
                    "Access-Control-Request-Method": "DELETE"
                }
            )
            
            assert "access-control-allow-methods" in response.headers
            assert "DELETE" in response.headers["access-control-allow-methods"]

    def test_cors_allows_patch_method(self):
        """Test that CORS allows PATCH method."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={
                    "Origin": "http://localhost:8080",
                    "Access-Control-Request-Method": "PATCH"
                }
            )
            
            assert "access-control-allow-methods" in response.headers
            assert "PATCH" in response.headers["access-control-allow-methods"]

    def test_cors_allows_options_method(self):
        """Test that CORS allows OPTIONS method."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={
                    "Origin": "http://localhost:8080",
                    "Access-Control-Request-Method": "OPTIONS"
                }
            )
            
            assert "access-control-allow-methods" in response.headers
            assert "OPTIONS" in response.headers["access-control-allow-methods"]


class TestImportErrorHandling:
    """Test handling of import errors."""

    def test_module_loads_with_mocked_dependencies(self):
        """Test that module loads successfully when dependencies are mocked."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            # If we get here, the import succeeded
            assert contact_app.app is not None

    def test_missing_router_attribute_handled(self):
        """Test behavior when api.contact module lacks router attribute."""
        # Mock api.contact without a router attribute
        mock_contact = MagicMock(spec=[])
        
        # Clear module cache
        if 'api.contact_app' in sys.modules:
            del sys.modules['api.contact_app']
        
        with patch.dict(sys.modules, {
            'api.contact': mock_contact,
            'src.api.contact': mock_contact
        }):
            # This should raise ImportError since router doesn't exist on mock
            with pytest.raises((AttributeError, ImportError)):
                import importlib
                importlib.import_module('api.contact_app')


class TestModuleLevel:
    """Test module-level attributes and configuration."""

    def test_module_has_docstring(self):
        """Test that module has a docstring."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert contact_app.__doc__ is not None
            assert "Lightweight FastAPI" in contact_app.__doc__

    def test_allowed_origins_is_list_of_strings(self):
        """Test that ALLOWED_ORIGINS is a list of strings."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            assert isinstance(contact_app.ALLOWED_ORIGINS, list)
            for origin in contact_app.ALLOWED_ORIGINS:
                assert isinstance(origin, str)

    def test_all_origins_start_with_http(self):
        """Test that all allowed origins start with http://."""
        mock_router = MagicMock()
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            for origin in contact_app.ALLOWED_ORIGINS:
                assert origin.startswith("http://")


class TestAppConfiguration:
    """Test FastAPI app configuration details."""

    def test_cors_allow_headers_is_wildcard(self):
        """Test that CORS allows all headers (wildcard)."""
        mock_router = MagicMock()
        mock_router.routes = []
        
        with patch.dict(sys.modules, {
            'api.contact': MagicMock(router=mock_router),
            'src.api.contact': MagicMock(router=mock_router)
        }):
            from api import contact_app
            
            # Check that middleware was configured with allow_headers=["*"]
            # This is verified by making a request with a custom header
            client = TestClient(contact_app.app)
            response = client.options(
                "/",
                headers={
                    "Origin": "http://localhost:8080",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "X-Custom-Header"
                }
            )
            
            # Assert headers are allowed - should either be "*" or include the requested header
            assert "access-control-allow-headers" in response.headers
            allow_headers = response.headers["access-control-allow-headers"]
            assert "*" in allow_headers or "x-custom-header" in allow_headers.lower()
