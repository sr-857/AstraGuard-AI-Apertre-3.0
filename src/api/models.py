"""
Pydantic models for API request/response validation.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

logger = logging.getLogger(__name__)


class ModelValidationError(Exception):
    """Raised when model validation fails with actionable context."""

    def __init__(self, message: str, field_name: Optional[str] = None,
                 provided_value: Optional[Any] = None,
                 constraints: Optional[Dict[str, Any]] = None):
        self.message = message
        self.field_name = field_name
        self.provided_value = provided_value
        self.constraints = constraints or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "field_name": self.field_name,
            "provided_value": self.provided_value,
            "constraints": self.constraints,
        }


class UserRole(str, Enum):
    """User roles with hierarchical permissions."""
    ADMIN = "admin"      # Full system access including user management
    OPERATOR = "operator"  # Full operational access (telemetry, phase changes)
    ANALYST = "analyst"   # Read-only access (status, history, monitoring)


class MissionPhaseEnum(str, Enum):
    """Mission phase enumeration."""
    LAUNCH = "LAUNCH"
    DEPLOYMENT = "DEPLOYMENT"
    NOMINAL_OPS = "NOMINAL_OPS"
    PAYLOAD_OPS = "PAYLOAD_OPS"
    SAFE_MODE = "SAFE_MODE"


class TelemetryInput(BaseModel):
    """Single telemetry data point."""
    voltage: float = Field(..., ge=0, le=50, description="Voltage in volts")
    temperature: float = Field(..., ge=-100, le=150, description="Temperature in Celsius")
    gyro: float = Field(..., description="Gyroscope reading in rad/s")
    current: Optional[float] = Field(None, ge=0, description="Current in amperes")
    wheel_speed: Optional[float] = Field(None, ge=0, description="Reaction wheel speed in RPM")

    cpu_usage: Optional[float] = Field(None, ge=0, le=100, description="CPU usage percentage")
    memory_usage: Optional[float] = Field(None, ge=0, le=100, description="Memory usage percentage")
    network_latency: Optional[float] = Field(None, ge=0, description="Network latency in ms")
    disk_io: Optional[float] = Field(None, ge=0, description="Disk I/O operations per second")
    error_rate: Optional[float] = Field(None, ge=0, description="Error rate per minute")
    response_time: Optional[float] = Field(None, ge=0, description="Response time in ms")
    active_connections: Optional[int] = Field(None, ge=0, description="Number of active connections")

    timestamp: Optional[datetime] = Field(None, description="Telemetry timestamp")

    @field_validator('timestamp', mode='before')
    @classmethod
    def set_timestamp(cls, v):
        """Set timestamp to now if not provided."""
        if v is None:
            return datetime.now()

        if isinstance(v, datetime):
            return v

        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError as e:
                logger.warning(
                    "timestamp_parsing_failed",
                    extra={
                        "provided_value": v[:50] if len(v) > 50 else v,
                        "error": str(e),
                        "action": "using_current_timestamp"
                    }
                )
                return datetime.now()

        logger.warning(
            "timestamp_type_invalid",
            extra={
                "provided_value": type(v).__name__,
                "expected_types": ["None", "datetime", "str"],
                "action": "using_current_timestamp"
            }
        )
        return datetime.now()


class TelemetryBatch(BaseModel):
    """Batch of telemetry data points."""
    telemetry: List[TelemetryInput] = Field(..., min_length=1, max_length=10000)

    @field_validator('telemetry')
    @classmethod
    def validate_telemetry_batch(cls, v):
        """Validate telemetry batch with edge case handling."""
        if not v:
            logger.warning(
                "empty_telemetry_batch",
                extra={
                    "action": "rejected",
                    "reason": "batch_must_contain_at_least_one_item"
                }
            )
            raise ValueError("Telemetry batch must contain at least one item")

        if len(v) > 10000:
            logger.warning(
                "telemetry_batch_too_large",
                extra={
                    "batch_size": len(v),
                    "max_allowed": 10000,
                    "action": "truncated_to_max"
                }
            )
            return v[:10000]

        return v


class AnomalyResponse(BaseModel):
    """Response from anomaly detection."""
    is_anomaly: bool
    anomaly_score: float = Field(..., ge=0, le=1)
    anomaly_type: str
    severity_score: float = Field(..., ge=0, le=1)
    severity_level: str
    mission_phase: str
    recommended_action: str
    escalation_level: str
    is_allowed: bool
    allowed_actions: List[str]
    should_escalate_to_safe_mode: bool
    confidence: float = Field(..., ge=0, le=1)
    reasoning: str
    recurrence_count: int = Field(..., ge=0)
    timestamp: datetime


class BatchAnomalyResponse(BaseModel):
    """Response from batch anomaly detection."""
    total_processed: int
    anomalies_detected: int
    results: List[AnomalyResponse]


class SystemStatus(BaseModel):
    """System health and status."""
    status: str = Field(..., description="Overall system status")
    mission_phase: str
    components: Dict[str, Any]
    uptime_seconds: float
    timestamp: datetime


class PhaseUpdateRequest(BaseModel):
    """Request to update mission phase."""
    phase: MissionPhaseEnum
    force: bool = Field(False, description="Force transition even if invalid")

    @field_validator('phase', mode='before')
    @classmethod
    def validate_phase(cls, v):
        """Validate and log phase transition."""
        if isinstance(v, MissionPhaseEnum):
            return v
        if isinstance(v, str):
            try:
                phase = MissionPhaseEnum(v.upper())
                logger.info(
                    "phase_normalized",
                    extra={
                        "original": v,
                        "normalized": phase.value,
                        "action": "normalized_to_enum"
                    }
                )
                return phase
            except ValueError:
                valid_phases = [p.value for p in MissionPhaseEnum]
                logger.error(
                    "invalid_phase_value",
                    extra={
                        "provided": v,
                        "valid_values": valid_phases
                    }
                )
                raise ValueError(f"Invalid phase: {v}. Valid phases: {valid_phases}")
        raise TypeError(f"Phase must be a string or MissionPhaseEnum, got {type(v).__name__}")


class PhaseUpdateResponse(BaseModel):
    """Response from phase update."""
    success: bool
    previous_phase: str
    new_phase: str
    message: str
    timestamp: datetime


class MemoryStats(BaseModel):
    """Memory store statistics."""
    total_events: int
    critical_events: int
    avg_age_hours: float
    max_recurrence: int
    timestamp: datetime


class AnomalyHistoryQuery(BaseModel):
    """Query parameters for anomaly history."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    severity_min: Optional[float] = Field(None, ge=0, le=1)

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v):
        """Validate and log limit value."""
        if v < 1:
            logger.info(
                "limit_adjusted",
                extra={
                    "requested": v,
                    "adjusted_to": 1,
                    "reason": "minimum_value_enforced"
                }
            )
            return 1
        if v > 1000:
            logger.info(
                "limit_adjusted",
                extra={
                    "requested": v,
                    "adjusted_to": 1000,
                    "reason": "maximum_value_enforced"
                }
            )
            return 1000
        return v

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def validate_datetime(cls, v):
        """Validate datetime inputs."""
        if v is None:
            return v
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(
                    "datetime_parse_failed",
                    extra={
                        "provided_value": v[:50] if len(v) > 50 else v,
                        "action": "ignored"
                    }
                )
                return None
        return v

    @field_validator('severity_min')
    @classmethod
    def validate_severity_min(cls, v):
        """Validate severity minimum."""
        if v is not None and (v < 0 or v > 1):
            logger.warning(
                "severity_min_out_of_range",
                extra={
                    "provided_value": v,
                    "valid_range": [0, 1],
                    "action": "clamped_to_boundary"
                }
            )
            return max(0, min(1, v))
        return v

    @field_validator('end_time')
    @classmethod
    def validate_time_range(cls, v, info):
        """Validate that end_time is not before start_time."""
        start_time = info.data.get('start_time')
        if start_time is not None and v is not None and v < start_time:
            logger.warning(
                "time_range_invalid",
                extra={
                    "start_time": start_time.isoformat(),
                    "end_time": v.isoformat(),
                    "action": "end_time_set_to_start_time"
                }
            )
            return start_time
        return v


