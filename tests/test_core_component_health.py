"""
Unit tests for core/component_health.py

Tests health status monitoring, component registration, status updates,
and system-level health aggregation.
"""

import pytest
import time
from datetime import datetime
from unittest.mock import patch

from core.component_health import (
    HealthStatus,
    ComponentHealth,
    SystemHealthMonitor,
    get_health_monitor,
)


class TestHealthStatus:
    """Test HealthStatus enum"""

    def test_health_status_values(self):
        """Test all health status values"""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.FAILED.value == "failed"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestComponentHealth:
    """Test ComponentHealth dataclass"""

    def test_initialization(self):
        """Test ComponentHealth initialization"""
        health = ComponentHealth(
            name="test_component",
            status=HealthStatus.HEALTHY,
            last_updated=datetime.now(),
            error_count=2,
            warning_count=1,
            last_error="Test error",
            fallback_active=True,
            metadata={"version": "1.0"}
        )

        assert health.name == "test_component"
        assert health.status == HealthStatus.HEALTHY
        assert health.error_count == 2
        assert health.warning_count == 1
        assert health.last_error == "Test error"
        assert health.fallback_active is True
        assert health.metadata == {"version": "1.0"}

    def test_default_values(self):
        """Test ComponentHealth default values"""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            last_updated=datetime.now()
        )

        assert health.error_count == 0
        assert health.warning_count == 0
        assert health.last_error is None
        assert health.last_error_time is None
        assert health.fallback_active is False
        assert health.metadata is None

    def test_to_dict(self):
        """Test ComponentHealth to_dict method"""
        timestamp = datetime.now()
        health = ComponentHealth(
            name="test",
            status=HealthStatus.DEGRADED,
            last_updated=timestamp,
            error_count=1,
            last_error="Error message",
            last_error_time=timestamp,
            metadata={"key": "value"}
        )

        data = health.to_dict()
        assert data["name"] == "test"
        assert data["status"] == "degraded"
        assert data["error_count"] == 1
        assert data["warning_count"] == 0
        assert data["last_error"] == "Error message"
        assert data["fallback_active"] is False
        assert data["metadata"] == {"key": "value"}
        assert "last_updated" in data
        assert "last_error_time" in data


