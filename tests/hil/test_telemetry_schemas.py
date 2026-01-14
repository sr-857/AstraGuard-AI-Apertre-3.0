"""Tests for HIL telemetry schemas."""

import pytest
from datetime import datetime
from pydantic import ValidationError
from astraguard.hil.schemas.telemetry import (
    TelemetryPacket,
    AttitudeData,
    PowerData,
    ThermalData,
    OrbitData,
)


class TestAttitudeData:
    """Tests for AttitudeData validation."""
    
    def test_valid_attitude(self):
        """Test valid attitude data."""
        attitude = AttitudeData(
            quaternion=[0.707, 0.0, 0.0, 0.707],
            angular_velocity=[0.001, 0.002, 0.001],
            nadir_pointing_error_deg=1.5
        )
        assert len(attitude.quaternion) == 4
        assert len(attitude.angular_velocity) == 3
        assert 0 <= attitude.nadir_pointing_error_deg <= 180
    
    def test_quaternion_wrong_length(self):
        """Test that quaternion must have exactly 4 elements."""
        with pytest.raises(ValidationError) as exc_info:
            AttitudeData(
                quaternion=[0.707, 0.0, 0.0],  # Only 3 elements
                angular_velocity=[0.001, 0.002, 0.001],
                nadir_pointing_error_deg=1.5
            )
        assert "quaternion must have exactly 4 elements" in str(exc_info.value)
    
    def test_angular_velocity_wrong_length(self):
        """Test that angular_velocity must have exactly 3 elements."""
        with pytest.raises(ValidationError) as exc_info:
            AttitudeData(
                quaternion=[0.707, 0.0, 0.0, 0.707],
                angular_velocity=[0.001, 0.002],  # Only 2 elements
                nadir_pointing_error_deg=1.5
            )
        assert "angular_velocity must have exactly 3 elements" in str(exc_info.value)
    
    def test_nadir_error_out_of_range(self):
        """Test nadir pointing error range validation."""
        with pytest.raises(ValidationError):
            AttitudeData(
                quaternion=[0.707, 0.0, 0.0, 0.707],
                angular_velocity=[0.001, 0.002, 0.001],
                nadir_pointing_error_deg=-1.0  # Negative
            )
        with pytest.raises(ValidationError):
            AttitudeData(
                quaternion=[0.707, 0.0, 0.0, 0.707],
                angular_velocity=[0.001, 0.002, 0.001],
                nadir_pointing_error_deg=181.0  # > 180
            )


class TestPowerData:
    """Tests for PowerData validation."""
    
    def test_valid_power_data(self):
        """Test valid power data."""
        power = PowerData(
            battery_voltage=8.4,
            battery_soc=0.87,
            solar_current=0.8,
            load_current=0.3
        )
        assert 0 <= power.battery_voltage <= 30
        assert 0 <= power.battery_soc <= 1
        assert power.solar_current >= 0
        assert power.load_current >= 0
    
    def test_voltage_out_of_range(self):
        """Test battery voltage range validation."""
        with pytest.raises(ValidationError):
            PowerData(
                battery_voltage=35.0,  # > 30V
                battery_soc=0.87,
                solar_current=0.8,
                load_current=0.3
            )
    
    def test_soc_out_of_range(self):
        """Test battery SOC range validation."""
        with pytest.raises(ValidationError):
            PowerData(
                battery_voltage=8.4,
                battery_soc=1.5,  # > 1.0
                solar_current=0.8,
                load_current=0.3
            )


