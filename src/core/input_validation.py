"""
Core Input Validation Module
Provides comprehensive input validation for all telemetry and decision data
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Raised when input validation fails"""
    pass

# ============================================================================
# TELEMETRY VALIDATION
# ============================================================================

@dataclass
class TelemetryData:
    """Validated telemetry schema with strict bounds checking"""
    voltage: float           # 0.0 - 15.0V
    temperature: float       # -50°C to 100°C
    gyro: float             # -360 to 360 deg/s
    current: float          # 0.0 - 5.0A
    wheel_speed: float      # 0 - 10000 RPM
    
    # Validation bounds
    BOUNDS = {
        'voltage': (0.0, 15.0, 'Volts'),
        'temperature': (-50.0, 100.0, 'Celsius'),
        'gyro': (-360.0, 360.0, 'deg/s'),
        'current': (0.0, 5.0, 'Amperes'),
        'wheel_speed': (0.0, 10000.0, 'RPM')
    }
    
    @staticmethod
    def validate(data: Dict[str, Any]) -> 'TelemetryData':
        """
        Validate and construct telemetry data with strict bounds.
        
        Args:
            data: Dictionary with telemetry values
            
        Returns:
            TelemetryData: Validated telemetry object
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(data, dict):
            raise ValidationError(f"Telemetry must be dict, got {type(data).__name__}")
        
        errors = []
        validated = {}
        
        for field, (min_val, max_val, unit) in TelemetryData.BOUNDS.items():
            value = data.get(field)
            
            # Type check
            if value is None:
                errors.append(f"{field}: missing (required)")
                continue
            
            if not isinstance(value, (int, float)):
                errors.append(f"{field}: expected numeric, got {type(value).__name__}")
                continue
            
            # Range check
            if not min_val <= value <= max_val:
                errors.append(
                    f"{field}: {value}{unit} out of range [{min_val}, {max_val}]{unit}"
                )
                continue
            
            validated[field] = float(value)
        
        if errors:
            error_msg = "; ".join(errors)
            logger.warning(f"Telemetry validation failed: {error_msg}")
            raise ValidationError(f"Telemetry validation failed: {error_msg}")
        
        return TelemetryData(**validated)


# ============================================================================
# POLICY DECISION VALIDATION
# ============================================================================

class SeverityLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AnomalyType(Enum):
    POWER_FAULT = "power_fault"
    THERMAL_FAULT = "thermal_fault"
    ATTITUDE_FAULT = "attitude_fault"
    UNKNOWN_FAULT = "unknown_fault"

@dataclass
class PolicyDecision:
    """Validated policy decision"""
    mission_phase: str
    anomaly_type: str
    severity: str
    recommended_action: str
    detection_confidence: float
    timestamp: str
    reasoning: Optional[str] = None
    
    REQUIRED_FIELDS = [
        'mission_phase',
        'anomaly_type',
        'severity',
        'recommended_action',
        'detection_confidence'
    ]
    
    VALID_SEVERITIES = {s.value for s in SeverityLevel}
    VALID_ANOMALY_TYPES = {a.value for a in AnomalyType}
    
    @staticmethod
    def validate(decision: Dict[str, Any]) -> 'PolicyDecision':
        """
        Validate policy engine decision.
        
        Args:
            decision: Decision dictionary from policy engine
            
        Returns:
            PolicyDecision: Validated decision object
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(decision, dict):
            raise ValidationError(f"Decision must be dict, got {type(decision).__name__}")
        
        errors = []
        
        # Check required fields
        missing_fields = [f for f in PolicyDecision.REQUIRED_FIELDS if f not in decision]
        if missing_fields:
            errors.append(f"Missing fields: {', '.join(missing_fields)}")
        
        # Validate each field
        if 'mission_phase' in decision:
            phase = decision['mission_phase']
            if not isinstance(phase, str) or not phase.strip():
                errors.append(f"mission_phase must be non-empty string, got '{phase}'")
        
        if 'anomaly_type' in decision:
            atype = decision['anomaly_type']
            if atype not in PolicyDecision.VALID_ANOMALY_TYPES:
                errors.append(
                    f"anomaly_type '{atype}' not in {PolicyDecision.VALID_ANOMALY_TYPES}"
                )
        
        if 'severity' in decision:
            severity = decision['severity']
            if severity not in PolicyDecision.VALID_SEVERITIES:
                errors.append(
                    f"severity '{severity}' not in {PolicyDecision.VALID_SEVERITIES}"
                )
        
        if 'detection_confidence' in decision:
            confidence = decision['detection_confidence']
            if not isinstance(confidence, (int, float)):
                errors.append(f"confidence must be numeric, got {type(confidence).__name__}")
            elif not 0.0 <= confidence <= 1.0:
                errors.append(f"confidence {confidence} out of range [0.0, 1.0]")
        
        if 'recommended_action' in decision:
            action = decision['recommended_action']
            if not isinstance(action, str) or not action.strip():
                errors.append(f"recommended_action must be non-empty string")
        
        if errors:
            error_msg = "; ".join(errors)
            logger.warning(f"Decision validation failed: {error_msg}")
            raise ValidationError(f"Decision validation failed: {error_msg}")
        
        return PolicyDecision(
            mission_phase=decision['mission_phase'],
            anomaly_type=decision['anomaly_type'],
            severity=decision['severity'],
            recommended_action=decision['recommended_action'],
            detection_confidence=float(decision['detection_confidence']),
            timestamp=decision.get('timestamp', ''),
            reasoning=decision.get('reasoning')
        )


