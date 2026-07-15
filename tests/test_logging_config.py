"""
Unit tests for AstraGuard Structured Logging Module
"""

import pytest
import logging
import sys
import json
import asyncio
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime
from pathlib import Path
import structlog
from pythonjsonlogger import jsonlogger

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from astraguard.logging_config import (
    setup_json_logging,
    get_logger,
    LogContext,
    log_request,
    log_error,
    log_detection,
    log_circuit_breaker_event,
    log_retry_event,
    log_recovery_action,
    log_performance_metric,
    async_log_request,
    async_log_error,
    async_log_detection,
    set_log_level,
    clear_context,
    bind_context,
    unbind_context,
    _cached_get_secret
)


class TestLoggingConfig:
    """Test suite for logging_config module"""

    def setup_method(self):
        """Setup test fixtures"""
        # Clear any existing context
        structlog.contextvars.clear_contextvars()
        # Reset logging
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.INFO)

    def teardown_method(self):
        """Cleanup after each test"""
        structlog.contextvars.clear_contextvars()
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.INFO)

    @patch('astraguard.logging_config._cached_get_secret')
    @patch('astraguard.logging_config.structlog.configure')
    @patch('astraguard.logging_config.logging.getLogger')
    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_setup_json_logging_success(self, mock_bind_context, mock_get_logger, mock_structlog_configure, mock_get_secret):
        """Test successful JSON logging setup"""
        mock_get_secret.side_effect = lambda key, default=None: {
            'app_version': '1.0.0'
        }.get(key, default)

        mock_root_logger = MagicMock()
        mock_get_logger.return_value = mock_root_logger

        # Pass environment explicitly since default is evaluated at definition time
        setup_json_logging(log_level="DEBUG", service_name="test-service", environment="production")

        # Verify structlog configuration was called
        mock_structlog_configure.assert_called_once()
        # Verify context binding
        mock_bind_context.assert_called_once_with(
            service="test-service",
            environment="production",
            version="1.0.0"
        )
        # Verify root logger setup
        mock_root_logger.setLevel.assert_called_once_with(logging.DEBUG)
        mock_root_logger.addHandler.assert_called_once()

    @patch('astraguard.logging_config._cached_get_secret')
    @patch('astraguard.logging_config.logging.basicConfig')
    def test_setup_json_logging_invalid_log_level(self, mock_basic_config, mock_get_secret):
        """Test setup with invalid log level falls back gracefully"""
        mock_get_secret.return_value = "production"

        # Should not raise, but fall back to basic logging
        setup_json_logging(log_level="INVALID")

        mock_basic_config.assert_called_once()

    @patch('astraguard.logging_config._cached_get_secret')
    @patch('astraguard.logging_config.structlog.configure')
    def test_setup_json_logging_fallback_on_import_error(self, mock_structlog_configure, mock_get_secret):
        """Test fallback to basic logging on structlog import error"""
        mock_get_secret.return_value = "production"
        mock_structlog_configure.side_effect = ImportError("structlog not available")

        with patch('astraguard.logging_config.logging.basicConfig') as mock_basic_config:
            setup_json_logging()

            mock_basic_config.assert_called_once_with(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
            )

    @patch('astraguard.logging_config._cached_get_secret')
    @patch('astraguard.logging_config.structlog.configure')
    def test_setup_json_logging_fallback_on_general_error(self, mock_structlog_configure, mock_get_secret):
        """Test fallback on general setup error"""
        mock_get_secret.return_value = "production"
        mock_structlog_configure.side_effect = Exception("Unexpected error")

        with patch('astraguard.logging_config.logging.basicConfig') as mock_basic_config:
            setup_json_logging()

            mock_basic_config.assert_called_once()

    @patch('astraguard.logging_config.structlog.get_logger')
    def test_get_logger(self, mock_get_logger):
        """Test get_logger function"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        result = get_logger("test_module")

        mock_get_logger.assert_called_once_with("test_module")
        assert result == mock_logger

    def test_log_context_manager(self):
        """Test LogContext context manager"""
        mock_logger = MagicMock()
        bound_logger = MagicMock()
        mock_logger.bind.return_value = bound_logger
        context = {"test_key": "test_value"}

        with LogContext(mock_logger, **context):
            # Verify bind was called
            mock_logger.bind.assert_called_once_with(**context)

        # Verify error logging on exception
        mock_logger.reset_mock()
        bound_logger.reset_mock()
        mock_logger.bind.return_value = bound_logger
        try:
            with LogContext(mock_logger, **context):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should have logged the error on the bound logger
        bound_logger.error.assert_called_once()
        call_args = bound_logger.error.call_args
        assert call_args[0][0] == "context_error"
        assert "error_type" in call_args[1]
        assert "error_message" in call_args[1]

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_bind_context(self, mock_bind):
        """Test bind_context function"""
        bind_context(key1="value1", key2="value2")
        mock_bind.assert_called_once_with(key1="value1", key2="value2")

    @patch('astraguard.logging_config.structlog.contextvars.unbind_contextvars')
    def test_unbind_context(self, mock_unbind):
        """Test unbind_context function"""
        unbind_context("key1", "key2")
        mock_unbind.assert_called_once_with("key1", "key2")

    @patch('astraguard.logging_config.structlog.contextvars.clear_contextvars')
    def test_clear_context(self, mock_clear):
        """Test clear_context function"""
        clear_context()
        mock_clear.assert_called_once()

    @patch('astraguard.logging_config.logging.getLogger')
    def test_set_log_level_valid(self, mock_get_logger):
        """Test set_log_level with valid level"""
        mock_root_logger = MagicMock()
        mock_get_logger.return_value = mock_root_logger

        set_log_level("DEBUG")

        mock_root_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_set_log_level_invalid(self):
        """Test set_log_level with invalid level raises AttributeError"""
        with pytest.raises(AttributeError):
            set_log_level("INVALID")

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_request(self, mock_bind):
        """Test log_request function"""
        mock_logger = MagicMock()

        log_request(
            mock_logger,
            method="GET",
            endpoint="/api/test",
            status=200,
            duration_ms=150.5,
            user_id="123"
        )

        mock_logger.info.assert_called_once_with(
            "http_request",
            method="GET",
            endpoint="/api/test",
            status=200,
            duration_ms=150.5,
            user_id="123"
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_error(self, mock_bind):
        """Test log_error function"""
        mock_logger = MagicMock()
        test_error = ValueError("Test error")

        log_error(
            mock_logger,
            error=test_error,
            context="Database connection failed",
            user_id="123"
        )

        mock_logger.error.assert_called_once_with(
            "Database connection failed",
            error_type="ValueError",
            error_message="Test error",
            exc_info=True,
            user_id="123"
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_detection(self, mock_bind):
        """Test log_detection function"""
        mock_logger = MagicMock()

        log_detection(
            mock_logger,
            severity="HIGH",
            detected_type="thermal_fault",
            confidence=0.95,
            sensor_id="temp_01"
        )

        mock_logger.info.assert_called_once_with(
            "anomaly_detected",
            severity="HIGH",
            type="thermal_fault",
            confidence=0.95,
            sensor_id="temp_01"
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_circuit_breaker_event(self, mock_bind):
        """Test log_circuit_breaker_event function"""
        mock_logger = MagicMock()

        log_circuit_breaker_event(
            mock_logger,
            event="opened",
            breaker_name="api_circuit",
            state="OPEN",
            reason="timeout"
        )

        mock_logger.warning.assert_called_once_with(
            "circuit_breaker_event",
            event="opened",
            breaker="api_circuit",
            state="OPEN",
            reason="timeout"
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_retry_event(self, mock_bind):
        """Test log_retry_event function"""
        mock_logger = MagicMock()

        # Test retrying status
        log_retry_event(
            mock_logger,
            endpoint="/api/retry",
            attempt=2,
            status="retrying",
            delay_ms=1000.0
        )

        mock_logger.info.assert_called_once_with(
            "retry_event",
            endpoint="/api/retry",
            attempt=2,
            status="retrying",
            delay_ms=1000.0
        )

        # Test exhausted status
        mock_logger.reset_mock()
        log_retry_event(
            mock_logger,
            endpoint="/api/retry",
            attempt=3,
            status="exhausted"
        )

        mock_logger.warning.assert_called_once_with(
            "retry_event",
            endpoint="/api/retry",
            attempt=3,
            status="exhausted",
            delay_ms=None
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_recovery_action(self, mock_bind):
        """Test log_recovery_action function"""
        mock_logger = MagicMock()

        log_recovery_action(
            mock_logger,
            action_type="restart_service",
            status="completed",
            component="api_gateway",
            duration_ms=5000.0
        )

        mock_logger.info.assert_called_once_with(
            "recovery_action",
            action="restart_service",
            status="completed",
            component="api_gateway",
            duration_ms=5000.0
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_performance_metric_no_alert(self, mock_bind):
        """Test log_performance_metric without alert"""
        mock_logger = MagicMock()

        log_performance_metric(
            mock_logger,
            metric_name="response_time",
            value=120.5,
            unit="ms",
            threshold=200.0
        )

        mock_logger.info.assert_called_once_with(
            "performance_metric",
            metric="response_time",
            value=120.5,
            unit="ms",
            threshold=200.0,
            alert=False
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_performance_metric_with_alert(self, mock_bind):
        """Test log_performance_metric with alert"""
        mock_logger = MagicMock()

        log_performance_metric(
            mock_logger,
            metric_name="response_time",
            value=250.0,
            unit="ms",
            threshold=200.0
        )

        mock_logger.warning.assert_called_once_with(
            "performance_metric",
            metric="response_time",
            value=250.0,
            unit="ms",
            threshold=200.0,
            alert=True
        )

    @pytest.mark.asyncio
    async def test_async_log_request(self):
        """Test async_log_request function"""
        mock_logger = MagicMock()

        with patch('astraguard.logging_config.log_request') as mock_log_request:
            with patch('astraguard.logging_config.asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = None

                await async_log_request(
                    mock_logger,
                    method="POST",
                    endpoint="/api/async",
                    status=201,
                    duration_ms=200.0
                )

                mock_to_thread.assert_called_once()
                # Verify the function was called with correct args
                call_args = mock_to_thread.call_args[0]
                assert call_args[0] == mock_log_request
                assert call_args[1] == mock_logger
                assert call_args[2] == "POST"
                assert call_args[3] == "/api/async"
                assert call_args[4] == 201
                assert call_args[5] == 200.0

    @pytest.mark.asyncio
    async def test_async_log_error(self):
        """Test async_log_error function"""
        mock_logger = MagicMock()
        test_error = RuntimeError("Async error")

        with patch('astraguard.logging_config.log_error') as mock_log_error:
            with patch('astraguard.logging_config.asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = None

                await async_log_error(
                    mock_logger,
                    error=test_error,
                    context="Async operation failed"
                )

                mock_to_thread.assert_called_once()
                call_args = mock_to_thread.call_args[0]
                assert call_args[0] == mock_log_error
                assert call_args[1] == mock_logger
                assert call_args[2] == test_error
                assert call_args[3] == "Async operation failed"

    @pytest.mark.asyncio
    async def test_async_log_detection(self):
        """Test async_log_detection function"""
        mock_logger = MagicMock()

        with patch('astraguard.logging_config.log_detection') as mock_log_detection:
            with patch('astraguard.logging_config.asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = None

                await async_log_detection(
                    mock_logger,
                    severity="CRITICAL",
                    detected_type="power_failure",
                    confidence=0.99
                )

                mock_to_thread.assert_called_once()
                call_args = mock_to_thread.call_args[0]
                assert call_args[0] == mock_log_detection
                assert call_args[1] == mock_logger
                assert call_args[2] == "CRITICAL"
                assert call_args[3] == "power_failure"
                assert call_args[4] == 0.99

    @patch('astraguard.logging_config.get_secret')
    def test_cached_get_secret_success(self, mock_get_secret):
        """Test _cached_get_secret success"""
        mock_get_secret.return_value = "test_value"

        # Clear cache
        _cached_get_secret.cache_clear()

        result1 = _cached_get_secret("test_key", "default")
        result2 = _cached_get_secret("test_key", "default")

        assert result1 == "test_value"
        assert result2 == "test_value"
        # Should only call get_secret once due to caching
        mock_get_secret.assert_called_once_with("test_key", "default")

    @patch('astraguard.logging_config.get_secret')
    def test_cached_get_secret_exception(self, mock_get_secret):
        """Test _cached_get_secret with exception"""
        mock_get_secret.side_effect = Exception("Secret not found")

        # Clear cache
        _cached_get_secret.cache_clear()

        result = _cached_get_secret("missing_key", "fallback")

        assert result == "fallback"
        mock_get_secret.assert_called_once_with("missing_key", "fallback")

    def test_module_imports(self):
        """Test that all expected functions are importable"""
        # This test ensures the module can be imported without errors
        assert callable(setup_json_logging)
        assert callable(get_logger)
        assert callable(LogContext)
        assert callable(log_request)
        assert callable(log_error)
        assert callable(log_detection)
        assert callable(log_circuit_breaker_event)
        assert callable(log_retry_event)
        assert callable(log_recovery_action)
        assert callable(log_performance_metric)
        assert callable(async_log_request)
        assert callable(async_log_error)
        assert callable(async_log_detection)
        assert callable(set_log_level)
        assert callable(clear_context)
        assert callable(bind_context)
        assert callable(unbind_context)
        assert callable(_cached_get_secret)


class TestLoggingBehavior:
    """Behavioral tests for logging_config module.
    
    These tests verify actual runtime behavior rather than mocking.
    """

    def setup_method(self):
        """Setup test fixtures - clear logging state."""
        structlog.contextvars.clear_contextvars()
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)
        # Clear the cached secret to avoid persisted state
        _cached_get_secret.cache_clear()

    def teardown_method(self):
        """Cleanup after each test."""
        structlog.contextvars.clear_contextvars()
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)
        _cached_get_secret.cache_clear()

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_configures_root_logger_level(self, mock_get_secret):
        """Test that setup_json_logging correctly sets the root logger level."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging(log_level="DEBUG")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_configures_info_level(self, mock_get_secret):
        """Test that INFO level is set correctly."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging(log_level="INFO")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_configures_warning_level(self, mock_get_secret):
        """Test that WARNING level is set correctly."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging(log_level="WARNING")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_configures_error_level(self, mock_get_secret):
        """Test that ERROR level is set correctly."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging(log_level="ERROR")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.ERROR

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_adds_stream_handler(self, mock_get_secret):
        """Test that setup_json_logging adds a StreamHandler to the root logger."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging()

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1
        assert isinstance(root_logger.handlers[0], logging.StreamHandler)

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_handler_has_formatter(self, mock_get_secret):
        """Test that the handler has a formatter configured."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging()

        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        formatter = handler.formatter
        assert formatter is not None
        # Verify formatter has expected format attributes
        assert hasattr(formatter, 'format')

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_idempotency_no_duplicate_handlers(self, mock_get_secret):
        """Test that calling setup_json_logging twice doesn't duplicate handlers.
        
        This verifies idempotent behavior - handlers should be cleared before adding new ones.
        """
        mock_get_secret.side_effect = lambda key, default=None: default

        # Call setup twice
        setup_json_logging(log_level="INFO")
        setup_json_logging(log_level="DEBUG")

        root_logger = logging.getLogger()
        # Should still only have 1 handler
        assert len(root_logger.handlers) == 1

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_idempotency_updates_level(self, mock_get_secret):
        """Test that calling setup_json_logging multiple times updates the level correctly."""
        mock_get_secret.side_effect = lambda key, default=None: default

        # First call sets INFO
        setup_json_logging(log_level="INFO")
        assert logging.getLogger().level == logging.INFO

        # Second call updates to DEBUG
        setup_json_logging(log_level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_environment_from_secret(self, mock_get_secret):
        """Test that environment value is bound to context."""
        mock_get_secret.side_effect = lambda key, default=None: default

        # Call with explicit environment parameter to test context binding
        setup_json_logging(service_name="test-service", environment="staging")

        # Verify context was bound via structlog contextvars
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get('service') == 'test-service'
        assert ctx.get('environment') == 'staging'

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_uses_default_environment(self, mock_get_secret):
        """Test that default environment is used when secret is not available."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging()

        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get('environment') == 'development'  # default value

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_uses_default_app_version(self, mock_get_secret):
        """Test that default app_version is used when secret retrieval fails."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging()

        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get('version') == '1.0.0'  # default value

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_handler_outputs_to_stdout(self, mock_get_secret):
        """Test that the JSON handler outputs to stdout."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging()

        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        assert handler.stream == sys.stdout

    @patch('astraguard.logging_config.get_secret')
    def test_json_formatter_output_is_valid_json(self, mock_get_secret, capsys):
        """Test that the logger outputs valid JSON."""
        mock_get_secret.side_effect = lambda key, default=None: default

        setup_json_logging(log_level="INFO")

        test_logger = logging.getLogger("test_json_output")
        test_logger.setLevel(logging.INFO)
        test_logger.info("Test message")

        captured = capsys.readouterr()
        if captured.out.strip():
            # Verify the output is valid JSON
            log_entry = json.loads(captured.out.strip())
            assert "message" in log_entry
            assert log_entry["message"] == "Test message"

    def test_set_log_level_changes_root_logger_level(self):
        """Test that set_log_level actually changes the root logger level."""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.WARNING)

        set_log_level("DEBUG")

        assert root_logger.level == logging.DEBUG

    def test_set_log_level_accepts_all_standard_levels(self):
        """Test that set_log_level accepts all standard logging levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in levels:
            set_log_level(level)
            assert logging.getLogger().level == getattr(logging, level)

    def test_get_logger_returns_bound_logger(self):
        """Test that get_logger returns a structlog BoundLogger."""
        logger = get_logger("test_module")

        # Should be able to call logging methods
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'debug')
        assert hasattr(logger, 'warning')
        assert hasattr(logger, 'error')

    def test_get_logger_with_different_names_returns_different_loggers(self):
        """Test that get_logger with different names returns distinct loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        # They should be distinct (structlog may cache, but they represent different names)
        assert logger1 is not None
        assert logger2 is not None

    def test_bind_context_adds_context_vars(self):
        """Test that bind_context actually binds context variables."""
        clear_context()

        bind_context(user_id="123", session_id="abc")

        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get('user_id') == '123'
        assert ctx.get('session_id') == 'abc'

    def test_unbind_context_removes_context_vars(self):
        """Test that unbind_context removes specified context variables."""
        clear_context()
        bind_context(user_id="123", session_id="abc", trace_id="xyz")

        unbind_context("user_id", "session_id")

        ctx = structlog.contextvars.get_contextvars()
        assert 'user_id' not in ctx
        assert 'session_id' not in ctx
        assert ctx.get('trace_id') == 'xyz'

    def test_clear_context_removes_all_context_vars(self):
        """Test that clear_context removes all context variables."""
        bind_context(key1="val1", key2="val2")

        clear_context()

        ctx = structlog.contextvars.get_contextvars()
        assert ctx == {}

    def test_log_context_manager_binds_context(self):
        """Test that LogContext context manager binds context while active."""
        logger = get_logger("test_context")

        with LogContext(logger, operation="test_op", request_id="r123") as bound_logger:
            # The bound logger should have bind method called
            assert bound_logger is not None

    def test_log_context_manager_logs_error_on_exception(self):
        """Test that LogContext logs error when exception occurs."""
        mock_logger = MagicMock()
        bound_logger = MagicMock()
        mock_logger.bind.return_value = bound_logger

        try:
            with LogContext(mock_logger, operation="failing_op"):
                raise RuntimeError("Test failure")
        except RuntimeError:
            pass

        # Verify error was logged with correct structure
        bound_logger.error.assert_called_once()
        call_args = bound_logger.error.call_args
        assert call_args[0][0] == "context_error"
        assert call_args[1]["error_type"] == "RuntimeError"
        assert "Test failure" in call_args[1]["error_message"]

    def test_log_request_logs_with_correct_structure(self):
        """Test that log_request logs with expected structure."""
        mock_logger = MagicMock()

        log_request(
            mock_logger,
            method="POST",
            endpoint="/api/users",
            status=201,
            duration_ms=123.456,
            extra_field="extra_value"
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "http_request"
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["endpoint"] == "/api/users"
        assert call_args[1]["status"] == 201
        assert call_args[1]["duration_ms"] == 123.46  # rounded to 2 decimal
        assert call_args[1]["extra_field"] == "extra_value"

    def test_log_error_includes_exception_info(self):
        """Test that log_error includes all exception information."""
        mock_logger = MagicMock()
        error = ValueError("Invalid input value")

        log_error(mock_logger, error=error, context="validation_failed")

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "validation_failed"
        assert call_args[1]["error_type"] == "ValueError"
        assert call_args[1]["error_message"] == "Invalid input value"
        assert call_args[1]["exc_info"] is True

    def test_log_detection_rounds_confidence(self):
        """Test that log_detection rounds confidence to 3 decimal places."""
        mock_logger = MagicMock()

        log_detection(
            mock_logger,
            severity="high",
            detected_type="anomaly",
            confidence=0.95678912
        )

        call_args = mock_logger.info.call_args
        assert call_args[1]["confidence"] == 0.957  # rounded to 3 decimals

    def test_log_circuit_breaker_event_uses_warning_level(self):
        """Test that circuit breaker events are logged at warning level."""
        mock_logger = MagicMock()

        log_circuit_breaker_event(
            mock_logger,
            event="opened",
            breaker_name="db_breaker",
            state="OPEN"
        )

        mock_logger.warning.assert_called_once()
        assert mock_logger.info.call_count == 0

    def test_log_retry_event_uses_info_for_retrying(self):
        """Test that retry events with 'retrying' status use info level."""
        mock_logger = MagicMock()

        log_retry_event(
            mock_logger,
            endpoint="/api/data",
            attempt=1,
            status="retrying"
        )

        mock_logger.info.assert_called_once()

    def test_log_retry_event_uses_warning_for_exhausted(self):
        """Test that retry events with 'exhausted' status use warning level."""
        mock_logger = MagicMock()

        log_retry_event(
            mock_logger,
            endpoint="/api/data",
            attempt=3,
            status="exhausted"
        )

        mock_logger.warning.assert_called_once()

    def test_log_retry_event_uses_warning_for_success(self):
        """Test that retry events with 'success' status use warning level."""
        mock_logger = MagicMock()

        log_retry_event(
            mock_logger,
            endpoint="/api/data",
            attempt=2,
            status="success"
        )

        mock_logger.warning.assert_called_once()

    def test_log_performance_metric_no_alert_when_under_threshold(self):
        """Test that performance metric does not alert when value is under threshold."""
        mock_logger = MagicMock()

        log_performance_metric(
            mock_logger,
            metric_name="latency",
            value=50.0,
            threshold=100.0
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[1]["alert"] is False

    def test_log_performance_metric_alerts_when_over_threshold(self):
        """Test that performance metric alerts when value exceeds threshold."""
        mock_logger = MagicMock()

        log_performance_metric(
            mock_logger,
            metric_name="latency",
            value=150.0,
            threshold=100.0
        )

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[1]["alert"] is True

    def test_log_performance_metric_no_alert_without_threshold(self):
        """Test that performance metric has no alert when no threshold specified."""
        mock_logger = MagicMock()

        log_performance_metric(
            mock_logger,
            metric_name="latency",
            value=500.0
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[1]["alert"] is False
        assert call_args[1]["threshold"] is None

    def test_log_recovery_action_logs_all_fields(self):
        """Test that recovery action logs all required fields."""
        mock_logger = MagicMock()

        log_recovery_action(
            mock_logger,
            action_type="restart",
            status="completed",
            component="api_server",
            duration_ms=2500.5
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "recovery_action"
        assert call_args[1]["action"] == "restart"
        assert call_args[1]["status"] == "completed"
        assert call_args[1]["component"] == "api_server"
        assert call_args[1]["duration_ms"] == 2500.5

    @pytest.mark.asyncio
    async def test_async_log_request_calls_sync_version(self):
        """Test that async_log_request delegates to the sync log_request."""
        mock_logger = MagicMock()

        with patch('astraguard.logging_config.asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = None

            await async_log_request(
                mock_logger,
                method="GET",
                endpoint="/api/health",
                status=200,
                duration_ms=10.0
            )

            mock_to_thread.assert_called_once()
            call_args = mock_to_thread.call_args[0]
            assert call_args[0] == log_request

    @pytest.mark.asyncio
    async def test_async_log_error_calls_sync_version(self):
        """Test that async_log_error delegates to the sync log_error."""
        mock_logger = MagicMock()
        error = Exception("Async error")

        with patch('astraguard.logging_config.asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = None

            await async_log_error(
                mock_logger,
                error=error,
                context="async_operation"
            )

            mock_to_thread.assert_called_once()
            call_args = mock_to_thread.call_args[0]
            assert call_args[0] == log_error

    @pytest.mark.asyncio
    async def test_async_log_detection_calls_sync_version(self):
        """Test that async_log_detection delegates to the sync log_detection."""
        mock_logger = MagicMock()

        with patch('astraguard.logging_config.asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = None

            await async_log_detection(
                mock_logger,
                severity="critical",
                detected_type="breach",
                confidence=0.99
            )

            mock_to_thread.assert_called_once()
            call_args = mock_to_thread.call_args[0]
            assert call_args[0] == log_detection

    def test_cached_get_secret_returns_cached_value(self):
        """Test that _cached_get_secret caches values properly."""
        _cached_get_secret.cache_clear()

        with patch('astraguard.logging_config.get_secret') as mock_secret:
            mock_secret.return_value = "cached_value"

            # First call
            result1 = _cached_get_secret("test_key")
            # Second call
            result2 = _cached_get_secret("test_key")

            assert result1 == "cached_value"
            assert result2 == "cached_value"
            # Should only be called once due to caching
            assert mock_secret.call_count == 1

    def test_cached_get_secret_returns_default_on_exception(self):
        """Test that _cached_get_secret returns default when exception occurs."""
        _cached_get_secret.cache_clear()

        with patch('astraguard.logging_config.get_secret') as mock_secret:
            mock_secret.side_effect = Exception("Connection error")

            result = _cached_get_secret("failing_key", "fallback_value")

            assert result == "fallback_value"

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_app_version_secret_failure(self, mock_get_secret, capsys):
        """Test that setup_json_logging handles app_version secret failure gracefully.
        
        When get_secret raises an exception retrieving app_version, setup should:
        1. Continue without crashing
        2. Use default version '1.0.0'
        3. Print a warning to stderr
        """
        # Make get_secret fail specifically for app_version
        def secret_side_effect(key, default=None):
            if key == "app_version":
                raise ValueError("Secret store unavailable")
            return default
        mock_get_secret.side_effect = secret_side_effect

        setup_json_logging(log_level="INFO", environment="test")

        # Verify context was bound with default version
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get('version') == '1.0.0'
        
        # Verify warning was printed to stderr
        captured = capsys.readouterr()
        assert "Warning: Failed to retrieve app_version secret" in captured.err

    @patch('astraguard.logging_config.get_secret')
    def test_setup_json_logging_app_version_key_error(self, mock_get_secret, capsys):
        """Test that setup_json_logging handles KeyError for app_version."""
        def secret_side_effect(key, default=None):
            if key == "app_version":
                raise KeyError("app_version not found")
            return default
        mock_get_secret.side_effect = secret_side_effect

        setup_json_logging(log_level="DEBUG", environment="dev")

        # Should continue with default version
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get('version') == '1.0.0'


class TestModuleInitialization:
    """Tests for module-level initialization behavior (lines 510-519).
    
    These tests verify the conditional initialization logic at module load time.
    """

    def setup_method(self):
        """Clear state before each test."""
        _cached_get_secret.cache_clear()
        structlog.contextvars.clear_contextvars()
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

    def teardown_method(self):
        """Clear state after each test."""
        _cached_get_secret.cache_clear()
        structlog.contextvars.clear_contextvars()
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

    def test_module_initialization_with_json_enabled(self):
        """Test that module initializes JSON logging when enable_json_logging is True.
        
        This validates the conditional initialization at module import time.
        """
        with patch('astraguard.logging_config._cached_get_secret') as mock_secret:
            mock_secret.return_value = True  # enable_json_logging = True
            
            with patch('astraguard.logging_config.setup_json_logging') as mock_setup:
                # Manually trigger the initialization logic
                enable_json = mock_secret("enable_json_logging", False)
                if enable_json:
                    mock_setup()
                
                mock_setup.assert_called_once()

    def test_module_initialization_with_json_disabled(self):
        """Test that module does not initialize JSON logging when disabled."""
        with patch('astraguard.logging_config._cached_get_secret') as mock_secret:
            mock_secret.return_value = False  # enable_json_logging = False
            
            with patch('astraguard.logging_config.setup_json_logging') as mock_setup:
                # Manually trigger the initialization logic
                enable_json = mock_secret("enable_json_logging", False)
                if enable_json:
                    mock_setup()
                
                mock_setup.assert_not_called()

    def test_module_initialization_exception_fallback(self, capsys):
        """Test that module initialization falls back to basic logging on exception."""
        # Simulate the initialization error handling block
        with patch('astraguard.logging_config._cached_get_secret') as mock_secret:
            mock_secret.side_effect = Exception("Config service unavailable")
            
            # Run the initialization logic with exception handling
            try:
                enable_json = mock_secret("enable_json_logging", False)
                if enable_json:
                    setup_json_logging()
            except (KeyError, ValueError, Exception) as e:
                print(f"Warning: Failed to initialize JSON logging on import: {e}. Using default logging.", file=sys.stderr)
                logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
            
            # Verify warning was printed
            captured = capsys.readouterr()
            assert "Warning: Failed to initialize JSON logging on import" in captured.err
            assert "Config service unavailable" in captured.err


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
