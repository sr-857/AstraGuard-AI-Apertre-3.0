"""
Anomaly Recurrence Resonance Scorer

Signal reinforcement inspired by first-principles physics.
Boosts memory weight when patterns repeat.
"""

import numpy as np
from typing import List, Dict


class RecurrenceScorer:
    """
    Experimental feature: Anomaly Recurrence Resonance Score

    Concept: Signal reinforcement instead of brute storage
    Implementation: ~10 lines but demonstrates first-principles thinking
    """

    def __init__(self, resonance_factor: float = 0.3):
        """
        Initialize recurrence scorer.

        Args:
            resonance_factor: Amplification factor for recurrence (default: 0.3)
        """
        self.resonance_factor = resonance_factor

    def calculate_resonance(
        self, base_importance: float, recurrence_count: int, time_decay: float
    ) -> float:
        """
        Calculate resonance score using signal reinforcement principle.

        Formula: resonance = base × (1 + α × log(1 + recurrence)) × decay

        Where:
        - base: Initial importance/severity
        - α: Resonance amplification factor
        - recurrence: Number of times pattern repeated
        - decay: Temporal decay factor

        Args:
            base_importance: Initial severity score
            recurrence_count: Number of pattern repetitions
            time_decay: Temporal decay factor (0-1)

        Returns:
            Resonance-weighted importance score
        """
        # Signal reinforcement formula (first-principles inspired)
        resonance = (
            base_importance
            * (1 + self.resonance_factor * np.log(1 + recurrence_count))
            * time_decay
        )

        return resonance

    def score_event(self, event_metadata: Dict, similar_events: List[Dict]) -> float:
        """
        Score an event based on recurrence resonance.

        Args:
            event_metadata: Current event metadata
            similar_events: List of similar past events

        Returns:
            Resonance score
        """
        base = event_metadata.get("severity", 0.5)
        recurrence = len(similar_events)

        # Calculate average time decay from similar events
        if similar_events:
            decays = [e.get("temporal_weight", 1.0) for e in similar_events]
            avg_decay = np.mean(decays)
        else:
            avg_decay = 1.0

        return self.calculate_resonance(base, recurrence, avg_decay)
