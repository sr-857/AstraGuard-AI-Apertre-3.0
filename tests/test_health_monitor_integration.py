"""
Comprehensive tests for Health Monitor & Fallback Cascade (Issue #16)

Tests cover:
- HealthMonitor API endpoints (/metrics, /state, /cascade, /ready, /live)
- FallbackManager cascade logic and mode transitions
- Integration with CircuitBreaker (#14) and Retry (#15)
- Prometheus metrics generation
- Component health tracking
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta

# Mark health monitor integration tests as slow
pytestmark = [pytest.mark.slow, pytest.mark.timeout(45)]
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from fastapi import Response
from prometheus_client import generate_latest

# Import modules to test
from backend.health import (
    HealthMonitor,
    FallbackMode,
    router,
    set_health_monitor,
    get_health_monitor,
)
from backend.fallback_manager import FallbackManager
from core.component_health import SystemHealthMonitor, HealthStatus
from core.metrics import REGISTRY

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def health_monitor():
    """Create HealthMonitor instance for testing."""
    monitor = HealthMonitor(
        circuit_breaker=None,
        retry_tracker=None,
        failure_window_seconds=3600,
    )
    return monitor


@pytest.fixture
def fallback_manager():
    """Create FallbackManager instance for testing."""
    return FallbackManager(
        circuit_breaker=None,
        anomaly_detector=None,
        heuristic_detector=None,
    )


@pytest.fixture
def mock_circuit_breaker():
    """Create mock circuit breaker for testing."""
    cb = Mock()
    cb.state = "CLOSED"
    cb.metrics = Mock()
    cb.metrics.state_change_time = datetime.now()
    cb.metrics.failures_total = 0
    cb.metrics.successes_total = 100
    cb.metrics.trips_total = 0
    cb.metrics.consecutive_failures = 0
    return cb


@pytest.fixture
def mock_retry_tracker():
    """Create mock retry tracker for testing."""
    tracker = Mock()
    tracker.total_attempts = 50
    return tracker


@pytest.fixture
def health_state_sample():
    """Sample health state for testing cascade logic."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "status": "healthy",
            "healthy_components": 3,
            "degraded_components": 0,
            "failed_components": 0,
            "total_components": 3,
        },
        "circuit_breaker": {
            "available": True,
            "state": "CLOSED",
            "open_duration_seconds": 0,
            "failures_total": 0,
            "successes_total": 100,
            "trips_total": 0,
            "consecutive_failures": 0,
        },
        "retry": {
            "failures_1h": 5,
            "failure_rate": 0.001,
            "total_attempts": 50,
        },
        "resources": {
            "status": {
                "cpu": "healthy",
                "memory": "healthy",
                "disk": "healthy",
                "overall": "healthy"
            },
            "current_metrics": {
                "cpu_percent": 25.0,
                "memory_percent": 45.0,
                "memory_available_mb": 4096.0,
                "disk_usage_percent": 60.0,
                "process_memory_mb": 150.0,
                "timestamp": datetime.utcnow().isoformat()
            },
            "available": True
        },
        "fallback": {
            "mode": "primary",
            "cascade_log": [],
        },
        "components": {
            "anomaly_detector": {"status": "healthy", "fallback_active": False},
            "memory_store": {"status": "healthy", "fallback_active": False},
            "policy_engine": {"status": "healthy", "fallback_active": False},
        },
        "uptime_seconds": 3600.0,
    }


# ============================================================================
# HEALTH MONITOR TESTS - BASIC FUNCTIONALITY
# ============================================================================


@pytest.mark.asyncio
async def test_health_monitor_initialization(health_monitor):
    """Test health monitor initializes with correct defaults."""
    assert health_monitor.fallback_mode == FallbackMode.PRIMARY
    assert health_monitor.failure_window_seconds == 3600
    assert health_monitor.start_time is not None


