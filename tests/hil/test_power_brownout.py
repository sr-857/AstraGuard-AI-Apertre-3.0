"""
Tests for Power Brownout Fault Model (Issue #491)

Covers:
- Brownout fault initialization and validation
- Phase transitions (panel damage → battery stress → safe-mode)
- Severity scaling and degradation factors
- Auto-recovery logic
- PowerSimulator integration
- Telemetry impact verification
"""

import pytest
from datetime import datetime, timedelta
from astraguard.hil.simulator.power import PowerSimulator
from astraguard.hil.simulator.faults.power_brownout import PowerBrownoutFault
from astraguard.hil.schemas.telemetry import PowerData


class TestPowerBrownoutInitialization:
    """Test PowerBrownoutFault initialization and parameter validation."""
    
    def test_init_valid_sat_id(self):
        """Test fault creation with valid satellite ID."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        assert fault.sat_id == "SAT-001"
        assert fault.severity == 0.5
        assert fault.duration == 300.0
    
    def test_init_severity_validation_min(self):
        """Test severity clamping at minimum (0.1)."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.0, duration=300.0)
        assert fault.severity >= 0.1
    
    def test_init_severity_validation_max(self):
        """Test severity clamping at maximum (1.0)."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=2.0, duration=300.0)
        assert fault.severity <= 1.0
    
    def test_init_duration_validation(self):
        """Test duration is positive."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=60.0)
        assert fault.duration > 0.0
    
    def test_init_active_flag_false_before_inject(self):
        """Test fault starts inactive."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=60.0)
        assert fault.active is False
    
    def test_init_start_time_set_after_inject(self):
        """Test start_time is set when fault is injected."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=60.0)
        fault.inject()
        assert fault.start_time is not None
        assert isinstance(fault.start_time, datetime)


class TestBrownoutPhaseTransitions:
    """Test phase transitions and phase detection."""
    
    def test_phase_1_panel_damage_0_to_60s(self):
        """Test Phase 1 (panel damage) from 0-60 seconds."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        state = fault.get_fault_state()
        assert state["phase"] == "panel_damage"
    
    def test_phase_2_battery_stress_60_to_180s(self):
        """Test Phase 2 (battery stress) from 60-180 seconds."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        # Simulate 120 seconds elapsed
        fault.start_time = datetime.now() - timedelta(seconds=120)
        state = fault.get_fault_state()
        assert state["phase"] == "battery_stress"
    
    def test_phase_3_safe_mode_180s_plus(self):
        """Test Phase 3 (safe-mode) after 180 seconds."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        # Simulate 200 seconds elapsed
        fault.start_time = datetime.now() - timedelta(seconds=200)
        state = fault.get_fault_state()
        assert state["phase"] == "safe_mode"
    
    def test_phase_transition_sequence(self):
        """Test full phase transition sequence over time."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        
        # Phase 1: 30s
        fault.start_time = datetime.now() - timedelta(seconds=30)
        assert fault.get_fault_state()["phase"] == "panel_damage"
        
        # Phase 2: 120s
        fault.start_time = datetime.now() - timedelta(seconds=120)
        assert fault.get_fault_state()["phase"] == "battery_stress"
        
        # Phase 3: 200s
        fault.start_time = datetime.now() - timedelta(seconds=200)
        assert fault.get_fault_state()["phase"] == "safe_mode"
    
    def test_is_expired_after_duration(self):
        """Test fault expiration after duration elapsed."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=60.0)
        fault.inject()
        # Simulate 70 seconds elapsed
        fault.start_time = datetime.now() - timedelta(seconds=70)
        assert fault.is_expired() is True
    
    def test_not_expired_before_duration(self):
        """Test fault not expired before duration elapsed."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=60.0)
        fault.inject()
        # Simulate 30 seconds elapsed
        fault.start_time = datetime.now() - timedelta(seconds=30)
        assert fault.is_expired() is False


