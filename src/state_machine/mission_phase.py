"""
Mission Phase Enumeration - Centralized definition of all mission phases.

This module provides a single source of truth for mission phases,
preventing hardcoded strings throughout the codebase.
"""

from enum import Enum


class MissionPhase(str, Enum):
    """
    Enumeration of all mission phases with their string representations.
    
    Phases represent different stages of a spacecraft's mission lifecycle,
    each with specific operational constraints and recovery policies.
    """

    LAUNCH = "LAUNCH"
    """Launch phase: High-risk operations, system validation, strict controls"""

    DEPLOYMENT = "DEPLOYMENT"
    """Deployment phase: Payload/subsystem initialization, moderate constraints"""

    NOMINAL_OPS = "NOMINAL_OPS"
    """Nominal operations: Steady-state mission execution, standard policies"""

    PAYLOAD_OPS = "PAYLOAD_OPS"
    """Payload operations: Specialized payload subsystem activities"""

    SAFE_MODE = "SAFE_MODE"
    """Safe mode: Emergency recovery mode, minimal operations only"""

    @classmethod
    def is_valid(cls, phase_str: str) -> bool:
        """
        Check if a string represents a valid mission phase.
        
        Args:
            phase_str: String to validate
            
        Returns:
            True if phase_str is a valid MissionPhase value
        """
        try:
            cls(phase_str)
            return True
        except ValueError:
            return False

    @classmethod
    def from_string(cls, phase_str: str) -> "MissionPhase":
        """
        Convert string to MissionPhase enum safely.
        
        Args:
            phase_str: String to convert
            
        Returns:
            MissionPhase enum value
            
        Raises:
            ValueError: If phase_str is not a valid phase
        """
        try:
            return cls(phase_str)
        except ValueError:
            valid_phases = ", ".join([p.value for p in cls])
            raise ValueError(
                f"Invalid mission phase '{phase_str}'. "
                f"Valid phases: {valid_phases}"
            )
