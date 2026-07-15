"""
Comprehensive unit tests for src/astraguard/tracing.py

Improvements:
- Removed redundant tests
- Fixed non-deterministic failures
- Improved assertion strictness
- Added missing edge cases
- Reduced over-mocking
- Better coverage without brittle logging assertions
"""

import pytest
from unittest.mock import MagicMock, call
import logging
import asyncio

# Import the module under test
from astraguard import tracing
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_get_secret(monkeypatch):
    """Mock the get_secret function from core.secrets"""
    def mock_secret(key: str, default: str = None):
        mock_values = {
            "environment": "test",
            "app_version": "1.0.0-test",
        }
        return mock_values.get(key, default)
    
    monkeypatch.setattr("astraguard.tracing.get_secret", mock_secret)
    return mock_secret


@pytest.fixture
def mock_tracer():
    """Mock Tracer instance with proper span behavior"""
    tracer = MagicMock(spec=trace.Tracer)
    span = MagicMock()
    span.set_attribute = MagicMock()
    span.record_exception = MagicMock()
    span.__enter__ = MagicMock(return_value=span)
    span.__exit__ = MagicMock(return_value=None)
    tracer.start_as_current_span = MagicMock(return_value=span)
    return tracer


# ============================================================================
# TESTS: initialize_tracing()
# ============================================================================