class AnomalyHistoryResponse(BaseModel):
    """Response with anomaly history."""
    count: int
    anomalies: List[AnomalyResponse]
    start_time: Optional[datetime]
    end_time: Optional[datetime]


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
    uptime_seconds: Optional[float] = None
    mission_phase: Optional[str] = None
    components_status: Optional[Dict[str, Dict[str, Any]]] = None
    error: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validate username format."""
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")

        username = v.strip().lower()
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters")

        if len(username) > 50:
            raise ValueError("Username cannot exceed 50 characters")

        return username


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str


class UserCreateRequest(BaseModel):
    """Request to create a new user."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    role: UserRole
    password: Optional[str] = Field(None, min_length=8)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validate username for security and formatting."""
        if not v or not v.strip():
            raise ValueError("Username cannot be empty or whitespace only")

        username = v.strip()

        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")

        if len(username) > 50:
            raise ValueError("Username cannot exceed 50 characters")

        if not username[0].isalnum():
            logger.warning(
                "username_starts_with_special",
                extra={
                    "username": username[:10] + "***" if len(username) > 10 else username,
                    "warning": "Username starts with special character"
                }
            )

        return username.lower()

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validate password strength."""
        if v is None:
            return v

        if len(v) < 8:
            logger.warning(
                "password_too_short",
                extra={
                    "min_length": 8,
                    "provided_length": len(v),
                    "warning": "Password meets minimum length but consider longer passwords"
                }
            )

        return v


class UserResponse(BaseModel):
    """User information response."""
    id: str
    username: str
    email: str
    role: str
    created_at: datetime
    is_active: bool


class APIKeyCreateRequest(BaseModel):
    """Request to create an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    permissions: List[str] = Field(..., min_length=1)

    @field_validator('name')
    @classmethod
    def validate_api_key_name(cls, v):
        """Validate API key name."""
        if not v or not v.strip():
            raise ValueError("API key name cannot be empty")

        name = v.strip()
        if len(name) > 100:
            raise ValueError("API key name cannot exceed 100 characters")

        logger.info(
            "api_key_name_valid",
            extra={
                "name_length": len(name),
                "action": "accepted"
            }
        )
        return name

    @field_validator('permissions')
    @classmethod
    def validate_permissions(cls, v):
        """Validate permissions list."""
        if not v:
            raise ValueError("At least one permission must be specified")

        valid_permissions = {'read', 'write', 'admin', 'execute'}
        invalid_permissions = set(p.lower() for p in v) - valid_permissions

        if invalid_permissions:
            logger.warning(
                "invalid_permissions_provided",
                extra={
                    "invalid_permissions": list(invalid_permissions),
                    "valid_permissions": list(valid_permissions),
                    "action": "accepted_with_warning"
                }
            )

        return [p.lower() for p in v]


class APIKeyResponse(BaseModel):
    """API key information response (without the key value)."""
    id: str
    name: str
    permissions: List[str]
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]


class APIKeyCreateResponse(BaseModel):
    """API key creation response (includes the key value)."""
    id: str
    name: str
    key: str
    permissions: List[str]
    created_at: datetime
    expires_at: Optional[datetime]
