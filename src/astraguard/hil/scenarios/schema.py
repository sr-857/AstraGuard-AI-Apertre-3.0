"""HIL test scenario YAML schema + validation."""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Dict, Any, Optional
from enum import Enum
import yaml


class FaultType(str, Enum):
    """Supported fault types for HIL testing."""
    POWER_BROWNOUT = "power_brownout"
    COMMS_DROPOUT = "comms_dropout"
    THERMAL_RUNAWAY = "thermal_runaway"
    ATTITUDE_DESYNC = "attitude_desync"


class SatelliteConfig(BaseModel):
    """Satellite configuration in a scenario."""
    id: str = Field(..., min_length=1, max_length=16, description="Satellite ID")
    initial_position_km: List[float] = Field(
        default=[0, 0, 420],
        description="Initial position [x, y, z] in kilometers"
    )
    neighbors: List[str] = Field(
        default_factory=list,
        description="List of neighboring satellite IDs for formation flying"
    )

    @field_validator("initial_position_km")
    @classmethod
    def validate_position(cls, v):
        """Ensure position is 3D vector."""
        if len(v) != 3:
            raise ValueError("Position must be [x, y, z]")
        return v


class FaultInjection(BaseModel):
    """Fault injection configuration."""
    model_config = ConfigDict(use_enum_values=False)
    
    type: FaultType
    satellite: str = Field(..., description="Target satellite ID")
    start_time_s: float = Field(..., ge=0, description="Fault start time in seconds")
    severity: float = Field(
        0.5,
        ge=0.1,
        le=1.0,
        description="Fault severity (0.1-1.0)"
    )
    duration_s: float = Field(
        300,
        ge=10,
        description="Fault duration in seconds (minimum 10s)"
    )


class SuccessCriteria(BaseModel):
    """Test success validation criteria."""
    max_nadir_error_deg: float = Field(
        5.0,
        ge=0,
        le=180,
        description="Maximum nadir pointing error in degrees"
    )
    min_battery_soc: float = Field(
        0.3,
        ge=0,
        le=1.0,
        description="Minimum battery state of charge (0-1)"
    )
    max_temperature_c: float = Field(
        50.0,
        ge=0,
        le=100,
        description="Maximum allowable temperature in Celsius"
    )
    max_packet_loss: float = Field(
        0.1,
        ge=0,
        le=1.0,
        description="Maximum allowable packet loss ratio (0-1)"
    )


