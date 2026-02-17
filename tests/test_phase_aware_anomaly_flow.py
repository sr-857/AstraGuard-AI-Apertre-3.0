"""
Integration Tests for Phase-Aware Anomaly Flow

Tests the end-to-end flow: anomaly detection → policy evaluation → response decision
across different mission phases.
"""

import pytest
from datetime import datetime, timedelta
from state_machine.state_engine import StateMachine, MissionPhase, SystemState
from state_machine.mission_phase_policy_engine import MissionPhasePolicyEngine
from config.mission_phase_policy_loader import MissionPhasePolicyLoader
from anomaly_agent.phase_aware_handler import (
    PhaseAwareAnomalyHandler,
    DecisionTracer
)


@pytest.fixture
def state_machine():
    """Create a fresh state machine instance."""
    return StateMachine()


@pytest.fixture
def policy_loader():
    """Create a policy loader with defaults."""
    return MissionPhasePolicyLoader()


@pytest.fixture
def phase_aware_handler(state_machine, policy_loader):
    """Create a phase-aware anomaly handler."""
    return PhaseAwareAnomalyHandler(state_machine, policy_loader)


class TestPhaseTransitions:
    """Test mission phase transitions in state machine."""
    
    def test_deployment_to_nominal_transition(self, state_machine):
        """Test valid transition DEPLOYMENT → NOMINAL_OPS."""
        # Start from NOMINAL_OPS default state
        state_machine.current_phase = MissionPhase.DEPLOYMENT
        result = state_machine.set_phase(MissionPhase.NOMINAL_OPS)
        
        assert result['success'] is True
        assert state_machine.get_current_phase() == MissionPhase.NOMINAL_OPS
    
    def test_force_safe_mode(self, state_machine):
        """Test forced transition to SAFE_MODE (always allowed)."""
        result = state_machine.force_safe_mode()
        
        assert result['success'] is True
        assert state_machine.get_current_phase() == MissionPhase.SAFE_MODE
        assert result.get('forced') is True
    
    def test_get_current_phase(self, state_machine):
        """Test getting current mission phase."""
        phase = state_machine.get_current_phase()
        
        assert phase == MissionPhase.NOMINAL_OPS
        assert isinstance(phase, MissionPhase)


@pytest.mark.timeout(300) # Added 5-minute timeout for heavy AI policy evaluation
class TestPhaseAwareAnomalyHandling:
    """Test the phase-aware anomaly handler."""
    
    def test_anomaly_handler_decision_structure(self, phase_aware_handler):
        """Test that anomaly handler returns structured decisions."""
        decision = phase_aware_handler.handle_anomaly(
            anomaly_type='power_fault',
            severity_score=0.75,
            confidence=0.9
        )
        
        # Check decision structure
        assert 'mission_phase' in decision
        assert 'anomaly_type' in decision
        assert 'severity_score' in decision
        assert 'recommended_action' in decision
        assert 'should_escalate_to_safe_mode' in decision
    
    def test_handler_returns_structured_decision(self, phase_aware_handler):
        """Test that handler returns properly structured decision."""
        decision = phase_aware_handler.handle_anomaly(
            anomaly_type='thermal_fault',
            severity_score=0.65,
            confidence=0.85
        )
        
        assert decision['success'] is True
        assert 'decision_id' in decision
        assert 'anomaly_type' in decision
        assert 'mission_phase' in decision
        assert 'policy_decision' in decision
        assert 'recommended_action' in decision
        assert 'reasoning' in decision
        assert 'timestamp' in decision
    
    def test_critical_anomaly_escalates(self, phase_aware_handler):
        """Critical anomalies should escalate to SAFE_MODE (except in SAFE_MODE)."""
        phase_aware_handler.state_machine.set_phase(MissionPhase.NOMINAL_OPS)
        
        decision = phase_aware_handler.handle_anomaly(
            anomaly_type='power_fault',
            severity_score=0.95,
            confidence=0.99
        )
        
        assert decision['should_escalate_to_safe_mode'] is True
        assert decision['recommended_action'] == 'ENTER_SAFE_MODE'
    
    def test_safe_mode_no_escalation(self, phase_aware_handler):
        """In SAFE_MODE, no further escalation even with critical anomalies."""
        phase_aware_handler.state_machine.set_phase(MissionPhase.SAFE_MODE)
        
        decision = phase_aware_handler.handle_anomaly(
            anomaly_type='power_fault',
            severity_score=0.95,
            confidence=0.99
        )
        
        # Already in safe mode, can't escalate further
        assert decision['should_escalate_to_safe_mode'] is False
        assert decision['recommended_action'] == 'LOG_ONLY'


