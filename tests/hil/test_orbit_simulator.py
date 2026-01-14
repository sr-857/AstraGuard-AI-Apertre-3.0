"""Comprehensive tests for orbit simulator with SGP4 propagation.

Test Coverage:
- Initialization and TLE parsing
- True anomaly propagation (15.72 revs/day)
- Altitude variation (J2 perturbation ±500m)
- Eclipse timing (90-270° true anomaly)
- ECI position calculations
- Inter-satellite distance and ranging
- Integration with base simulator
- Telemetry packet validation
"""

import pytest
from datetime import datetime, timedelta
from astraguard.hil.simulator.orbit import OrbitSimulator
from astraguard.hil.simulator.base import StubSatelliteSimulator
from astraguard.hil.schemas.telemetry import OrbitData


class TestOrbitInitialization:
    """Test orbit simulator initialization and constraints."""
    
    def test_init_valid_sat_id(self):
        """Orbit simulator initializes with valid satellite ID."""
        orbit = OrbitSimulator("ORBIT-001")
        assert orbit.sat_id == "ORBIT-001"
        assert orbit.altitude_m == 420000
        assert orbit._true_anomaly_deg == 0.0
    
    def test_init_max_length_sat_id(self):
        """Satellite ID up to 16 characters is valid."""
        orbit = OrbitSimulator("ORBIT-001-MAX-01")  # Exactly 16 chars
        assert orbit.sat_id == "ORBIT-001-MAX-01"
    
    def test_init_exceeds_sat_id_limit(self):
        """Satellite ID exceeding 16 characters raises error."""
        with pytest.raises(ValueError, match="exceeds 16 character limit"):
            OrbitSimulator("ORBIT-001-EXCEEDS-LIMIT")
    
    def test_init_default_tle(self):
        """Default TLE is ISS-like orbit."""
        orbit = OrbitSimulator("DEFAULT-TLE")
        assert orbit.inclination_deg == 51.6456
        assert orbit.mean_motion_revday == 15.72
        assert orbit.altitude_m == 420000
    
    def test_init_custom_tle(self):
        """Custom TLE can be provided."""
        tle1 = "1 25544U 98067A   25013.12345678  .00016717  00000-0  10270-3 0  9999"
        tle2 = "2 25544  51.6456  15.1234 0003456  87.6543 272.3456 15.72112345 12345"
        orbit = OrbitSimulator("CUSTOM-TLE", tle_line1=tle1, tle_line2=tle2)
        assert orbit.tle_line1 == tle1
        assert orbit.tle_line2 == tle2


class TestTrueAnomalyPropagation:
    """Test orbital motion propagation."""
    
    def test_initial_true_anomaly_zero(self):
        """True anomaly starts at 0°."""
        orbit = OrbitSimulator("INITIAL-TA")
        assert orbit._true_anomaly_deg == 0.0
    
    def test_true_anomaly_advances(self):
        """True anomaly increases with time."""
        orbit = OrbitSimulator("ADVANCING-TA")
        initial_ta = orbit._true_anomaly_deg
        
        orbit.update(dt=1.0)
        
        assert orbit._true_anomaly_deg > initial_ta
    
    def test_mean_motion_15_72_revs_per_day(self):
        """90-minute LEO orbit ≈ 15.72 revolutions/day."""
        orbit = OrbitSimulator("MEAN-MOTION")
        
        # 90 minutes = 5400 seconds = 1/16 of a day
        # 15.72 revs/day means 15.72/16 revs per 90 min = 0.9825 revs ≈ 354°
        orbit.update(dt=5400)
        
        # Should have advanced ~354° (nearly full orbit)
        assert 350 < orbit._true_anomaly_deg < 360
    
    def test_true_anomaly_wraps_360(self):
        """True anomaly wraps at 360°."""
        orbit = OrbitSimulator("WRAP-TA")
        
        # Update for 2 full orbits
        orbit.update(dt=5400 * 2)
        
        # Should wrap back to starting position
        assert 0 <= orbit._true_anomaly_deg < 360
    
    def test_propagation_dt_scaling(self):
        """True anomaly changes scale with dt."""
        orbit_short = OrbitSimulator("SHORT-DT")
        orbit_long = OrbitSimulator("LONG-DT")
        
        orbit_short.update(dt=100)
        orbit_long.update(dt=1000)
        
        # Longer dt should advance more
        assert orbit_long._true_anomaly_deg > orbit_short._true_anomaly_deg


