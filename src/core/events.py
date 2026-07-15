"""
Event Taxonomy for AstraGuard Core Subsystems.
Defines the structure of events used in the event-driven architecture.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

@dataclass
class Event:
    """Base class for all system events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.__class__.__name__,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

@dataclass
class TelemetryReceived(Event):
    """Emitted when raw telemetry data is ingested."""
    telemetry_data: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "telemetry_data": self.telemetry_data,
            "source": self.source
        })
        return data

@dataclass
class AnomalyDetected(Event):
    """Emitted when the anomaly detection engine identifies an issue."""
    anomaly_score: float = 0.0
    is_anomaly: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "anomaly_score": self.anomaly_score,
            "is_anomaly": self.is_anomaly,
            "details": self.details
        })
        return data

@dataclass
class StateTransitioned(Event):
    """Emitted when the system state or mission phase changes."""
    previous_state: str = ""
    new_state: str = ""
    transition_type: str = "state" # 'state' or 'phase'
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "transition_type": self.transition_type,
            "reason": self.reason
        })
        return data

@dataclass
class RecoveryInitiated(Event):
    """Emitted when an automated recovery procedure begins."""
    recovery_plan_id: str = ""
    target_component: str = ""
    steps: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "recovery_plan_id": self.recovery_plan_id,
            "target_component": self.target_component,
            "steps": self.steps
        })
        return data
