"""
Comprehensive tests for Recovery Orchestrator (Issue #17)

Tests cover:
- Recovery condition evaluation (circuit, cache, accuracy)
- Recovery action execution
- Cooldown enforcement (prevent thrashing)
- Metrics tracking and history
- Configuration loading and management
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from backend.orchestration.recovery_orchestrator import (
    RecoveryOrchestrator,
    RecoveryConfig,
    RecoveryAction,
    RecoveryMetrics,
)

# Mark recovery orchestrator tests as slow
pytestmark = [pytest.mark.slow, pytest.mark.timeout(45)]

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def recovery_config():
    """Create recovery config with defaults."""
    return RecoveryConfig(config_path="config/recovery.yaml")


@pytest.fixture
def mock_health_monitor():
    """Create mock health monitor."""
    monitor = AsyncMock()
    monitor.get_comprehensive_state = AsyncMock(return_value={
        "timestamp": datetime.utcnow().isoformat(),
        "circuit_breaker": {
            "state": "CLOSED",
            "open_duration_seconds": 0,
        },
        "retry": {
            "failures_1h": 5,
        },
        "system": {
            "failed_components": 0,
        },
    })
    return monitor


@pytest.fixture
def mock_fallback_manager():
    """Create mock fallback manager."""
    manager = AsyncMock()
    manager.cascade = AsyncMock()
    return manager


@pytest.fixture
def recovery_orchestrator(mock_health_monitor, mock_fallback_manager):
    """Create recovery orchestrator with mocks."""
    orch = RecoveryOrchestrator(
        health_monitor=mock_health_monitor,
        fallback_manager=mock_fallback_manager,
        config_path="config/recovery.yaml",
    )
    return orch


@pytest.fixture
def circuit_open_state():
    """Health state with open circuit."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "circuit_breaker": {
            "state": "OPEN",
            "open_duration_seconds": 400,  # > 300s threshold
        },
        "retry": {"failures_1h": 5},
        "system": {"failed_components": 0},
    }


@pytest.fixture
def high_retry_failures_state():
    """Health state with high retry failures."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "circuit_breaker": {
            "state": "CLOSED",
            "open_duration_seconds": 0,
        },
        "retry": {"failures_1h": 75},  # > 50 threshold
        "system": {"failed_components": 0},
    }


@pytest.fixture
def multiple_failures_state():
    """Health state with multiple component failures."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "circuit_breaker": {
            "state": "CLOSED",
            "open_duration_seconds": 0,
        },
        "retry": {"failures_1h": 5},
        "system": {"failed_components": 2},  # >= 2 threshold
    }


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================


def test_recovery_config_load_defaults():
    """Test config loads with defaults when file missing."""
    config = RecoveryConfig(config_path="/nonexistent/path.yaml")
    
    assert config.get("enabled") is True
    assert config.get("poll_interval") == 30
    assert config.get("thresholds.circuit_open_duration") == 300


def test_recovery_config_get_nested():
    """Test config dot-notation access."""
    config = RecoveryConfig(config_path="config/recovery.yaml")
    
    assert config.get("thresholds.circuit_open_duration") == 300
    assert config.get("cooldowns.circuit_restart") == 300
    assert config.get("recovery_actions.circuit_restart.enabled") is True


def test_recovery_config_get_default():
    """Test config returns default for missing keys."""
    config = RecoveryConfig(config_path="config/recovery.yaml")
    
    assert config.get("nonexistent.key", "default_value") == "default_value"


# ============================================================================
# CIRCUIT RECOVERY TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_recovery_not_triggered_when_closed(recovery_orchestrator):
    """Test circuit recovery doesn't trigger when circuit is CLOSED."""
    state = {
        "circuit_breaker": {
            "state": "CLOSED",
            "open_duration_seconds": 0,
        },
        "retry": {"failures_1h": 5},
        "system": {"failed_components": 0},
    }
    
    with patch.object(recovery_orchestrator, '_action_circuit_restart') as mock_action:
        await recovery_orchestrator._evaluate_circuit_recovery(state)
        mock_action.assert_not_called()


@pytest.mark.asyncio
async def test_circuit_recovery_triggered_when_open_exceeds_threshold(
    recovery_orchestrator,
    circuit_open_state,
):
    """Test circuit recovery triggered when circuit open > threshold."""
    with patch.object(recovery_orchestrator, '_execute_action') as mock_execute:
        await recovery_orchestrator._evaluate_circuit_recovery(circuit_open_state)
        
        # Should have called execute_action
        assert mock_execute.called


