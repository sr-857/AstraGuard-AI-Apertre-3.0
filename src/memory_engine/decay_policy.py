"""
Decay Policy for Adaptive Memory

Implements safe decay mechanisms with critical event protection.
"""

from datetime import datetime, timedelta


class DecayPolicy:
    """
    Safe decay mechanism for memory pruning.

    Features:
    - Exponential decay for old events
    - Critical event protection
    - Configurable retention policies
    """

    def __init__(self, default_retention_hours: int = 24):
        """
        Initialize decay policy.

        Args:
            default_retention_hours: Default retention period
        """
        self.default_retention_hours = default_retention_hours
        self.retention_policies = {
            "critical": None,  # Never decay
            "high": 168,  # 7 days
            "medium": 72,  # 3 days
            "low": 24,  # 1 day
        }

    def should_keep(self, event, current_time: datetime) -> bool:
        """
        Determine if event should be kept in memory.

        Args:
            event: Memory event to evaluate
            current_time: Current timestamp

        Returns:
            True if event should be kept, False otherwise
        """
        # Always keep critical events
        if event.is_critical:
            return True

        # Get retention policy based on severity
        severity = event.metadata.get("severity_level", "medium")
        retention_hours = self.retention_policies.get(
            severity, self.default_retention_hours
        )

        # If retention is None (critical), always keep
        if retention_hours is None:
            return True

        # Check if event is within retention period
        age = current_time - event.timestamp
        return age < timedelta(hours=retention_hours)

    def calculate_decay_weight(
        self, event, current_time: datetime, decay_lambda: float = 0.1
    ) -> float:
        """
        Calculate decay weight for an event.

        Args:
            event: Memory event
            current_time: Current timestamp
            decay_lambda: Decay rate parameter

        Returns:
            Decay weight (0-1)
        """
        import numpy as np

        age_hours = (current_time - event.timestamp).total_seconds() / 3600
        return np.exp(-decay_lambda * age_hours)
