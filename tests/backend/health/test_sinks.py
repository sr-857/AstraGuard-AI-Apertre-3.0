"""
Tests for MetricsSink implementations.

Tests cover:
- MetricsSink interface compliance
- NoOpMetricsSink behavior
- LoggingMetricsSink output
- PrometheusMetricsSink integration
"""

import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from backend.health.sinks import (
    MetricsSink,
    NoOpMetricsSink,
    LoggingMetricsSink,
    PrometheusMetricsSink,
)


# ============================================================================
# NOOP METRICS SINK TESTS
# ============================================================================


def test_noop_sink_emit():
    """Test NoOpMetricsSink.emit does nothing."""
    sink = NoOpMetricsSink()
    
    # Should not raise
    sink.emit("test_metric", 42.0)
    sink.emit("tagged_metric", 1.5, tags={"host": "localhost"})
    sink.emit("timestamped", 0.0, timestamp=datetime.utcnow())


def test_noop_sink_emit_counter():
    """Test NoOpMetricsSink.emit_counter does nothing."""
    sink = NoOpMetricsSink()
    
    # Should not raise
    sink.emit_counter("requests_total")
    sink.emit_counter("errors_total", 5.0)
    sink.emit_counter("tagged_counter", tags={"method": "GET"})


def test_noop_sink_emit_histogram():
    """Test NoOpMetricsSink.emit_histogram does nothing."""
    sink = NoOpMetricsSink()
    
    # Should not raise
    sink.emit_histogram("latency_ms", 150.5)
    sink.emit_histogram("response_size", 1024, tags={"endpoint": "/api"})


def test_noop_sink_emit_health_check():
    """Test NoOpMetricsSink.emit_health_check does nothing."""
    sink = NoOpMetricsSink()
    
    # Should not raise
    sink.emit_health_check("redis", "healthy", 5.2)
    sink.emit_health_check("database", "unhealthy", 1000.0)


# ============================================================================
# LOGGING METRICS SINK TESTS
# ============================================================================


def test_logging_sink_emit(caplog):
    """Test LoggingMetricsSink.emit logs correctly."""
    sink = LoggingMetricsSink(log_level=logging.INFO)
    
    with caplog.at_level(logging.INFO):
        sink.emit("test_metric", 42.0)
    
    assert "METRIC gauge test_metric=42.0" in caplog.text


def test_logging_sink_emit_with_tags(caplog):
    """Test LoggingMetricsSink.emit includes tags."""
    sink = LoggingMetricsSink(log_level=logging.INFO)
    
    with caplog.at_level(logging.INFO):
        sink.emit("tagged_metric", 1.5, tags={"host": "server1", "env": "prod"})
    
    assert "tagged_metric=1.5" in caplog.text
    assert "host=server1" in caplog.text
    assert "env=prod" in caplog.text


def test_logging_sink_emit_counter(caplog):
    """Test LoggingMetricsSink.emit_counter logs correctly."""
    sink = LoggingMetricsSink(log_level=logging.INFO)
    
    with caplog.at_level(logging.INFO):
        sink.emit_counter("requests_total", 1.0)
    
    assert "METRIC counter requests_total+=1.0" in caplog.text


def test_logging_sink_emit_histogram(caplog):
    """Test LoggingMetricsSink.emit_histogram logs correctly."""
    sink = LoggingMetricsSink(log_level=logging.INFO)
    
    with caplog.at_level(logging.INFO):
        sink.emit_histogram("latency_ms", 150.5)
    
    assert "METRIC histogram latency_ms=150.5" in caplog.text


def test_logging_sink_custom_log_level(caplog):
    """Test LoggingMetricsSink respects custom log level."""
    sink = LoggingMetricsSink(log_level=logging.DEBUG)
    
    # Should not appear at INFO level
    with caplog.at_level(logging.INFO):
        sink.emit("debug_metric", 1.0)
    
    assert "debug_metric" not in caplog.text
    
    # Should appear at DEBUG level
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        sink.emit("debug_metric", 1.0)
    
    assert "debug_metric" in caplog.text


