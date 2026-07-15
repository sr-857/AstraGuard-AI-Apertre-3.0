"""
Tests for Enhanced Recovery Orchestrator (Feature Request #2)

Tests all new features:
1. Severity-threshold based triggering
2. CubeSat-specific recovery actions
3. Escalation chains with conditions
4. Dry-run mode
5. Phase-aware action execution
6. Per-anomaly recovery policies
"""

import pytest
import asyncio
import os
import tempfile
import yaml
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Mark recovery orchestrator tests as slow
pytestmark = [pytest.mark.slow, pytest.mark.timeout(45)]

# Add parent directory to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.orchestration.recovery_orchestrator_enhanced import (
    EnhancedRecoveryOrchestrator,
    RecoveryConfig,
    AnomalyEvent,
    RecoveryResult,
    RecoveryAction,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    config = {
        "enabled": True,
        "poll_interval": 1,
        "dry_run_mode": False,
        "thresholds": {
            "circuit_open_duration": 300,
            "retry_failures_1h": 50,
        },
        "cooldowns": {
            "reduce_power_load": 5,
            "activate_cooling": 5,
            "stabilize_attitude": 5,
        },
        "recovery_policies": {
            "power_fault": {
                "severity_threshold": 0.7,
                "escalation_chain": [
                    {
                        "action": "reduce_power_load",
                        "condition": "severity >= 0.7",
                        "params": {
                            "target_subsystems": ["PAYLOAD"],
                            "power_reduction_percent": 30
                        },
                        "timeout": 10
                    }
                ]
            },
            "thermal_fault": {
                "severity_threshold": 0.6,
                "escalation_chain": [
                    {
                        "action": "activate_cooling",
                        "condition": "severity >= 0.6",
                        "params": {"duty_cycle": 80},
                        "timeout": 10
                    },
                    {
                        "action": "reduce_processor_load",
                        "condition": "severity >= 0.8",
                        "params": {"cpu_throttle_percent": 20},
                        "timeout": 10
                    }
                ]
            }
        },
        "recovery_actions": {
            "reduce_power_load": {"enabled": True, "timeout": 10},
            "activate_cooling": {"enabled": True, "timeout": 10},
            "reduce_processor_load": {"enabled": True, "timeout": 10},
            "stabilize_attitude": {
                "enabled": True,
                "timeout": 10,
                "phase_restrictions": {
                    "LAUNCH": False,
                    "DEPLOYMENT": False,
                    "NOMINAL_OPS": True,
                }
            }
        },
        "advanced": {
            "max_concurrent_actions": 1,
            "verify_recovery_success": False,
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_state_machine():
    """Mock state machine for testing."""
    mock = Mock()
    mock.get_current_phase.return_value = Mock(value="NOMINAL_OPS")
    mock.force_safe_mode.return_value = {"success": True, "message": "Safe mode activated"}
    return mock


@pytest.fixture
def orchestrator(temp_config_file, mock_state_machine):
    """Create orchestrator instance for testing."""
    return EnhancedRecoveryOrchestrator(
        state_machine=mock_state_machine,
        config_path=temp_config_file
    )


# ============================================================================
# TEST 1: SEVERITY-THRESHOLD BASED TRIGGERING
# ============================================================================


class TestSeverityThresholdTriggering:
    """Test that anomalies trigger recovery based on severity thresholds."""

    @pytest.mark.asyncio
    async def test_below_threshold_no_recovery(self, orchestrator):
        """Anomaly below threshold should not trigger recovery."""
        # Power fault threshold is 0.7
        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.5,  # Below 0.7
            confidence=0.9
        )

        # Process queue
        await orchestrator._process_anomaly_queue()

        # No actions should be executed
        assert len(orchestrator._action_history) == 0

    @pytest.mark.asyncio
    async def test_above_threshold_triggers_recovery(self, orchestrator):
        """Anomaly above threshold should trigger recovery."""
        # Power fault threshold is 0.7
        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.8,  # Above 0.7
            confidence=0.9
        )

        # Process queue
        await orchestrator._process_anomaly_queue()

        # Action should be executed
        assert len(orchestrator._action_history) > 0
        assert orchestrator._action_history[0].action_type == "reduce_power_load"
        assert orchestrator._action_history[0].severity_score == 0.8

    @pytest.mark.asyncio
    async def test_exact_threshold_triggers_recovery(self, orchestrator):
        """Anomaly at exact threshold should trigger recovery."""
        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.7,  # Exact threshold
            confidence=0.9
        )

        await orchestrator._process_anomaly_queue()

        assert len(orchestrator._action_history) > 0