class TestSystemHealthMonitor:
    """Test SystemHealthMonitor singleton"""

    @pytest.fixture
    def monitor(self):
        """Create a fresh health monitor for testing"""
        # Reset singleton for clean testing
        SystemHealthMonitor._instance = None
        monitor = SystemHealthMonitor()
        yield monitor
        # Cleanup after test
        monitor.reset()

    def test_singleton_pattern(self):
        """Test that SystemHealthMonitor is a singleton"""
        # Reset singleton
        SystemHealthMonitor._instance = None

        monitor1 = SystemHealthMonitor()
        monitor2 = SystemHealthMonitor()

        assert monitor1 is monitor2

    def test_initialization(self, monitor):
        """Test monitor initialization"""
        assert monitor._system_status == HealthStatus.HEALTHY
        assert len(monitor._components) == 0

    def test_register_component(self, monitor):
        """Test component registration"""
        metadata = {"version": "1.0", "type": "anomaly_detector"}

        monitor.register_component("anomaly_detector", metadata)

        assert "anomaly_detector" in monitor._components
        health = monitor._components["anomaly_detector"]
        assert health.name == "anomaly_detector"
        assert health.status == HealthStatus.HEALTHY
        assert health.metadata == metadata

    def test_mark_healthy(self, monitor):
        """Test marking component as healthy"""
        # First register and mark as failed
        monitor.register_component("test_comp")
        monitor.mark_failed("test_comp", "Test failure")

        # Then mark as healthy
        metadata = {"recovered": True}
        monitor.mark_healthy("test_comp", metadata)

        health = monitor._components["test_comp"]
        assert health.status == HealthStatus.HEALTHY
        assert health.fallback_active is False
        assert health.metadata["recovered"] is True

    def test_mark_degraded(self, monitor):
        """Test marking component as degraded"""
        monitor.register_component("test_comp")

        monitor.mark_degraded("test_comp", "Performance issue", fallback_active=True)

        health = monitor._components["test_comp"]
        assert health.status == HealthStatus.DEGRADED
        assert health.warning_count == 1
        assert health.last_error == "Performance issue"
        assert health.fallback_active is True
        assert health.last_error_time is not None

    def test_mark_failed(self, monitor):
        """Test marking component as failed"""
        monitor.register_component("test_comp")

        monitor.mark_failed("test_comp", "Critical error")

        health = monitor._components["test_comp"]
        assert health.status == HealthStatus.FAILED
        assert health.error_count == 1
        assert health.last_error == "Critical error"
        assert health.last_error_time is not None

    def test_auto_registration_on_status_change(self, monitor):
        """Test that status changes auto-register unknown components"""
        # Mark healthy without prior registration
        monitor.mark_healthy("auto_registered")

        assert "auto_registered" in monitor._components
        health = monitor._components["auto_registered"]
        assert health.status == HealthStatus.HEALTHY

    def test_system_status_aggregation_healthy(self, monitor):
        """Test system status when all components are healthy"""
        monitor.register_component("comp1")
        monitor.register_component("comp2")

        monitor.mark_healthy("comp1")
        monitor.mark_healthy("comp2")

        assert monitor._system_status == HealthStatus.HEALTHY
        assert monitor.is_system_healthy()
        assert not monitor.is_system_degraded()

    def test_system_status_aggregation_degraded(self, monitor):
        """Test system status when some components are degraded"""
        monitor.register_component("comp1")
        monitor.register_component("comp2")

        monitor.mark_healthy("comp1")
        monitor.mark_degraded("comp2")

        assert monitor._system_status == HealthStatus.DEGRADED
        assert not monitor.is_system_healthy()
        assert monitor.is_system_degraded()

    def test_system_status_aggregation_failed(self, monitor):
        """Test system status when some components are failed"""
        monitor.register_component("comp1")
        monitor.register_component("comp2")

        monitor.mark_healthy("comp1")
        monitor.mark_failed("comp2")

        assert monitor._system_status == HealthStatus.FAILED  # System is FAILED if critical component fails
        assert not monitor.is_system_healthy()
        assert not monitor.is_system_degraded()  # Should be FAILED, not DEGRADED

    def test_system_status_empty_components(self, monitor):
        """Test system status with no components"""
        # Reset to clear any components
        monitor.reset()
        assert monitor._system_status == HealthStatus.HEALTHY  # Default when no components

    def test_get_component_health_auto_register(self, monitor):
        """Test get_component_health auto-registers unknown components"""
        health = monitor.get_component_health("unknown_comp")

        assert health.name == "unknown_comp"
        assert health.status == HealthStatus.UNKNOWN
        assert "unknown_comp" in monitor._components

    def test_get_component_health_existing(self, monitor):
        """Test get_component_health for existing components"""
        monitor.register_component("existing_comp")
        monitor.mark_failed("existing_comp", "Error")

        health = monitor.get_component_health("existing_comp")

        assert health.name == "existing_comp"
        assert health.status == HealthStatus.FAILED
        assert health.last_error == "Error"

    def test_get_all_health(self, monitor):
        """Test get_all_health returns all components"""
        monitor.register_component("comp1")
        monitor.register_component("comp2")
        monitor.mark_healthy("comp1")
        monitor.mark_degraded("comp2")

        all_health = monitor.get_all_health()

        assert len(all_health) == 2
        assert all_health["comp1"]["status"] == "healthy"
        assert all_health["comp2"]["status"] == "degraded"

    def test_get_system_status(self, monitor):
        """Test get_system_status returns comprehensive info"""
        monitor.register_component("comp1")
        monitor.register_component("comp2")
        monitor.register_component("comp3")

        monitor.mark_healthy("comp1")
        monitor.mark_degraded("comp2")
        monitor.mark_failed("comp3")

        status = monitor.get_system_status()

        assert status["overall_status"] == "failed"
        assert "timestamp" in status
        assert status["component_counts"]["healthy"] == 1
        assert status["component_counts"]["degraded"] == 1
        assert status["component_counts"]["failed"] == 1
        assert status["component_counts"]["total"] == 3
        assert len(status["components"]) == 3

    def test_reset_functionality(self, monitor):
        """Test reset clears all state"""
        monitor.register_component("comp1")
        monitor.mark_failed("comp1")

        monitor.reset()

        # Should be able to create new instance
        new_monitor = SystemHealthMonitor()
        assert new_monitor is not monitor
        assert len(new_monitor._components) == 0
        assert new_monitor._system_status == HealthStatus.HEALTHY

    def test_thread_safety(self, monitor):
        """Test that operations are thread-safe"""
        import threading
        import time

        results = []
        errors = []

        def worker(component_name):
            try:
                monitor.register_component(component_name)
                time.sleep(0.01)  # Small delay to increase chance of race conditions
                monitor.mark_healthy(component_name)
                results.append(component_name)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(f"comp{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert len(monitor._components) == 10


class TestGlobalFunctions:
    """Test global health monitor functions"""

    def test_get_health_monitor_singleton(self):
        """Test get_health_monitor returns singleton"""
        # Reset global state
        import core.component_health
        core.component_health._health_monitor = None
        SystemHealthMonitor._instance = None

        monitor1 = get_health_monitor()
        monitor2 = get_health_monitor()

        assert monitor1 is monitor2
        assert isinstance(monitor1, SystemHealthMonitor)

    def test_get_health_monitor_persistence(self):
        """Test get_health_monitor persists across calls"""
        # Reset global state
        import core.component_health
        core.component_health._health_monitor = None

        monitor = get_health_monitor()
        monitor.register_component("test")

        # Get again
        monitor2 = get_health_monitor()
        assert monitor2 is monitor
        assert "test" in monitor2._components


class TestIntegrationScenarios:
    """Test realistic integration scenarios"""

    @pytest.fixture
    def monitor(self):
        """Create fresh monitor for integration tests"""
        SystemHealthMonitor._instance = None
        monitor = SystemHealthMonitor()
        yield monitor
        monitor.reset()

    def test_anomaly_detector_lifecycle(self, monitor):
        """Test typical anomaly detector health lifecycle"""
        # Initial registration
        monitor.register_component("anomaly_detector", {"version": "2.1.0"})

        # Normal operation
        monitor.mark_healthy("anomaly_detector", {"accuracy": 0.95})

        # Performance degradation
        monitor.mark_degraded("anomaly_detector",
                             "High latency detected",
                             fallback_active=True,
                             metadata={"latency_ms": 150})

        # Recovery
        monitor.mark_healthy("anomaly_detector", {"latency_ms": 45})

        # Check final state
        health = monitor.get_component_health("anomaly_detector")
        assert health.status == HealthStatus.HEALTHY
        assert health.warning_count == 1
        assert health.fallback_active is False
        assert health.metadata["latency_ms"] == 45

    def test_system_wide_failure_scenario(self, monitor):
        """Test system behavior during widespread component failures"""
        components = ["anomaly_detector", "state_machine", "memory_engine", "api_server"]

        # Register all components
        for comp in components:
            monitor.register_component(comp)

        # All start healthy
        for comp in components:
            monitor.mark_healthy(comp)
        assert monitor.is_system_healthy()

        # Multiple components fail
        monitor.mark_failed("anomaly_detector", "Model corruption")
        monitor.mark_failed("memory_engine", "Out of memory")
        monitor.mark_degraded("api_server", "High error rate")

        # System should be FAILED (anomaly_detector and memory_engine are critical)
        assert not monitor.is_system_degraded()
        assert not monitor.is_system_healthy()
        assert monitor._system_status == HealthStatus.FAILED

        # Check system status details
        status = monitor.get_system_status()
        assert status["component_counts"]["failed"] == 2
        assert status["component_counts"]["degraded"] == 1
        assert status["component_counts"]["healthy"] == 1

    def test_health_monitor_logging(self, monitor):
        """Test that health changes are logged appropriately"""
        monitor.register_component("test_comp")

        with patch('core.component_health.logger') as mock_logger:
            monitor.mark_failed("test_comp", "Test failure")
            mock_logger.error.assert_called_once()

            monitor.mark_degraded("test_comp", "Test degradation")
            mock_logger.warning.assert_called_once()

            monitor.mark_healthy("test_comp")
            mock_logger.debug.assert_called()  # Healthy changes are debug level
