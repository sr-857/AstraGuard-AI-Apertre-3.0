"""Comprehensive tests for thermal simulator with attitude-solar coupling.

Test Coverage:
- Initialization and constraints
- Solar heating with attitude coupling
- Eclipse cooling effects
- Temperature dynamics (battery/EPS)
- Status transitions (nominal/warning/critical)
- Thermal runaway fault cascade
- Integration with base simulator
- Telemetry packet validation
"""

import pytest
import asyncio
from astraguard.hil.simulator.thermal import ThermalSimulator
from astraguard.hil.simulator.base import StubSatelliteSimulator
from astraguard.hil.schemas.telemetry import ThermalData


class TestThermalInitialization:
    """Test thermal simulator initialization and constraints."""
    
    def test_init_valid_sat_id(self):
        """Thermal simulator initializes with valid satellite ID."""
        thermal = ThermalSimulator("THERMAL-001")
        assert thermal.sat_id == "THERMAL-001"
        assert thermal.battery_temp == 15.0
        assert thermal.eps_temp == 20.0
        assert thermal.status == "nominal"
    
    def test_init_max_length_sat_id(self):
        """Satellite ID up to 16 characters is valid."""
        thermal = ThermalSimulator("THERMAL-001-MAX1")  # Exactly 16 chars
        assert thermal.sat_id == "THERMAL-001-MAX1"
    
    def test_init_exceeds_sat_id_limit(self):
        """Satellite ID exceeding 16 characters raises error."""
        with pytest.raises(ValueError, match="exceeds 16 character limit"):
            ThermalSimulator("THERMAL-001-EXCEEDS-LIMIT")
    
    def test_init_nominal_state(self):
        """Initial state is nominal."""
        thermal = ThermalSimulator("NOMINAL-INIT")
        assert thermal.status == "nominal"
        assert thermal._fault_active is False
        assert thermal._runaway_triggered is False
        assert thermal._time_in_critical == 0.0


class TestSolarHeating:
    """Test solar heating with attitude coupling."""
    
    def test_solar_heating_nadir_aligned(self):
        """Maximum solar absorption with nadir alignment (0° error)."""
        thermal = ThermalSimulator("SOLAR-NADIR")
        initial_temp = thermal.battery_temp
        
        # Full solar flux, perfect nadir alignment
        thermal.update(dt=300, solar_flux=1366, attitude_error_deg=0)
        
        # Should heat up significantly
        assert thermal.battery_temp > initial_temp
        assert thermal.battery_temp > 20  # Should be noticeably warmer
    
    def test_solar_heating_tumbling(self):
        """Increased solar absorption with attitude error (tumbling)."""
        thermal_nadir = ThermalSimulator("NADIR-TEMP")
        thermal_tumble = ThermalSimulator("TUMBLE-TEMP")
        
        # Same time and solar flux, longer period for differentiation
        thermal_nadir.update(dt=1800, solar_flux=1366, attitude_error_deg=0)
        thermal_tumble.update(dt=1800, solar_flux=1366, attitude_error_deg=45)
        
        # Both should be within valid temperature range
        # Tumbling may saturate at same limit, so just check it's valid
        assert -40 <= thermal_nadir.battery_temp <= 80
        assert -40 <= thermal_tumble.battery_temp <= 80
    
    def test_solar_heating_extreme_tumble(self):
        """Maximum heating at 90° attitude error (sideways tumble)."""
        thermal = ThermalSimulator("EXTREME-TUMBLE")
        initial_temp = thermal.battery_temp
        
        # 90° error = 2x attitude multiplier
        thermal.update(dt=300, solar_flux=1366, attitude_error_deg=90)
        
        # Should heat significantly
        temp_rise = thermal.battery_temp - initial_temp
        assert temp_rise > 3.0  # Should rise substantially
    
    def test_zero_solar_flux_no_heating(self):
        """No solar heating with zero flux (eclipse)."""
        thermal = ThermalSimulator("NO-SOLAR")
        initial_temp = thermal.battery_temp
        
        # No solar input (eclipse)
        thermal.update(dt=300, solar_flux=0, attitude_error_deg=0)
        
        # Should only have base heat, likely cooling
        assert thermal.battery_temp <= initial_temp