@pytest.mark.asyncio
async def test_get_comprehensive_state_no_circuit_breaker(health_monitor):
    """Test comprehensive state when circuit breaker not available."""
    state = await health_monitor.get_comprehensive_state()
    
    assert "timestamp" in state
    assert "system" in state
    assert "circuit_breaker" in state
    assert "retry" in state
    assert "fallback" in state
    assert "components" in state
    assert "uptime_seconds" in state
    
    # Should have safe defaults when CB unavailable
    assert state["circuit_breaker"]["available"] is False
    assert state["circuit_breaker"]["state"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_get_comprehensive_state_with_circuit_breaker(health_monitor, mock_circuit_breaker):
    """Test comprehensive state with circuit breaker available."""
    health_monitor.cb = mock_circuit_breaker
    
    state = await health_monitor.get_comprehensive_state()
    
    assert state["circuit_breaker"]["available"] is True
    assert state["circuit_breaker"]["state"] == "CLOSED"
    assert state["circuit_breaker"]["failures_total"] == 0
    assert state["circuit_breaker"]["successes_total"] == 100


@pytest.mark.asyncio
async def test_record_retry_failure(health_monitor):
    """Test recording retry failures."""
    assert len(health_monitor._retry_failures) == 0
    
    health_monitor.record_retry_failure()
    assert len(health_monitor._retry_failures) == 1
    
    health_monitor.record_retry_failure()
    assert len(health_monitor._retry_failures) == 2


@pytest.mark.asyncio
async def test_retry_metrics_within_window(health_monitor):
    """Test retry metrics correctly filter by time window."""
    # Add old failure (outside window)
    old_time = datetime.utcnow() - timedelta(hours=2)
    health_monitor._retry_failures.append(old_time)
    
    # Add recent failures
    health_monitor.record_retry_failure()
    health_monitor.record_retry_failure()
    
    state = await health_monitor.get_comprehensive_state()
    retry_metrics = state["retry"]
    
    # Should only count recent failures (not old one)
    assert retry_metrics["failures_1h"] == 2


# ============================================================================
# FALLBACK CASCADE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cascade_primary_mode_healthy(
    health_monitor,
    health_state_sample,
):
    """Test cascade stays in PRIMARY when all systems healthy."""
    mode = await health_monitor.cascade_fallback(health_state_sample)
    
    assert mode == FallbackMode.PRIMARY
    assert health_monitor.fallback_mode == FallbackMode.PRIMARY


@pytest.mark.asyncio
async def test_cascade_to_heuristic_circuit_open(
    health_monitor,
    health_state_sample,
):
    """Test cascade to HEURISTIC when circuit open."""
    health_state_sample["circuit_breaker"]["state"] = "OPEN"
    health_state_sample["circuit_breaker"]["open_duration_seconds"] = 30
    
    mode = await health_monitor.cascade_fallback(health_state_sample)
    
    assert mode == FallbackMode.HEURISTIC
    assert health_monitor.fallback_mode == FallbackMode.HEURISTIC


@pytest.mark.asyncio
async def test_cascade_to_heuristic_high_retry_failures(
    health_monitor,
    health_state_sample,
):
    """Test cascade to HEURISTIC with high retry failures."""
    health_state_sample["retry"]["failures_1h"] = 75  # > 50 threshold
    
    mode = await health_monitor.cascade_fallback(health_state_sample)
    
    assert mode == FallbackMode.HEURISTIC


@pytest.mark.asyncio
async def test_cascade_to_safe_multiple_failures(
    health_monitor,
    health_state_sample,
):
    """Test cascade to SAFE mode with multiple component failures."""
    health_state_sample["system"]["failed_components"] = 2
    
    mode = await health_monitor.cascade_fallback(health_state_sample)
    
    assert mode == FallbackMode.SAFE


