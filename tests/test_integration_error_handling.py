"""
Integration Tests for Error Handling & Graceful Degradation

Tests that error handling works correctly when components interact
with each other across the system.
"""

import pytest
from unittest.mock import patch, MagicMock
from core.component_health import SystemHealthMonitor, HealthStatus
from core.error_handling import (
    ModelLoadError,
    AnomalyEngineError,
    PolicyEvaluationError,
    StateTransitionError,
)
from state_machine.state_engine import StateMachine, MissionPhase
from state_machine.mission_phase_policy_engine import MissionPhasePolicyEngine
from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler
from config.mission_phase_policy_loader import MissionPhasePolicyLoader

from anomaly.anomaly_detector import detect_anomaly

# Mark integration error handling tests as slow
pytestmark = [pytest.mark.slow, pytest.mark.timeout(45)]
class TestEndToEndErrorHandling:
    """Test error handling across full system stack."""
    
    def teardown_method(self):
        """Reset health monitor after each test."""
        monitor = SystemHealthMonitor()
        monitor.reset()
    
    def test_anomaly_detector_failure_doesnt_crash_handler(self):
        """Test that anomaly detector failure doesn't crash phase-aware handler."""
        sm = StateMachine()
        sm.set_phase(MissionPhase.NOMINAL_OPS)
        loader = MissionPhasePolicyLoader()
        handler = PhaseAwareAnomalyHandler(sm, loader)
        
        # Handler should handle invalid input gracefully
        decision = handler.handle_anomaly(
            anomaly_type='unknown',
            severity_score=None,  # Invalid
            confidence=0.8
        )
        
        # Should return safe default instead of crashing
        assert decision is not None
        assert 'mission_phase' in decision
    
    def test_policy_evaluation_failure_returns_safe_default(self):
        """Test that policy evaluation failure returns safe default."""
        loader = MissionPhasePolicyLoader()
        engine = MissionPhasePolicyEngine(loader.get_policy())
        
        # Invalid severity should trigger error handling
        decision = engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='power_fault',
            severity_score=-1.0,  # Invalid
            anomaly_attributes={}
        )
        
        # Should still return a decision structure
        assert decision is not None
        # Severity classification should handle gracefully
        assert hasattr(decision, 'anomaly_type')
    
    def test_state_transition_error_maintains_last_good_state(self):
        """Test that invalid state transition doesn't corrupt system state."""
        sm = StateMachine()
        initial_phase = sm.get_current_phase()
        
        # Try invalid transition
        try:
            sm.mission_phase = None
            sm.set_phase(MissionPhase.LAUNCH)
        except Exception:
            pass
        
        # System should remain in valid state
        current = sm.get_current_phase()
        assert current is not None
    
    def test_health_monitor_tracks_cascade_failures(self):
        """Test that health monitor correctly tracks cascading failures."""
        monitor = SystemHealthMonitor()
        
        # Register components
        monitor.register_component("anomaly_detector")
        monitor.register_component("policy_engine")
        monitor.register_component("state_machine")
        
        # Mark one as degraded
        monitor.mark_degraded("anomaly_detector", "Model load failed")
        assert not monitor.is_system_healthy()
        assert monitor.is_system_degraded()
        
        # Mark another as degraded
        monitor.mark_degraded("policy_engine", "Invalid config")
        
        # System should still be degraded (not failed)
        assert monitor.is_system_degraded()
        assert not monitor.is_system_healthy()
    
    def test_fallback_propagation_through_stack(self):
        """Test that fallbacks propagate correctly through component stack."""
        sm = StateMachine()
        sm.set_phase(MissionPhase.NOMINAL_OPS)
        loader = MissionPhasePolicyLoader()
        handler = PhaseAwareAnomalyHandler(sm, loader)
        
        # Simulate a realistic anomaly that might have invalid data
        test_cases = [
            {
                'anomaly_type': '',  # Empty type
                'severity_score': 0.5,
                'confidence': 0.8,
            },
            {
                'anomaly_type': 'power_fault',
                'severity_score': 1.5,  # Out of range
                'confidence': 0.8,
            },
            {
                'anomaly_type': 'power_fault',
                'severity_score': 0.5,
                'confidence': 2.0,  # Out of range
            },
        ]
        
        for test_case in test_cases:
            decision = handler.handle_anomaly(**test_case)
            # Should not crash, should return some decision
            assert decision is not None
            assert 'recommended_action' in decision or 'success' in decision
    
    def test_system_remains_operational_under_partial_failures(self):
        """Test that system remains operational even with partial failures."""
        monitor = SystemHealthMonitor()
        sm = StateMachine()
        
        # Register all components
        monitor.register_component("anomaly_detector")
        monitor.register_component("policy_engine")
        monitor.register_component("state_machine")
        monitor.register_component("memory_engine")
        
        # Mark 50% of components as degraded
        monitor.mark_degraded("anomaly_detector", "Using heuristic mode")
        monitor.mark_degraded("memory_engine", "Disk I/O error")
        
        # System should still be operational but degraded
        assert monitor.is_system_degraded()
        assert not monitor.is_system_healthy()
        
        status = monitor.get_system_status()
        assert status['component_counts']['degraded'] == 2
        assert status['component_counts']['healthy'] == 2
    
    def test_structured_logging_includes_context(self):
        """Test that structured logging includes appropriate context."""
        sm = StateMachine()
        loader = MissionPhasePolicyLoader()
        handler = PhaseAwareAnomalyHandler(sm, loader)
        
        # Handle anomaly that might generate error
        decision = handler.handle_anomaly(
            anomaly_type='thermal_fault',
            severity_score=0.85,
            confidence=0.9,
            anomaly_metadata={'subsystem': 'EPS'}
        )
        
        # Should have context in decision
        assert decision is not None
        assert 'mission_phase' in decision
        
        # Should be able to serialize to dict (for logging)
        if hasattr(decision, '__dict__'):
            assert len(decision.__dict__) > 0