class TestInitializeTracing:
    """Tests for initialize_tracing function"""

    def test_successful_initialization_with_all_components(self, mock_get_secret, monkeypatch):
        """Test successful initialization creates all required components"""
        mock_jaeger_exporter = MagicMock()
        mock_resource = MagicMock()
        mock_tracer_provider = MagicMock(spec=TracerProvider)
        mock_processor = MagicMock()

        jaeger_class = MagicMock(return_value=mock_jaeger_exporter)
        resource_class = MagicMock(return_value=mock_resource)
        resource_class.create = MagicMock(return_value=mock_resource)
        provider_class = MagicMock(return_value=mock_tracer_provider)
        processor_class = MagicMock(return_value=mock_processor)
        set_provider_mock = MagicMock()

        monkeypatch.setattr("astraguard.tracing.JaegerExporter", jaeger_class)
        monkeypatch.setattr("astraguard.tracing.Resource", resource_class)
        monkeypatch.setattr("astraguard.tracing.TracerProvider", provider_class)
        monkeypatch.setattr("astraguard.tracing.BatchSpanProcessor", processor_class)
        monkeypatch.setattr("astraguard.tracing.trace.set_tracer_provider", set_provider_mock)

        # Call function
        result = tracing.initialize_tracing(
            service_name="test-service",
            jaeger_host="jaeger.test",
            jaeger_port=6831,
            batch_size=512,
            export_interval=5.0,
            enabled=True
        )

        # Verify all components were created correctly
        assert result is mock_tracer_provider
        jaeger_class.assert_called_once_with(
            agent_host_name="jaeger.test",
            agent_port=6831,
            transport_format="grpc"
        )
        resource_class.create.assert_called_once()
        provider_class.assert_called_once_with(resource=mock_resource)
        processor_class.assert_called_once_with(
            mock_jaeger_exporter,
            max_export_batch_size=512,
            schedule_delay_millis=5000
        )
        mock_tracer_provider.add_span_processor.assert_called_once_with(mock_processor)
        set_provider_mock.assert_called_once_with(mock_tracer_provider)

    def test_disabled_tracing_returns_noop_provider(self, monkeypatch):
        """Test that disabled tracing returns a no-op TracerProvider without initialization"""
        # Ensure no initialization code is called
        jaeger_mock = MagicMock()
        monkeypatch.setattr("astraguard.tracing.JaegerExporter", jaeger_mock)

        result = tracing.initialize_tracing(enabled=False)

        # Verify provider returned but Jaeger not initialized
        assert result is not None
        assert isinstance(result, TracerProvider)
        jaeger_mock.assert_not_called()

    def test_connection_error_triggers_graceful_degradation(self, mock_get_secret, monkeypatch, caplog):
        """Test that ConnectionError is caught and returns noop provider.
        
        Note: The @retry decorator wraps this function but the inner try-except
        catches exceptions before the decorator can retry, providing graceful degradation.
        """
        def raising_jaeger(*args, **kwargs):
            raise ConnectionError("Failed to connect")

        monkeypatch.setattr("astraguard.tracing.JaegerExporter", raising_jaeger)

        with caplog.at_level(logging.WARNING):
            result = tracing.initialize_tracing(enabled=True)
        
        # Verify graceful degradation: returns noop provider instead of raising
        assert result is not None
        assert isinstance(result, TracerProvider)
        # Verify error was logged
        assert any("Failed to initialize Jaeger" in record.message for record in caplog.records)

    def test_inner_try_except_provides_graceful_error_handling(self, mock_get_secret, monkeypatch, caplog):
        """Test that inner try-except catches all exceptions and returns noop provider.
        
        IMPORTANT: The @retry decorator wraps initialize_tracing(), but the inner
        try-except block catches exceptions BEFORE they can propagate to the decorator.
        Therefore, the retry decorator cannot actually trigger - it's a safety net
        that never activates in practice. The primary error handling is the inner
        try-except which ensures we always return a TracerProvider (noop on failure).
        """
        call_count = [0]
        
        def always_failing_jaeger(*args, **kwargs):
            call_count[0] += 1
            # Always fail to demonstrate that exception is caught by inner try-except
            raise ConnectionError("Service unavailable")

        monkeypatch.setattr("astraguard.tracing.JaegerExporter", always_failing_jaeger)

        with caplog.at_level(logging.WARNING):
            # Exception should be caught, not retried by decorator
            result = tracing.initialize_tracing(enabled=True)
        
        # Verify exception was caught and noop provider returned
        assert result is not None
        assert isinstance(result, TracerProvider)
        # Verify Jaeger exporter was called exactly once (no retry from decorator)
        assert call_count[0] == 1, f"Expected 1 call (no decorator retry), but got {call_count[0]}"
        # Verify error was logged
        assert any("Failed to initialize Jaeger" in record.message for record in caplog.records)

    def test_os_error_triggers_graceful_degradation(self, mock_get_secret, monkeypatch, caplog):
        """Test that OSError is caught and returns noop provider.
        
        Note: The @retry decorator wraps this function but the inner try-except
        catches exceptions before the decorator can retry, providing graceful degradation.
        """
        def raising_jaeger(*args, **kwargs):
            raise OSError("Network unavailable")

        monkeypatch.setattr("astraguard.tracing.JaegerExporter", raising_jaeger)

        with caplog.at_level(logging.WARNING):
            result = tracing.initialize_tracing(enabled=True)
        
        # Verify graceful degradation: returns noop provider instead of raising
        assert result is not None
        assert isinstance(result, TracerProvider)
        # Verify error was logged
        assert any("Failed to initialize Jaeger" in record.message for record in caplog.records)

    def test_resource_includes_service_name_environment_version(self, monkeypatch):
        """Test Resource is created with correct attributes"""
        resource_create_mock = MagicMock()
        
        def mock_secret(key, default=None):
            return {"environment": "production", "app_version": "2.1.0"}.get(key, default)

        monkeypatch.setattr("astraguard.tracing.get_secret", mock_secret)
        monkeypatch.setattr("astraguard.tracing.JaegerExporter", MagicMock(return_value=MagicMock()))
        monkeypatch.setattr("astraguard.tracing.Resource.create", resource_create_mock)
        monkeypatch.setattr("astraguard.tracing.BatchSpanProcessor", MagicMock(return_value=MagicMock()))
        monkeypatch.setattr("astraguard.tracing.TracerProvider", MagicMock(return_value=MagicMock(spec=TracerProvider)))
        monkeypatch.setattr("astraguard.tracing.trace.set_tracer_provider", MagicMock())

        tracing.initialize_tracing(service_name="my-service", enabled=True)

        resource_create_mock.assert_called_once()
        resource_attrs = resource_create_mock.call_args[0][0]
        assert "service.name" in resource_attrs or "my-service" in str(resource_attrs)
        assert resource_attrs["environment"] == "production"
        assert resource_attrs["version"] == "2.1.0"

    def test_custom_batch_parameters(self, mock_get_secret, monkeypatch):
        """Test custom batch_size and export_interval are applied correctly"""
        processor_class = MagicMock(return_value=MagicMock())
        
        monkeypatch.setattr("astraguard.tracing.JaegerExporter", MagicMock(return_value=MagicMock()))
        monkeypatch.setattr("astraguard.tracing.BatchSpanProcessor", processor_class)
        monkeypatch.setattr("astraguard.tracing.TracerProvider", MagicMock(return_value=MagicMock(spec=TracerProvider)))
        monkeypatch.setattr("astraguard.tracing.trace.set_tracer_provider", MagicMock())

        tracing.initialize_tracing(
            batch_size=2048,
            export_interval=15.5,
            enabled=True
        )

        processor_class.assert_called_once()
        call_kwargs = processor_class.call_args[1]
        assert call_kwargs['max_export_batch_size'] == 2048
        assert call_kwargs['schedule_delay_millis'] == 15500

    def test_generic_exception_returns_noop_provider(self, mock_get_secret, monkeypatch, caplog):
        """Test that non-retryable exceptions are caught and return noop provider"""
        monkeypatch.setattr(
            "astraguard.tracing.JaegerExporter",
            MagicMock(side_effect=ValueError("Invalid configuration"))
        )

        with caplog.at_level(logging.WARNING):
            result = tracing.initialize_tracing(enabled=True)

        # Should return a provider even on failure
        assert result is not None


