"""
Structured Output Schema

Pydantic models for enforcing JSON structure in LLM responses.
Ensures type safety and consistent parsing.
"""
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator, ValidationError
import enum

class ConfidenceLevel(str, enum.Enum):
    """Confidence levels for agent decisions."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ActionType(str, enum.Enum):
    """Allowed action types for agents."""
    ANALYZE = "analyze"
    EXECUTE = "execute"
    PLAN = "plan"
    WAIT = "wait"
    ESCALATE = "escalate"
    REQUEST_CLARIFICATION = "request_clarification"

class ToolCall(BaseModel):
    """Structure for a tool invocation."""
    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: Dict[str, Any] = Field(..., description="Arguments for the tool")

    @field_validator('tool_name')
    def validate_tool_name(cls, v):
        if not v or not v.strip():
            raise ValueError("tool_name cannot be empty")
        return v.strip()

class AgentAnalysis(BaseModel):
    """Analysis component of the agent's response."""
    observation: str = Field(..., description="What the agent observed in the input")
    reasoning: str = Field(..., description="Chain of thought leading to the conclusion")
    key_factors: List[str] = Field(..., description="List of critical factors identified")

class AgentOutput(BaseModel):
    """
    Main structured output for agent responses.
    This schema is enforced on LLM completions.
    """
    analysis: AgentAnalysis = Field(..., description="Detailed analysis of the situation")
    action: ActionType = Field(..., description="Primary action to take")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="List of tools to execute, if any")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 - 1.0)")
    next_step_hint: Optional[str] = Field(None, description="Hint for the next iteration")

    @field_validator('confidence')
    def validate_confidence(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return round(v, 2)

    def is_confident(self, threshold: float = 0.7) -> bool:
        """Check if response meets confidence threshold."""
        return self.confidence >= threshold

    def has_tools(self) -> bool:
        """Check if any tools are requested."""
        return bool(self.tool_calls)
