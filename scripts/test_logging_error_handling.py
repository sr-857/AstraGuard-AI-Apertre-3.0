#!/usr/bin/env python3
"""
Comprehensive test script for error handling improvements in logging_config.py
Tests all edge cases, fallbacks, and integration scenarios.
"""

import sys
import os
import tempfile
import shutil
import subprocess
from unittest.mock import patch, MagicMock
import logging

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_import_without_errors():
    """Test that the module can be imported without errors"""
    print("Testing module import...")
    try:
        import astraguard.logging_config
        print("✓ Module imported successfully")
        return True
    except Exception as e:
        print(f"✗ Module import failed: {e}")
        return False

def test_setup_json_logging_valid():
    """Test setup_json_logging with valid parameters"""
    print("Testing setup_json_logging with valid parameters...")
    try:
        from astraguard.logging_config import setup_json_logging
        setup_json_logging(log_level="INFO", service_name="test-service")
        print("✓ Valid setup succeeded")
        return True
    except Exception as e:
        print(f"✗ Valid setup failed: {e}")
        return False

def test_setup_json_logging_invalid_log_level():
    """Test setup_json_logging with invalid log level"""
    print("Testing setup_json_logging with invalid log level...")
    try:
        from astraguard.logging_config import setup_json_logging
        setup_json_logging(log_level="INVALID_LEVEL")
        print("✗ Should have failed with invalid log level")
        return False
    except ValueError as e:
        if "Invalid log level" in str(e):
            print("✓ Correctly caught invalid log level")
            return True
        else:
            print(f"✗ Wrong error for invalid log level: {e}")
            return False
    except Exception as e:
        print(f"✗ Unexpected error for invalid log level: {e}")
        return False

def test_get_secret_failure():
    """Test handling of get_secret failures"""
    print("Testing get_secret failure handling...")
    try:
        from astraguard.logging_config import setup_json_logging
        with patch('astraguard.logging_config.get_secret', side_effect=KeyError("secret not found")):
            # Capture stderr to check for warning message
            import io
            from contextlib import redirect_stderr
            stderr_capture = io.StringIO()
            with redirect_stderr(stderr_capture):
                setup_json_logging(log_level="INFO")
            stderr_output = stderr_capture.getvalue()
            if "Failed to retrieve app_version secret" in stderr_output:
                print("✓ get_secret failure handled correctly")
                return True
            else:
                print(f"✗ Expected warning not found in stderr: {stderr_output}")
                return False
    except Exception as e:
        print(f"✗ get_secret failure test failed: {e}")
        return False

def test_missing_dependencies():
    """Test behavior when structlog is missing"""
    print("Testing missing dependencies handling...")
    try:
        # Temporarily hide structlog
        original_structlog = sys.modules.get('structlog')
        if 'structlog' in sys.modules:
            del sys.modules['structlog']

        # Mock import to raise ImportError
        def mock_import(name, *args, **kwargs):
            if name == 'structlog':
                raise ImportError("No module named 'structlog'")
            return __builtins__['__import__'](name, *args, **kwargs)

        original_import = __builtins__['__import__']
        __builtins__['__import__'] = mock_import

        try:
            # Re-import the module to trigger the error
            if 'astraguard.logging_config' in sys.modules:
                del sys.modules['astraguard.logging_config']
            import astraguard.logging_config
            print("✓ Missing dependencies handled gracefully")
            return True
        finally:
            __builtins__['__import__'] = original_import
            if original_structlog:
                sys.modules['structlog'] = original_structlog
    except Exception as e:
        print(f"✗ Missing dependencies test failed: {e}")
        return False

def test_set_log_level_valid():
    """Test set_log_level with valid level"""
    print("Testing set_log_level with valid level...")
    try:
        from astraguard.logging_config import set_log_level
        set_log_level("DEBUG")
        print("✓ Valid log level set successfully")
        return True
    except Exception as e:
        print(f"✗ Valid log level setting failed: {e}")
        return False

def test_set_log_level_invalid():
    """Test set_log_level with invalid level"""
    print("Testing set_log_level with invalid level...")
    try:
        from astraguard.logging_config import set_log_level
        import io
        from contextlib import redirect_stderr
        stderr_capture = io.StringIO()
        with redirect_stderr(stderr_capture):
            set_log_level("INVALID")
        stderr_output = stderr_capture.getvalue()
        if "Failed to set log level" in stderr_output:
            print("✓ Invalid log level handled correctly")
            return True
        else:
            print(f"✗ Expected warning not found: {stderr_output}")
            return False
    except Exception as e:
        print(f"✗ Invalid log level test failed: {e}")
        return False

def test_initialization_failure():
    """Test initialization failure on import"""
    print("Testing initialization failure handling...")
    try:
        # Test by patching get_secret to fail
        with patch('astraguard.logging_config.get_secret', side_effect=Exception("Init failure")):
            # Re-import to trigger initialization
            if 'astraguard.logging_config' in sys.modules:
                del sys.modules['astraguard.logging_config']
            import astraguard.logging_config
            print("✓ Initialization failure handled gracefully")
            return True
    except Exception as e:
        print(f"✗ Initialization failure test failed: {e}")
        return False

def test_logger_functionality():
    """Test that logging functions work after setup"""
    print("Testing logger functionality...")
    try:
        from astraguard.logging_config import get_logger, log_error
        logger = get_logger("test")
        # Test basic logging
        logger.info("Test message")
        # Test error logging
        try:
            raise ValueError("Test error")
        except Exception as e:
            log_error(logger, e, "test context")
        print("✓ Logger functionality works")
        return True
    except Exception as e:
        print(f"✗ Logger functionality test failed: {e}")
        return False

def test_integration_with_existing_code():
    """Test integration with existing code that uses logging_config"""
    print("Testing integration with existing code...")
    try:
        # Test imports from files that use logging_config
        import src.core.auth
        import src.core.audit_logger
        import src.api.service
        print("✓ Integration with existing code successful")
        return True
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("=" * 60)
    print("COMPREHENSIVE ERROR HANDLING TESTS FOR logging_config.py")
    print("=" * 60)

    tests = [
        test_import_without_errors,
        test_setup_json_logging_valid,
        test_setup_json_logging_invalid_log_level,
        test_get_secret_failure,
        test_missing_dependencies,
        test_set_log_level_valid,
        test_set_log_level_invalid,
        test_initialization_failure,
        test_logger_functionality,
        test_integration_with_existing_code,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 60)
    print(f"TEST RESULTS: {passed}/{total} tests passed")
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"❌ {total - passed} tests failed")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