# ============================================================================
# TEST 2: ESCALATION CHAINS WITH CONDITIONS
# ============================================================================


class TestEscalationChains:
    """Test multi-step escalation chains with conditional execution."""

    @pytest.mark.asyncio
    async def test_single_step_escalation(self, orchestrator):
        """Low severity triggers only first step."""
        # Thermal threshold 0.6, step 2 needs 0.8
        await orchestrator.handle_anomaly(
            anomaly_type="thermal_fault",
            severity_score=0.7,  # >= 0.6 but < 0.8
            confidence=0.9
        )

        await orchestrator._process_anomaly_queue()

        # Only first action should execute
        assert len(orchestrator._action_history) == 1
        assert orchestrator._action_history[0].action_type == "activate_cooling"

    @pytest.mark.asyncio
    async def test_multi_step_escalation(self, orchestrator):
        """High severity triggers multiple steps."""
        # Thermal: step 1 at 0.6, step 2 at 0.8
        await orchestrator.handle_anomaly(
            anomaly_type="thermal_fault",
            severity_score=0.9,  # Triggers both steps
            confidence=0.9
        )

        await orchestrator._process_anomaly_queue()

        # Both actions should execute
        assert len(orchestrator._action_history) == 2
        assert orchestrator._action_history[0].action_type == "activate_cooling"
        assert orchestrator._action_history[1].action_type == "reduce_processor_load"

    @pytest.mark.asyncio
    async def test_condition_evaluation_severity(self, orchestrator):
        """Test condition evaluation with severity variable."""
        event = AnomalyEvent(
            anomaly_type="test",
            severity_score=0.85,
            confidence=0.9,
            timestamp=datetime.utcnow()
        )

        # Test various conditions
        assert orchestrator._evaluate_condition("always", event, 1) is True
        assert orchestrator._evaluate_condition("severity >= 0.8", event, 1) is True
        assert orchestrator._evaluate_condition("severity >= 0.9", event, 1) is False
        assert orchestrator._evaluate_condition("severity < 0.9", event, 1) is True


# ============================================================================
# TEST 3: DRY-RUN MODE
# ============================================================================


class TestDryRunMode:
    """Test dry-run mode for safe testing."""

    @pytest.mark.asyncio
    async def test_dry_run_mode_enabled(self, orchestrator):
        """Actions should be logged but not executed in dry-run mode."""
        # Enable dry-run
        orchestrator.config.config["dry_run_mode"] = True
        assert orchestrator.is_dry_run() is True

        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.8,
            confidence=0.9
        )

        await orchestrator._process_anomaly_queue()

        # Action logged
        assert len(orchestrator._action_history) > 0
        action = orchestrator._action_history[0]

        # But marked as dry-run
        assert action.dry_run is True
        assert action.result == RecoveryResult.SKIPPED_DRY_RUN
        assert action.success is True  # "Success" in dry-run means simulation worked

    @pytest.mark.asyncio
    async def test_dry_run_toggle(self, orchestrator):
        """Test toggling dry-run mode."""
        # Initially disabled
        assert orchestrator.is_dry_run() is False

        # Toggle on
        result = orchestrator.toggle_dry_run()
        assert result is True
        assert orchestrator.is_dry_run() is True

        # Toggle off
        result = orchestrator.toggle_dry_run()
        assert result is False
        assert orchestrator.is_dry_run() is False

    @pytest.mark.asyncio
    async def test_dry_run_no_cooldown(self, orchestrator):
        """Dry-run actions should not trigger cooldowns."""
        orchestrator.config.config["dry_run_mode"] = True

        # Execute action in dry-run
        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.8,
            confidence=0.9
        )
        await orchestrator._process_anomaly_queue()

        # Cooldown should NOT be recorded
        assert "reduce_power_load" not in orchestrator._last_action_times