class TestDegradationModes:
    """Test graceful degradation in different failure modes."""
    
    def teardown_method(self):
        """Reset health monitor after each test."""
        monitor = SystemHealthMonitor()
        monitor.reset()
    
    @pytest.mark.asyncio
    async def test_heuristic_fallback_in_anomaly_detector(self):
        """Test that anomaly detector falls back to heuristic mode."""
        from anomaly.anomaly_detector import detect_anomaly, _USING_HEURISTIC_MODE
        
        # Detect anomaly in heuristic mode
        is_anomalous, score = await detect_anomaly({
            'voltage': 6.5,
            'temperature': 50.0,
            'gyro': 0.2
        })
        
        # Should return valid result even if model isn't loaded
        assert isinstance(is_anomalous, bool)
        assert 0 <= score <= 1
    
    def test_policy_fallback_returns_conservative_decision(self):
        """Test that policy engine returns conservative decisions on error."""
        loader = MissionPhasePolicyLoader()
        engine = MissionPhasePolicyEngine(loader.get_policy())
        
        # Try to evaluate with invalid parameters
        decision = engine.evaluate(
            mission_phase=MissionPhase.NOMINAL_OPS,
            anomaly_type='invalid_type',
            severity_score=0.75,
            anomaly_attributes={}
        )
        
        # Should return a valid decision structure
        assert decision is not None
    
    def test_state_machine_rejects_invalid_transitions(self):
        """Test that state machine properly rejects invalid transitions."""
        sm = StateMachine()
        sm.set_phase(MissionPhase.NOMINAL_OPS)
        
        # Try invalid transition
        try:
            # Can't go backwards from NOMINAL_OPS to LAUNCH
            sm.set_phase(MissionPhase.LAUNCH)
            assert False, "Should have raised error"
        except Exception:
            # Expected to fail
            pass
        
        # Should still be in previous phase
        assert sm.get_current_phase() == MissionPhase.NOMINAL_OPS