@pytest.mark.asyncio
async def test_circuit_recovery_respects_cooldown(recovery_orchestrator, circuit_open_state):
    """Test circuit recovery respects cooldown period."""
    # Set last action time to now
    recovery_orchestrator._last_action_times["circuit_restart"] = datetime.utcnow()
    
    with patch.object(recovery_orchestrator, '_execute_action') as mock_execute:
        await recovery_orchestrator._evaluate_circuit_recovery(circuit_open_state)
        
        # Should not execute due to cooldown
        mock_execute.assert_not_called()


# ============================================================================
# CACHE RECOVERY TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cache_recovery_not_triggered_when_failures_low(recovery_orchestrator):
    """Test cache recovery doesn't trigger when retry failures low."""
    state = {
        "circuit_breaker": {"state": "CLOSED", "open_duration_seconds": 0},
        "retry": {"failures_1h": 5},  # < 50 threshold
        "system": {"failed_components": 0},
    }
    
    with patch.object(recovery_orchestrator, '_action_cache_purge') as mock_action:
        await recovery_orchestrator._evaluate_cache_recovery(state)
        mock_action.assert_not_called()


@pytest.mark.asyncio
async def test_cache_recovery_triggered_when_failures_exceed_threshold(
    recovery_orchestrator,
    high_retry_failures_state,
):
    """Test cache recovery triggered when retry failures exceed threshold."""
    with patch.object(recovery_orchestrator, '_execute_action') as mock_execute:
        await recovery_orchestrator._evaluate_cache_recovery(high_retry_failures_state)
        
        assert mock_execute.called


# ============================================================================
# ACCURACY/SAFETY RECOVERY TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_safety_recovery_not_triggered_when_components_healthy(recovery_orchestrator):
    """Test safe mode recovery doesn't trigger when components healthy."""
    state = {
        "circuit_breaker": {"state": "CLOSED", "open_duration_seconds": 0},
        "retry": {"failures_1h": 5},
        "system": {"failed_components": 0},  # < 2 threshold
    }
    
    with patch.object(recovery_orchestrator, '_action_safe_mode') as mock_action:
        await recovery_orchestrator._evaluate_accuracy_recovery(state)
        mock_action.assert_not_called()


@pytest.mark.asyncio
async def test_safety_recovery_triggered_when_multiple_failures(
    recovery_orchestrator,
    multiple_failures_state,
):
    """Test safe mode recovery triggered when multiple components failed."""
    with patch.object(recovery_orchestrator, '_execute_action') as mock_execute:
        await recovery_orchestrator._evaluate_accuracy_recovery(multiple_failures_state)
        
        assert mock_execute.called


# ============================================================================
# RECOVERY ACTION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_restart_action(recovery_orchestrator):
    """Test circuit restart recovery action executes successfully."""
    # Should complete without error
    await recovery_orchestrator._action_circuit_restart()
    # Implicitly passed if no exception raised


@pytest.mark.asyncio
async def test_cache_purge_action(recovery_orchestrator):
    """Test cache purge recovery action executes successfully."""
    # Should complete without error
    await recovery_orchestrator._action_cache_purge()
    # Implicitly passed if no exception raised


@pytest.mark.asyncio
async def test_safe_mode_action(recovery_orchestrator, mock_fallback_manager):
    """Test safe mode recovery action executes successfully."""
    await recovery_orchestrator._action_safe_mode()
    
    # Should have called cascade on fallback manager
    mock_fallback_manager.cascade.assert_called_once()


@pytest.mark.asyncio
async def test_execute_action_updates_metrics(recovery_orchestrator):
    """Test executing action updates metrics correctly."""
    initial_count = recovery_orchestrator.metrics.total_actions_executed
    
    with patch.object(recovery_orchestrator, '_action_circuit_restart'):
        await recovery_orchestrator._execute_action("circuit_restart", reason="test")
    
    assert recovery_orchestrator.metrics.total_actions_executed == initial_count + 1
    assert recovery_orchestrator.metrics.actions_by_type["circuit_restart"] == 1


@pytest.mark.asyncio
async def test_execute_action_records_history(recovery_orchestrator):
    """Test executing action is recorded in history."""
    initial_count = len(recovery_orchestrator._action_history)
    
    with patch.object(recovery_orchestrator, '_action_circuit_restart'):
        await recovery_orchestrator._execute_action("circuit_restart", reason="test")
    
    assert len(recovery_orchestrator._action_history) == initial_count + 1
    assert recovery_orchestrator._action_history[-1].action_type == "circuit_restart"