# ============================================================================
# TEST 4: PHASE-AWARE ACTION EXECUTION
# ============================================================================


class TestPhaseAwareExecution:
    """Test phase restrictions on recovery actions."""

    @pytest.mark.asyncio
    async def test_action_allowed_in_phase(self, orchestrator, mock_state_machine):
        """Action should execute when allowed in current phase."""
        # Set phase to NOMINAL_OPS (allowed for stabilize_attitude)
        mock_state_machine.get_current_phase.return_value = Mock(value="NOMINAL_OPS")

        # Check restriction
        allowed = orchestrator._check_phase_restrictions("stabilize_attitude")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_action_restricted_in_phase(self, orchestrator, mock_state_machine):
        """Action should be blocked when restricted in current phase."""
        # Set phase to LAUNCH (restricted for stabilize_attitude)
        mock_state_machine.get_current_phase.return_value = Mock(value="LAUNCH")

        # Check restriction
        allowed = orchestrator._check_phase_restrictions("stabilize_attitude")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_no_restrictions_allows_all(self, orchestrator):
        """Actions without restrictions should always be allowed."""
        # reduce_power_load has no phase_restrictions in config
        allowed = orchestrator._check_phase_restrictions("reduce_power_load")
        assert allowed is True


# ============================================================================
# TEST 5: CUBESAT-SPECIFIC RECOVERY ACTIONS
# ============================================================================


class TestCubeSatRecoveryActions:
    """Test all 9 new CubeSat-specific recovery actions."""

    @pytest.mark.asyncio
    async def test_reduce_power_load(self, orchestrator):
        """Test reduce_power_load action."""
        params = {
            "target_subsystems": ["PAYLOAD", "HEATER"],
            "power_reduction_percent": 30
        }

        await orchestrator._action_reduce_power_load(params)
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_activate_cooling(self, orchestrator):
        """Test activate_cooling action."""
        params = {
            "duty_cycle": 80,
            "target_temperature": 35
        }

        await orchestrator._action_activate_cooling(params)
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_stabilize_attitude(self, orchestrator):
        """Test stabilize_attitude action."""
        params = {
            "use_thrusters": False,
            "use_wheels": True,
            "target_mode": "nadir_pointing"
        }

        await orchestrator._action_stabilize_attitude(params)
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_reduce_processor_load(self, orchestrator):
        """Test reduce_processor_load action."""
        params = {
            "cpu_throttle_percent": 20,
            "disable_non_critical_tasks": True
        }

        await orchestrator._action_reduce_processor_load(params)
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_enter_safe_mode(self, orchestrator, mock_state_machine):
        """Test enter_safe_mode action."""
        params = {
            "reason": "test_fault",
            "preserve_state": True
        }

        await orchestrator._action_enter_safe_mode(params)

        # Should have called state machine
        mock_state_machine.force_safe_mode.assert_called_once()

    @pytest.mark.asyncio
    async def test_alert_ground(self, orchestrator):
        """Test alert_ground action."""
        params = {
            "channel": "emergency",
            "priority": "high",
            "message": "Test alert"
        }

        await orchestrator._action_alert_ground(params)
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_restart_radio(self, orchestrator):
        """Test restart_radio action."""
        params = {
            "radio_id": "primary",
            "warm_restart": True
        }

        await orchestrator._action_restart_radio(params)
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_switch_to_backup_radio(self, orchestrator):
        """Test switch_to_backup_radio action."""
        params = {}

        await orchestrator._action_switch_to_backup_radio(params)
        # Should complete without errors

    @pytest.mark.asyncio
    async def test_log_detailed_state(self, orchestrator):
        """Test log_detailed_state action."""
        params = {
            "include_telemetry": True,
            "include_component_health": True,
            "duration_seconds": 60
        }

        await orchestrator._action_log_detailed_state(params)
        # Should complete without errors