# ============================================================================
# TESTS: Instrumentation functions
# ============================================================================

class TestInstrumentation:
    """Tests for setup_auto_instrumentation and instrument_fastapi"""

    def test_auto_instrumentation_instruments_requests_and_redis(self, monkeypatch):
        """Test auto-instrumentation calls instrument() on both instrumentors"""
        req_inst = MagicMock()
        redis_inst = MagicMock()

        monkeypatch.setattr(
            "astraguard.tracing.RequestsInstrumentor",
            MagicMock(return_value=req_inst)
        )
        monkeypatch.setattr(
            "astraguard.tracing.RedisInstrumentor",
            MagicMock(return_value=redis_inst)
        )

        tracing.setup_auto_instrumentation()

        req_inst.instrument.assert_called_once()
        redis_inst.instrument.assert_called_once()

    def test_auto_instrumentation_handles_import_error_gracefully(self, monkeypatch):
        """Test ImportError doesn't crash auto-instrumentation"""
        monkeypatch.setattr(
            "astraguard.tracing.RequestsInstrumentor",
            MagicMock(side_effect=ImportError("requests not found"))
        )

        # Should not raise
        tracing.setup_auto_instrumentation()

    def test_auto_instrumentation_handles_runtime_error(self, monkeypatch):
        """Test runtime errors during instrumentation are caught"""
        req_inst = MagicMock()
        req_inst.instrument = MagicMock(side_effect=RuntimeError("Failed"))
        
        monkeypatch.setattr(
            "astraguard.tracing.RequestsInstrumentor",
            MagicMock(return_value=req_inst)
        )

        # Should not raise
        tracing.setup_auto_instrumentation()

    def test_fastapi_instrumentation_calls_instrument_app(self, monkeypatch):
        """Test FastAPI instrumentation correctly calls instrument_app"""
        instrumentor_class = MagicMock()
        mock_app = MagicMock()

        monkeypatch.setattr("astraguard.tracing.FastAPIInstrumentor", instrumentor_class)

        tracing.instrument_fastapi(mock_app)

        instrumentor_class.instrument_app.assert_called_once_with(mock_app)

    def test_fastapi_instrumentation_handles_errors(self, monkeypatch):
        """Test FastAPI instrumentation error handling"""
        monkeypatch.setattr(
            "astraguard.tracing.FastAPIInstrumentor",
            MagicMock(side_effect=ImportError("FastAPI not found"))
        )

        # Should not raise
        tracing.instrument_fastapi(MagicMock())


