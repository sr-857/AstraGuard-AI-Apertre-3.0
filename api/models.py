"""
Pydantic models for API request/response validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


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

    # Predictive maintenance fields
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
        return v


class TelemetryBatch(BaseModel):
    """Batch of telemetry data points."""
    telemetry: List[TelemetryInput] = Field(..., min_length=1, max_length=1000)


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