class Scenario(BaseModel):
    """Complete HIL test scenario definition."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "nominal_formation",
                "description": "Baseline formation flying",
                "duration_s": 900,
                "satellites": [
                    {
                        "id": "ASTRA-001",
                        "initial_position_km": [0, 0, 420],
                        "neighbors": ["ASTRA-002"]
                    }
                ],
                "fault_sequence": [],
                "success_criteria": {}
            }
        }
    )
    
    name: str = Field(..., description="Scenario name")
    description: str = Field(..., description="Scenario description")
    duration_s: int = Field(
        1800,
        ge=60,
        le=86400,
        description="Test duration in seconds (60s - 24h)"
    )
    satellites: List[SatelliteConfig] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Satellite configurations (1-10 sats)"
    )
    fault_sequence: List[FaultInjection] = Field(
        default_factory=list,
        description="Timed sequence of fault injections"
    )
    success_criteria: SuccessCriteria = Field(
        default_factory=SuccessCriteria,
        description="Test success validation criteria"
    )

    @field_validator("fault_sequence")
    @classmethod
    def faults_sorted(cls, v):
        """Ensure faults sorted by start_time."""
        return sorted(v, key=lambda f: f.start_time_s)

    @field_validator("fault_sequence")
    @classmethod
    def validate_fault_targets(cls, v, info):
        """Ensure all faults target known satellites."""
        if "satellites" in info.data:
            sat_ids = {s.id for s in info.data["satellites"]}
            for fault in v:
                if fault.satellite not in sat_ids:
                    raise ValueError(f"Fault targets unknown satellite: {fault.satellite}")
        return v

    @field_validator("fault_sequence")
    @classmethod
    def validate_fault_times(cls, v, info):
        """Ensure all faults start before test ends."""
        if "duration_s" in info.data:
            duration = info.data["duration_s"]
            for fault in v:
                if fault.start_time_s + fault.duration_s > duration:
                    raise ValueError(
                        f"Fault at {fault.start_time_s}s with duration {fault.duration_s}s "
                        f"exceeds test duration {duration}s"
                    )
        return v


def load_scenario(file_path: str) -> Scenario:
    """
    Load and validate YAML scenario file.
    
    Args:
        file_path: Path to YAML scenario file
        
    Returns:
        Validated Scenario object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML is invalid
        ValueError: If scenario validation fails
    """
    with open(file_path, "r") as f:
        data = yaml.safe_load(f)
    
    if data is None:
        raise ValueError("Empty YAML file")
    
    return Scenario(**data)


def validate_scenario(scenario: Scenario) -> Dict[str, Any]:
    """
    Validate scenario for execution readiness.
    
    Args:
        scenario: Scenario object to validate
        
    Returns:
        Dict with 'valid' (bool) and 'issues' (list of error strings)
    """
    issues = []
    
    # Check satellite count
    if len(scenario.satellites) == 0:
        issues.append("No satellites defined")
    
    # Check neighbor references
    sat_ids = {s.id for s in scenario.satellites}
    for sat in scenario.satellites:
        for neighbor_id in sat.neighbors:
            if neighbor_id not in sat_ids:
                issues.append(
                    f"Satellite {sat.id} references unknown neighbor {neighbor_id}"
                )
            if neighbor_id == sat.id:
                issues.append(f"Satellite {sat.id} cannot be its own neighbor")
    
    # Check fault references
    for fault in scenario.fault_sequence:
        if fault.satellite not in sat_ids:
            issues.append(f"Fault targets unknown satellite: {fault.satellite}")
    
    # Check timeline consistency
    for fault in scenario.fault_sequence:
        if fault.start_time_s + fault.duration_s > scenario.duration_s:
            issues.append(
                f"Fault {fault.type} on {fault.satellite} extends beyond "
                f"test duration ({fault.start_time_s + fault.duration_s}s > "
                f"{scenario.duration_s}s)"
            )
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "satellite_count": len(scenario.satellites),
        "fault_count": len(scenario.fault_sequence),
    }


# YAML Schema documentation
SCENARIO_SCHEMA = """
# HIL Test Scenario YAML Schema

name: str (required)
  - Scenario name for identification

description: str (required)
  - Human-readable scenario description

duration_s: int (default: 1800)
  - Test duration in seconds (60s minimum, 24h maximum)

satellites: list (required, 1-10 items)
  - List of satellite configurations
  - id: str (required)
      - Unique satellite identifier (1-16 chars)
    initial_position_km: [x, y, z] (default: [0, 0, 420])
      - Initial position in kilometers
      - x, y, z coordinates
    neighbors: list (default: [])
      - List of neighboring satellite IDs
      - Enables formation flying detection

fault_sequence: list (default: [])
  - List of timed fault injections
  - Automatically sorted by start_time_s
  - type: str (required)
      - power_brownout | comms_dropout | thermal_runaway | attitude_desync
    satellite: str (required)
      - Target satellite ID
    start_time_s: float (required)
      - Fault injection time in seconds (>= 0)
    severity: float (default: 0.5)
      - Fault severity level (0.1-1.0)
    duration_s: float (default: 300)
      - Fault duration in seconds (>= 10)

success_criteria: object (default: all nominal)
  - Test validation thresholds
  - max_nadir_error_deg: float (default: 5.0)
      - Maximum nadir pointing error (0-180)
  - min_battery_soc: float (default: 0.3)
      - Minimum battery state of charge (0-1)
  - max_temperature_c: float (default: 50.0)
      - Maximum temperature threshold (0-100°C)
  - max_packet_loss: float (default: 0.1)
      - Maximum comms packet loss (0-1)

# Example:
# name: "nominal_formation"
# description: "Baseline multi-sat formation"
# duration_s: 900
# satellites:
#   - id: "SAT-A"
#     initial_position_km: [0, 0, 420]
#     neighbors: ["SAT-B"]
#   - id: "SAT-B"
#     initial_position_km: [1.2, 0, 420]
#     neighbors: ["SAT-A"]
# fault_sequence: []
# success_criteria:
#   max_nadir_error_deg: 2.0
#   min_battery_soc: 0.7
"""
