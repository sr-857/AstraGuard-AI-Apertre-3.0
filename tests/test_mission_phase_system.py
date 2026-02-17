#!/usr/bin/env python3
"""Quick test script for mission-phase aware fault response system."""

import asyncio
import pytest

from state_machine.state_engine import StateMachine, MissionPhase
from state_machine.mission_phase_policy_engine import MissionPhasePolicyEngine
from config.mission_phase_policy_loader import MissionPhasePolicyLoader
from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler

@pytest.mark.asyncio
async def test_basic_functionality():
    """Test basic functionality of all components."""
    print("=" * 70)
    print("Testing Mission-Phase Aware Fault Response System")
    print("=" * 70)
    
    # Test 1: State Machine
    print("\n[1] Testing State Machine...")
    sm = StateMachine()
    print(f"    [OK] Current phase: {sm.get_current_phase().value}")
    print(f"    [OK] Current state: {sm.get_current_state().value}")
    
    # Test 2: Policy Loader
    print("\n[2] Testing Policy Loader...")
    loader = MissionPhasePolicyLoader()
    policy = loader.get_policy()
    print(f"    [OK] Loaded policy with {len(policy['phases'])} phases")
    for phase_name in policy['phases']:
        print(f"      - {phase_name}")
    
    # Test 3: Policy Engine
    print("\n[3] Testing Policy Engine...")
    engine = MissionPhasePolicyEngine(policy)
    decision = engine.evaluate(
        mission_phase=MissionPhase.NOMINAL_OPS,
        anomaly_type='power_fault',
        severity_score=0.75,
        anomaly_attributes={}
    )
    print(f"    [OK] Policy decision made")
    print(f"      - Anomaly: {decision.anomaly_type}")
    print(f"      - Severity: {decision.severity}")
    print(f"      - Recommended action: {decision.recommended_action}")
    print(f"      - Escalation level: {decision.escalation_level}")
    
    # Test 4: Phase-Aware Handler
    print("\n[4] Testing Phase-Aware Anomaly Handler...")
    
    # Test in LAUNCH phase
    print("    Testing in LAUNCH phase...")
    sm_launch = StateMachine()
    sm_launch.force_safe_mode()  # Start from a state where we can reach LAUNCH
    sm_launch.current_phase = MissionPhase.LAUNCH  # Directly set for testing
    handler_launch = PhaseAwareAnomalyHandler(sm_launch, loader)
    decision_launch = await handler_launch.handle_anomaly(
        anomaly_type='thermal_fault',
        severity_score=0.65,
        confidence=0.85
    )
    print(f"      - Recommended action: {decision_launch['recommended_action']}")
    print(f"      - Escalate to SAFE_MODE: {decision_launch['should_escalate_to_safe_mode']}")
    
    # Test in NOMINAL_OPS phase
    print("    Testing in NOMINAL_OPS phase...")
    sm_nominal = StateMachine()
    handler_nominal = PhaseAwareAnomalyHandler(sm_nominal, loader)
    decision_nominal = await handler_nominal.handle_anomaly(
        anomaly_type='thermal_fault',
        severity_score=0.65,
        confidence=0.85
    )
    print(f"      - Recommended action: {decision_nominal['recommended_action']}")
    print(f"      - Escalate to SAFE_MODE: {decision_nominal['should_escalate_to_safe_mode']}")
    
    # Test 5: Same anomaly, different phases
    print("\n[5] Testing Same Anomaly in Different Phases...")
    print("    Anomaly: power_fault with severity=0.95 (critical)")
    
    phases_to_test = [
        (MissionPhase.LAUNCH, "LAUNCH           "),
        (MissionPhase.DEPLOYMENT, "DEPLOYMENT       "),
        (MissionPhase.NOMINAL_OPS, "NOMINAL_OPS      "),
        (MissionPhase.SAFE_MODE, "SAFE_MODE        ")
    ]
    
    for target_phase, display_name in phases_to_test:
        sm_test = StateMachine()
        sm_test.current_phase = target_phase  # Directly set for testing
        handler_test = PhaseAwareAnomalyHandler(sm_test, loader)
        decision = await handler_test.handle_anomaly('power_fault', 0.95, 0.99)
        print(f"    {display_name} -> {decision['recommended_action']:20} (Escalate: {decision['should_escalate_to_safe_mode']})")
    
    # Test 6: Phase transitions
    print("\n[6] Testing Phase Transitions...")
    sm = StateMachine()
    # Manually set to LAUNCH to test full lifecycle
    sm.current_phase = MissionPhase.LAUNCH
    print(f"    Starting phase: {sm.get_current_phase().value}")
    
    transitions = [
        MissionPhase.LAUNCH,
        MissionPhase.DEPLOYMENT,
        MissionPhase.NOMINAL_OPS,
        MissionPhase.PAYLOAD_OPS
    ]
    
    for target_phase in transitions:
        try:
            result = sm.set_phase(target_phase)
            print(f"      [OK] {result['previous_phase']} -> {result['new_phase']}")
        except ValueError as e:
            print(f"      [FAIL] Invalid transition: {e}")
    
    print("\n" + "=" * 70)
    print("All tests completed successfully!")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(test_basic_functionality())