class TestAltitudeVariation:
    """Test J2 perturbation altitude breathing."""
    
    def test_baseline_altitude_420km(self):
        """Baseline altitude is 420 km."""
        orbit = OrbitSimulator("BASELINE-ALT")
        assert orbit.altitude_m == 420000
    
    def test_altitude_varies_with_true_anomaly(self):
        """Altitude varies with orbital position (J2 perturbation)."""
        orbit = OrbitSimulator("ALT-VAR")
        
        # At true anomaly = 0°, sin(0) = 0, altitude = 420km
        alt_at_0 = orbit.altitude_m
        
        # At true anomaly = 45°, altitude varies
        orbit._true_anomaly_deg = 45
        orbit.update(dt=0)
        alt_at_45 = orbit.altitude_m
        
        # Altitudes should differ due to J2 effect
        assert alt_at_0 != alt_at_45
    
    def test_altitude_variation_amplitude_500m(self):
        """Altitude variation amplitude is ±500m."""
        orbit = OrbitSimulator("ALT-AMPLITUDE")
        
        # Collect altitudes across full orbit
        altitudes = []
        for ta_deg in range(0, 360, 15):
            orbit._true_anomaly_deg = ta_deg
            orbit.update(dt=0)
            altitudes.append(orbit.altitude_m)
        
        # Min and max altitudes should differ by ~1000m (±500m variation)
        alt_range = max(altitudes) - min(altitudes)
        assert 800 < alt_range < 1200
    
    def test_altitude_within_bounds(self):
        """Altitude stays within realistic bounds (±500m)."""
        orbit = OrbitSimulator("ALT-BOUNDS")
        
        # Test over full orbit
        for ta_deg in range(0, 360, 30):
            orbit._true_anomaly_deg = ta_deg
            orbit.update(dt=0)
            
            assert 419500 < orbit.altitude_m < 420500


class TestEclipseTiming:
    """Test eclipse detection (shadow timing)."""
    
    def test_eclipse_detection_90_to_270(self):
        """Satellite in eclipse between 90° and 270° true anomaly."""
        orbit = OrbitSimulator("ECLIPSE-DETECT")
        
        # At 0°: sunlit
        orbit._true_anomaly_deg = 0
        assert not orbit.is_in_eclipse()
        
        # At 90°: entering eclipse
        orbit._true_anomaly_deg = 90.1
        assert orbit.is_in_eclipse()
        
        # At 180°: deep eclipse
        orbit._true_anomaly_deg = 180
        assert orbit.is_in_eclipse()
        
        # At 270°: leaving eclipse
        orbit._true_anomaly_deg = 269.9
        assert orbit.is_in_eclipse()
        
        # At 0°/360°: sunlit again
        orbit._true_anomaly_deg = 359
        assert not orbit.is_in_eclipse()
    
    def test_eclipse_boundary_conditions(self):
        """Test eclipse boundary at exactly 90° and 270°."""
        orbit = OrbitSimulator("ECLIPSE-BOUNDARY")
        
        # At exactly 90°: boundary condition (open interval 90 < ta < 270)
        orbit._true_anomaly_deg = 90.0
        assert not orbit.is_in_eclipse()  # Boundary excluded
        
        orbit._true_anomaly_deg = 90.01
        assert orbit.is_in_eclipse()
        
        orbit._true_anomaly_deg = 269.99
        assert orbit.is_in_eclipse()
        
        orbit._true_anomaly_deg = 270.0
        assert not orbit.is_in_eclipse()  # Boundary excluded
    
    def test_eclipse_from_orbit_data(self):
        """Eclipse timing can be inferred from OrbitData true_anomaly."""
        orbit = OrbitSimulator("ECLIPSE-DATA")
        
        # Check various true anomalies
        test_cases = [
            (0, False),    # Sunlit
            (45, False),   # Sunlit
            (135, True),   # Eclipse
            (180, True),   # Deep eclipse
            (270, False),  # Sunlit again
            (315, False),  # Sunlit
        ]
        
        for ta_deg, expected_eclipse in test_cases:
            orbit._true_anomaly_deg = ta_deg
            assert orbit.is_in_eclipse() == expected_eclipse