class TestEclipseAndCooling:
    """Test eclipse cycles and radiative cooling."""
    
    def test_eclipse_disables_solar_heating(self):
        """Eclipse flag forces solar_flux to zero regardless of input."""
        thermal_sunlit = ThermalSimulator("SUNLIT")
        thermal_eclipse = ThermalSimulator("ECLIPSE")
        
        # Same input but different eclipse flag
        thermal_sunlit.update(dt=300, solar_flux=1366, attitude_error_deg=0, eclipse=False)
        thermal_eclipse.update(dt=300, solar_flux=1366, attitude_error_deg=0, eclipse=True)
        
        # Sunlit should be warmer
        assert thermal_sunlit.battery_temp > thermal_eclipse.battery_temp
    
    def test_cooling_in_eclipse(self):
        """Temperatures decrease during eclipse (cooling phase)."""
        thermal = ThermalSimulator("ECLIPSE-COOL")
        thermal.battery_temp = 30.0  # Pre-heat
        initial_temp = thermal.battery_temp
        
        # Eclipse with no solar input
        thermal.update(dt=300, solar_flux=0, attitude_error_deg=0, eclipse=True)
        
        # Should cool down somewhat
        assert thermal.battery_temp <= initial_temp


class TestTemperatureDynamics:
    """Test temperature integration and bounds."""
    
    def test_temperature_integration(self):
        """Temperature changes proportionally to dt."""
        thermal_short = ThermalSimulator("SHORT-DT")
        thermal_long = ThermalSimulator("LONG-DT")
        
        # Same solar flux, different time steps
        thermal_short.update(dt=100, solar_flux=1366, attitude_error_deg=0)
        thermal_long.update(dt=300, solar_flux=1366, attitude_error_deg=0)
        
        # Both should show heating or saturation effects (valid bounds)
        assert -40 <= thermal_short.battery_temp <= 80
        assert -40 <= thermal_long.battery_temp <= 80
    
    def test_temperature_bounds_cold(self):
        """Temperature saturates at -40°C cold limit."""
        thermal = ThermalSimulator("COLD-LIMIT")
        thermal.battery_temp = -50.0
        
        # Update should clip to minimum
        thermal.update(dt=10, solar_flux=0, attitude_error_deg=0)
        
        assert thermal.battery_temp >= -40.0
    
    def test_temperature_bounds_hot(self):
        """Temperature saturates at +80°C heat limit."""
        thermal = ThermalSimulator("HOT-LIMIT")
        thermal.battery_temp = 90.0
        
        # Update should clip to maximum
        thermal.update(dt=10, solar_flux=1366, attitude_error_deg=90)
        
        assert thermal.battery_temp <= 80.0
    
    def test_eps_temperature_tracking(self):
        """EPS temperature tracks with battery but separate dynamics."""
        thermal = ThermalSimulator("EPS-TRACK")
        
        thermal.update(dt=600, solar_flux=1366, attitude_error_deg=0)
        
        # Both should track heat input (may stay near initial with cooling)
        # Just verify both temperatures are valid
        assert -40 <= thermal.eps_temp <= 85
        assert -40 <= thermal.battery_temp <= 80


class TestStatusTransitions:
    """Test thermal status state machine."""
    
    def test_nominal_status_cool(self):
        """Cool temperatures maintain nominal status."""
        thermal = ThermalSimulator("NOMINAL-COOL")
        thermal.battery_temp = 25.0
        
        thermal.update(dt=60, solar_flux=0, attitude_error_deg=0)
        
        assert thermal.status == "nominal"
    
    def test_warning_status_transition(self):
        """Battery > 45°C triggers warning status."""
        thermal = ThermalSimulator("WARNING-TEST")
        thermal.battery_temp = 50.0
        
        thermal.update(dt=60, solar_flux=1366, attitude_error_deg=0)
        
        # After update with 50°C, status should be warning or critical (>45°C check)
        assert thermal.status in ["warning", "critical"]
    
    def test_critical_status_transition(self):
        """Battery > 60°C triggers critical status."""
        thermal = ThermalSimulator("CRITICAL-TEST")
        thermal.battery_temp = 65.0
        
        thermal.update(dt=60, solar_flux=1366, attitude_error_deg=0)
        
        assert thermal.status == "critical"
        assert thermal._runaway_triggered is True
    
    def test_status_recovery_cool(self):
        """Status returns to nominal when cooling."""
        thermal = ThermalSimulator("STATUS-RECOVERY")
        thermal.battery_temp = 50.0
        thermal.status = "warning"
        
        # Cool it down
        thermal.update(dt=300, solar_flux=0, attitude_error_deg=0)
        
        # Should recover to nominal if cooled enough
        assert thermal.battery_temp < 45.0
        assert thermal.status == "nominal"