# ============================================================================
# PHASE TRANSITION VALIDATION
# ============================================================================

class MissionPhaseValidator:
    """Validate mission phase transitions"""
    
    VALID_PHASES = {
        'LAUNCH', 'DEPLOYMENT', 'NOMINAL_OPS', 'DEGRADED_MODE',
        'SAFE_MODE', 'RECOVERY_OPS', 'PAYLOAD_OPS'
    }
    
    VALID_TRANSITIONS = {
        'LAUNCH': {'DEPLOYMENT', 'SAFE_MODE'},
        'DEPLOYMENT': {'NOMINAL_OPS', 'SAFE_MODE'},
        'NOMINAL_OPS': {'DEGRADED_MODE', 'SAFE_MODE', 'RECOVERY_OPS', 'PAYLOAD_OPS'},
        'DEGRADED_MODE': {'NOMINAL_OPS', 'SAFE_MODE', 'RECOVERY_OPS'},
        'SAFE_MODE': {'NOMINAL_OPS', 'RECOVERY_OPS'},
        'RECOVERY_OPS': {'NOMINAL_OPS', 'SAFE_MODE'},
        'PAYLOAD_OPS': {'NOMINAL_OPS', 'SAFE_MODE'}
    }
    
    @staticmethod
    def validate_phase(phase: str) -> str:
        """
        Validate a phase string.
        
        Args:
            phase: Phase name to validate
            
        Returns:
            str: Validated phase name
            
        Raises:
            ValidationError: If phase is invalid
        """
        if not isinstance(phase, str):
            raise ValidationError(f"Phase must be string, got {type(phase).__name__}")
        
        phase_upper = phase.upper().strip()
        
        if phase_upper not in MissionPhaseValidator.VALID_PHASES:
            raise ValidationError(
                f"Phase '{phase_upper}' not in {MissionPhaseValidator.VALID_PHASES}"
            )
        
        return phase_upper
    
    @staticmethod
    def validate_transition(current_phase: str, next_phase: str) -> Tuple[str, str]:
        """
        Validate phase transition is allowed.
        
        Args:
            current_phase: Current mission phase
            next_phase: Proposed next phase
            
        Returns:
            Tuple[str, str]: Validated (current, next) phases
            
        Raises:
            ValidationError: If transition is invalid
        """
        current = MissionPhaseValidator.validate_phase(current_phase)
        next_p = MissionPhaseValidator.validate_phase(next_phase)
        
        if current == next_p:
            raise ValidationError(f"Cannot transition from {current} to itself")
        
        allowed = MissionPhaseValidator.VALID_TRANSITIONS.get(current, set())
        if next_p not in allowed:
            raise ValidationError(
                f"Invalid transition: {current} -> {next_p}. "
                f"Allowed: {current} -> {allowed}"
            )
        
        return current, next_p