# ============================================================================
# TESTS: get_tracer()
# ============================================================================

class TestGetTracer:
    """Tests for get_tracer function"""

    def test_get_tracer_returns_tracer_from_opentelemetry(self, monkeypatch):
        """Test get_tracer delegates to OpenTelemetry API"""
        mock_tracer = MagicMock()
        get_tracer_mock = MagicMock(return_value=mock_tracer)
        monkeypatch.setattr("astraguard.tracing.trace.get_tracer", get_tracer_mock)

        result = tracing.get_tracer(name="my.tracer")

        assert result is mock_tracer
        get_tracer_mock.assert_called_once_with("my.tracer")

    def test_get_tracer_with_default_name(self, monkeypatch):
        """Test get_tracer with default module name"""
        get_tracer_mock = MagicMock()
        monkeypatch.setattr("astraguard.tracing.trace.get_tracer", get_tracer_mock)

        tracing.get_tracer()

        get_tracer_mock.assert_called_once()


# ============================================================================
# TESTS: Synchronous span context managers
# ============================================================================

class TestSyncSpanContextManagers:
    """Tests for synchronous span context managers"""

    def test_span_creates_span_with_name(self, monkeypatch, mock_tracer):
        """Test basic span creation"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        with tracing.span("operation_name"):
            pass

        mock_tracer.start_as_current_span.assert_called_once_with("operation_name")

    def test_span_sets_attributes_as_strings(self, monkeypatch, mock_tracer):
        """Test span converts all attribute values to strings"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        attrs = {
            "str_val": "text",
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
            "none_val": None
        }

        with tracing.span("test", attributes=attrs):
            pass

        span = mock_tracer.start_as_current_span.return_value
        assert span.set_attribute.call_count == 5
        
        # Verify all values converted to strings
        for call_args in span.set_attribute.call_args_list:
            assert isinstance(call_args[0][1], str)

    def test_span_with_empty_attributes_doesnt_set_any(self, monkeypatch, mock_tracer):
        """Test that empty attributes dict doesn't set any attributes"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        with tracing.span("test", attributes={}):
            pass

        span = mock_tracer.start_as_current_span.return_value
        span.set_attribute.assert_not_called()

    def test_span_propagates_exceptions(self, monkeypatch, mock_tracer):
        """Test that exceptions raised within span are propagated"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        with pytest.raises(ValueError, match="test error"):
            with tracing.span("test"):
                raise ValueError("test error")

    def test_span_anomaly_detection_sets_required_attributes(self, monkeypatch, mock_tracer):
        """Test anomaly detection span sets data.size and model attributes"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        with tracing.span_anomaly_detection(data_size=1500, model_name="detector-v2"):
            pass

        mock_tracer.start_as_current_span.assert_called_once_with("anomaly_detection")
        span = mock_tracer.start_as_current_span.return_value
        
        set_attr_calls = span.set_attribute.call_args_list
        assert call("data.size", 1500) in set_attr_calls
        assert call("model", "detector-v2") in set_attr_calls

    def test_span_anomaly_detection_records_exceptions(self, monkeypatch, mock_tracer):
        """Test anomaly detection span records exceptions via record_exception"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        error = RuntimeError("Model failed")
        try:
            with tracing.span_anomaly_detection(data_size=100):
                raise error
        except RuntimeError:
            pass

        mock_tracer.start_as_current_span.return_value.record_exception.assert_called_once_with(error)


# ============================================================================
# TESTS: Async span context managers
# ============================================================================

