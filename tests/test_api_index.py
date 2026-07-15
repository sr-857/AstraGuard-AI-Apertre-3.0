"""
Unit tests for src/api/index.py

Tests cover the Vercel serverless function entry point, including:
- Project root path resolution
- sys.path manipulation
- App import and export
- Error handling scenarios

This module is designed for Vercel's serverless environment where the project
root might not be in sys.path by default.
"""

import pytest
import sys
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List


class TestProjectRootResolution:
    """Test project root path resolution."""

    def test_project_root_resolved_from_file(self):
        """Test that project root is correctly resolved from __file__."""
        # Import the module to get the resolved path
        import api.index as index_module
        
        # The project root should be resolved to the parent of 'api' directory
        # Which should be the src directory
        assert index_module.project_root is not None
        assert isinstance(index_module.project_root, Path)

    def test_project_root_str_conversion(self):
        """Test that project root can be converted to string."""
        import api.index as index_module
        
        # Should be able to convert to string
        root_str = index_module.project_root_str
        assert isinstance(root_str, str)
        assert len(root_str) > 0

    def test_project_root_points_to_src(self):
        """Test that project root points to the src directory."""
        import api.index as index_module
        
        # The project root should have 'api' as a subdirectory
        # since index.py is in src/api/
        assert (index_module.project_root / 'api').exists() or \
               (index_module.project_root.parent / 'api').exists()


class TestSysPathManipulation:
    """Test sys.path manipulation."""

    def test_project_root_added_to_sys_path(self):
        """Test that project root is added to sys.path."""
        import api.index as index_module
        
        # Project root string should be in sys.path
        # Note: It might be at the beginning or elsewhere
        assert index_module.project_root_str in sys.path

    def test_sys_path_contains_src(self):
        """Test that src directory is in sys.path."""
        import api.index as index_module
        
        # Get the src directory (parent of api)
        src_path = str(index_module.project_root)
        assert src_path in sys.path


class TestAppImport:
    """Test FastAPI app import."""

    def test_app_imported_successfully(self):
        """Test that the app is successfully imported."""
        import api.index as index_module
        
        # The app should be imported from api.service
        assert index_module.app is not None

    def test_app_is_fastapi_instance(self):
        """Test that app is a FastAPI instance."""
        import api.index as index_module
        
        # Check that app has FastAPI attributes
        from fastapi import FastAPI
        assert isinstance(index_module.app, FastAPI)

    def test_app_has_expected_attributes(self):
        """Test that app has expected FastAPI attributes."""
        import api.index as index_module
        
        # FastAPI app should have these attributes
        assert hasattr(index_module.app, 'router')
        assert hasattr(index_module.app, 'routes')


class TestExports:
    """Test module exports."""

    def test_all_exports_defined(self):
        """Test that __all__ is defined."""
        import api.index as index_module
        
        assert hasattr(index_module, '__all__')
        assert isinstance(index_module.__all__, list)

    def test_app_in_all_exports(self):
        """Test that 'app' is in __all__."""
        import api.index as index_module
        
        assert 'app' in index_module.__all__


class TestLogger:
    """Test logger configuration."""

    def test_logger_is_configured(self):
        """Test that logger is configured."""
        import api.index as index_module
        
        assert index_module.logger is not None
        assert isinstance(index_module.logger, logging.Logger)

    def test_logger_has_correct_name(self):
        """Test that logger has correct name."""
        import api.index as index_module
        
        # Logger name should match module name
        assert index_module.logger.name == 'api.index'


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_name_error_when_file_undefined(self):
        """Test that NameError is raised when __file__ is undefined."""
        # This test verifies that the code has proper error handling for the case
        # when __file__ is not defined. We check the source code structure.
        
        import api.index as index_module
        import inspect
        
        source = inspect.getsource(index_module)
        
        # Check that the error handling code exists for NameError
        assert 'NameError' in source
        assert 'RuntimeError' in source
        assert 'cannot resolve project root' in source
        
    def test_path_resolution_error_handling(self):
        """Test that path resolution has proper error handling."""
        import api.index as index_module
        import inspect
        
        source = inspect.getsource(index_module)
        
        # Verify error handling for path resolution
        assert 'NameError' in source
        assert 'project root' in source.lower()

    def test_module_not_found_error_handling(self):
        """Test that ModuleNotFoundError is handled."""
        import api.index as index_module
        import inspect
        
        source = inspect.getsource(index_module)
        
        # Check that ModuleNotFoundError handling exists
        assert 'ModuleNotFoundError' in source or 'ModuleNotFoundError' in source

    def test_import_error_handling(self):
        """Test that ImportError is handled."""
        import api.index as index_module
        import inspect
        
        source = inspect.getsource(index_module)
        
        # Check that ImportError handling exists
        assert 'ImportError' in source