@pytest.mark.asyncio
async def test_action_failure_tracked_in_metrics(recovery_orchestrator):
    """Test failed action is tracked in metrics."""
    async def failing_action():
        raise RuntimeError("Action failed")
    
    recovery_orchestrator._action_handlers["circuit_restart"] = failing_action
    
    await recovery_orchestrator._execute_action("circuit_restart", reason="test")
    
    assert recovery_orchestrator.metrics.failed_actions == 1
    assert recovery_orchestrator._action_history[-1].success is False


# ============================================================================
# COOLDOWN TESTS
# ============================================================================


def test_cooldown_first_execution_allowed(recovery_orchestrator):
    """Test first execution is allowed (no cooldown yet)."""
    assert recovery_orchestrator._check_cooldown("circuit_restart") is True


def test_cooldown_prevents_immediate_reexecution(recovery_orchestrator):
    """Test cooldown prevents immediate re-execution."""
    recovery_orchestrator._record_cooldown("circuit_restart")
    
    # Immediately check - should fail
    assert recovery_orchestrator._check_cooldown("circuit_restart") is False


def test_cooldown_expires_after_duration(recovery_orchestrator):
    """Test cooldown expires after configured duration."""
    # Set last action time to 301 seconds ago
    recovery_orchestrator._last_action_times["circuit_restart"] = (
        datetime.utcnow() - timedelta(seconds=301)
    )
    
    # 300 second cooldown should have expired
    assert recovery_orchestrator._check_cooldown("circuit_restart") is True


def test_get_cooldown_remaining(recovery_orchestrator):
    """Test getting remaining cooldown time."""
    recovery_orchestrator._record_cooldown("circuit_restart")
    
    remaining = recovery_orchestrator._get_cooldown_remaining("circuit_restart")
    
    # Should be close to 300 seconds (allow some margin)
    assert 290 < remaining <= 300


# ============================================================================
# RECOVERY CYCLE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_recovery_cycle_evaluates_all_conditions(
    recovery_orchestrator,
    mock_health_monitor,
):
    """Test recovery cycle evaluates all recovery conditions."""
    with patch.object(recovery_orchestrator, '_evaluate_circuit_recovery') as mock_circuit:
        with patch.object(recovery_orchestrator, '_evaluate_cache_recovery') as mock_cache:
            with patch.object(recovery_orchestrator, '_evaluate_accuracy_recovery') as mock_accuracy:
                await recovery_orchestrator._recovery_cycle()
    
    mock_circuit.assert_called_once()
    mock_cache.assert_called_once()
    mock_accuracy.assert_called_once()


@pytest.mark.asyncio
async def test_recovery_cycle_handles_errors_gracefully(recovery_orchestrator):
    """Test recovery cycle handles errors without crashing."""
    recovery_orchestrator.health_monitor.get_comprehensive_state.side_effect = Exception("Mock error")
    
    # Should not raise
    await recovery_orchestrator._recovery_cycle()


# ============================================================================
# METRICS TESTS
# ============================================================================


def test_get_metrics(recovery_orchestrator):
    """Test getting aggregated recovery metrics."""
    recovery_orchestrator.metrics.total_actions_executed = 10
    recovery_orchestrator.metrics.successful_actions = 8
    recovery_orchestrator.metrics.failed_actions = 2
    
    metrics = recovery_orchestrator.get_metrics()
    
    assert metrics["total_actions_executed"] == 10
    assert metrics["successful_actions"] == 8
    assert metrics["failed_actions"] == 2
    assert metrics["success_rate"] == 0.8


def test_get_action_history(recovery_orchestrator):
    """Test getting action history."""
    # Add some actions
    action1 = RecoveryAction("circuit_restart", datetime.utcnow(), "test1")
    action2 = RecoveryAction("cache_purge", datetime.utcnow(), "test2")
    recovery_orchestrator._action_history = [action1, action2]
    
    history = recovery_orchestrator.get_action_history(limit=10)
    
    assert len(history) == 2
    assert history[0]["action_type"] == "circuit_restart"
    assert history[1]["action_type"] == "cache_purge"