class TestAsyncSpanContextManagers:
    """Tests for async span context managers"""

    @pytest.mark.asyncio
    async def test_async_span_creates_span_properly(self, monkeypatch, mock_tracer):
        """Test async span context manager works correctly"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        async with tracing.async_span("async_operation", attributes={"key": "value"}):
            await asyncio.sleep(0.001)

        mock_tracer.start_as_current_span.assert_called_once_with("async_operation")
        span = mock_tracer.start_as_current_span.return_value
        assert call("key", "value") in span.set_attribute.call_args_list

    @pytest.mark.asyncio
    async def test_async_span_anomaly_detection_records_exceptions(self, monkeypatch, mock_tracer):
        """Test async anomaly detection span records exceptions"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        error = ValueError("Async error")

        try:
            async with tracing.async_span_anomaly_detection(data_size=200):
                raise error
        except ValueError:
            pass

        mock_tracer.start_as_current_span.return_value.record_exception.assert_called_once_with(error)

    @pytest.mark.asyncio
    async def test_async_external_call_with_timeout(self, monkeypatch, mock_tracer):
        """Test async external call with timeout attribute"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        async with tracing.async_span_external_call("api", "call", timeout=10.0):
            pass

        span = mock_tracer.start_as_current_span.return_value
        assert call("timeout", 10.0) in span.set_attribute.call_args_list


# ============================================================================
# TESTS: shutdown_tracing()
# ============================================================================

class TestShutdownTracing:
    """Tests for shutdown_tracing function"""

    def test_shutdown_calls_force_flush_on_provider(self, monkeypatch):
        """Test shutdown calls force_flush if provider supports it"""
        mock_provider = MagicMock()
        mock_provider.force_flush = MagicMock()
        
        monkeypatch.setattr(
            "astraguard.tracing.trace.get_tracer_provider",
            MagicMock(return_value=mock_provider)
        )

        tracing.shutdown_tracing()

        mock_provider.force_flush.assert_called_once()

    def test_shutdown_handles_provider_without_force_flush(self, monkeypatch):
        """Test shutdown handles providers that don't have force_flush"""
        mock_provider = MagicMock(spec=[])  # No methods
        
        monkeypatch.setattr(
            "astraguard.tracing.trace.get_tracer_provider",
            MagicMock(return_value=mock_provider)
        )

        # Should not raise
        tracing.shutdown_tracing()

    def test_shutdown_handles_connection_error_gracefully(self, monkeypatch, caplog):
        """Test shutdown handles ConnectionError during flush"""
        mock_provider = MagicMock()
        mock_provider.force_flush = MagicMock(side_effect=ConnectionError("Lost connection"))
        
        monkeypatch.setattr(
            "astraguard.tracing.trace.get_tracer_provider",
            MagicMock(return_value=mock_provider)
        )

        with caplog.at_level(logging.WARNING):
            # Should not raise
            tracing.shutdown_tracing()

        # Error should be logged (but we don't strictly require specific text)
        assert len(caplog.records) > 0

    def test_shutdown_handles_generic_exception(self, monkeypatch, caplog):
        """Test shutdown handles unexpected exceptions during flush"""
        mock_provider = MagicMock()
        mock_provider.force_flush = MagicMock(side_effect=RuntimeError("Unexpected"))
        
        monkeypatch.setattr(
            "astraguard.tracing.trace.get_tracer_provider",
            MagicMock(return_value=mock_provider)
        )

        with caplog.at_level(logging.WARNING):
            # Should not raise
            tracing.shutdown_tracing()

        assert len(caplog.records) > 0