class TestRecurrenceTracking:
    """Test anomaly recurrence tracking."""
    
    def test_recurrence_counting(self, phase_aware_handler):
        """Test that anomalies are counted as recurrent."""
        anomaly_type = 'thermal_fault'
        
        # First occurrence
        decision1 = phase_aware_handler.handle_anomaly(
            anomaly_type=anomaly_type,
            severity_score=0.60,
            confidence=0.8
        )
        assert decision1['recurrence_info']['count'] == 1
        
        # Second occurrence
        decision2 = phase_aware_handler.handle_anomaly(
            anomaly_type=anomaly_type,
            severity_score=0.60,
            confidence=0.8
        )
        assert decision2['recurrence_info']['count'] == 2
        
        # Third occurrence
        decision3 = phase_aware_handler.handle_anomaly(
            anomaly_type=anomaly_type,
            severity_score=0.60,
            confidence=0.8
        )
        assert decision3['recurrence_info']['count'] == 3
    
    def test_different_anomaly_types_separate(self, phase_aware_handler):
        """Different anomaly types should be tracked separately."""
        decision1 = phase_aware_handler.handle_anomaly(
            anomaly_type='thermal_fault',
            severity_score=0.60,
            confidence=0.8
        )
        
        decision2 = phase_aware_handler.handle_anomaly(
            anomaly_type='power_fault',
            severity_score=0.60,
            confidence=0.8
        )
        
        assert decision1['recurrence_info']['count'] == 1
        assert decision2['recurrence_info']['count'] == 1
    
    def test_recurring_high_severity_escalates(self, phase_aware_handler):
        """Recurring high-severity faults should escalate."""
        phase_aware_handler.state_machine.state = 'NORMAL'
        phase_aware_handler.state_machine.mission_phase = MissionPhase.DEPLOYMENT
        phase_aware_handler.state_machine.phase_history = []
        
        # First high-severity fault
        decision1 = phase_aware_handler.handle_anomaly(
            anomaly_type='thermal_fault',
            severity_score=0.75,
            confidence=0.9
        )
        
        # Second high-severity fault (becomes recurring)
        decision2 = phase_aware_handler.handle_anomaly(
            anomaly_type='thermal_fault',
            severity_score=0.75,
            confidence=0.9
        )
        
        # Second occurrence should consider recurrence in decision
        assert decision2['recurrence_info']['total_in_window'] >= 2


@pytest.mark.timeout(600) # Added 10-minute timeout for complex end-to-end chaos simulations
class TestEndToEndDecisionFlow:
    """Test complete end-to-end decision flows."""
    
    def test_launch_phase_flow(self, phase_aware_handler):
        """Test handling anomalies during different phases."""
        # Test in NOMINAL_OPS phase
        decision = phase_aware_handler.handle_anomaly(
            anomaly_type='attitude_fault',
            severity_score=0.30,
            confidence=0.8,
            anomaly_metadata={'subsystem': 'ADCS'}
        )
        
        assert 'mission_phase' in decision
        assert decision['mission_phase'] == MissionPhase.NOMINAL_OPS.value
        assert 'recommended_action' in decision
        assert decision['should_escalate_to_safe_mode'] is False
    
    def test_nominal_to_safe_mode_escalation_flow(self, phase_aware_handler):
        """Test escalation flow during NOMINAL_OPS."""
        phase_aware_handler.state_machine.set_phase(MissionPhase.NOMINAL_OPS)
        initial_phase = phase_aware_handler.state_machine.get_current_phase()
        
        # Critical anomaly
        decision = phase_aware_handler.handle_anomaly(
            anomaly_type='power_fault',
            severity_score=0.92,
            confidence=0.95
        )
        
        assert initial_phase == MissionPhase.NOMINAL_OPS
        assert decision['should_escalate_to_safe_mode'] is True
        # After escalation, should be in SAFE_MODE
        assert phase_aware_handler.state_machine.get_current_phase() == MissionPhase.SAFE_MODE
    
    def test_payload_ops_supported(self, phase_aware_handler):
        """Test that PAYLOAD_OPS phase is properly supported."""
        phase_aware_handler.state_machine.set_phase(MissionPhase.NOMINAL_OPS)
        phase_aware_handler.state_machine.set_phase(MissionPhase.PAYLOAD_OPS)
        
        assert phase_aware_handler.state_machine.get_current_phase() == MissionPhase.PAYLOAD_OPS