# ============================================================================
# TEST 6: COOLDOWN MANAGEMENT
# ============================================================================


class TestCooldownManagement:
    """Test cooldown protection prevents action thrashing."""

    @pytest.mark.asyncio
    async def test_cooldown_blocks_repeat_action(self, orchestrator):
        """Second action within cooldown period should be skipped."""
        # First execution
        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.8,
            confidence=0.9
        )
        await orchestrator._process_anomaly_queue()

        assert len(orchestrator._action_history) == 1
        assert orchestrator._action_history[0].result == RecoveryResult.SUCCESS

        # Second execution (should be blocked by cooldown)
        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.8,
            confidence=0.9
        )
        await orchestrator._process_anomaly_queue()

        # Second action skipped
        assert len(orchestrator._action_history) == 2
        assert orchestrator._action_history[1].result == RecoveryResult.SKIPPED_COOLDOWN

    @pytest.mark.asyncio
    async def test_cooldown_expires(self, orchestrator):
        """Action should execute after cooldown expires."""
        # Override cooldown to 0 seconds for testing
        orchestrator.config.config["cooldowns"]["reduce_power_load"] = 0

        # First execution
        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.8,
            confidence=0.9
        )
        await orchestrator._process_anomaly_queue()

        # Second execution (cooldown expired)
        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.8,
            confidence=0.9
        )
        await orchestrator._process_anomaly_queue()

        # Both actions executed
        assert len(orchestrator._action_history) == 2
        assert orchestrator._action_history[0].result == RecoveryResult.SUCCESS
        assert orchestrator._action_history[1].result == RecoveryResult.SUCCESS


# ============================================================================
# TEST 7: METRICS & HISTORY
# ============================================================================


class TestMetricsAndHistory:
    """Test enhanced metrics and action history tracking."""

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, orchestrator):
        """Test metrics are properly tracked."""
        # Execute some actions
        await orchestrator.handle_anomaly("power_fault", 0.8, 0.9)
        await orchestrator._process_anomaly_queue()

        metrics = orchestrator.get_metrics()

        assert metrics["total_actions_executed"] == 1
        assert metrics["successful_actions"] == 1
        assert metrics["failed_actions"] == 0
        assert metrics["dry_run_mode"] is False
        assert "reduce_power_load" in metrics["actions_by_type"]
        assert "power_fault" in metrics["actions_by_anomaly"]

    @pytest.mark.asyncio
    async def test_action_history_records_details(self, orchestrator):
        """Test action history records all details."""
        await orchestrator.handle_anomaly(
            anomaly_type="thermal_fault",
            severity_score=0.75,
            confidence=0.92
        )
        await orchestrator._process_anomaly_queue()

        history = orchestrator.get_action_history(limit=10)

        assert len(history) > 0
        action = history[0]

        # Check all fields
        assert "timestamp" in action
        assert action["action_type"] == "activate_cooling"
        assert "reason" in action
        assert action["anomaly_type"] == "thermal_fault"
        assert action["severity_score"] == 0.75
        assert action["success"] is True
        assert "duration_seconds" in action
        assert "params" in action

    @pytest.mark.asyncio
    async def test_average_mttr_calculation(self, orchestrator):
        """Test MTTR calculation."""
        # Execute multiple actions
        for i in range(3):
            await orchestrator.handle_anomaly("power_fault", 0.8, 0.9)
            await orchestrator._process_anomaly_queue()
            # Reset cooldown for testing
            orchestrator._last_action_times.clear()
            await asyncio.sleep(0.1)

        metrics = orchestrator.get_metrics()

        # MTTR should be calculated
        assert metrics["average_mttr_seconds"] > 0
        assert metrics["successful_actions"] == 3


