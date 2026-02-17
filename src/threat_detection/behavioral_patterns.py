"""
Behavioral Pattern Definitions for Threat Detection

Defines patterns for normal vs. anomalous behavior across different
dimensions: time, geography, actions, and sequences.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Callable
from datetime import datetime, time, timedelta
from enum import Enum
import numpy as np
from collections import defaultdict


class BehaviorDimension(Enum):
    """Dimensions of behavior analysis."""
    TEMPORAL = "temporal"           # Time-based patterns
    GEOGRAPHIC = "geographic"       # Location-based patterns
    ACTION = "action"               # Action-based patterns
    SEQUENCE = "sequence"           # Action sequence patterns
    VOLUME = "volume"               # Data/request volume patterns
    PEER = "peer"                   # Peer group comparison


class PatternType(Enum):
    """Types of behavior patterns."""
    NORMAL = "normal"
    ANOMALOUS = "anomalous"
    SUSPICIOUS = "suspicious"


@dataclass
class BehaviorPattern:
    """Definition of a behavior pattern."""
    name: str
    dimension: BehaviorDimension
    pattern_type: PatternType
    description: str
    indicators: List[str]
    confidence_threshold: float = 0.7
    severity_weight: float = 1.0
    
    # Scoring function (returns 0-1 score based on data)
    scorer: Optional[Callable[[Dict[str, Any]], float]] = None
    
    def calculate_score(self, data: Dict[str, Any]) -> float:
        """Calculate pattern match score."""
        if self.scorer:
            return self.scorer(data)
        
        # Default: check for indicator presence
        score = 0.0
        for indicator in self.indicators:
            if indicator in data:
                value = data[indicator]
                if isinstance(value, (int, float)):
                    score += min(1.0, abs(value))
                elif isinstance(value, bool) and value:
                    score += 1.0
        
        return min(1.0, score / max(1, len(self.indicators)))


# Predefined behavioral patterns
BEHAVIORAL_PATTERNS = {
    # Temporal patterns
    "business_hours_access": BehaviorPattern(
        name="business_hours_access",
        dimension=BehaviorDimension.TEMPORAL,
        pattern_type=PatternType.NORMAL,
        description="Access during normal business hours (9 AM - 6 PM)",
        indicators=["hour_of_day", "is_business_hours"],
        confidence_threshold=0.8,
        severity_weight=0.5,
        scorer=lambda d: 1.0 if d.get("is_business_hours", False) else 0.3
    ),
    
    "off_hours_access": BehaviorPattern(
        name="off_hours_access",
        dimension=BehaviorDimension.TEMPORAL,
        pattern_type=PatternType.SUSPICIOUS,
        description="Access outside normal business hours",
        indicators=["hour_of_day", "is_business_hours", "is_weekend"],
        confidence_threshold=0.7,
        severity_weight=1.2,
        scorer=lambda d: 0.7 if not d.get("is_business_hours", True) else 0.2
    ),
    
    "weekend_access": BehaviorPattern(
        name="weekend_access",
        dimension=BehaviorDimension.TEMPORAL,
        pattern_type=PatternType.SUSPICIOUS,
        description="Access during weekends",
        indicators=["day_of_week", "is_weekend"],
        confidence_threshold=0.6,
        severity_weight=1.0,
        scorer=lambda d: 0.8 if d.get("is_weekend", False) else 0.1
    ),
    
    "consistent_schedule": BehaviorPattern(
        name="consistent_schedule",
        dimension=BehaviorDimension.TEMPORAL,
        pattern_type=PatternType.NORMAL,
        description="Access at consistent times",
        indicators=["schedule_variance", "typical_access_time"],
        confidence_threshold=0.75,
        severity_weight=0.6,
        scorer=lambda d: max(0.0, 1.0 - d.get("schedule_variance", 1.0))
    ),
    
    # Geographic patterns
    "usual_location": BehaviorPattern(
        name="usual_location",
        dimension=BehaviorDimension.GEOGRAPHIC,
        pattern_type=PatternType.NORMAL,
        description="Access from typical geographic location",
        indicators=["geo_distance_from_usual", "is_known_location"],
        confidence_threshold=0.8,
        severity_weight=0.5,
        scorer=lambda d: 1.0 if d.get("is_known_location", False) else max(0.0, 1.0 - d.get("geo_distance_from_usual", 1.0))
    ),
    
    "impossible_travel": BehaviorPattern(
        name="impossible_travel",
        dimension=BehaviorDimension.GEOGRAPHIC,
        pattern_type=PatternType.ANOMALOUS,
        description="Geographic locations too far apart for time elapsed",
        indicators=["geo_velocity", "time_between_access", "geo_distance"],
        confidence_threshold=0.8,
        severity_weight=2.0,
        scorer=lambda d: 1.0 if d.get("geo_velocity", 0) > 800 else 0.0  # 800 km/h threshold
    ),
    
    "new_country_access": BehaviorPattern(
        name="new_country_access",
        dimension=BehaviorDimension.GEOGRAPHIC,
        pattern_type=PatternType.SUSPICIOUS,
        description="First-time access from a new country",
        indicators=["is_new_country", "country_risk_score"],
        confidence_threshold=0.7,
        severity_weight=1.3,
        scorer=lambda d: 0.8 if d.get("is_new_country", False) else 0.1
    ),
    
    "high_risk_country": BehaviorPattern(
        name="high_risk_country",
        dimension=BehaviorDimension.GEOGRAPHIC,
        pattern_type=PatternType.ANOMALOUS,
        description="Access from high-risk geographic region",
        indicators=["country_risk_score", "is_high_risk_country"],
        confidence_threshold=0.75,
        severity_weight=1.5,
        scorer=lambda d: min(1.0, d.get("country_risk_score", 0))
    ),
    
    # Action patterns
    "normal_action_set": BehaviorPattern(
        name="normal_action_set",
        dimension=BehaviorDimension.ACTION,
        pattern_type=PatternType.NORMAL,
        description="Typical actions for user role",
        indicators=["action_typicality", "role_action_match"],
        confidence_threshold=0.8,
        severity_weight=0.5,
        scorer=lambda d: d.get("action_typicality", 0.5)
    ),
    
    "privilege_escalation": BehaviorPattern(
        name="privilege_escalation",
        dimension=BehaviorDimension.ACTION,
        pattern_type=PatternType.ANOMALOUS,
        description="Attempt to gain elevated privileges",
        indicators=["sudo_usage", "permission_change", "admin_access_attempt"],
        confidence_threshold=0.75,
        severity_weight=2.0,
        scorer=lambda d: max(
            d.get("sudo_usage", 0),
            d.get("permission_change", 0),
            d.get("admin_access_attempt", 0) * 0.8
        )
    ),
    
    "data_access_spike": BehaviorPattern(
        name="data_access_spike",
        dimension=BehaviorDimension.ACTION,
        pattern_type=PatternType.SUSPICIOUS,
        description="Unusual increase in data access volume",
        indicators=["data_access_rate", "unique_files_accessed", "sensitive_data_access"],
        confidence_threshold=0.7,
        severity_weight=1.4,
        scorer=lambda d: min(1.0, (
            d.get("data_access_rate", 0) * 0.4 +
            d.get("sensitive_data_access", 0) * 0.6
        ))
    ),
    
    "unusual_api_usage": BehaviorPattern(
        name="unusual_api_usage",
        dimension=BehaviorDimension.ACTION,
        pattern_type=PatternType.SUSPICIOUS,
        description="API calls not typical for user/application",
        indicators=["api_novelty", "api_risk_score", "uncommon_endpoint"],
        confidence_threshold=0.75,
        severity_weight=1.2,
        scorer=lambda d: max(
            d.get("api_novelty", 0),
            d.get("api_risk_score", 0) * 0.8
        )
    ),
    
    # Sequence patterns
    "typical_sequence": BehaviorPattern(
        name="typical_sequence",
        dimension=BehaviorDimension.SEQUENCE,
        pattern_type=PatternType.NORMAL,
        description="Common action sequence for user",
        indicators=["sequence_likelihood", "typical_transition"],
        confidence_threshold=0.8,
        severity_weight=0.6,
        scorer=lambda d: d.get("sequence_likelihood", 0.5)
    ),
    
    "attack_chain_sequence": BehaviorPattern(
        name="attack_chain_sequence",
        dimension=BehaviorDimension.SEQUENCE,
        pattern_type=PatternType.ANOMALOUS,
        description="Sequence matching known attack patterns",
        indicators=["attack_chain_match", "recon_to_exploit_transition"],
        confidence_threshold=0.75,
        severity_weight=2.0,
        scorer=lambda d: d.get("attack_chain_match", 0)
    ),
    
    "rapid_action_sequence": BehaviorPattern(
        name="rapid_action_sequence",
        dimension=BehaviorDimension.SEQUENCE,
        pattern_type=PatternType.SUSPICIOUS,
        description="Unusually fast sequence of actions",
        indicators=["action_rate", "time_between_actions", "automation_indicators"],
        confidence_threshold=0.7,
        severity_weight=1.3,
        scorer=lambda d: min(1.0, d.get("action_rate", 0) / 10)  # Normalize to 10 actions/sec
    ),
    
    # Volume patterns
    "normal_volume": BehaviorPattern(
        name="normal_volume",
        dimension=BehaviorDimension.VOLUME,
        pattern_type=PatternType.NORMAL,
        description="Typical request/data volume",
        indicators=["request_count_zscore", "data_volume_zscore"],
        confidence_threshold=0.75,
        severity_weight=0.5,
        scorer=lambda d: max(0.0, 1.0 - abs(d.get("request_count_zscore", 2.0)) / 3.0)
    ),
    
    "volume_spike": BehaviorPattern(
        name="volume_spike",
        dimension=BehaviorDimension.VOLUME,
        pattern_type=PatternType.SUSPICIOUS,
        description="Sudden increase in request/data volume",
        indicators=["request_count_zscore", "data_volume_zscore", "volume_trend"],
        confidence_threshold=0.7,
        severity_weight=1.2,
        scorer=lambda d: min(1.0, max(
            d.get("request_count_zscore", 0) / 3.0,
            d.get("data_volume_zscore", 0) / 3.0
        ))
    ),
    
    "drip_exfiltration": BehaviorPattern(
        name="drip_exfiltration",
        dimension=BehaviorDimension.VOLUME,
        pattern_type=PatternType.ANOMALOUS,
        description="Low-and-slow data exfiltration pattern",
        indicators=["small_regular_transfers", "off_hours_small_transfers", "unusual_destination"],
        confidence_threshold=0.75,
        severity_weight=1.8,
        scorer=lambda d: (
            0.4 if d.get("small_regular_transfers", False) else 0.0 +
            0.4 if d.get("off_hours_small_transfers", False) else 0.0 +
            0.2 if d.get("unusual_destination", False) else 0.0
        )
    ),
    
    # Peer patterns
    "peer_consistent": BehaviorPattern(
        name="peer_consistent",
        dimension=BehaviorDimension.PEER,
        pattern_type=PatternType.NORMAL,
        description="Behavior consistent with peer group",
        indicators=["peer_deviation_score", "role_similarity"],
        confidence_threshold=0.75,
        severity_weight=0.6,
        scorer=lambda d: max(0.0, 1.0 - d.get("peer_deviation_score", 1.0))
    ),
    
    "peer_outlier": BehaviorPattern(
        name="peer_outlier",
        dimension=BehaviorDimension.PEER,
        pattern_type=PatternType.SUSPICIOUS,
        description="Behavior significantly different from peers",
        indicators=["peer_deviation_score", "uncommon_for_role"],
        confidence_threshold=0.7,
        severity_weight=1.3,
        scorer=lambda d: min(1.0, d.get("peer_deviation_score", 0))
    ),
}


class PatternMatcher:
    """Matches data against behavioral patterns."""
    
    def __init__(self, patterns: Optional[Dict[str, BehaviorPattern]] = None):
        self.patterns = patterns or BEHAVIORAL_PATTERNS
        self.match_history: List[Dict[str, Any]] = []
    
    def match_patterns(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Match data against all patterns.
        
        Returns:
            Dictionary with match results
        """
        matches = {
            "normal": [],
            "suspicious": [],
            "anomalous": [],
            "scores": {}
        }
        
        for name, pattern in self.patterns.items():
            score = pattern.calculate_score(data)
            
            if score >= pattern.confidence_threshold:
                match_info = {
                    "pattern": name,
                    "dimension": pattern.dimension.value,
                    "score": score,
                    "severity_weight": pattern.severity_weight
                }
                
                if pattern.pattern_type == PatternType.NORMAL:
                    matches["normal"].append(match_info)
                elif pattern.pattern_type == PatternType.SUSPICIOUS:
                    matches["suspicious"].append(match_info)
                else:  # ANOMALOUS
                    matches["anomalous"].append(match_info)
            
            matches["scores"][name] = score
        
        # Calculate aggregate scores
        matches["normal_score"] = self._aggregate_score(matches["normal"])
        matches["suspicious_score"] = self._aggregate_score(matches["suspicious"])
        matches["anomalous_score"] = self._aggregate_score(matches["anomalous"])
        
        # Calculate weighted risk score
        matches["risk_score"] = self._calculate_risk_score(matches)
        
        self.match_history.append({
            "timestamp": datetime.now(),
            "matches": matches
        })
        
        return matches
    
    def _aggregate_score(self, matches: List[Dict[str, Any]]) -> float:
        """Calculate aggregate score from matches."""
        if not matches:
            return 0.0
        
        # Weighted average
        total_weight = sum(m["severity_weight"] for m in matches)
        weighted_sum = sum(m["score"] * m["severity_weight"] for m in matches)
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _calculate_risk_score(self, matches: Dict[str, Any]]) -> float:
        """Calculate overall risk score."""
        # Risk = anomalous * 2 + suspicious - normal * 0.5
        risk = (
            matches["anomalous_score"] * 2.0 +
            matches["suspicious_score"] * 1.0 -
            matches["normal_score"] * 0.5
        )
        
        # Normalize to 0-1
        return max(0.0, min(1.0, risk))
    
    def get_dimension_summary(self, data: Dict[str, Any]) -> Dict[BehaviorDimension, float]:
        """Get risk score summary by dimension."""
        dimension_scores = defaultdict(list)
        
        for name, pattern in self.patterns.items():
            score = pattern.calculate_score(data)
            dimension_scores[pattern.dimension].append(
                score * pattern.severity_weight
            )
        
        return {
            dim: np.mean(scores) if scores else 0.0
            for dim, scores in dimension_scores.items()
        }


def get_pattern_matcher() -> PatternMatcher:
    """Get default pattern matcher."""
    return PatternMatcher(BEHAVIORAL_PATTERNS)