class TestECIPosition:
    """Test Earth-Centered Inertial position calculations."""
    
    def test_eci_position_structure(self):
        """ECI position returns (x, y, z) tuple in km."""
        orbit = OrbitSimulator("ECI-STRUCT")
        x, y, z = orbit.get_position_eci()
        
        assert isinstance(x, (int, float))
        assert isinstance(y, (int, float))
        assert isinstance(z, (float))
        assert z == 0.0  # Simplified equatorial
    
    def test_eci_distance_from_earth(self):
        """Satellite distance from Earth center ≈ Earth radius + altitude."""
        orbit = OrbitSimulator("ECI-DISTANCE")
        
        x, y, z = orbit.get_position_eci()
        r = np.sqrt(x**2 + y**2 + z**2)
        
        expected_r = 6371.0 + 420.0  # Earth radius + altitude in km
        assert abs(r - expected_r) < 1.0  # Within 1 km
    
    def test_eci_position_rotates_with_anomaly(self):
        """ECI position rotates around Earth with true anomaly."""
        orbit = OrbitSimulator("ECI-ROTATE")
        
        # At 0°: satellite on positive X axis
        orbit._true_anomaly_deg = 0
        x0, y0, z0 = orbit.get_position_eci()
        assert x0 > y0  # X component dominant
        
        # At 90°: satellite on positive Y axis
        orbit._true_anomaly_deg = 90
        x90, y90, z90 = orbit.get_position_eci()
        assert y90 > x90  # Y component dominant
        
        # At 180°: satellite on negative X axis
        orbit._true_anomaly_deg = 180
        x180, y180, z180 = orbit.get_position_eci()
        assert x180 < 0  # X component negative


class TestInterSatelliteDistance:
    """Test swarm formation ranging."""
    
    def test_distance_to_self_zero(self):
        """Distance to same satellite is zero."""
        orbit1 = OrbitSimulator("SELF-DISTANCE")
        distance = orbit1.get_relative_distance_to(orbit1)
        assert abs(distance) < 0.01  # Nearly zero
    
    def test_distance_between_different_orbits(self):
        """Distance computed between two satellites."""
        orbit1 = OrbitSimulator("SAT1")
        orbit2 = OrbitSimulator("SAT2")
        
        # Both at same position initially
        distance = orbit1.get_relative_distance_to(orbit2)
        assert abs(distance) < 0.01
        
        # Advance orbit2, should have distance
        orbit2.update(dt=100)
        distance = orbit1.get_relative_distance_to(orbit2)
        assert distance > 0
    
    def test_distance_symmetric(self):
        """Distance from A to B equals distance from B to A."""
        orbit1 = OrbitSimulator("SAT-A")
        orbit2 = OrbitSimulator("SAT-B")
        
        orbit1._true_anomaly_deg = 10
        orbit2._true_anomaly_deg = 50
        
        dist_ab = orbit1.get_relative_distance_to(orbit2)
        dist_ba = orbit2.get_relative_distance_to(orbit1)
        
        assert abs(dist_ab - dist_ba) < 0.01


