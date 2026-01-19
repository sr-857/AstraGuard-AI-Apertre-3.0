"""Structured operator feedback schema for adaptive learning loop."""

from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from typing import Optional
from datetime import datetime


class FeedbackLabel(str, Enum):
    """Operator assessment of recovery action efficacy."""

    CORRECT = "correct"
    INSUFFICIENT = "insufficient"
    WRONG = "wrong"


class FeedbackEvent(BaseModel):
    """Pydantic model for operator-validated fault recovery events."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    fault_id: str = Field(..., min_length=1, max_length=64)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    anomaly_type: str = Field(..., min_length=1, max_length=64)
    recovery_action: str = Field(..., min_length=1, max_length=128)
    label: Optional[FeedbackLabel] = None
    operator_notes: Optional[str] = Field(None, max_length=500)
    mission_phase: str = Field(
        ..., pattern=r"^(LAUNCH|DEPLOYMENT|NOMINAL_OPS|PAYLOAD_OPS|SAFE_MODE)$"
    )
    confidence_score: float = Field(1.0, ge=0.0, le=1.0)
