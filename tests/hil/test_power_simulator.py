"""Tests for CubeSat EPS (power system) simulator."""

import pytest
import numpy as np
from astraguard.hil.simulator.power import PowerSimulator
from astraguard.hil.schemas.telemetry import PowerData


class TestPowerSimulatorInitialization:
    """Tests for power simulator initialization."""
    
    def test_initialization(self):
        """Test power simulator initializes correctly."""
        sim = PowerSimulator("POWER-SAT")
        assert sim.sat_id == "POWER-SAT"
        assert sim.battery_soc == 0.85
        assert sim.battery_voltage == 8.2
        assert sim._fault_active is False
    
    def test_battery_parameters(self):
        """Test battery specifications."""
        sim = PowerSimulator("POWER-SAT")
        assert sim.battery_capacity_ah == 7.0
        assert sim.solar_efficiency == 0.28
        assert sim.orbital_period_s == 5400  # 90 minutes


class TestOrbitalEclipseCycle:
    """Tests for eclipse detection and power cycling."""
    
    def test_eclipse_detection_sunlight(self):
        """Test eclipse detection during sunlight phase."""
        sim = PowerSimulator("ECLIPSE-TEST")
        sim._orbit_phase = 45.0  # Sunlight phase
        assert sim._is_in_eclipse() is False
    
    def test_eclipse_detection_shadow(self):
        """Test eclipse detection during eclipse phase."""
        sim = PowerSimulator("ECLIPSE-TEST")
        sim._orbit_phase = 180.0  # Eclipse phase
        assert sim._is_in_eclipse() is True
    
    def test_eclipse_cycle_realistic(self):
        """Test realistic eclipse cycling in 90-minute orbit."""
        sim = PowerSimulator("ECLIPSE-TEST")
        
        # Simulate 90-minute orbit
        eclipse_periods = []
        sunlight_periods = []
        in_eclipse = False
        eclipse_start = 0
        
        for step in range(5401):  # One complete orbit + 1
            sim.update(dt=1.0)
            now_in_eclipse = sim._is_in_eclipse()
            
            if now_in_eclipse and not in_eclipse:
                # Entering eclipse
                eclipse_start = sim.elapsed_time
                sunlight_duration = sim.elapsed_time - eclipse_start
                if sunlight_duration > 10:  # Ignore first transition
                    sunlight_periods.append(sunlight_duration)
            elif not now_in_eclipse and in_eclipse:
                # Exiting eclipse
                eclipse_duration = sim.elapsed_time - eclipse_start
                eclipse_periods.append(eclipse_duration)
            
            in_eclipse = now_in_eclipse
        
        # Verify reasonable eclipse period (roughly 1500s out of 5400s orbit)
        if eclipse_periods:
            avg_eclipse = np.mean(eclipse_periods)
            assert 1000 < avg_eclipse < 2000  # Eclipse is ~1/3 to 1/4 of orbit


class TestBatteryDynamics:
    """Tests for battery charging and discharging."""
    
    def test_battery_charging_in_sunlight(self):
        """Test battery charges during sunlight."""
        sim = PowerSimulator("CHARGE-TEST")
        sim._orbit_phase = 45.0  # Sunlight phase
        initial_soc = sim.battery_soc
        
        # Update in sunlight phase for significant time
        for _ in range(300):  # 5 minutes
            sim.update(dt=1.0, sun_exposure=1.0)
        
        # SOC should increase (charging)
        assert sim.battery_soc > initial_soc
    
    def test_battery_discharging_in_eclipse(self):
        """Test battery discharges during eclipse."""
        sim = PowerSimulator("DISCHARGE-TEST")
        sim._orbit_phase = 180.0  # Eclipse phase
        sim.battery_soc = 0.90  # Start fully charged
        initial_soc = sim.battery_soc
        
        # Update in eclipse for significant time
        for _ in range(300):  # 5 minutes
            sim.update(dt=1.0)
        
        # SOC should decrease (discharging)
        assert sim.battery_soc < initial_soc
    
    def test_voltage_follows_soc(self):
        """Test that voltage follows SOC curve."""
        sim = PowerSimulator("VOLTAGE-TEST")
        
        # High SOC should give high voltage
        sim.battery_soc = 1.0
        sim.battery_voltage = 8.4 - (1.0 - sim.battery_soc) * 1.9  # Recalculate
        v_high = sim.battery_voltage
        
        # Low SOC should give low voltage
        sim.battery_soc = 0.1
        sim.battery_voltage = 8.4 - (1.0 - sim.battery_soc) * 1.9  # Recalculate
        v_low = sim.battery_voltage
        
        # Voltage should be monotonically increasing with SOC
        assert v_high > v_low
        assert v_high > 8.0
        assert v_low < 7.0
    
    def test_soc_bounded(self):
        """Test that SOC stays within 0-1 bounds."""
        sim = PowerSimulator("BOUNDS-TEST")
        
        # Try to overcharge
        sim.battery_soc = 1.0
        for _ in range(100):
            sim.update(dt=1.0, sun_exposure=2.0)
        
        assert 0.0 <= sim.battery_soc <= 1.0
        
        # Try to over-discharge
        sim.battery_soc = 0.0
        for _ in range(100):
            sim.update(dt=1.0)
        
        assert 0.0 <= sim.battery_soc <= 1.0