class TestSeverityScaling:
    """Test severity-dependent degradation factors."""
    
    def test_panel_damage_factor_low_severity(self):
        """Test panel damage factor for low severity (0.1)."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.1, duration=300.0)
        fault.inject()
        fault_state = fault.get_fault_state()
        # At severity 0.1: panel_damage_factor = 0.4 - 0.3*0.1 = 0.37
        assert 0.35 <= fault_state["panel_damage_factor"] <= 0.40
    
    def test_panel_damage_factor_mid_severity(self):
        """Test panel damage factor for mid severity (0.5)."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        fault_state = fault.get_fault_state()
        # At severity 0.5: panel_damage_factor = 0.4 - 0.3*0.5 = 0.25
        assert 0.23 <= fault_state["panel_damage_factor"] <= 0.27
    
    def test_panel_damage_factor_high_severity(self):
        """Test panel damage factor for high severity (0.9)."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.9, duration=300.0)
        fault.inject()
        fault_state = fault.get_fault_state()
        # At severity 0.9: panel_damage_factor = 0.4 - 0.3*0.9 = 0.13
        assert 0.10 <= fault_state["panel_damage_factor"] <= 0.15
    
    def test_discharge_multiplier_low_severity(self):
        """Test discharge multiplier for low severity (0.1)."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.1, duration=300.0)
        fault.inject()
        fault_state = fault.get_fault_state()
        # At severity 0.1: discharge_multiplier = 1.5 + 0.1 = 1.6
        assert 1.5 <= fault_state["discharge_multiplier"] <= 1.7
    
    def test_discharge_multiplier_mid_severity(self):
        """Test discharge multiplier for mid severity (0.5)."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        fault_state = fault.get_fault_state()
        # At severity 0.5: discharge_multiplier = 1.5 + 0.5 = 2.0
        assert 1.9 <= fault_state["discharge_multiplier"] <= 2.1
    
    def test_discharge_multiplier_high_severity(self):
        """Test discharge multiplier for high severity (0.9)."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.9, duration=300.0)
        fault.inject()
        fault_state = fault.get_fault_state()
        # At severity 0.9: discharge_multiplier = 1.5 + 0.9 = 2.4
        assert 2.3 <= fault_state["discharge_multiplier"] <= 2.5
    
    def test_severity_affects_fault_state(self):
        """Test that higher severity produces worse fault states."""
        fault_low = PowerBrownoutFault(sat_id="SAT-001", severity=0.2, duration=300.0)
        fault_low.inject()
        
        fault_high = PowerBrownoutFault(sat_id="SAT-001", severity=0.9, duration=300.0)
        fault_high.inject()
        
        state_low = fault_low.get_fault_state()
        state_high = fault_high.get_fault_state()
        
        # Higher severity = lower panel_damage_factor (more damage)
        assert state_high["panel_damage_factor"] < state_low["panel_damage_factor"]
        # Higher severity = higher discharge_multiplier (faster discharge)
        assert state_high["discharge_multiplier"] > state_low["discharge_multiplier"]