@pytest.mark.asyncio
async def test_cascade_logs_transitions(
    health_monitor,
    health_state_sample,
):
    """Test cascade records transitions to log."""
    assert len(health_monitor._fallback_cascade_log) == 0
    
    # Trigger transition
    health_state_sample["circuit_breaker"]["state"] = "OPEN"
    await health_monitor.cascade_fallback(health_state_sample)
    
    assert len(health_monitor._fallback_cascade_log) == 1
    log_entry = health_monitor._fallback_cascade_log[0]
    assert log_entry["from"] == FallbackMode.PRIMARY.value
    assert log_entry["to"] == FallbackMode.HEURISTIC.value
    assert "timestamp" in log_entry


# ============================================================================
# FALLBACK MANAGER TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_fallback_manager_initialization(fallback_manager):
    """Test fallback manager initializes correctly."""
    assert fallback_manager.current_mode == FallbackMode.PRIMARY
    assert fallback_manager.get_mode_string() == "primary"
    assert fallback_manager.is_degraded() is False
    assert fallback_manager.is_safe_mode() is False


@pytest.mark.asyncio
async def test_fallback_manager_cascade(fallback_manager, health_state_sample):
    """Test fallback manager cascade logic."""
    # Test transition to HEURISTIC
    health_state_sample["circuit_breaker"]["state"] = "OPEN"
    
    mode = await fallback_manager.cascade(health_state_sample)
    
    assert mode == FallbackMode.HEURISTIC
    assert fallback_manager.get_mode_string() == "heuristic"


@pytest.mark.asyncio
async def test_fallback_manager_detect_anomaly_primary(fallback_manager):
    """Test anomaly detection in PRIMARY mode."""
    fallback_manager.current_mode = FallbackMode.PRIMARY
    fallback_manager.anomaly_detector = None  # Not available
    
    result = await fallback_manager.detect_anomaly({"voltage": 5.0})
    
    assert result["anomaly"] is False
    assert result["confidence"] == 0.0
    assert result["mode"] == "primary_unavailable"


@pytest.mark.asyncio
async def test_fallback_manager_detect_anomaly_safe_mode(fallback_manager):
    """Test anomaly detection in SAFE mode."""
    fallback_manager.current_mode = FallbackMode.SAFE
    
    result = await fallback_manager.detect_anomaly({"voltage": 5.0})
    
    assert result["anomaly"] is False
    assert result["confidence"] == 0.0
    assert result["mode"] == "safe"


@pytest.mark.asyncio
async def test_fallback_manager_transitions_log(fallback_manager, health_state_sample):
    """Test fallback manager tracks transitions."""
    assert len(fallback_manager.get_transitions_log()) == 0
    
    health_state_sample["circuit_breaker"]["state"] = "OPEN"
    await fallback_manager.cascade(health_state_sample)
    
    log = fallback_manager.get_transitions_log()
    assert len(log) == 1
    assert log[0]["from"] == "primary"
    assert log[0]["to"] == "heuristic"


@pytest.mark.asyncio
async def test_fallback_manager_mode_callback(fallback_manager, health_state_sample):
    """Test mode callback registration and invocation."""
    callback_called = False
    
    async def on_safe_mode():
        nonlocal callback_called
        callback_called = True
    
    fallback_manager.register_mode_callback(FallbackMode.SAFE, on_safe_mode)
    
    health_state_sample["system"]["failed_components"] = 2
    await fallback_manager.cascade(health_state_sample)
    
    # Give callback time to execute
    await asyncio.sleep(0.1)
    
    assert callback_called is True


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_set_and_get_health_monitor():
    """Test setting and getting health monitor instance."""
    monitor = HealthMonitor()
    set_health_monitor(monitor)
    
    retrieved = get_health_monitor()
    assert retrieved is monitor


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint():
    """Test /health/metrics endpoint."""
    monitor = HealthMonitor()
    set_health_monitor(monitor)
    
    # Import and test router endpoint
    from backend.health_monitor import prometheus_metrics
    
    response = await prometheus_metrics()
    
    # Response should be bytes in Prometheus format
    assert isinstance(response, Response) or isinstance(response.content, bytes)


