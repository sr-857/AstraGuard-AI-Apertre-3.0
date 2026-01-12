"""
Race Condition Test for Health Monitor State Inconsistency

Tests concurrent access to health monitor components to reproduce
the race condition where components appear healthy but are actually failing.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List
import pytest

from core.component_health import SystemHealthMonitor, HealthStatus
from backend.health_monitor import HealthMonitor, FallbackMode


def test_concurrent_component_updates():
    """Test concurrent component status updates that can cause race conditions."""
    monitor = SystemHealthMonitor()
    monitor.reset()  # Ensure clean state

    # Register test components
    components = ["api_server", "database", "cache", "worker"]

    def rapid_status_updates(component: str, iterations: int = 100):
        """Simulate rapid status changes for a component."""
        for i in range(iterations):
            # Simulate component going through states rapidly
            monitor.mark_healthy(component)
            monitor.mark_degraded(component, f"temp error {i}")
            monitor.mark_failed(component, f"critical error {i}")
            monitor.mark_healthy(component)  # Back to healthy

    # Run concurrent updates
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for comp in components:
            future = executor.submit(rapid_status_updates, comp, 50)
            futures.append(future)

        # Wait for all updates to complete
        for future in futures:
            future.result()

    # Check final state - should be consistent
    status = monitor.get_system_status()

    # All components should be healthy at the end
    assert status["component_counts"]["healthy"] == len(components)
    assert status["component_counts"]["failed"] == 0
    assert status["component_counts"]["degraded"] == 0

    print("✓ Concurrent component updates completed without inconsistency")


def test_health_monitor_cascade_race():
    """Test race condition in cascade_fallback method."""
    # Create monitor with minimal dependencies to avoid secrets initialization
    from unittest.mock import MagicMock
    monitor = HealthMonitor()
    monitor.resource_monitor = MagicMock()
    monitor.resource_monitor.check_resource_health.return_value = {"overall": "healthy"}
    monitor.resource_monitor.get_current_metrics.return_value = MagicMock()
    monitor.resource_monitor.get_current_metrics.return_value.to_dict.return_value = {}

    def trigger_cascades(iterations: int = 50):
        """Trigger cascade evaluations rapidly."""
        for i in range(iterations):
            asyncio.run(monitor.cascade_fallback())

    def update_components(iterations: int = 50):
        """Update component health rapidly."""
        for i in range(iterations):
            monitor.component_health.mark_failed("test_component", f"error {i}")
            monitor.component_health.mark_healthy("test_component")

    # Run both operations concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        cascade_future = executor.submit(trigger_cascades, 30)
        update_future = executor.submit(update_components, 30)

        cascade_future.result()
        update_future.result()

    # Verify final state is consistent
    state = asyncio.run(monitor.get_comprehensive_state())

    # Should not be in inconsistent state
    fallback_mode = state["fallback"]["mode"]
    failed_components = state["system"]["failed_components"]

    # If in safe mode, should have failed components
    if fallback_mode == FallbackMode.SAFE.value:
        assert failed_components >= 2, "Safe mode should require multiple failures"

    print("✓ Cascade race condition test completed")


def test_concurrent_health_checks():
    """Test concurrent health state queries during updates."""
    monitor = HealthMonitor()

    results = []

    def health_checks(iterations: int = 20):
        """Perform health checks concurrently."""
        for i in range(iterations):
            try:
                state = asyncio.run(monitor.get_comprehensive_state())
                results.append(state)
            except Exception as e:
                results.append(f"error: {e}")

    def component_failures(iterations: int = 20):
        """Simulate component failures during health checks."""
        for i in range(iterations):
            monitor.component_health.mark_failed("network", f"timeout {i}")
            time.sleep(0.01)  # Small delay to increase race window
            monitor.component_health.mark_healthy("network")

    # Run concurrent operations
    with ThreadPoolExecutor(max_workers=2) as executor:
        check_future = executor.submit(health_checks, 15)
        fail_future = executor.submit(component_failures, 15)

        check_future.result()
        fail_future.result()

    # Verify no errors occurred
    errors = [r for r in results if isinstance(r, str) and r.startswith("error")]
    assert len(errors) == 0, f"Health check errors: {errors}"

    print("✓ Concurrent health checks completed successfully")


if __name__ == "__main__":
    print("Running race condition tests...")

    test_concurrent_component_updates()
    test_health_monitor_cascade_race()
    test_concurrent_health_checks()

    print("All race condition tests passed!")
