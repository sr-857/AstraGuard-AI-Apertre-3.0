"""
Confidence Score Calculator for Anomaly Decisions

Computes a single confidence score [0.0, 1.0] based on multiple factors:
- Anomaly detection score (primary signal)
- Historical recurrence/memory signal
- Mission phase context
- Policy alignment
- Temporal decay

Higher score = higher confidence in the system's decision.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceFactors:
    """
    Internal breakdown of confidence factors.
    Not exposed in public API but useful for debugging/logging.
    """
    anomaly_score: float
    recurrence_boost: float
    phase_penalty: float
    policy_alignment: float
    temporal_weight: float


class ConfidenceScorer:
    """
    Multi-factor confidence score calculator.
    
    Computes a single aggregated confidence score based on:
    1. Anomaly detection score (strongest contributor)
    2. Historical recurrence/memory signal
    3. Mission phase context
    4. Policy alignment
    5. Temporal decay
    
    Design principles:
    - Pure computation (no side effects)
    - Integration-friendly (pass data, not objects)
    - Adjustable weights via constants
    """
    
    # Default weights for each factor (sum to 1.0)
    WEIGHT_ANOMALY_SCORE = 0.40      # Primary signal
    WEIGHT_RECURRENCE = 0.20         # Historical pattern
    WEIGHT_PHASE_CONTEXT = 0.15      # Mission phase appropriateness
    WEIGHT_POLICY_ALIGNMENT = 0.15   # Policy compliance
    WEIGHT_TEMPORAL = 0.10           # Time decay
    
    # Phase risk levels (higher = more risky/unusual)
    PHASE_RISK = {
        "LAUNCH": 0.9,           # Very risky, penalize confidence
        "DEPLOYMENT": 0.7,       # Risky, moderate penalty
        "NOMINAL_OPS": 0.3,      # Standard operations, low penalty
        "PAYLOAD_OPS": 0.4,      # Science mission, slight penalty
        "SAFE_MODE": 0.8,        # Emergency mode, high penalty
    }
    
    def __init__(
        self,
        weight_anomaly: float = WEIGHT_ANOMALY_SCORE,
        weight_recurrence: float = WEIGHT_RECURRENCE,
        weight_phase: float = WEIGHT_PHASE_CONTEXT,
        weight_policy: float = WEIGHT_POLICY_ALIGNMENT,
        weight_temporal: float = WEIGHT_TEMPORAL,
    ):
        """
        Initialize confidence scorer with custom weights.
        
        Args:
            weight_anomaly: Weight for anomaly detection score (default: 0.40)
            weight_recurrence: Weight for recurrence signal (default: 0.20)
            weight_phase: Weight for phase context (default: 0.15)
            weight_policy: Weight for policy alignment (default: 0.15)
            weight_temporal: Weight for temporal decay (default: 0.10)
        """
        self.weight_anomaly = weight_anomaly
        self.weight_recurrence = weight_recurrence
        self.weight_phase = weight_phase
        self.weight_policy = weight_policy
        self.weight_temporal = weight_temporal
        
        # Validate weights sum to 1.0 (with tolerance for floating point)
        total_weight = sum([
            weight_anomaly, weight_recurrence, weight_phase,
            weight_policy, weight_temporal
        ])
        if not (0.99 <= total_weight <= 1.01):
            logger.warning(
                f"Confidence weights sum to {total_weight:.3f}, not 1.0. "
                f"Normalizing weights."
            )
            # Normalize weights
            self.weight_anomaly /= total_weight
            self.weight_recurrence /= total_weight
            self.weight_phase /= total_weight
            self.weight_policy /= total_weight
            self.weight_temporal /= total_weight
    
    def calculate_confidence(
        self,
        anomaly_score: float,
        recurrence_count: int = 0,
        mission_phase: str = "NOMINAL_OPS",
        policy_allowed: bool = True,
        temporal_decay: float = 1.0,
        anomaly_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculate aggregated confidence score.
        
        Args:
            anomaly_score: Anomaly detection score [0.0, 1.0] (primary signal)
            recurrence_count: Number of similar historical anomalies (default: 0)
            mission_phase: Current mission phase (default: "NOMINAL_OPS")
            policy_allowed: Whether action is allowed by phase policy (default: True)
            temporal_decay: Time decay factor [0.0, 1.0] (default: 1.0)
            anomaly_metadata: Optional metadata for future extensions
        
        Returns:
            Confidence score [0.0, 1.0]
        """
        # Validate inputs
        anomaly_score = self._clamp(anomaly_score, 0.0, 1.0)
        temporal_decay = self._clamp(temporal_decay, 0.0, 1.0)
        recurrence_count = max(0, recurrence_count)
        
        # 1. Anomaly score contribution (primary signal)
        anomaly_contribution = anomaly_score * self.weight_anomaly
        
        # 2. Recurrence contribution (historical pattern)
        # More recurrences = higher confidence (logarithmic growth)
        import math
        if recurrence_count > 0:
            recurrence_signal = min(1.0, 0.3 + 0.2 * math.log(1 + recurrence_count))
        else:
            recurrence_signal = 0.0
        recurrence_contribution = recurrence_signal * self.weight_recurrence
        
        # 3. Phase context contribution (penalize risky phases)
        phase_risk = self.PHASE_RISK.get(mission_phase, 0.5)
        phase_signal = 1.0 - phase_risk  # Invert: lower risk = higher confidence
        phase_contribution = phase_signal * self.weight_phase
        
        # 4. Policy alignment contribution
        policy_signal = 1.0 if policy_allowed else 0.3  # Heavy penalty if not allowed
        policy_contribution = policy_signal * self.weight_policy
        
        # 5. Temporal contribution (time decay)
        temporal_contribution = temporal_decay * self.weight_temporal
        
        # Aggregate confidence score
        confidence = (
            anomaly_contribution +
            recurrence_contribution +
            phase_contribution +
            policy_contribution +
            temporal_contribution
        )
        
        # Ensure final score is in valid range
        confidence = self._clamp(confidence, 0.0, 1.0)
        
        # Log factor breakdown for debugging
        logger.debug(
            f"Confidence calculation: "
            f"anomaly={anomaly_contribution:.3f}, "
            f"recurrence={recurrence_contribution:.3f}, "
            f"phase={phase_contribution:.3f}, "
            f"policy={policy_contribution:.3f}, "
            f"temporal={temporal_contribution:.3f}, "
            f"total={confidence:.3f}"
        )
        
        return confidence
    
    def calculate_confidence_with_breakdown(
        self,
        anomaly_score: float,
        recurrence_count: int = 0,
        mission_phase: str = "NOMINAL_OPS",
        policy_allowed: bool = True,
        temporal_decay: float = 1.0,
        anomaly_metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[float, ConfidenceFactors]:
        """
        Calculate confidence score with detailed factor breakdown.
        
        Useful for debugging and internal analysis.
        
        Args:
            Same as calculate_confidence()
        
        Returns:
            Tuple of (confidence_score, ConfidenceFactors)
        """
        # Validate inputs
        anomaly_score = self._clamp(anomaly_score, 0.0, 1.0)
        temporal_decay = self._clamp(temporal_decay, 0.0, 1.0)
        recurrence_count = max(0, recurrence_count)
        
        # Calculate individual factors
        anomaly_contribution = anomaly_score * self.weight_anomaly
        
        import math
        if recurrence_count > 0:
            recurrence_signal = min(1.0, 0.3 + 0.2 * math.log(1 + recurrence_count))
        else:
            recurrence_signal = 0.0
        recurrence_contribution = recurrence_signal * self.weight_recurrence
        
        phase_risk = self.PHASE_RISK.get(mission_phase, 0.5)
        phase_signal = 1.0 - phase_risk
        phase_contribution = phase_signal * self.weight_phase
        
        policy_signal = 1.0 if policy_allowed else 0.3
        policy_contribution = policy_signal * self.weight_policy
        
        temporal_contribution = temporal_decay * self.weight_temporal
        
        # Aggregate
        confidence = self._clamp(
            anomaly_contribution + recurrence_contribution + phase_contribution +
            policy_contribution + temporal_contribution,
            0.0, 1.0
        )
        
        # Build breakdown
        factors = ConfidenceFactors(
            anomaly_score=anomaly_contribution,
            recurrence_boost=recurrence_contribution,
            phase_penalty=phase_contribution,
            policy_alignment=policy_contribution,
            temporal_weight=temporal_contribution,
        )
        
        return confidence, factors
    
    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        """Clamp value to range [min_val, max_val]."""
        return max(min_val, min(max_val, value))


# Convenience function for quick integration
def calculate_confidence(
    anomaly_score: float,
    recurrence_count: int = 0,
    mission_phase: str = "NOMINAL_OPS",
    policy_allowed: bool = True,
    temporal_decay: float = 1.0,
) -> float:
    """
    Convenience function to calculate confidence without instantiating scorer.
    
    Uses default weights.
    
    Args:
        anomaly_score: Anomaly detection score [0.0, 1.0]
        recurrence_count: Number of similar historical anomalies
        mission_phase: Current mission phase
        policy_allowed: Whether action is allowed by phase policy
        temporal_decay: Time decay factor [0.0, 1.0]
    
    Returns:
        Confidence score [0.0, 1.0]
    """
    scorer = ConfidenceScorer()
    return scorer.calculate_confidence(
        anomaly_score=anomaly_score,
        recurrence_count=recurrence_count,
        mission_phase=mission_phase,
        policy_allowed=policy_allowed,
        temporal_decay=temporal_decay,
    )