def test_get_cooldown_status(recovery_orchestrator):
    """Test getting cooldown status for all actions."""
    status = recovery_orchestrator.get_cooldown_status()
    
    assert "circuit_restart" in status
    assert "cache_purge" in status
    assert "safe_mode" in status
    
    # All should be available initially
    assert all(s["available"] for s in status.values())


# ============================================================================
# LIFECYCLE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_run_respects_enabled_flag(recovery_orchestrator):
    """Test run respects enabled flag in config."""
    recovery_orchestrator.config.config["enabled"] = False
    
    # Should return immediately
    await recovery_orchestrator.run()
    
    assert recovery_orchestrator._running is False


@pytest.mark.asyncio
async def test_run_loop_execution(recovery_orchestrator):
    """Test run loop executes recovery cycles."""
    recovery_orchestrator.config.config["poll_interval"] = 0.1  # Short interval
    
    cycle_count = 0
    original_cycle = recovery_orchestrator._recovery_cycle
    
    async def counting_cycle():
        nonlocal cycle_count
        cycle_count += 1
        if cycle_count >= 2:
            recovery_orchestrator.stop()
        await original_cycle()
    
    recovery_orchestrator._recovery_cycle = counting_cycle
    
    await recovery_orchestrator.run()
    
    assert cycle_count >= 2
    assert recovery_orchestrator._running is False


@pytest.mark.asyncio
async def test_stop_ends_orchestrator(recovery_orchestrator):
    """Test stop method ends the orchestrator."""
    # Start in task
    task = asyncio.create_task(recovery_orchestrator.run())
    await asyncio.sleep(0.1)
    
    recovery_orchestrator.stop()
    await asyncio.sleep(0.2)
    
    assert recovery_orchestrator._running is False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_full_recovery_flow_circuit_restart(recovery_orchestrator, circuit_open_state):
    """Test full flow: detect circuit issue → execute recovery."""
    recovery_orchestrator.health_monitor.get_comprehensive_state.return_value = circuit_open_state
    
    # Execute one cycle
    await recovery_orchestrator._recovery_cycle()
    
    # Should have recorded an action
    assert len(recovery_orchestrator._action_history) > 0
    assert recovery_orchestrator.metrics.total_actions_executed > 0


@pytest.mark.asyncio
async def test_concurrent_condition_evaluation(
    recovery_orchestrator,
    circuit_open_state,
    high_retry_failures_state,
):
    """Test handling multiple concurrent conditions."""
    # State with both circuit open AND high retry failures
    combined_state = {
        **circuit_open_state,
        "retry": {"failures_1h": 75},
    }
    
    recovery_orchestrator.health_monitor.get_comprehensive_state.return_value = combined_state
    
    await recovery_orchestrator._recovery_cycle()
    
    # Should evaluate all conditions
    assert recovery_orchestrator.metrics.total_actions_executed > 0


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_handles_missing_health_monitor(mock_fallback_manager):
    """Test orchestrator handles missing health monitor gracefully."""
    orch = RecoveryOrchestrator(
        health_monitor=None,
        fallback_manager=mock_fallback_manager,
    )
    
    # Should not crash
    await orch._recovery_cycle()


@pytest.mark.asyncio
async def test_handles_malformed_health_state(recovery_orchestrator):
    """Test orchestrator handles malformed health state."""
    recovery_orchestrator.health_monitor.get_comprehensive_state.return_value = {}
    
    # Should not crash
    await recovery_orchestrator._recovery_cycle()


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_recovery_cycle_completes_quickly(recovery_orchestrator):
    """Test recovery cycle completes in reasonable time."""
    import time
    
    start = time.time()
    await recovery_orchestrator._recovery_cycle()
    duration = time.time() - start
    
    # Should complete in < 1 second
    assert duration < 1.0


def test_metrics_aggregation_performance(recovery_orchestrator):
    """Test metric aggregation is fast."""
    import time
    
    # Add many actions manually to metrics
    for i in range(100):
        recovery_orchestrator.metrics.total_actions_executed += 1
        recovery_orchestrator.metrics.successful_actions += 1
        action = RecoveryAction(
            f"action_{i % 3}",
            datetime.utcnow(),
            f"reason_{i}",
            success=True,
        )
        recovery_orchestrator._record_action_history(action)
    
    start = time.time()
    metrics = recovery_orchestrator.get_metrics()
    duration = time.time() - start
    
    # Should complete in < 100ms
    assert duration < 0.1
    assert metrics["total_actions_executed"] == 100