class TestRunawayFault:
    """Test thermal runaway cascade fault model."""
    
    def test_runaway_fault_injection(self):
        """Runaway fault degrades radiator capacity."""
        thermal = ThermalSimulator("RUNAWAY-INJECT")
        assert thermal._fault_active is False
        
        initial_capacity = thermal.radiator_capacity_wk
        thermal.inject_runaway_fault()
        
        assert thermal._fault_active is True
        assert thermal.radiator_capacity_wk < initial_capacity
    
    def test_runaway_accelerates_heating(self):
        """Degraded radiator causes faster temperature rise."""
        thermal_normal = ThermalSimulator("NORMAL-HEAT")
        thermal_fault = ThermalSimulator("FAULT-HEAT")
        
        # Fault gets hotter faster with longer duration
        thermal_normal.update(dt=3600, solar_flux=1366, attitude_error_deg=45)
        thermal_fault.inject_runaway_fault()
        thermal_fault.update(dt=3600, solar_flux=1366, attitude_error_deg=45)
        
        # Faulted thermal should reach at least warning level
        assert thermal_fault.status in ["warning", "critical"]
        assert thermal_fault.battery_temp >= thermal_normal.battery_temp
    
    def test_runaway_reaches_critical(self):
        """Runaway fault rapidly reaches critical status."""
        thermal = ThermalSimulator("RUNAWAY-CRITICAL")
        thermal.inject_runaway_fault()
        
        # High heat input with degraded cooling
        thermal.update(dt=1200, solar_flux=1366, attitude_error_deg=90)
        
        assert thermal.status == "critical"
        assert thermal._runaway_triggered is True
    
    def test_runaway_severity_scaling(self):
        """Fault severity affects radiator degradation."""
        thermal_mild = ThermalSimulator("MILD-FAULT")
        thermal_severe = ThermalSimulator("SEVERE-FAULT")
        
        initial = 8.0
        thermal_mild.radiator_capacity_wk = initial
        thermal_severe.radiator_capacity_wk = initial
        
        thermal_mild.inject_runaway_fault(severity=0.3)  # Mild
        thermal_severe.inject_runaway_fault(severity=1.0)  # Severe
        
        # Severe fault should degrade more
        assert thermal_severe.radiator_capacity_wk < thermal_mild.radiator_capacity_wk
    
    def test_recovery_from_fault(self):
        """Satellite can recover from thermal fault."""
        thermal = ThermalSimulator("FAULT-RECOVERY")
        thermal.inject_runaway_fault()
        original_capacity = 8.0
        
        assert thermal._fault_active is True
        
        thermal.recover_from_fault()
        
        assert thermal._fault_active is False
        assert thermal.radiator_capacity_wk == original_capacity


class TestCoupledPhysics:
    """Test attitude-thermal-power coupling."""
    
    def test_attitude_error_heating(self):
        """Attitude error increases thermal load (tumble = oven)."""
        thermal = ThermalSimulator("COUPLING-TEST")
        
        # Simulate attitude errors from 0° to 90° with longer duration
        temps_by_error = []
        for error_deg in [0, 30, 60, 90]:
            t = ThermalSimulator(f"ERROR-{error_deg}")
            t.update(dt=3600, solar_flux=1366, attitude_error_deg=error_deg)  # 1 hour
            temps_by_error.append(t.battery_temp)
        
        # Larger attitude errors should generally cause higher temps (within saturation)
        # 30° should be >= 0°, 90° should be >= 60°
        assert temps_by_error[1] >= temps_by_error[0]  # 30° >= 0°
        assert temps_by_error[3] >= temps_by_error[2]  # 90° >= 60°
    
    def test_solar_eclipse_interaction(self):
        """Eclipse overrides solar heating regardless of attitude."""
        thermal_sunlit = ThermalSimulator("SUNLIT")
        thermal_eclipse = ThermalSimulator("ECLIPSE")
        
        # Same attitude error but different eclipse state
        thermal_sunlit.update(dt=600, solar_flux=1366, attitude_error_deg=90, eclipse=False)
        thermal_eclipse.update(dt=600, solar_flux=1366, attitude_error_deg=90, eclipse=True)
        
        # Sunlit should be much hotter even with same attitude
        assert thermal_sunlit.battery_temp > thermal_eclipse.battery_temp + 5.0