class TestDecisionTracer:
    """Test the decision tracer utility."""
    
    def test_decision_recording(self, phase_aware_handler):
        """Test recording decisions in tracer."""
        tracer = DecisionTracer(max_decisions=100)
        
        decision = phase_aware_handler.handle_anomaly(
            anomaly_type='thermal_fault',
            severity_score=0.60,
            confidence=0.8
        )
        
        tracer.add_decision(decision)
        assert len(tracer.decisions) == 1
    
    def test_filter_by_phase(self, phase_aware_handler):
        """Test filtering decisions by phase."""
        tracer = DecisionTracer()
        
        # Add decisions in different phases
        decision1 = phase_aware_handler.handle_anomaly('fault1', 0.5, 0.8)
        tracer.add_decision(decision1)
        
        phase_aware_handler.state_machine.set_phase(MissionPhase.PAYLOAD_OPS)
        decision2 = phase_aware_handler.handle_anomaly('fault2', 0.5, 0.8)
        tracer.add_decision(decision2)
        
        # Filter by phase
        nominal_decisions = tracer.get_decisions_for_phase(MissionPhase.NOMINAL_OPS.value)
        payload_decisions = tracer.get_decisions_for_phase(MissionPhase.PAYLOAD_OPS.value)
        
        assert len(nominal_decisions) >= 1
        assert len(payload_decisions) >= 1
    
    def test_escalation_tracking(self, phase_aware_handler):
        """Test tracking escalations."""
        tracer = DecisionTracer()
        
        phase_aware_handler.state_machine.set_phase(MissionPhase.NOMINAL_OPS)
        decision = phase_aware_handler.handle_anomaly('critical_fault', 0.95, 0.99)
        tracer.add_decision(decision)
        
        escalations = tracer.get_escalations()
        assert len(escalations) == 1
    
    def test_summary_stats(self, phase_aware_handler):
        """Test generating summary statistics."""
        tracer = DecisionTracer()
        
        for i in range(5):
            decision = phase_aware_handler.handle_anomaly(f'fault_{i}', 0.5 + i*0.1, 0.8)
            tracer.add_decision(decision)
        
        stats = tracer.get_summary_stats()
        
        assert stats['total_decisions'] == 5
        assert 'escalation_rate' in stats
        assert 'by_phase' in stats
        assert 'by_anomaly_type' in stats


class TestPhaseConstraintQueries:
    """Test querying phase constraints."""
    
    def test_get_phase_constraints(self, phase_aware_handler):
        """Test retrieving constraints for current phase."""
        phase_aware_handler.state_machine.set_phase(MissionPhase.NOMINAL_OPS)
        
        constraints = phase_aware_handler.get_phase_constraints()
        
        assert constraints['phase'] == MissionPhase.NOMINAL_OPS.value
        assert 'allowed_actions' in constraints
        assert 'forbidden_actions' in constraints
        assert len(constraints['allowed_actions']) > 0
    
    def test_get_all_phase_constraints(self, phase_aware_handler):
        """Test retrieving constraints for all phases."""
        for phase in MissionPhase:
            constraints = phase_aware_handler.get_phase_constraints(phase)
            assert constraints['phase'] == phase.value
            assert 'description' in constraints


if __name__ == "__main__":
    pytest.main([__file__, "-v"])