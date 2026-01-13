"""Unit tests for orchestrator decision logic."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from backend.orchestration.recovery_orchestrator import RecoveryOrchestrator, RecoveryMetrics


class MockHealthMonitor:
    """Mock health monitor for testing."""
    
    def __init__(self):
        self.state = {
            "system": {"status": "HEALTHY", "failed_components": 0},
            "circuit_breaker": {"state": "CLOSED", "open_duration_seconds": 0},
            "retry": {"failures_1h": 0, "state": "STABLE"},
            "fallback": {"mode": "PRIMARY"},
        }
    
    async def get_comprehensive_state(self):
        return self.state.copy()


class MockFallbackManager:
    """Mock fallback manager for testing."""
    
    def __init__(self):
        self.current_mode = "PRIMARY"
        self.cascade_called = False
    
    async def cascade(self, state):
        self.cascade_called = True
        self.current_mode = "SAFE"
        return True
    
    async def set_mode(self, mode):
        self.current_mode = mode
        return True


class TestRecoveryOrchestratorDecisionLogic:
    """Test recovery orchestrator decision logic (pure functions)."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create mock health monitor."""
        return MockHealthMonitor()
    
    @pytest.fixture
    def fallback_manager(self):
        """Create mock fallback manager."""
        return MockFallbackManager()
    
    @pytest.fixture
    def orchestrator(self, health_monitor, fallback_manager):
        """Create orchestrator with mocked dependencies."""
        return RecoveryOrchestrator(
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
            config_path="config/recovery.yaml",
        )
    
    def test_initialization(self, orchestrator):
        """Test orchestrator initializes correctly."""
        assert orchestrator.health_monitor is not None
        assert orchestrator.fallback_manager is not None
        assert orchestrator._running is False
        assert isinstance(orchestrator.metrics, RecoveryMetrics)
        assert len(orchestrator._action_handlers) == 3
    
    def test_cooldown_check_first_execution(self, orchestrator):
        """Test cooldown check allows first execution."""
        assert orchestrator._check_cooldown("circuit_restart") is True
        assert orchestrator._check_cooldown("cache_purge") is True
        assert orchestrator._check_cooldown("safe_mode") is True
    
    def test_cooldown_check_enforces_wait(self, orchestrator):
        """Test cooldown check enforces waiting period."""
        # Record first execution
        orchestrator._record_cooldown("circuit_restart")
        
        # Should be in cooldown immediately after
        assert orchestrator._check_cooldown("circuit_restart") is False
        
        # Check cooldown remaining
        remaining = orchestrator._get_cooldown_remaining("circuit_restart")
        assert remaining > 0
    
    def test_cooldown_check_expires(self, orchestrator):
        """Test cooldown expires after configured duration."""
        # Record execution in the past
        past_time = datetime.utcnow() - timedelta(seconds=400)
        orchestrator._last_action_times["circuit_restart"] = past_time
        
        # Should be allowed (default cooldown is 300s)
        assert orchestrator._check_cooldown("circuit_restart") is True
    
    def test_get_metrics(self, orchestrator):
        """Test metrics retrieval."""
        metrics = orchestrator.get_metrics()
        
        assert metrics["total_actions_executed"] == 0
        assert metrics["successful_actions"] == 0
        assert metrics["failed_actions"] == 0
        assert metrics["success_rate"] == 0.0
        assert metrics["running"] is False
    
    def test_get_cooldown_status(self, orchestrator):
        """Test cooldown status retrieval."""
        status = orchestrator.get_cooldown_status()
        
        assert "circuit_restart" in status
        assert "cache_purge" in status
        assert "safe_mode" in status
        
        # All should be available initially
        assert status["circuit_restart"]["available"] is True
        assert status["cache_purge"]["available"] is True
        assert status["safe_mode"]["available"] is True
    
    def test_get_status(self, orchestrator):
        """Test status retrieval."""
        status = orchestrator.get_status()
        
        assert "running" in status
        assert "enabled" in status
        assert "metrics" in status
        assert "cooldown_status" in status
        assert status["running"] is False
    
    @pytest.mark.asyncio
    async def test_evaluate_circuit_recovery_healthy(self, orchestrator, health_monitor):
        """Test circuit recovery evaluation when circuit is healthy."""
        # Circuit is CLOSED - no recovery needed
        state = await health_monitor.get_comprehensive_state()
        
        initial_actions = orchestrator.metrics.total_actions_executed
        await orchestrator._evaluate_circuit_recovery(state)
        
        # No action should be taken
        assert orchestrator.metrics.total_actions_executed == initial_actions
    
    @pytest.mark.asyncio
    async def test_evaluate_circuit_recovery_threshold_exceeded(self, orchestrator, health_monitor):
        """Test circuit recovery triggers when threshold exceeded."""
        # Set circuit to OPEN for longer than threshold
        health_monitor.state["circuit_breaker"]["state"] = "OPEN"
        health_monitor.state["circuit_breaker"]["open_duration_seconds"] = 400
        
        state = await health_monitor.get_comprehensive_state()
        
        initial_actions = orchestrator.metrics.total_actions_executed
        await orchestrator._evaluate_circuit_recovery(state)
        
        # Action should be taken
        assert orchestrator.metrics.total_actions_executed == initial_actions + 1
    
    @pytest.mark.asyncio
    async def test_evaluate_cache_recovery_threshold_exceeded(self, orchestrator, health_monitor):
        """Test cache recovery triggers when retry failures high."""
        # Set retry failures above threshold
        health_monitor.state["retry"]["failures_1h"] = 60
        
        state = await health_monitor.get_comprehensive_state()
        
        initial_actions = orchestrator.metrics.total_actions_executed
        await orchestrator._evaluate_cache_recovery(state)
        
        # Action should be taken
        assert orchestrator.metrics.total_actions_executed == initial_actions + 1
    
    @pytest.mark.asyncio
    async def test_evaluate_accuracy_recovery_threshold_exceeded(self, orchestrator, health_monitor):
        """Test safe mode triggers when multiple components fail."""
        # Set failed components above threshold
        health_monitor.state["system"]["failed_components"] = 3
        
        state = await health_monitor.get_comprehensive_state()
        
        initial_actions = orchestrator.metrics.total_actions_executed
        await orchestrator._evaluate_accuracy_recovery(state)
        
        # Action should be taken
        assert orchestrator.metrics.total_actions_executed == initial_actions + 1
    
    @pytest.mark.asyncio
    async def test_handle_event_health_check(self, orchestrator, health_monitor):
        """Test handling health check events."""
        health_monitor.state["circuit_breaker"]["state"] = "OPEN"
        health_monitor.state["circuit_breaker"]["open_duration_seconds"] = 400
        
        event = {
            "type": "health_check",
            "state": health_monitor.state,
        }
        
        initial_actions = orchestrator.metrics.total_actions_executed
        await orchestrator.handle_event(event)
        
        # Should trigger circuit recovery
        assert orchestrator.metrics.total_actions_executed == initial_actions + 1
    
    @pytest.mark.asyncio
    async def test_handle_event_manual_trigger(self, orchestrator):
        """Test handling manual trigger events."""
        event = {
            "type": "manual_trigger",
            "action_type": "safe_mode",
            "reason": "Testing manual trigger",
        }
        
        initial_actions = orchestrator.metrics.total_actions_executed
        await orchestrator.handle_event(event)
        
        # Should execute the specified action
        assert orchestrator.metrics.total_actions_executed == initial_actions + 1
        assert orchestrator.metrics.last_action_type == "safe_mode"
    
    @pytest.mark.asyncio
    async def test_action_circuit_restart_success(self, orchestrator):
        """Test circuit restart action executes successfully."""
        await orchestrator._action_circuit_restart()
        # Should complete without error
    
    @pytest.mark.asyncio
    async def test_action_cache_purge_success(self, orchestrator):
        """Test cache purge action executes successfully."""
        await orchestrator._action_cache_purge()
        # Should complete without error
    
    @pytest.mark.asyncio
    async def test_action_safe_mode_success(self, orchestrator, fallback_manager):
        """Test safe mode action executes successfully."""
        await orchestrator._action_safe_mode()
        
        # Should trigger fallback cascade
        assert fallback_manager.cascade_called is True
        assert fallback_manager.current_mode == "SAFE"


