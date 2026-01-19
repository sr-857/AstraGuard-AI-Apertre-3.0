from typing import Dict


def classify(data: Dict) -> str:
    """
    Classify the type of fault based on telemetry data.
    Returns: 'normal', 'power_fault', 'thermal_fault', 'attitude_fault', or 'unknown_fault'
    """
    # Extract key telemetry parameters from the input data dictionary
    # Use default values if keys are missing to ensure robustness
    voltage = data.get("voltage", 8.0)  # Battery voltage in volts
    temperature = data.get("temperature", 25.0)  # System temperature in Celsius
    gyro = abs(data.get("gyro", 0.0))  # Absolute gyroscope reading in rad/s

    # Fault classification logic based on predefined thresholds
    # Check for power-related faults first (highest priority)
    if voltage < 7.3:
        # Critical voltage threshold: below 7.3V indicates battery/power system failure
        return "power_fault"
    
    # Check for thermal faults (overheating)
    if temperature > 32.0:
        # Temperature safety limit: above 32°C suggests cooling system issues
        return "thermal_fault"
    
    # Check for attitude/orientation faults (excessive rotation)
    if gyro > 0.05:
        # Gyroscopic threshold: above 0.05 rad/s indicates unstable attitude
        return "attitude_fault"

    # If no faults detected, system is operating normally
    return "normal"


def get_fault_severity(fault_type: str) -> str:
    """Get severity level for a fault type."""
    # Mapping of fault types to their severity levels
    # Severity levels: critical (immediate action required), high (urgent), medium (monitor), low (normal)
    severity_map = {
        "power_fault": "critical",  # Power issues can cause immediate system shutdown
        "thermal_fault": "high",    # Overheating can lead to component damage
        "attitude_fault": "medium", # Orientation issues may affect mission but not immediately critical
        "normal": "low",            # No fault detected
        "unknown_fault": "low",     # Unknown state, assume low risk
    }
    return severity_map.get(fault_type, "low")


def get_fault_description(fault_type: str) -> str:
    """Get human-readable description for a fault type."""
    # Human-readable descriptions for each fault type, including threshold values
    desc_map = {
        "power_fault": "Voltage dropped below critical threshold (7.3V)",  # Battery low
        "thermal_fault": "Temperature exceeded safety limit (32°C)",      # Overheating
        "attitude_fault": "Gyroscope detected excessive rotation (>0.05 rad/s)",  # Unstable orientation
        "normal": "System operating within normal parameters",            # All good
        "unknown_fault": "Unidentified anomaly detected",                 # Something unexpected
    }
    return desc_map.get(fault_type, "Unknown system state")