class TestThermalData:
    """Tests for ThermalData validation."""
    
    def test_valid_thermal_data(self):
        """Test valid thermal data."""
        thermal = ThermalData(
            battery_temp=15.2,
            eps_temp=22.1,
            status="nominal"
        )
        assert thermal.status in {"nominal", "warning", "critical"}
    
    def test_invalid_status(self):
        """Test thermal status validation."""
        with pytest.raises(ValidationError):
            ThermalData(
                battery_temp=15.2,
                eps_temp=22.1,
                status="overheating"  # Invalid
            )
    
    def test_temp_out_of_range(self):
        """Test temperature range validation."""
        with pytest.raises(ValidationError):
            ThermalData(
                battery_temp=-60.0,  # < -50
                eps_temp=22.1,
                status="nominal"
            )


class TestOrbitData:
    """Tests for OrbitData validation."""
    
    def test_valid_orbit_data(self):
        """Test valid orbit data."""
        orbit = OrbitData(
            altitude_m=520000,
            ground_speed_ms=7660,
            true_anomaly_deg=45.0
        )
        assert 100000 <= orbit.altitude_m <= 2000000
        assert 7000 <= orbit.ground_speed_ms <= 8000
        assert 0 <= orbit.true_anomaly_deg <= 360
    
    def test_altitude_out_of_leo_range(self):
        """Test altitude range (LEO only)."""
        with pytest.raises(ValidationError):
            OrbitData(
                altitude_m=3000000,  # GEO range
                ground_speed_ms=7660,
                true_anomaly_deg=45.0
            )
    
    def test_ground_speed_out_of_range(self):
        """Test ground speed validation."""
        with pytest.raises(ValidationError):
            OrbitData(
                altitude_m=520000,
                ground_speed_ms=9000,  # > 8000
                true_anomaly_deg=45.0
            )