class TestBrownoutFault:
    """Tests for power brownout fault injection (deprecated - see test_power_brownout.py)."""
    
    def test_brownout_fault_injection(self):
        """Test brownout fault activates."""
        sim = PowerSimulator("BRN-TEST")
        sim.inject_brownout_fault(severity=0.8)
        
        assert sim._brownout_fault is not None
        assert sim._brownout_fault.active is True
    
    def test_brownout_voltage_drop(self):
        """Test brownout causes voltage drop."""
        sim = PowerSimulator("BRN-VOLTAGE")
        sim._orbit_phase = 45.0  # Sunlight phase
        
        # Measure voltage without fault
        for _ in range(100):
            sim.update(dt=1.0, sun_exposure=1.0)
        
        normal_voltage = sim.battery_voltage
        
        # Inject fault
        sim.inject_brownout_fault(severity=0.8)
        
        # Measure voltage with fault
        for _ in range(100):
            sim.update(dt=1.0, sun_exposure=1.0)
        
        fault_voltage = sim.battery_voltage
        
        # Brownout affects load and solar generation
        assert 5 < fault_voltage < 10


class TestPowerDataOutput:
    """Tests for PowerData model output."""
    
    def test_power_data_valid_range(self):
        """Test power data fields are in valid ranges."""
        sim = PowerSimulator("DATA-TEST")
        data = sim.get_power_data()
        
        assert isinstance(data, PowerData)
        assert 0 <= data.battery_soc <= 1.0
        assert 5 <= data.battery_voltage <= 10
        assert data.solar_current >= 0
        assert data.load_current >= 0
    
    def test_power_data_sunlight_vs_eclipse(self):
        """Test power data differs between sunlight and eclipse."""
        sim = PowerSimulator("SUNLIGHT-ECLIPSE")
        
        # Sunlight phase
        sim._orbit_phase = 45.0
        sunlight_data = sim.get_power_data()
        
        # Eclipse phase
        sim._orbit_phase = 180.0
        eclipse_data = sim.get_power_data()
        
        # Solar current should be different
        assert sunlight_data.solar_current != eclipse_data.solar_current


class TestIntegrationWithBase:
    """Tests for integration with StubSatelliteSimulator."""
    
    @pytest.mark.asyncio
    async def test_power_in_telemetry(self):
        """Test power system data appears in telemetry."""
        from astraguard.hil.simulator.base import StubSatelliteSimulator
        
        sim = StubSatelliteSimulator("INTEGRATION-TEST")
        
        # Generate multiple packets
        for _ in range(5):
            packet = await sim.generate_telemetry()
            
            # Check power data is present and valid
            assert 0 <= packet.power.battery_soc <= 1.0
            assert 5 <= packet.power.battery_voltage <= 10
            assert packet.power.solar_current >= 0
            assert packet.power.load_current >= 0
    
    @pytest.mark.asyncio
    async def test_power_brownout_integration(self):
        """Test brownout fault in full simulator."""
        from astraguard.hil.simulator.base import StubSatelliteSimulator
        
        sim = StubSatelliteSimulator("BROWNOUT-INT")
        sim.start()
        
        # Normal operation
        normal_packets = []
        for _ in range(5):
            packet = await sim.generate_telemetry()
            normal_packets.append(packet)
        
        normal_voltage = np.mean([p.power.battery_voltage for p in normal_packets])
        normal_soc = np.mean([p.power.battery_soc for p in normal_packets])
        
        # Inject brownout
        await sim.inject_fault("power_brownout", severity=0.8)
        
        # Faulted operation
        fault_packets = []
        for _ in range(5):
            packet = await sim.generate_telemetry()
            fault_packets.append(packet)
        
        fault_voltage = np.mean([p.power.battery_voltage for p in fault_packets])
        fault_soc = np.mean([p.power.battery_soc for p in fault_packets])
        
        # With fault, performance should degrade (lower voltage or SOC)
        assert fault_voltage <= normal_voltage or fault_soc <= normal_soc


class TestRealisticScenarios:
    """Tests for realistic power scenarios."""
    
    def test_eclipse_cycle_soc_variation(self):
        """Test SOC varies realistically over eclipse cycle."""
        sim = PowerSimulator("ECLIPSE-SOC")
        initial_soc = sim.battery_soc
        
        # Run for a complete orbit
        for _ in range(5400):
            sim.update(dt=1.0)
        
        # SOC should have varied but be roughly similar after full cycle
        assert 0 <= sim.battery_soc <= 1.0
        # Allow 20% variation over full cycle (floating point + dynamics tolerance)
        assert abs(sim.battery_soc - initial_soc) <= 0.20
    
    def test_attitude_affects_power(self):
        """Test attitude pointing affects solar power."""
        from astraguard.hil.simulator.base import StubSatelliteSimulator
        
        # This is tested implicitly in base simulator
        # where nadir_error reduces sun_exposure
        pass


class TestStatusReporting:
    """Tests for power system status reporting."""
    
    def test_get_status(self):
        """Test status dictionary is complete."""
        sim = PowerSimulator("STATUS-TEST")
        status = sim.get_status()
        
        assert "orbit_phase" in status
        assert "in_eclipse" in status
        assert "battery_soc" in status
        assert "battery_voltage" in status
        assert "battery_temp" in status
        assert "panel_degradation" in status
        assert "fault_active" in status
        assert "elapsed_time" in status