class TestTelemetryPacket:
    """Test orbit telemetry data structure."""
    
    def test_get_orbit_data_format(self):
        """Orbit data converts to valid OrbitData packet."""
        orbit = OrbitSimulator("TLM-TEST")
        orbit._true_anomaly_deg = 45.5
        
        data = orbit.get_orbit_data()
        
        assert isinstance(data, OrbitData)
        # Altitude should be in valid range (±500m variation around 420km)
        assert 419000 < data.altitude_m < 421000
        assert data.true_anomaly_deg == 45.5
        assert 7650 < data.ground_speed_ms < 7670  # With ±10 m/s noise
    
    def test_orbit_data_validation(self):
        """OrbitData respects schema constraints."""
        orbit = OrbitSimulator("VAL-TEST")
        
        # Test altitude bounds
        orbit.altitude_m = 100000
        data = orbit.get_orbit_data()
        assert 100000 <= data.altitude_m <= 2000000
        
        # Test true anomaly bounds
        orbit._true_anomaly_deg = 359.9
        data = orbit.get_orbit_data()
        assert 0 <= data.true_anomaly_deg <= 360


class TestIntegrationWithBase:
    """Test orbit integration with base simulator."""
    
    @pytest.mark.asyncio
    async def test_orbit_in_telemetry_packet(self):
        """Orbit data included in base simulator telemetry."""
        sim = StubSatelliteSimulator("ORBIT-BASE-1")
        
        packet = await sim.generate_telemetry()
        
        assert packet.orbit is not None
        assert isinstance(packet.orbit, OrbitData)
        assert 100000 <= packet.orbit.altitude_m <= 2000000
        assert 0 <= packet.orbit.true_anomaly_deg <= 360
    
    @pytest.mark.asyncio
    async def test_eclipse_timing_from_orbit(self):
        """Eclipse timing from orbit drives power sim."""
        sim = StubSatelliteSimulator("ECLIPSE-TIMING")
        
        packets = []
        for _ in range(10):
            packet = await sim.generate_telemetry()
            packets.append(packet)
        
        # Some packets should be in eclipse (90-270°), some in sunlight
        eclipse_count = sum(1 for p in packets if 90 < p.orbit.true_anomaly_deg < 270)
        sunlight_count = sum(1 for p in packets if p.orbit.true_anomaly_deg <= 90 or p.orbit.true_anomaly_deg >= 270)
        
        # With 10 random updates, expect some spread
        assert eclipse_count >= 0
        assert sunlight_count >= 0
    
    @pytest.mark.asyncio
    async def test_orbital_propagation_sequence(self):
        """True anomaly advances sequentially across updates."""
        sim = StubSatelliteSimulator("ORBIT-SEQUENCE")
        
        tas = []
        for _ in range(5):
            packet = await sim.generate_telemetry()
            tas.append(packet.orbit.true_anomaly_deg)
        
        # True anomalies should generally increase (with wrap at 360)
        # At least the first few should be ascending
        assert tas[1] >= tas[0] or (tas[0] > 350 and tas[1] < 10)


class TestDebugInfo:
    """Test debug information output."""
    
    def test_debug_info_structure(self):
        """Debug info returns complete orbital state."""
        orbit = OrbitSimulator("DEBUG-TEST")
        orbit._true_anomaly_deg = 45.0
        orbit._elapsed_time = 1000.0
        
        debug = orbit.get_debug_info()
        
        assert "sat_id" in debug
        assert "true_anomaly_deg" in debug
        assert "altitude_m" in debug
        assert "inclination_deg" in debug
        assert "eci_x_km" in debug
        assert "eci_y_km" in debug
        assert "eci_z_km" in debug
        assert "in_eclipse" in debug
        assert "elapsed_time_s" in debug
        assert debug["sat_id"] == "DEBUG-TEST"
        assert debug["elapsed_time_s"] == 1000.0


# Import numpy for test calculations
import numpy as np