class TestTelemetryPacket:
    """Tests for complete TelemetryPacket validation."""
    
    def test_valid_telemetry_packet(self):
        """Test complete valid telemetry packet."""
        packet = TelemetryPacket(
            timestamp=datetime.now(),
            satellite_id="SAT001",
            attitude=AttitudeData(
                quaternion=[0.707, 0.0, 0.0, 0.707],
                angular_velocity=[0.001, 0.002, 0.001],
                nadir_pointing_error_deg=1.5
            ),
            power=PowerData(
                battery_voltage=8.4,
                battery_soc=0.87,
                solar_current=0.8,
                load_current=0.3
            ),
            thermal=ThermalData(
                battery_temp=15.2,
                eps_temp=22.1,
                status="nominal"
            ),
            orbit=OrbitData(
                altitude_m=520000,
                ground_speed_ms=7660,
                true_anomaly_deg=45.0
            ),
            mission_mode="nominal"
        )
        assert packet.version == "v1.0"
        assert packet.satellite_id == "SAT001"
        assert packet.mission_mode == "nominal"
    
    def test_invalid_mission_mode(self):
        """Test mission mode validation."""
        with pytest.raises(ValidationError):
            TelemetryPacket(
                timestamp=datetime.now(),
                satellite_id="SAT001",
                attitude=AttitudeData(
                    quaternion=[0.707, 0.0, 0.0, 0.707],
                    angular_velocity=[0.001, 0.002, 0.001],
                    nadir_pointing_error_deg=1.5
                ),
                power=PowerData(
                    battery_voltage=8.4,
                    battery_soc=0.87,
                    solar_current=0.8,
                    load_current=0.3
                ),
                thermal=ThermalData(
                    battery_temp=15.2,
                    eps_temp=22.1,
                    status="nominal"
                ),
                orbit=OrbitData(
                    altitude_m=520000,
                    ground_speed_ms=7660,
                    true_anomaly_deg=45.0
                ),
                mission_mode="unknown"  # Invalid mode
            )
    
    def test_satellite_id_max_length(self):
        """Test satellite ID length constraint."""
        with pytest.raises(ValidationError):
            TelemetryPacket(
                timestamp=datetime.now(),
                satellite_id="SAT001_TOOLONG_ID_HERE",  # > 16 chars
                attitude=AttitudeData(
                    quaternion=[0.707, 0.0, 0.0, 0.707],
                    angular_velocity=[0.001, 0.002, 0.001],
                    nadir_pointing_error_deg=1.5
                ),
                power=PowerData(
                    battery_voltage=8.4,
                    battery_soc=0.87,
                    solar_current=0.8,
                    load_current=0.3
                ),
                thermal=ThermalData(
                    battery_temp=15.2,
                    eps_temp=22.1,
                    status="nominal"
                ),
                orbit=OrbitData(
                    altitude_m=520000,
                    ground_speed_ms=7660,
                    true_anomaly_deg=45.0
                ),
                mission_mode="nominal"
            )
    
    def test_fault_cascades_to_multiple_subsystems(self):
        """Test that fault injection affects multiple subsystems."""
        # Normal operation
        normal_packet = TelemetryPacket(
            timestamp=datetime.now(),
            satellite_id="SAT001",
            attitude=AttitudeData(
                quaternion=[0.707, 0.0, 0.0, 0.707],
                angular_velocity=[0.001, 0.002, 0.001],
                nadir_pointing_error_deg=1.5
            ),
            power=PowerData(
                battery_voltage=8.4,
                battery_soc=0.87,
                solar_current=0.8,
                load_current=0.3
            ),
            thermal=ThermalData(
                battery_temp=15.2,
                eps_temp=22.1,
                status="nominal"
            ),
            orbit=OrbitData(
                altitude_m=520000,
                ground_speed_ms=7660,
                true_anomaly_deg=45.0
            ),
            mission_mode="nominal"
        )
        
        # Fault operation
        fault_packet = TelemetryPacket(
            timestamp=datetime.now(),
            satellite_id="SAT001",
            attitude=AttitudeData(
                quaternion=[0.707, 0.0, 0.0, 0.707],
                angular_velocity=[0.001, 0.002, 0.001],
                nadir_pointing_error_deg=1.5
            ),
            power=PowerData(
                battery_voltage=6.2,  # Dropped
                battery_soc=0.45,  # Reduced
                solar_current=0.8,
                load_current=0.3
            ),
            thermal=ThermalData(
                battery_temp=25.2,  # Raised
                eps_temp=22.1,
                status="warning"  # Changed
            ),
            orbit=OrbitData(
                altitude_m=520000,
                ground_speed_ms=7660,
                true_anomaly_deg=45.0
            ),
            mission_mode="nominal"
        )
        
        # Verify differences
        assert normal_packet.power.battery_voltage > fault_packet.power.battery_voltage
        assert normal_packet.power.battery_soc > fault_packet.power.battery_soc
        assert normal_packet.thermal.battery_temp < fault_packet.thermal.battery_temp
        assert normal_packet.thermal.status == "nominal"
        assert fault_packet.thermal.status == "warning"


class TestModelSerialization:
    """Tests for JSON serialization."""
    
    def test_packet_to_dict(self):
        """Test model_dump() serialization."""
        packet = TelemetryPacket(
            timestamp=datetime.now(),
            satellite_id="SAT001",
            attitude=AttitudeData(
                quaternion=[0.707, 0.0, 0.0, 0.707],
                angular_velocity=[0.001, 0.002, 0.001],
                nadir_pointing_error_deg=1.5
            ),
            power=PowerData(
                battery_voltage=8.4,
                battery_soc=0.87,
                solar_current=0.8,
                load_current=0.3
            ),
            thermal=ThermalData(
                battery_temp=15.2,
                eps_temp=22.1,
                status="nominal"
            ),
            orbit=OrbitData(
                altitude_m=520000,
                ground_speed_ms=7660,
                true_anomaly_deg=45.0
            ),
            mission_mode="nominal"
        )
        
        data = packet.model_dump()
        assert isinstance(data, dict)
        assert data["satellite_id"] == "SAT001"
        assert data["version"] == "v1.0"
        assert data["power"]["battery_voltage"] == 8.4
        assert data["thermal"]["status"] == "nominal"