class TestRecoveryOrchestratorMetrics:
    """Test metrics tracking in recovery orchestrator."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with minimal dependencies."""
        return RecoveryOrchestrator(
            health_monitor=MockHealthMonitor(),
            fallback_manager=MockFallbackManager(),
        )
    
    def test_metrics_update_success(self, orchestrator):
        """Test metrics update for successful action."""
        from backend.orchestration.recovery_orchestrator import RecoveryAction
        
        action = RecoveryAction(
            action_type="circuit_restart",
            timestamp=datetime.utcnow(),
            reason="Test",
            success=True,
            duration_seconds=1.5,
        )
        
        orchestrator._update_metrics(action)
        
        assert orchestrator.metrics.total_actions_executed == 1
        assert orchestrator.metrics.successful_actions == 1
        assert orchestrator.metrics.failed_actions == 0
        assert orchestrator.metrics.actions_by_type["circuit_restart"] == 1
    
    def test_metrics_update_failure(self, orchestrator):
        """Test metrics update for failed action."""
        from backend.orchestration.recovery_orchestrator import RecoveryAction
        
        action = RecoveryAction(
            action_type="cache_purge",
            timestamp=datetime.utcnow(),
            reason="Test",
            success=False,
            error="Test error",
            duration_seconds=0.5,
        )
        
        orchestrator._update_metrics(action)
        
        assert orchestrator.metrics.total_actions_executed == 1
        assert orchestrator.metrics.successful_actions == 0
        assert orchestrator.metrics.failed_actions == 1
        assert orchestrator.metrics.actions_by_type["cache_purge"] == 1
    
    def test_action_history_recording(self, orchestrator):
        """Test action history is recorded."""
        from backend.orchestration.recovery_orchestrator import RecoveryAction
        
        action = RecoveryAction(
            action_type="safe_mode",
            timestamp=datetime.utcnow(),
            reason="Test",
            success=True,
        )
        
        orchestrator._record_action_history(action)
        
        assert len(orchestrator._action_history) == 1
        assert orchestrator._action_history[0] == action
    
    def test_action_history_limit(self, orchestrator):
        """Test action history respects maximum size."""
        from backend.orchestration.recovery_orchestrator import RecoveryAction
        
        # Add more than max_history actions
        for i in range(150):
            action = RecoveryAction(
                action_type="circuit_restart",
                timestamp=datetime.utcnow(),
                reason=f"Test {i}",
                success=True,
            )
            orchestrator._record_action_history(action, max_history=100)
        
        # Should only keep last 100
        assert len(orchestrator._action_history) == 100


