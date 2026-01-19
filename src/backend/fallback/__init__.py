"""
Fallback Package

Provides fallback orchestration and condition parsing for AstraGuard backend.

Components:
- FallbackManager: Progressive fallback cascade orchestration
- ConditionParser: Safe, pure condition evaluation
- FallbackMode: Enum for system operation modes
"""

from .manager import FallbackManager, FallbackMode
from .condition_parser import (
    ConditionParser,
    Condition,
    parse_condition,
    evaluate,
)

__all__ = [
    "FallbackManager",
    "FallbackMode",
    "ConditionParser",
    "Condition",
    "parse_condition",
    "evaluate",
]
