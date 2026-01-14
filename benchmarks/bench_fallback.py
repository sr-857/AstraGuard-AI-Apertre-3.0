#!/usr/bin/env python3
"""
Microbenchmarks for FallbackManager

Benchmarks the cascade decision logic and mode transitions.
Run with: pytest benchmarks/bench_fallback.py --benchmark-only
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.fallback.manager import FallbackManager, FallbackMode
from backend.storage import MemoryStorage


@pytest.fixture
def memory_storage():
    """Create in-memory storage for tests."""
    return MemoryStorage()


@pytest.fixture
def fallback_manager(memory_storage):
    """Create FallbackManager with in-memory storage."""
    return FallbackManager(storage=memory_storage)


# Health states for different scenarios
HEALTHY_STATE = {
    "circuit_breaker": {"state": "CLOSED", "failure_count": 0},
    "retry": {"failures_1h": 0},
    "system": {"failed_components": 0},
}

DEGRADED_STATE = {
    "circuit_breaker": {"state": "OPEN", "failure_count": 5},
    "retry": {"failures_1h": 10},
    "system": {"failed_components": 1},
}

CRITICAL_STATE = {
    "circuit_breaker": {"state": "OPEN", "failure_count": 10},
    "retry": {"failures_1h": 50},
    "system": {"failed_components": 2},
}


def test_cascade_healthy_state(benchmark, fallback_manager):
    """Benchmark cascade evaluation with healthy system state."""
    
    def cascade_healthy():
        return fallback_manager.cascade(HEALTHY_STATE)
    
    result = benchmark(cascade_healthy)
    assert result == FallbackMode.PRIMARY


def test_cascade_degraded_state(benchmark, fallback_manager):
    """Benchmark cascade evaluation transitioning to HEURISTIC mode."""
    
    def cascade_degraded():
        return fallback_manager.cascade(DEGRADED_STATE)
    
    result = benchmark(cascade_degraded)
    assert result == FallbackMode.HEURISTIC


def test_cascade_critical_state(benchmark, fallback_manager):
    """Benchmark cascade evaluation transitioning to SAFE mode."""
    
    def cascade_critical():
        return fallback_manager.cascade(CRITICAL_STATE)
    
    result = benchmark(cascade_critical)
    assert result == FallbackMode.SAFE


def test_cascade_mode_transition_cycle(benchmark, fallback_manager):
    """Benchmark full mode transition cycle: PRIMARY -> HEURISTIC -> SAFE -> PRIMARY."""
    
    def transition_cycle():
        # Go through all states
        fallback_manager.cascade(HEALTHY_STATE)
        fallback_manager.cascade(DEGRADED_STATE)
        fallback_manager.cascade(CRITICAL_STATE)
        fallback_manager.cascade(HEALTHY_STATE)
        return fallback_manager.get_current_mode()
    
    result = benchmark(transition_cycle)
    assert result == FallbackMode.PRIMARY


def test_get_current_mode(benchmark, fallback_manager):
    """Benchmark getting current mode (should be very fast)."""
    
    def get_mode():
        return fallback_manager.get_current_mode()
    
    result = benchmark(get_mode)
    assert result == FallbackMode.PRIMARY


def test_is_degraded_check(benchmark, fallback_manager):
    """Benchmark degraded mode check."""
    
    def check_degraded():
        return fallback_manager.is_degraded()
    
    result = benchmark(check_degraded)
    assert result is False


def test_get_metrics(benchmark, fallback_manager):
    """Benchmark metrics retrieval."""
    
    # Do some transitions first
    fallback_manager.cascade(HEALTHY_STATE)
    fallback_manager.cascade(DEGRADED_STATE)
    fallback_manager.cascade(HEALTHY_STATE)
    
    def get_metrics():
        return fallback_manager.get_metrics()
    
    result = benchmark(get_metrics)
    assert "current_mode" in result


def test_cascade_repeated_same_state(benchmark, fallback_manager):
    """Benchmark repeated cascade calls with same state (no transition)."""
    
    def repeated_cascade():
        for _ in range(10):
            fallback_manager.cascade(HEALTHY_STATE)
        return fallback_manager.get_current_mode()
    
    result = benchmark(repeated_cascade)
    assert result == FallbackMode.PRIMARY
