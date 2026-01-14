#!/usr/bin/env python3
"""
Microbenchmarks for RecoveryOrchestrator

Benchmarks the recovery cycle evaluation and action selection.
Run with: pytest benchmarks/bench_orchestrator.py --benchmark-only
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.orchestration.recovery_orchestrator import (
    RecoveryOrchestrator,
    RecoveryConfig,
    RecoveryMetrics,
)


@pytest.fixture
def mock_health_monitor():
    """Create mock health monitor."""
    monitor = MagicMock()
    monitor.get_comprehensive_state = AsyncMock(return_value={
        "circuit_breaker": {"state": "CLOSED", "failure_count": 0},
        "retry": {"failures_1h": 0},
        "system": {"failed_components": 0},
        "components": {
            "anomaly_detector": {"healthy": True},
            "memory_store": {"healthy": True},
            "cache": {"healthy": True},
        },
    })
    return monitor


@pytest.fixture
def mock_fallback_manager():
    """Create mock fallback manager."""
    manager = MagicMock()
    manager.cascade = MagicMock(return_value="primary")
    manager.is_degraded = MagicMock(return_value=False)
    manager.is_safe_mode = MagicMock(return_value=False)
    return manager


@pytest.fixture
def mock_storage():
    """Create mock storage."""
    storage = MagicMock()
    storage.get = AsyncMock(return_value=None)
    storage.set = AsyncMock()
    storage.connect = AsyncMock()
    storage.close = AsyncMock()
    return storage


@pytest.fixture
def recovery_orchestrator(mock_health_monitor, mock_fallback_manager, mock_storage):
    """Create RecoveryOrchestrator with mocked dependencies."""
    return RecoveryOrchestrator(
        health_monitor=mock_health_monitor,
        fallback_manager=mock_fallback_manager,
        storage=mock_storage,
    )


def test_get_status(benchmark, recovery_orchestrator):
    """Benchmark status retrieval."""
    
    def get_status():
        return recovery_orchestrator.get_status()
    
    result = benchmark(get_status)
    assert "running" in result


def test_handle_event_healthy(benchmark, recovery_orchestrator):
    """Benchmark handling healthy event."""
    
    healthy_event = {
        "type": "health_update",
        "circuit_breaker": {"state": "CLOSED"},
        "system": {"failed_components": 0},
    }
    
    def handle_event():
        return asyncio.get_event_loop().run_until_complete(
            recovery_orchestrator.handle_event(healthy_event)
        )
    
    benchmark(handle_event)


def test_handle_event_degraded(benchmark, recovery_orchestrator):
    """Benchmark handling degraded event."""
    
    degraded_event = {
        "type": "health_update",
        "circuit_breaker": {"state": "OPEN", "failure_count": 5},
        "system": {"failed_components": 1},
    }
    
    def handle_event():
        return asyncio.get_event_loop().run_until_complete(
            recovery_orchestrator.handle_event(degraded_event)
        )
    
    benchmark(handle_event)


def test_recovery_metrics_tracking(benchmark):
    """Benchmark metrics tracking operations."""
    
    metrics = RecoveryMetrics()
    
    def track_metrics():
        metrics.total_actions_executed += 1
        metrics.successful_actions += 1
        metrics.actions_by_type["circuit_restart"] += 1
        return metrics.total_actions_executed
    
    result = benchmark(track_metrics)
    assert result > 0


def test_recovery_config_loading(benchmark):
    """Benchmark config loading and key access."""
    
    def load_and_access():
        config = RecoveryConfig()
        return (
            config.get("enabled"),
            config.get("poll_interval"),
            config.get("thresholds.circuit_open_duration"),
        )
    
    result = benchmark(load_and_access)
    assert result[0] is True  # enabled


def test_config_get_operations(benchmark):
    """Benchmark repeated config.get() operations."""
    
    config = RecoveryConfig()
    
    def get_multiple_values():
        values = []
        for key in ["enabled", "poll_interval", "thresholds.circuit_open_duration",
                    "thresholds.retry_failure_threshold", "thresholds.component_failure_count"]:
            values.append(config.get(key))
        return values
    
    result = benchmark(get_multiple_values)
    assert len(result) == 5


def test_get_cooldown_status(benchmark, recovery_orchestrator):
    """Benchmark cooldown status retrieval."""
    
    def get_cooldown():
        return recovery_orchestrator.get_cooldown_status()
    
    result = benchmark(get_cooldown)
    assert isinstance(result, dict)