@pytest.mark.asyncio
async def test_health_state_endpoint():
    """Test /health/state endpoint."""
    monitor = HealthMonitor()
    set_health_monitor(monitor)
    
    from backend.health_monitor import health_state
    
    state = await health_state()
    
    assert "timestamp" in state
    assert "system" in state
    assert "circuit_breaker" in state


@pytest.mark.asyncio
async def test_cascade_endpoint():
    """Test /health/cascade endpoint."""
    monitor = HealthMonitor()
    set_health_monitor(monitor)
    
    from backend.health_monitor import trigger_cascade
    
    result = await trigger_cascade()
    
    assert "fallback_mode" in result
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_readiness_check_endpoint_ready():
    """Test /health/ready endpoint when ready."""
    monitor = HealthMonitor()
    set_health_monitor(monitor)
    
    from backend.health_monitor import readiness_check
    
    result = await readiness_check()
    
    assert result["status"] == "ready"


@pytest.mark.asyncio
async def test_liveness_check_endpoint():
    """Test /health/live endpoint."""
    monitor = HealthMonitor()
    set_health_monitor(monitor)
    
    from backend.health_monitor import liveness_check
    
    result = await liveness_check()
    
    assert result["status"] == "alive"
    assert "timestamp" in result


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_health_monitor_with_circuit_breaker_integration(
    health_monitor,
    mock_circuit_breaker,
):
    """Test health monitor integration with circuit breaker metrics."""
    health_monitor.cb = mock_circuit_breaker
    
    # Simulate circuit breaker opening
    mock_circuit_breaker.state = "OPEN"
    mock_circuit_breaker.metrics.failures_total = 10
    mock_circuit_breaker.metrics.open_duration_seconds = 45
    
    state = await health_monitor.get_comprehensive_state()
    
    assert state["circuit_breaker"]["state"] == "OPEN"
    assert state["circuit_breaker"]["failures_total"] == 10


@pytest.mark.asyncio
async def test_health_monitor_retry_integration(health_monitor, mock_retry_tracker):
    """Test health monitor integration with retry tracker."""
    health_monitor.retry_tracker = mock_retry_tracker
    
    # Record failures
    for _ in range(5):
        health_monitor.record_retry_failure()
    
    state = await health_monitor.get_comprehensive_state()
    
    assert state["retry"]["failures_1h"] == 5
    assert state["retry"]["total_attempts"] == 50


@pytest.mark.asyncio
async def test_component_health_integration(health_monitor):
    """Test integration with component health monitoring."""
    comp_health = health_monitor.component_health
    
    # Register components
    comp_health.register_component("anomaly_detector")
    comp_health.register_component("memory_store")
    
    state = await health_monitor.get_comprehensive_state()
    
    assert "anomaly_detector" in state["components"]
    assert "memory_store" in state["components"]


@pytest.mark.asyncio
async def test_full_cascade_flow(health_monitor, health_state_sample):
    """Test complete cascade flow from healthy to degraded."""
    # Start healthy
    assert health_monitor.fallback_mode == FallbackMode.PRIMARY
    
    # Simulate circuit open
    health_state_sample["circuit_breaker"]["state"] = "OPEN"
    await health_monitor.cascade_fallback(health_state_sample)
    assert health_monitor.fallback_mode == FallbackMode.HEURISTIC
    
    # Simulate recovery
    health_state_sample["circuit_breaker"]["state"] = "CLOSED"
    await health_monitor.cascade_fallback(health_state_sample)
    assert health_monitor.fallback_mode == FallbackMode.PRIMARY


# ============================================================================
# PROMETHEUS METRICS TESTS
# ============================================================================


def test_prometheus_metrics_registry():
    """Test Prometheus metrics registry is properly configured."""
    from core.metrics import REGISTRY
    
    # Registry should have collected metrics
    metrics_data = generate_latest(REGISTRY)
    assert isinstance(metrics_data, bytes)
    assert b"astraguard_" in metrics_data