class TestHealthStatusExposure:
    """Test that health status is properly exposed for dashboard integration."""
    
    def teardown_method(self):
        """Reset health monitor after each test."""
        monitor = SystemHealthMonitor()
        monitor.reset()
    
    def test_health_status_json_serializable(self):
        """Test that health status can be serialized to JSON."""
        import json
        
        monitor = SystemHealthMonitor()
        monitor.register_component("test_component")
        monitor.mark_degraded("test_component", "Test error", fallback_active=True)
        
        status = monitor.get_system_status()
        
        # Should be JSON serializable (no circular refs, etc)
        json_str = json.dumps(status)
        assert json_str is not None
        assert len(json_str) > 0
        
        # Should deserialize back correctly
        restored = json.loads(json_str)
        assert restored['overall_status'] == 'degraded'
    
    def test_component_health_has_error_details(self):
        """Test that component health includes error details."""
        monitor = SystemHealthMonitor()
        monitor.register_component("detector")
        
        error_msg = "Model file not found"
        monitor.mark_degraded("detector", error_msg, fallback_active=True)
        
        health = monitor.get_component_health("detector")
        assert health.last_error == error_msg
        assert health.fallback_active is True
        assert health.status == HealthStatus.DEGRADED
    
    def test_dashboard_can_query_system_status(self):
        """Test that dashboard integration API works."""
        monitor = SystemHealthMonitor()
        
        # Simulate dashboard querying for status
        monitor.register_component("anomaly_detector")
        monitor.register_component("policy_engine")
        
        monitor.mark_healthy("anomaly_detector")
        monitor.mark_degraded("policy_engine", "Config error")
        
        status = monitor.get_system_status()
        
        # Dashboard should be able to display this
        assert status['overall_status'] in ['healthy', 'degraded', 'failed']
        assert 'components' in status
        assert len(status['components']) == 2
        
        # Should have component-level details
        for comp_name, comp_status in status['components'].items():
            assert 'status' in comp_status
            assert 'error_count' in comp_status or 'last_error' in comp_status


class TestCascadingFailureProtection:
    """Test that failures don't cascade through the system."""
    
    @pytest.mark.asyncio
    async def test_anomaly_detection_failure_doesnt_break_state_machine(self):
        """Test that anomaly detection failures don't break state machine."""
        sm = StateMachine()
        initial_phase = sm.get_current_phase()
        
        # Try to process data with anomaly detector in degraded mode
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01}
        is_anomalous, score = await detect_anomaly(data)
        
        # State machine should be unaffected
        assert sm.get_current_phase() == initial_phase
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
    
    @pytest.mark.asyncio
    async def test_policy_evaluation_failure_doesnt_break_detector(self):
        """Test that policy evaluation failures don't break detector."""
        loader = MissionPhasePolicyLoader()
        engine = MissionPhasePolicyEngine(loader.get_policy())
        
        # Anomaly detection should work independent of policy
        data = {"voltage": 7.5, "temperature": 30.0, "gyro": 0.02}
        is_anomalous, score = await detect_anomaly(data)
        
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)


class TestErrorRecovery:
    """Test system recovery after errors."""
    
    def test_state_machine_maintains_last_known_good_state(self):
        """Test state machine keeps last known-good state on error."""
        sm = StateMachine()
        initial_phase = MissionPhase.NOMINAL_OPS
        sm.current_phase = initial_phase
        
        # Try invalid transition - should raise error
        try:
            sm.set_phase(MissionPhase.LAUNCH)
        except StateTransitionError:
            pass  # Expected
        
        # Should still be in initial phase
        assert sm.get_current_phase() == initial_phase
    
    @pytest.mark.asyncio
    async def test_anomaly_detector_recovers_after_error(self):
        """Test anomaly detector can recover from errors."""
        # First call with valid data
        data1 = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01}
        is_anomalous1, score1 = await detect_anomaly(data1)
        assert isinstance(is_anomalous1, bool)
        
        # Call with problematic data should be handled
        try:
            is_anomalous2, score2 = await detect_anomaly({"invalid": "data"})
        except:
            pass  # May raise, should be handled
        
        # Third call should still work
        data3 = {"voltage": 7.9, "temperature": 26.0, "gyro": 0.02}
        is_anomalous3, score3 = await detect_anomaly(data3)
        assert isinstance(is_anomalous3, bool)