# ============================================================================
# TEST 8: PARAMETER PASSING
# ============================================================================


class TestParameterPassing:
    """Test parameters are correctly passed to actions."""

    @pytest.mark.asyncio
    async def test_params_passed_to_action(self, orchestrator):
        """Test action receives parameters from config."""
        await orchestrator.handle_anomaly(
            anomaly_type="power_fault",
            severity_score=0.8,
            confidence=0.9
        )
        await orchestrator._process_anomaly_queue()

        # Check action history has params
        action = orchestrator._action_history[0]
        assert action.params == {
            "target_subsystems": ["PAYLOAD"],
            "power_reduction_percent": 30
        }


# ============================================================================
# TEST 9: ERROR HANDLING
# ============================================================================


class TestErrorHandling:
    """Test graceful error handling."""

    @pytest.mark.asyncio
    async def test_unknown_anomaly_type(self, orchestrator):
        """Unknown anomaly type should not crash."""
        await orchestrator.handle_anomaly(
            anomaly_type="unknown_fault_type",
            severity_score=0.9,
            confidence=0.9
        )

        # Should not raise exception
        await orchestrator._process_anomaly_queue()

        # No actions executed (no policy for this type)
        assert len(orchestrator._action_history) == 0

    @pytest.mark.asyncio
    async def test_invalid_condition(self, orchestrator):
        """Invalid condition should raise ValueError."""
        event = AnomalyEvent(
            anomaly_type="test",
            severity_score=0.8,
            confidence=0.9,
            timestamp=datetime.utcnow()
        )

        # Invalid syntax should raise ValueError
        with pytest.raises(ValueError):
            orchestrator._evaluate_condition("invalid syntax here", event, 1)


# ============================================================================
# TEST 10: INTEGRATION TEST
# ============================================================================


class TestIntegrationFlow:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_complete_recovery_flow(self, orchestrator):
        """Test complete recovery flow from anomaly to action."""
        # 1. Detect thermal fault
        await orchestrator.handle_anomaly(
            anomaly_type="thermal_fault",
            severity_score=0.85,
            confidence=0.95,
            recurrence_count=1
        )

        # 2. Process queue
        await orchestrator._process_anomaly_queue()

        # 3. Verify actions executed
        assert len(orchestrator._action_history) == 2  # Both steps

        # 4. Verify metrics updated
        metrics = orchestrator.get_metrics()
        assert metrics["total_actions_executed"] == 2
        # Note: actions_by_anomaly counts by unique anomaly type, not action count
        assert metrics["actions_by_anomaly"]["thermal_fault"] >= 1

        # 5. Verify cooldowns set
        assert "activate_cooling" in orchestrator._last_action_times
        assert "reduce_processor_load" in orchestrator._last_action_times

    @pytest.mark.asyncio
    async def test_dry_run_to_production_flow(self, orchestrator):
        """Test workflow from dry-run testing to production."""
        # 1. Test in dry-run mode
        orchestrator.config.config["dry_run_mode"] = True

        await orchestrator.handle_anomaly("power_fault", 0.8, 0.9)
        await orchestrator._process_anomaly_queue()

        dry_run_action = orchestrator._action_history[0]
        assert dry_run_action.dry_run is True
        assert dry_run_action.result == RecoveryResult.SKIPPED_DRY_RUN

        # 2. Switch to production
        orchestrator.toggle_dry_run()
        assert orchestrator.is_dry_run() is False

        # Clear cooldowns for test
        orchestrator._last_action_times.clear()

        # 3. Execute in production
        await orchestrator.handle_anomaly("power_fault", 0.8, 0.9)
        await orchestrator._process_anomaly_queue()

        production_action = orchestrator._action_history[1]
        assert production_action.dry_run is False
        assert production_action.result == RecoveryResult.SUCCESS


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