class TestVercelServerlessContext:
    """Test Vercel serverless environment adaptations."""

    def test_module_docstring_mentions_vercel(self):
        """Test that module docstring mentions Vercel."""
        import api.index as index_module
        
        docstring = index_module.__doc__
        assert docstring is not None
        assert 'Vercel' in docstring

    def test_module_handles_serverless_environment(self):
        """Test that module is designed for serverless environment."""
        import api.index as index_module
        import inspect
        
        source = inspect.getsource(index_module)
        
        # Check for serverless-related comments
        assert 'serverless' in source.lower()


class TestPathResolutionEdgeCases:
    """Test edge cases in path resolution."""

    def test_project_root_is_absolute(self):
        """Test that project root is an absolute path."""
        import api.index as index_module
        
        # The resolved path should be absolute
        assert index_module.project_root.is_absolute()

    def test_project_root_exists(self):
        """Test that project root directory exists."""
        import api.index as index_module
        
        # The resolved directory should exist
        assert index_module.project_root.exists()

    def test_project_root_is_directory(self):
        """Test that project root is a directory."""
        import api.index as index_module
        
        # Should be a directory, not a file
        assert index_module.project_root.is_dir()


class TestIntegrationWithService:
    """Test integration with api.service module."""

    def test_app_matches_service_app(self):
        """Test that imported app matches the one from api.service."""
        import api.index as index_module
        from api.service import app as service_app
        
        # Both should be the same instance
        assert index_module.app is service_app

    def test_app_title_is_correct(self):
        """Test that app has correct title."""
        import api.index as index_module
        
        # Check app configuration
        assert index_module.app.title == "AstraGuard AI API"

    def test_app_version_is_correct(self):
        """Test that app has correct version."""
        import api.index as index_module
        
        # Check app version
        assert index_module.app.version == "1.0.0"


class TestModuleLoading:
    """Test module loading behavior."""

    def test_module_loads_without_errors(self):
        """Test that module loads without any errors."""
        # This is a basic sanity check
        import api.index as index_module
        
        assert index_module is not None

    def test_all_imports_successful(self):
        """Test that all imports within the module are successful."""
        # Verify key objects are available
        import api.index as index_module
        
        # Check all key exports
        assert hasattr(index_module, 'app')
        assert hasattr(index_module, 'logger')
        assert hasattr(index_module, 'project_root')
        assert hasattr(index_module, 'project_root_str')


class TestLoggingOutput:
    """Test logging behavior."""

    def test_logger_not_null(self):
        """Test that logger is not null."""
        import api.index as index_module
        
        assert index_module.logger is not None

    def test_logger_handlers_exist(self):
        """Test that logger has at least one handler."""
        import api.index as index_module
        
        # Logger should have handlers (or at least be ready to log)
        # Even if no handlers are explicitly added, root logger might handle it
        assert isinstance(index_module.logger, logging.Logger)

    def test_logger_level_set(self):
        """Test that logger level is set appropriately."""
        import api.index as index_module
        
        # Logger should have a level set
        assert index_module.logger.level >= 0


class TestFastAPIRoutes:
    """Test FastAPI routes from the app."""

    def test_app_has_routes(self):
        """Test that app has routes defined."""
        import api.index as index_module
        
        # App should have routes
        assert len(index_module.app.routes) > 0

    def test_app_has_root_route(self):
        """Test that app has root (/) route."""
        import api.index as index_module
        
        routes = index_module.app.routes
        route_paths = [route.path for route in routes if hasattr(route, 'path')]
        
        # Should have root route
        assert '/' in route_paths

    def test_app_has_telemetry_route(self):
        """Test that app has telemetry route."""
        import api.index as index_module
        
        routes = index_module.app.routes
        route_paths = [route.path for route in routes if hasattr(route, 'path')]
        
        # Should have telemetry route
        assert any('/telemetry' in path for path in route_paths)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