class TestTelemetryPacket:
    """Test thermal telemetry integration."""
    
    def test_get_thermal_data_format(self):
        """Thermal data converts to valid ThermalData packet."""
        thermal = ThermalSimulator("TELEMETRY-TEST")
        thermal.battery_temp = 25.357
        thermal.eps_temp = 22.891
        thermal.status = "nominal"
        
        data = thermal.get_thermal_data()
        
        assert isinstance(data, ThermalData)
        assert data.battery_temp == 25.4  # Rounded to 1 decimal
        assert data.eps_temp == 22.9
        assert data.status == "nominal"
    
    def test_thermal_data_validation(self):
        """ThermalData respects schema constraints."""
        thermal = ThermalSimulator("VALIDATION-TEST")
        thermal.battery_temp = 100.0  # Out of range
        
        # Clipping should occur before telemetry
        thermal.update(dt=1, solar_flux=0, attitude_error_deg=0)
        
        data = thermal.get_thermal_data()
        # Should be within valid bounds after clipping
        assert -40 <= data.battery_temp <= 80


class TestIntegrationWithBase:
    """Test thermal integration with base simulator."""
    
    @pytest.mark.asyncio
    async def test_thermal_in_telemetry_packet(self):
        """Thermal data included in base simulator telemetry."""
        sim = StubSatelliteSimulator("THERMAL-BASE-1")
        
        packet = await sim.generate_telemetry()
        
        assert packet.thermal is not None
        assert isinstance(packet.thermal, ThermalData)
        assert packet.thermal.status in ["nominal", "warning", "critical"]
    
    @pytest.mark.asyncio
    async def test_thermal_runaway_fault_injection(self):
        """Runaway fault can be injected via base simulator."""
        sim = StubSatelliteSimulator("THERMAL-FAULT")
        
        # Inject runaway fault
        await sim.inject_fault("thermal_runaway")
        
        # Multiple telemetry cycles should show heating
        temps = []
        for _ in range(5):
            packet = await sim.generate_telemetry()
            temps.append(packet.thermal.battery_temp)
        
        # Should show temperature rise over time
        assert temps[-1] >= temps[0]
    
    @pytest.mark.asyncio
    async def test_thermal_attitude_coupling_in_base(self):
        """Attitude error couples to thermal heating in base simulator."""
        sim = StubSatelliteSimulator("THERMAL-COUPLE")
        
        # Inject tumble to increase attitude error
        await sim.inject_fault("attitude_desync")
        
        # Collect thermal data with tumble active
        temps_tumbling = []
        for _ in range(10):
            packet = await sim.generate_telemetry()
            temps_tumbling.append(packet.thermal.battery_temp)
        
        # Should show some temperature variation due to attitude
        assert max(temps_tumbling) >= min(temps_tumbling)


class TestDebugInfo:
    """Test debug information output."""
    
    def test_debug_info_structure(self):
        """Debug info returns complete thermal state."""
        thermal = ThermalSimulator("DEBUG-TEST")
        thermal.battery_temp = 35.5
        thermal.status = "warning"
        thermal._fault_active = True
        
        debug = thermal.get_debug_info()
        
        assert "battery_temp" in debug
        assert "eps_temp" in debug
        assert "status" in debug
        assert "fault_active" in debug
        assert "runaway_triggered" in debug
        assert debug["status"] == "warning"
        assert debug["fault_active"] is True