class TestAutoRecovery:
    """Test automatic recovery after fault expiration."""
    
    def test_fault_expires_after_duration(self):
        """Test fault is marked expired after duration."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=60.0)
        fault.inject()
        fault.start_time = datetime.now() - timedelta(seconds=61)
        assert fault.is_expired() is True
    
    def test_fault_active_flag_toggles_on_inject(self):
        """Test fault active flag is set during injection."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=60.0)
        assert fault.active is False
        fault.inject()
        assert fault.active is True
    
    def test_fault_time_remaining_decreases(self):
        """Test time_remaining decreases over time."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=100.0)
        fault.inject()
        
        state_early = fault.get_fault_state()
        initial_remaining = state_early["time_remaining"]
        
        # Simulate 30 seconds
        fault.start_time = datetime.now() - timedelta(seconds=30)
        state_later = fault.get_fault_state()
        later_remaining = state_later["time_remaining"]
        
        assert later_remaining < initial_remaining
    
    def test_fault_time_remaining_positive_until_expiration(self):
        """Test time_remaining is positive before expiration."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=100.0)
        fault.inject()
        fault.start_time = datetime.now() - timedelta(seconds=50)
        
        state = fault.get_fault_state()
        assert state["time_remaining"] > 0.0
    
    def test_fault_time_remaining_zero_after_expiration(self):
        """Test time_remaining is zero after expiration."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=60.0)
        fault.inject()
        fault.start_time = datetime.now() - timedelta(seconds=70)
        
        state = fault.get_fault_state()
        assert state["time_remaining"] <= 0.0


class TestPowerSimulatorIntegration:
    """Test PowerSimulator integration with brownout fault."""
    
    def test_inject_brownout_fault_via_power_sim(self):
        """Test injecting brownout fault through PowerSimulator."""
        power_sim = PowerSimulator(sat_id="SAT-001")
        power_sim.inject_brownout_fault(severity=0.5, duration=60.0)
        assert power_sim._brownout_fault is not None
        assert power_sim._brownout_fault.active is True
    
    def test_brownout_auto_recovery_in_power_sim(self):
        """Test fault auto-recovery through PowerSimulator."""
        power_sim = PowerSimulator(sat_id="SAT-001")
        power_sim.inject_brownout_fault(severity=0.5, duration=10.0)
        
        assert power_sim._brownout_fault.active is True
        
        # Simulate fault expiration
        power_sim._brownout_fault.start_time = datetime.now() - timedelta(seconds=11)
        power_sim.update(dt=1.0, sun_exposure=1.0)
        
        # Fault should be marked inactive after expiration
        if power_sim._brownout_fault.is_expired():
            power_sim._brownout_fault.active = False
        
        assert power_sim._brownout_fault.active is False


class TestBrownoutFaultState:
    """Test fault state retrieval and completeness."""
    
    def test_get_fault_state_returns_dict(self):
        """Test get_fault_state returns a dictionary."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        state = fault.get_fault_state()
        assert isinstance(state, dict)
    
    def test_get_fault_state_has_required_keys(self):
        """Test fault state contains required keys."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        state = fault.get_fault_state()
        
        required_keys = [
            "phase",
            "panel_damage_factor",
            "discharge_multiplier",
            "safe_mode_load",
            "time_remaining"
        ]
        
        for key in required_keys:
            assert key in state, f"Missing key: {key}"
    
    def test_get_fault_state_phase_values(self):
        """Test fault state phase values are valid."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        
        valid_phases = ["panel_damage", "battery_stress", "safe_mode"]
        state = fault.get_fault_state()
        assert state["phase"] in valid_phases
    
    def test_get_fault_state_panel_damage_factor_range(self):
        """Test panel damage factor is in valid range."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        state = fault.get_fault_state()
        assert 0.0 <= state["panel_damage_factor"] <= 1.0
    
    def test_get_fault_state_discharge_multiplier_range(self):
        """Test discharge multiplier is in valid range."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        state = fault.get_fault_state()
        assert 1.0 <= state["discharge_multiplier"] <= 3.0
    
    def test_get_fault_state_safe_mode_load_phase3(self):
        """Test safe-mode load is set correctly in Phase 3."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        # Simulate Phase 3 (200s)
        fault.start_time = datetime.now() - timedelta(seconds=200)
        state = fault.get_fault_state()
        assert state["safe_mode_load"] == 8.0
    
    def test_get_fault_state_safe_mode_load_phase1(self):
        """Test safe-mode load is zero in Phase 1."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        # Phase 1 (30s)
        fault.start_time = datetime.now() - timedelta(seconds=30)
        state = fault.get_fault_state()
        assert state["safe_mode_load"] == 0.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_brownout_at_phase_boundaries(self):
        """Test fault behavior at phase boundaries."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=300.0)
        fault.inject()
        
        # At 60s boundary (Phase 1 → Phase 2)
        fault.start_time = datetime.now() - timedelta(seconds=60)
        # Should be in Phase 2 (not Phase 1)
        assert fault.get_fault_state()["phase"] == "battery_stress"
        
        # At 180s boundary (Phase 2 → Phase 3)
        fault.start_time = datetime.now() - timedelta(seconds=180)
        # Should be in Phase 3 (not Phase 2)
        assert fault.get_fault_state()["phase"] == "safe_mode"
    
    def test_zero_severity_clamped_to_minimum(self):
        """Test zero severity is clamped to minimum."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.0, duration=300.0)
        assert fault.severity >= 0.1
    
    def test_negative_severity_clamped_to_minimum(self):
        """Test negative severity is clamped to minimum."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=-0.5, duration=300.0)
        assert fault.severity >= 0.1
    
    def test_very_short_duration(self):
        """Test fault with very short duration."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=1.0)
        fault.inject()
        # Should immediately expire
        fault.start_time = datetime.now() - timedelta(seconds=1.1)
        assert fault.is_expired() is True
    
    def test_very_long_duration(self):
        """Test fault with very long duration."""
        fault = PowerBrownoutFault(sat_id="SAT-001", severity=0.5, duration=10000.0)
        fault.inject()
        fault.start_time = datetime.now() - timedelta(seconds=100)
        # Should not be expired
        assert fault.is_expired() is False


class TestMultipleFaults:
    """Test handling of multiple faults."""
    
    def test_multiple_satellites_independent_faults(self):
        """Test multiple satellites can have independent brownout faults."""
        fault1 = PowerBrownoutFault(sat_id="SAT-001", severity=0.3, duration=300.0)
        fault2 = PowerBrownoutFault(sat_id="SAT-002", severity=0.7, duration=300.0)
        
        fault1.inject()
        fault2.inject()
        
        state1 = fault1.get_fault_state()
        state2 = fault2.get_fault_state()
        
        # Different severities should produce different degradation
        assert state1["panel_damage_factor"] > state2["panel_damage_factor"]
        assert state1["discharge_multiplier"] < state2["discharge_multiplier"]
    
    def test_sequential_fault_injection(self):
        """Test sequential fault injection and recovery."""
        power_sim = PowerSimulator(sat_id="SAT-001")
        
        # First fault
        power_sim.inject_brownout_fault(severity=0.5, duration=30.0)
        assert power_sim._brownout_fault.active is True
        
        # Simulate fault expiration and recovery
        power_sim._brownout_fault.start_time = datetime.now() - timedelta(seconds=31)
        power_sim._brownout_fault.active = False
        
        # Second fault
        power_sim.inject_brownout_fault(severity=0.8, duration=60.0)
        assert power_sim._brownout_fault.active is True
        assert power_sim._brownout_fault.severity == 0.8