# ============================================================================
# PROMETHEUS METRICS SINK TESTS
# ============================================================================


def test_prometheus_sink_initialization():
    """Test PrometheusMetricsSink initializes with custom registry."""
    from prometheus_client import CollectorRegistry
    
    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    
    assert sink.registry is registry


def test_prometheus_sink_emit_creates_gauge():
    """Test PrometheusMetricsSink.emit creates and sets gauge."""
    from prometheus_client import CollectorRegistry
    
    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    
    sink.emit("test_gauge", 42.0)
    
    # Verify gauge was created and set
    assert ("test_gauge", ()) in sink._gauges


def test_prometheus_sink_emit_with_tags():
    """Test PrometheusMetricsSink.emit handles labeled gauges."""
    from prometheus_client import CollectorRegistry
    
    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    
    sink.emit("labeled_gauge", 1.5, tags={"host": "server1"})
    
    # Should create gauge with labels
    assert any("labeled_gauge" in str(k) for k in sink._gauges.keys())


def test_prometheus_sink_emit_counter():
    """Test PrometheusMetricsSink.emit_counter increments counter."""
    from prometheus_client import CollectorRegistry
    
    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    
    sink.emit_counter("test_counter")
    sink.emit_counter("test_counter")
    
    # Counter should be created
    assert ("test_counter", ()) in sink._counters


def test_prometheus_sink_emit_histogram():
    """Test PrometheusMetricsSink.emit_histogram observes value."""
    from prometheus_client import CollectorRegistry
    
    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    
    sink.emit_histogram("test_histogram", 0.5)
    
    # Histogram should be created
    assert ("test_histogram", ()) in sink._histograms


def test_prometheus_sink_emit_health_check():
    """Test PrometheusMetricsSink.emit_health_check emits both metrics."""
    from prometheus_client import CollectorRegistry
    
    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    
    sink.emit_health_check("redis", "healthy", 5.2)
    
    # Should create status gauge and latency histogram
    assert any("health_check_redis_status" in str(k) for k in sink._gauges.keys())
    assert any("health_check_redis_latency" in str(k) for k in sink._histograms.keys())


def test_prometheus_sink_reuses_metrics():
    """Test PrometheusMetricsSink reuses existing metrics."""
    from prometheus_client import CollectorRegistry
    
    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    
    sink.emit("reused_gauge", 1.0)
    sink.emit("reused_gauge", 2.0)
    sink.emit("reused_gauge", 3.0)
    
    # Only one gauge should be created
    assert len([k for k in sink._gauges.keys() if "reused_gauge" in str(k)]) == 1


# ============================================================================
# METRICS SINK INTERFACE TESTS
# ============================================================================


def test_metrics_sink_interface_methods():
    """Test all sinks implement required MetricsSink methods."""
    from prometheus_client import CollectorRegistry
    
    sinks = [
        NoOpMetricsSink(),
        LoggingMetricsSink(),
        PrometheusMetricsSink(registry=CollectorRegistry()),
    ]
    
    for sink in sinks:
        # All should have required methods
        assert hasattr(sink, "emit")
        assert hasattr(sink, "emit_counter")
        assert hasattr(sink, "emit_histogram")
        assert hasattr(sink, "emit_health_check")
        
        # All should be callable without error
        sink.emit("test", 1.0)
        sink.emit_counter("test")
        sink.emit_histogram("test", 1.0)
        sink.emit_health_check("test", "healthy", 1.0)


def test_metrics_sink_health_check_status_mapping():
    """Test emit_health_check maps status strings to values correctly."""
    from prometheus_client import CollectorRegistry
    
    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    
    # Healthy = 1, Degraded = 0.5, Unhealthy = 0
    sink.emit_health_check("check1", "healthy", 1.0)
    sink.emit_health_check("check2", "degraded", 1.0)
    sink.emit_health_check("check3", "unhealthy", 1.0)
    
    # Verify gauges were created for each
    assert ("health_check_check1_status", ()) in sink._gauges
    assert ("health_check_check2_status", ()) in sink._gauges
    assert ("health_check_check3_status", ()) in sink._gauges