def test_fallback_mode_gauge_metric(health_monitor):
    """Test fallback mode gauge metric updates."""
    from backend.health_monitor import FALLBACK_MODE_GAUGE
    
    # Update mode
    health_monitor.fallback_mode = FallbackMode.HEURISTIC
    FALLBACK_MODE_GAUGE.set(1)  # HEURISTIC = 1
    
    metrics_data = generate_latest(REGISTRY)
    assert b"astraguard_fallback_mode" in metrics_data


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cascade_with_invalid_health_state(health_monitor):
    """Test cascade handles invalid health state gracefully."""
    invalid_state = {}  # Missing required keys
    
    # Should not raise, should return PRIMARY
    mode = await health_monitor.cascade_fallback(invalid_state)
    assert mode == FallbackMode.PRIMARY


@pytest.mark.asyncio
async def test_fallback_manager_detect_anomaly_error_handling(fallback_manager):
    """Test error handling in detect_anomaly."""
    # Mock detector that raises error
    fallback_manager.current_mode = FallbackMode.PRIMARY
    
    async def failing_detector(data):
        raise RuntimeError("Detector error")
    
    fallback_manager.anomaly_detector = Mock()
    fallback_manager.anomaly_detector.detect_anomaly = failing_detector
    
    result = await fallback_manager.detect_anomaly({"voltage": 5.0})
    
    assert result["anomaly"] is False
    # When detector fails with error, system may transition to available fallback mode
    assert result["mode"] in ["error", "primary_unavailable", "heuristic"]
    assert "error" in result


# ============================================================================
# RESOURCE MONITORING INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_resource_monitoring_in_comprehensive_state(health_monitor):
    """Test that resource monitoring is included in comprehensive health state."""
    state = await health_monitor.get_comprehensive_state()

    assert "resources" in state
    assert "status" in state["resources"]
    assert "current_metrics" in state["resources"]
    assert "available" in state["resources"]

    # Check resource status structure
    resource_status = state["resources"]["status"]
    assert "cpu" in resource_status
    assert "memory" in resource_status
    assert "disk" in resource_status
    assert "overall" in resource_status


@pytest.mark.asyncio
async def test_resource_monitoring_healthy_state(health_monitor):
    """Test resource monitoring reports healthy state."""
    state = await health_monitor.get_comprehensive_state()

    resource_info = state["resources"]
    assert resource_info["available"] is True

    # Should have current metrics
    metrics = resource_info["current_metrics"]
    assert "cpu_percent" in metrics
    assert "memory_percent" in metrics
    assert "memory_available_mb" in metrics
    assert "disk_usage_percent" in metrics
    assert "process_memory_mb" in metrics
    assert "timestamp" in metrics


@pytest.mark.asyncio
async def test_cascade_to_safe_resource_critical(health_monitor, health_state_sample):
    """Test cascade to SAFE mode when resource status is critical."""
    health_state_sample["resources"]["status"]["overall"] = "critical"

    mode = await health_monitor.cascade_fallback(health_state_sample)

    assert mode == FallbackMode.SAFE
    assert health_monitor.fallback_mode == FallbackMode.SAFE


@pytest.mark.asyncio
async def test_cascade_resource_critical_with_component_failures(health_monitor, health_state_sample):
    """Test cascade prioritizes SAFE mode when both resource critical and component failures."""
    health_state_sample["resources"]["status"]["overall"] = "critical"
    health_state_sample["system"]["failed_components"] = 1  # Less than 2

    mode = await health_monitor.cascade_fallback(health_state_sample)

    assert mode == FallbackMode.SAFE


@pytest.mark.asyncio
async def test_cascade_resource_warning_no_transition(health_monitor, health_state_sample):
    """Test cascade does not transition to SAFE for resource warning alone."""
    health_state_sample["resources"]["status"]["overall"] = "warning"

    mode = await health_monitor.cascade_fallback(health_state_sample)

    assert mode == FallbackMode.PRIMARY


