"""
Tests for HealthMonitor with new abstractions.

Tests cover:
- MetricsSink injection
- HealthCheck registration and execution
- Backward compatibility
- Integration with existing functionality
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from backend.health.monitor import (
    HealthMonitor,
    FallbackMode,
    set_health_monitor,
    get_health_monitor,
)
from backend.health.checks import (
    HealthCheck,
    HealthCheckResult,
    HealthCheckStatus,
    BaseHealthCheck,
)
from backend.health.sinks import NoOpMetricsSink, LoggingMetricsSink


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def noop_sink():
    """Create NoOpMetricsSink for testing."""
    return NoOpMetricsSink()


@pytest.fixture
def health_monitor(noop_sink):
    """Create HealthMonitor with NoOpMetricsSink."""
    return HealthMonitor(
        circuit_breaker=None,
        retry_tracker=None,
        failure_window_seconds=3600,
        metrics_sink=noop_sink,
    )


@pytest.fixture
def mock_health_check():
    """Create a mock health check."""
    class MockCheck(BaseHealthCheck):
        def __init__(self):
            super().__init__("mock_check")
            self.call_count = 0
        
        async def _perform_check(self):
            self.call_count += 1
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.HEALTHY,
                message="Mock check passed",
            )
    
    return MockCheck()


# ============================================================================
# METRICS SINK INJECTION TESTS
# ============================================================================


def test_health_monitor_accepts_metrics_sink(noop_sink):
    """Test HealthMonitor accepts metrics_sink parameter."""
    monitor = HealthMonitor(metrics_sink=noop_sink)
    
    assert monitor.metrics_sink is noop_sink


def test_health_monitor_defaults_to_noop_sink():
    """Test HealthMonitor defaults to NoOpMetricsSink when not provided."""
    monitor = HealthMonitor()
    
    assert isinstance(monitor.metrics_sink, NoOpMetricsSink)


def test_health_monitor_uses_custom_sink():
    """Test HealthMonitor uses provided custom sink."""
    sink = LoggingMetricsSink()
    monitor = HealthMonitor(metrics_sink=sink)
    
    assert monitor.metrics_sink is sink


# ============================================================================
# HEALTH CHECK REGISTRATION TESTS
# ============================================================================


def test_register_check(health_monitor, mock_health_check):
    """Test registering a health check."""
    health_monitor.register_check(mock_health_check)
    
    assert "mock_check" in health_monitor._health_checks


def test_unregister_check(health_monitor, mock_health_check):
    """Test unregistering a health check."""
    health_monitor.register_check(mock_health_check)
    health_monitor.unregister_check("mock_check")
    
    assert "mock_check" not in health_monitor._health_checks


def test_unregister_nonexistent_check(health_monitor):
    """Test unregistering a check that doesn't exist doesn't raise."""
    # Should not raise
    health_monitor.unregister_check("nonexistent")


@pytest.mark.asyncio
async def test_run_checks_executes_all(health_monitor, mock_health_check):
    """Test run_checks executes all registered checks."""
    health_monitor.register_check(mock_health_check)
    
    results = await health_monitor.run_checks()
    
    assert "mock_check" in results
    assert results["mock_check"].status == HealthCheckStatus.HEALTHY
    assert mock_health_check.call_count == 1


@pytest.mark.asyncio
async def test_run_checks_handles_errors(health_monitor):
    """Test run_checks handles check errors gracefully."""
    
    class FailingCheck(BaseHealthCheck):
        def __init__(self):
            super().__init__("failing")
        
        async def _perform_check(self):
            raise RuntimeError("Check failed!")
    
    health_monitor.register_check(FailingCheck())
    
    results = await health_monitor.run_checks()
    
    assert "failing" in results
    assert results["failing"].status == HealthCheckStatus.UNHEALTHY


# ============================================================================
# COMPREHENSIVE STATE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_comprehensive_state_includes_health_checks(health_monitor, mock_health_check):
    """Test get_comprehensive_state includes health check results."""
    health_monitor.register_check(mock_health_check)
    
    state = await health_monitor.get_comprehensive_state()
    
    assert "health_checks" in state
    assert "mock_check" in state["health_checks"]
    assert state["health_checks"]["mock_check"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_comprehensive_state_emits_metrics(health_monitor):
    """Test get_comprehensive_state emits metrics via sink."""
    sink = Mock(spec=NoOpMetricsSink)
    sink.emit = Mock()
    sink.emit_health_check = Mock()
    health_monitor.metrics_sink = sink
    
    await health_monitor.get_comprehensive_state()
    
    # Should emit duration metric
    sink.emit.assert_called()


# ============================================================================
# BACKWARD COMPATIBILITY TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_backward_compatible_init():
    """Test HealthMonitor works with old-style initialization."""
    # Old style without metrics_sink
    monitor = HealthMonitor(
        circuit_breaker=None,
        retry_tracker=None,
        failure_window_seconds=3600,
    )
    
    assert monitor.fallback_mode == FallbackMode.PRIMARY
    assert isinstance(monitor.metrics_sink, NoOpMetricsSink)


@pytest.mark.asyncio
async def test_backward_compatible_comprehensive_state():
    """Test get_comprehensive_state returns expected structure."""
    monitor = HealthMonitor()
    
    state = await monitor.get_comprehensive_state()
    
    # Should have all expected keys
    assert "timestamp" in state
    assert "system" in state
    assert "circuit_breaker" in state
    assert "retry" in state
    assert "resources" in state
    assert "fallback" in state
    assert "components" in state
    assert "uptime_seconds" in state


@pytest.mark.asyncio
async def test_cascade_emits_metrics():
    """Test cascade_fallback emits metrics via sink."""
    sink = Mock(spec=NoOpMetricsSink)
    sink.emit = Mock()
    sink.emit_counter = Mock()
    
    monitor = HealthMonitor(metrics_sink=sink)
    
    # Trigger cascade that changes mode
    state = {
        "circuit_breaker": {"state": "OPEN"},
        "retry": {"failures_1h": 0},
        "system": {"failed_components": 0},
        "resources": {"status": {"overall": "healthy"}},
    }
    
    await monitor.cascade_fallback(state)
    
    # Should emit transition counter and mode gauge
    assert sink.emit_counter.called or sink.emit.called


# ============================================================================
# RECORD RETRY FAILURE TESTS
# ============================================================================


def test_record_retry_failure_emits_counter(health_monitor):
    """Test record_retry_failure emits counter via sink."""
    sink = Mock(spec=NoOpMetricsSink)
    sink.emit_counter = Mock()
    health_monitor.metrics_sink = sink
    
    health_monitor.record_retry_failure()
    
    sink.emit_counter.assert_called_with("retry_failures_total")


# ============================================================================
# GLOBAL INSTANCE TESTS
# ============================================================================


def test_set_and_get_health_monitor():
    """Test setting and getting global health monitor instance."""
    monitor = HealthMonitor()
    set_health_monitor(monitor)
    
    retrieved = get_health_monitor()
    
    assert retrieved is monitor


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_full_integration_flow():
    """Test complete flow with checks, sink, and state retrieval."""
    from prometheus_client import CollectorRegistry
    from backend.health.sinks import PrometheusMetricsSink
    
    # Create monitor with Prometheus sink
    registry = CollectorRegistry()
    sink = PrometheusMetricsSink(registry=registry)
    monitor = HealthMonitor(metrics_sink=sink)
    
    # Register a check
    class SimpleCheck(BaseHealthCheck):
        def __init__(self):
            super().__init__("simple")
        
        async def _perform_check(self):
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.HEALTHY,
            )
    
    monitor.register_check(SimpleCheck())
    
    # Get state
    state = await monitor.get_comprehensive_state()
    
    # Verify
    assert state["health_checks"]["simple"]["status"] == "healthy"
    assert ("health_check_simple_status", ()) in sink._gauges


@pytest.mark.asyncio
async def test_cascade_with_checks():
    """Test cascade considers health check results."""
    monitor = HealthMonitor()
    
    # Get initial state
    initial_mode = await monitor.cascade_fallback()
    
    assert initial_mode == FallbackMode.PRIMARY


@pytest.mark.asyncio
async def test_multiple_checks_aggregation():
    """Test running multiple health checks."""
    monitor = HealthMonitor()
    
    class Check1(BaseHealthCheck):
        def __init__(self):
            super().__init__("check1")
        
        async def _perform_check(self):
            return HealthCheckResult(name=self.name, status=HealthCheckStatus.HEALTHY)
    
    class Check2(BaseHealthCheck):
        def __init__(self):
            super().__init__("check2")
        
        async def _perform_check(self):
            return HealthCheckResult(name=self.name, status=HealthCheckStatus.DEGRADED)
    
    monitor.register_check(Check1())
    monitor.register_check(Check2())
    
    results = await monitor.run_checks()
    
    assert len(results) == 2
    assert results["check1"].status == HealthCheckStatus.HEALTHY
    assert results["check2"].status == HealthCheckStatus.DEGRADED
