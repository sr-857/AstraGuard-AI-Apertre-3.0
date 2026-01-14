"""Tests for HIL attitude simulator."""

import pytest
import numpy as np
from astraguard.hil.simulator.attitude import AttitudeSimulator
from astraguard.hil.schemas.telemetry import AttitudeData


class TestAttitudeSimulatorInitialization:
    """Tests for AttitudeSimulator initialization and nominal pointing."""
    
    def test_initialization(self):
        """Test attitude simulator initializes with nadir pointing."""
        sim = AttitudeSimulator("TEST-SAT")
        assert sim.sat_id == "TEST-SAT"
        assert sim._mode == "nadir_pointing"
        assert sim._fault_active is False
    
    def test_quaternion_normalized(self):
        """Test that quaternion remains normalized."""
        sim = AttitudeSimulator("TEST-SAT")
        q_norm = np.linalg.norm(sim._quaternion)
        assert abs(q_norm - 1.0) < 1e-6
    
    def test_nadir_pointing_initial(self):
        """Test initial nadir pointing error is very small."""
        sim = AttitudeSimulator("TEST-SAT")
        attitude = sim.get_attitude_data()
        
        assert isinstance(attitude, AttitudeData)
        assert abs(attitude.nadir_pointing_error_deg) < 1.0


class TestAttitudeNominalPropagation:
    """Tests for nominal attitude dynamics."""
    
    def test_update_preserves_quaternion_norm(self):
        """Test that quaternion remains normalized after update."""
        sim = AttitudeSimulator("TEST-SAT")
        
        for _ in range(10):
            sim.update(dt=1.0)
            q_norm = np.linalg.norm(sim._quaternion)
            assert abs(q_norm - 1.0) < 1e-6
    
    def test_nominal_angular_velocity_damping(self):
        """Test that angular velocity damps in nominal mode."""
        sim = AttitudeSimulator("TEST-SAT")
        
        # Set initial angular velocity
        sim._angular_velocity = np.array([0.1, 0.1, 0.1])
        initial_mag = np.linalg.norm(sim._angular_velocity)
        
        # Update several times
        for _ in range(5):
            sim.update(dt=1.0)
        
        final_mag = np.linalg.norm(sim._angular_velocity)
        
        # Should damp down
        assert final_mag < initial_mag
    
    def test_nadir_error_small_in_nominal_mode(self):
        """Test that nadir error stays small during nominal operation."""
        sim = AttitudeSimulator("TEST-SAT")
        
        for _ in range(20):
            sim.update(dt=1.0)
            attitude = sim.get_attitude_data()
            assert attitude.nadir_pointing_error_deg < 5.0  # Should stay well-pointed


class TestTumbleFault:
    """Tests for tumble fault injection and dynamics."""
    
    def test_tumble_fault_injection(self):
        """Test that tumble fault activates tumble mode."""
        sim = AttitudeSimulator("TUMBLE-TEST")
        sim.inject_tumble_fault()
        
        assert sim._fault_active is True
        assert sim._mode == "tumble"
        assert sim._tumble_start is not None
    
    def test_tumble_increases_angular_velocity(self):
        """Test that tumble mode increases angular velocity."""
        sim = AttitudeSimulator("TUMBLE-TEST")
        sim.inject_tumble_fault()
        
        # Update several times in tumble mode
        for _ in range(10):
            sim.update(dt=1.0)
        
        # Angular velocity magnitude should be significant
        omega_mag = np.linalg.norm(sim._angular_velocity)
        assert omega_mag > 0.01  # Should have noticeable rotation
    
    def test_tumble_increases_nadir_error(self):
        """Test that tumble causes large nadir pointing errors."""
        sim = AttitudeSimulator("TUMBLE-TEST")
        
        # Get initial error (should be small)
        initial_attitude = sim.get_attitude_data()
        initial_error = initial_attitude.nadir_pointing_error_deg
        
        # Inject tumble and update
        sim.inject_tumble_fault()
        for _ in range(15):
            sim.update(dt=1.0)
        
        # Get final error (should be large)
        final_attitude = sim.get_attitude_data()
        final_error = final_attitude.nadir_pointing_error_deg
        
        # Tumbling should increase pointing error (dynamics dependent on time/rates)
        assert final_error > initial_error
        assert final_error > 5.0  # Should have meaningful error
    
    def test_tumble_duration_tracking(self):
        """Test that tumble duration is tracked correctly."""
        import time
        
        sim = AttitudeSimulator("TUMBLE-TEST")
        sim.inject_tumble_fault()
        
        initial_duration = sim.get_tumble_duration()
        assert initial_duration >= 0.0  # Should be very close to 0
        
        time.sleep(0.1)
        
        later_duration = sim.get_tumble_duration()
        assert later_duration > 0.05  # At least 50ms passed