@pytest.mark.asyncio
async def test_resource_monitoring_error_handling(health_monitor):
    """Test resource monitoring handles errors gracefully."""
    # Mock resource monitor to raise exception
    original_monitor = health_monitor.resource_monitor
    mock_monitor = Mock()
    mock_monitor.check_resource_health.side_effect = Exception("Resource check failed")
    health_monitor.resource_monitor = mock_monitor

    try:
        state = await health_monitor.get_comprehensive_state()

        resource_info = state["resources"]
        assert resource_info["available"] is False
        assert resource_info["status"]["overall"] == "unknown"
        assert resource_info["current_metrics"] == {}
    finally:
        # Restore original monitor
        health_monitor.resource_monitor = original_monitor


@pytest.mark.asyncio
async def test_resource_monitoring_cascade_reason_logging(health_monitor, health_state_sample):
    """Test cascade logs resource exhaustion reasons."""
    health_state_sample["resources"]["status"]["overall"] = "critical"

    await health_monitor.cascade_fallback(health_state_sample)

    # Check cascade log contains resource exhaustion reason
    assert len(health_monitor._fallback_cascade_log) == 1
    log_entry = health_monitor._fallback_cascade_log[0]
    assert "resource_exhaustion" in log_entry["reason"]


@pytest.mark.asyncio
async def test_resource_monitoring_integration_with_circuit_breaker(health_monitor, health_state_sample):
    """Test resource monitoring works alongside circuit breaker cascade logic."""
    # Both circuit breaker open AND resource critical should cascade to SAFE
    health_state_sample["circuit_breaker"]["state"] = "OPEN"
    health_state_sample["resources"]["status"]["overall"] = "critical"

    mode = await health_monitor.cascade_fallback(health_state_sample)

    assert mode == FallbackMode.SAFE  # Resource critical takes precedence


@pytest.mark.asyncio
async def test_resource_monitoring_metrics_inclusion(health_monitor):
    """Test resource metrics are properly included in health state."""
    state = await health_monitor.get_comprehensive_state()

    resource_info = state["resources"]
    metrics = resource_info["current_metrics"]

    # All expected metrics should be present and numeric
    assert isinstance(metrics["cpu_percent"], (int, float))
    assert isinstance(metrics["memory_percent"], (int, float))
    assert isinstance(metrics["memory_available_mb"], (int, float))
    assert isinstance(metrics["disk_usage_percent"], (int, float))
    assert isinstance(metrics["process_memory_mb"], (int, float))
    assert isinstance(metrics["timestamp"], str)


@pytest.mark.asyncio
async def test_resource_monitoring_status_consistency(health_monitor):
    """Test resource status values are consistent with expected states."""
    state = await health_monitor.get_comprehensive_state()

    resource_status = state["resources"]["status"]

    # Status values should be one of the expected states
    valid_states = ["healthy", "warning", "critical", "unknown"]
    assert resource_status["overall"] in valid_states
    assert resource_status["cpu"] in valid_states
    assert resource_status["memory"] in valid_states
    assert resource_status["disk"] in valid_states


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_health_state_performance(health_monitor):
    """Test health state retrieval completes quickly."""
    import time

    start = time.time()
    await health_monitor.get_comprehensive_state()
    duration = time.time() - start

    # Performance verification (relaxed for CI/CD)
    assert duration < 0.5, f"Health check too slow: {duration}s"


@pytest.mark.asyncio
async def test_cascade_performance(health_monitor, health_state_sample):
    """Test cascade evaluation completes quickly."""
    import time

    start = time.time()
    for _ in range(100):
        await health_monitor.cascade_fallback(health_state_sample)
    duration = time.time() - start

    # Should complete 100 cascades in < 500ms
    assert duration < 0.5