class TestRecoveryOrchestratorLifecycle:
    """Test orchestrator lifecycle (start/stop)."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked dependencies."""
        return RecoveryOrchestrator(
            health_monitor=MockHealthMonitor(),
            fallback_manager=MockFallbackManager(),
        )
    
    def test_stop_sets_running_false(self, orchestrator):
        """Test stop sets running flag to False."""
        orchestrator._running = True
        orchestrator.stop()
        assert orchestrator._running is False
    
    @pytest.mark.asyncio
    async def test_run_exits_when_disabled(self, orchestrator):
        """Test run exits immediately when disabled."""
        # Disable orchestrator
        orchestrator.config.config["enabled"] = False
        
        # Should exit without starting
        await orchestrator.run()
        
        assert orchestrator._running is False
    
    @pytest.mark.asyncio
    async def test_run_starts_and_stops(self, orchestrator):
        """Test run can be started and stopped."""
        # Start orchestrator in background
        run_task = asyncio.create_task(orchestrator.run())
        
        # Give it time to start
        await asyncio.sleep(0.1)
        assert orchestrator._running is True
        
        # Stop orchestrator
        orchestrator.stop()
        
        # Wait for task to complete
        await asyncio.sleep(0.1)
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass
        
        assert orchestrator._running is False