# ============================================================================
# EDGE CASES AND COMPREHENSIVE SCENARIOS
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_span_with_negative_data_size(self, monkeypatch, mock_tracer):
        """Test anomaly detection handles negative data size"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        # Should not raise
        with tracing.span_anomaly_detection(data_size=-100):
            pass

        span = mock_tracer.start_as_current_span.return_value
        assert call("data.size", -100) in span.set_attribute.call_args_list

    def test_span_with_zero_data_size(self, monkeypatch, mock_tracer):
        """Test anomaly detection with zero data size"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        with tracing.span_anomaly_detection(data_size=0):
            pass

        span = mock_tracer.start_as_current_span.return_value
        assert call("data.size", 0) in span.set_attribute.call_args_list

    def test_span_with_very_large_data_size(self, monkeypatch, mock_tracer):
        """Test span handles very large numbers"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        large = 10**15
        with tracing.span_anomaly_detection(data_size=large):
            pass

        span = mock_tracer.start_as_current_span.return_value
        assert call("data.size", large) in span.set_attribute.call_args_list

    def test_span_with_unicode_in_attributes(self, monkeypatch, mock_tracer):
        """Test span handles Unicode characters in attributes"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        unicode_attrs = {
            "emoji": "🚀🔥",
            "chinese": "测试",
            "arabic": "اختبار",
            "mixed": "test™®"
        }

        with tracing.span("unicode_test", attributes=unicode_attrs):
            pass

        span = mock_tracer.start_as_current_span.return_value
        assert span.set_attribute.call_count == 4

    def test_span_with_special_characters_in_name(self, monkeypatch, mock_tracer):
        """Test span allows special characters in span name"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        special_name = "op::name-with_special.chars/and\\slashes"
        
        with tracing.span(special_name):
            pass

        mock_tracer.start_as_current_span.assert_called_once_with(special_name)

    def test_initialize_with_extreme_batch_parameters(self, mock_get_secret, monkeypatch):
        """Test initialization with extreme batch size and interval values"""
        processor_class = MagicMock(return_value=MagicMock())
        
        monkeypatch.setattr("astraguard.tracing.JaegerExporter", MagicMock(return_value=MagicMock()))
        monkeypatch.setattr("astraguard.tracing.BatchSpanProcessor", processor_class)
        monkeypatch.setattr("astraguard.tracing.TracerProvider", MagicMock(return_value=MagicMock(spec=TracerProvider)))
        monkeypatch.setattr("astraguard.tracing.trace.set_tracer_provider", MagicMock())

        # Test with very small values
        tracing.initialize_tracing(batch_size=1, export_interval=0.001, enabled=True)
        
        call_kwargs = processor_class.call_args[1]
        assert call_kwargs['max_export_batch_size'] == 1
        assert call_kwargs['schedule_delay_millis'] == 1  # 0.001 * 1000 = 1

    def test_multiple_span_contexts_in_sequence(self, monkeypatch, mock_tracer):
        """Test multiple span types can be used sequentially without interference"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        with tracing.span("op1"):
            pass
        with tracing.span_anomaly_detection(data_size=100):
            pass
        with tracing.span("op2"):
            pass

        assert mock_tracer.start_as_current_span.call_count == 3

    @pytest.mark.asyncio
    async def test_mixed_sync_async_spans_dont_interfere(self, monkeypatch, mock_tracer):
        """Test that sync and async spans can coexist"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        # Sync span
        with tracing.span("sync_span"):
            pass

        # Async span
        async with tracing.async_span("async_span"):
            pass

        assert mock_tracer.start_as_current_span.call_count == 2

    def test_span_attribute_with_complex_dict(self, monkeypatch, mock_tracer):
        """Test span converts complex nested structures to strings"""
        monkeypatch.setattr("astraguard.tracing.get_tracer", MagicMock(return_value=mock_tracer))

        complex_attrs = {
            "nested_dict": {"a": {"b": {"c": 1}}},
            "list": [1, [2, [3, 4]]],
            "tuple": (1, 2, 3),
            "mixed": {"list": [1, 2], "dict": {"key": "val"}}
        }

        with tracing.span("complex", attributes=complex_attrs):
            pass

        span = mock_tracer.start_as_current_span.return_value
        # All should be converted to strings
        for call_args in span.set_attribute.call_args_list:
            assert isinstance(call_args[0][1], str)

    def test_initialization_with_empty_service_name(self, mock_get_secret, monkeypatch):
        """Test initialization with empty service name still works"""
        monkeypatch.setattr("astraguard.tracing.JaegerExporter", MagicMock(return_value=MagicMock()))
        monkeypatch.setattr("astraguard.tracing.BatchSpanProcessor", MagicMock(return_value=MagicMock()))
        monkeypatch.setattr("astraguard.tracing.TracerProvider", MagicMock(return_value=MagicMock(spec=TracerProvider)))
        monkeypatch.setattr("astraguard.tracing.trace.set_tracer_provider", MagicMock())

        # Should not raise even with empty name
        result = tracing.initialize_tracing(service_name="", enabled=True)
        assert result is not None