class TestRecovery:
    """Tests for attitude control recovery."""
    
    def test_recovery_clears_fault_flag(self):
        """Test that recovery clears fault active flag."""
        sim = AttitudeSimulator("RECOVERY-TEST")
        sim.inject_tumble_fault()
        assert sim._fault_active is True
        
        sim.recover_control()
        assert sim._fault_active is False
        assert sim._mode == "nadir_pointing"
    
    def test_recovery_damps_angular_velocity(self):
        """Test that recovery reduces angular velocity."""
        sim = AttitudeSimulator("RECOVERY-TEST")
        sim.inject_tumble_fault()
        
        # Tumble for a bit
        for _ in range(10):
            sim.update(dt=1.0)
        
        tumble_omega = np.linalg.norm(sim._angular_velocity)
        
        # Recover
        sim.recover_control()
        recovered_omega = np.linalg.norm(sim._angular_velocity)
        
        assert recovered_omega < tumble_omega * 0.1


class TestStatusReporting:
    """Tests for status and diagnostic information."""
    
    def test_get_status_nominal(self):
        """Test status reporting in nominal mode."""
        sim = AttitudeSimulator("STATUS-TEST")
        status = sim.get_status()
        
        assert status["mode"] == "nadir_pointing"
        assert status["fault_active"] is False
        assert abs(status["quaternion_norm"] - 1.0) < 1e-6
        assert status["angular_velocity_magnitude"] >= 0
        assert status["tumble_duration"] == 0.0
    
    def test_get_status_tumble(self):
        """Test status reporting during tumble."""
        sim = AttitudeSimulator("STATUS-TEST")
        sim.inject_tumble_fault()
        
        for _ in range(5):
            sim.update(dt=1.0)
        
        status = sim.get_status()
        
        assert status["mode"] == "tumble"
        assert status["fault_active"] is True
        assert status["tumble_duration"] > 0.0
        assert status["angular_velocity_magnitude"] > 0.01


class TestAttitudeDataOutput:
    """Tests for AttitudeData model output."""
    
    def test_attitude_data_valid_quaternion_length(self):
        """Test that attitude data has valid quaternion."""
        sim = AttitudeSimulator("DATA-TEST")
        attitude = sim.get_attitude_data()
        
        assert len(attitude.quaternion) == 4
        # Quaternion should be normalized
        q_norm = np.linalg.norm(attitude.quaternion)
        assert abs(q_norm - 1.0) < 1e-5
    
    def test_attitude_data_valid_angular_velocity_length(self):
        """Test that attitude data has valid angular velocity."""
        sim = AttitudeSimulator("DATA-TEST")
        attitude = sim.get_attitude_data()
        
        assert len(attitude.angular_velocity) == 3
    
    def test_nadir_error_range(self):
        """Test that nadir error is in valid range."""
        sim = AttitudeSimulator("DATA-TEST")
        
        for _ in range(50):
            attitude = sim.get_attitude_data()
            assert 0 <= attitude.nadir_pointing_error_deg <= 180


class TestIntegrationWithBase:
    """Tests for integration with StubSatelliteSimulator."""
    
    @pytest.mark.asyncio
    async def test_attitude_simulator_in_base(self):
        """Test that attitude simulator is used in telemetry generation."""
        from astraguard.hil.simulator.base import StubSatelliteSimulator
        
        sim = StubSatelliteSimulator("INTEGRATION-TEST")
        
        # Generate multiple telemetry packets
        packets = []
        for _ in range(5):
            packet = await sim.generate_telemetry()
            packets.append(packet)
        
        # Check that attitude data is structured correctly
        for packet in packets:
            assert len(packet.attitude.quaternion) == 4
            assert len(packet.attitude.angular_velocity) == 3
            assert 0 <= packet.attitude.nadir_pointing_error_deg <= 180
    
    @pytest.mark.asyncio
    async def test_attitude_fault_injection(self):
        """Test that attitude_desync fault is properly injected."""
        from astraguard.hil.simulator.base import StubSatelliteSimulator
        
        sim = StubSatelliteSimulator("FAULT-TEST")
        sim.start()
        
        # Generate normal telemetry
        normal_packet = await sim.generate_telemetry()
        normal_error = normal_packet.attitude.nadir_pointing_error_deg
        
        # Inject attitude fault
        await sim.inject_fault("attitude_desync")
        
        # Generate faulted telemetry
        error_accumulation = []
        for _ in range(10):
            packet = await sim.generate_telemetry()
            error_accumulation.append(packet.attitude.nadir_pointing_error_deg)
        
        final_error = error_accumulation[-1]
        
        # Error should increase during tumble
        assert final_error > normal_error + 5.0
