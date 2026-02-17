"""
Behavioral Analyzer for Threat Detection

Integrates baseline profiling and pattern matching to provide
comprehensive behavioral analysis for threat detection.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import deque

from .baseline_profiler import (
    BaselineProfiler, 
    BaselineType, 
    get_baseline_profiler,
    DeviationResult
)
from .behavioral_patterns import (
    PatternMatcher, 
    get_pattern_matcher,
    BehaviorPattern,
    PatternType
)
from core.error_handling import safe_execute, AstraGuardException
from core.timeout_handler import async_timeout

logger = logging.getLogger(__name__)


class AnalysisResultType(Enum):
    """Types of behavioral analysis results."""
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    ANOMALOUS = "anomalous"
    UNKNOWN = "unknown"


@dataclass
class BehavioralAnalysisResult:
    """Complete behavioral analysis result."""
    entity_id: str
    timestamp: datetime
    result_type: AnalysisResultType
    risk_score: float
    baseline_deviation: Optional[DeviationResult]
    pattern_matches: Dict[str, Any]
    behavioral_summary: Dict[str, Any]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
            "result_type": self.result_type.value,
            "risk_score": self.risk_score,
            "baseline_deviation": self.baseline_deviation.to_dict() if self.baseline_deviation else None,
            "pattern_matches": self.pattern_matches,
            "behavioral_summary": self.behavioral_summary,
            "recommendations": self.recommendations
        }


class BehavioralAnalyzer:
    """
    Main behavioral analyzer integrating baseline profiling and pattern matching.
    
    Provides comprehensive behavioral analysis for users, systems, and applications
    to detect anomalies and potential security threats.
    """
    
    def __init__(self):
        self.baseline_profiler = get_baseline_profiler()
        self.pattern_matcher = get_pattern_matcher()
        
        # Analysis history
        self.analysis_history: deque = deque(maxlen=10000)
        
        # Risk score thresholds
        self.risk_thresholds = {
            "low": 0.3,
            "medium": 0.5,
            "high": 0.7,
            "critical": 0.9
        }
        
        # Minimum samples for reliable analysis
        self.min_samples = 10
        
    async def analyze_entity(self, entity_id: str,
                            entity_type: BaselineType,
                            current_data: Dict[str, Any]) -> BehavioralAnalysisResult:
        """
        Perform comprehensive behavioral analysis on an entity.
        
        Args:
            entity_id: Unique identifier for the entity
            entity_type: Type of entity (user, system, application, etc.)
            current_data: Current behavior data
            
        Returns:
            BehavioralAnalysisResult with complete analysis
        """
        logger.debug(f"Analyzing {entity_type.value} entity: {entity_id}")
        
        # Check if baseline exists
        has_baseline = entity_id in self.baseline_profiler.profiles
        
        # Detect baseline deviation if baseline exists
        baseline_deviation = None
        if has_baseline:
            baseline_deviation = await self.baseline_profiler.detect_deviation(
                entity_id, current_data
            )
        
        # Match behavioral patterns
        pattern_matches = self.pattern_matcher.match_patterns(current_data)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(
            baseline_deviation, pattern_matches, has_baseline
        )
        
        # Determine result type
        result_type = self._determine_result_type(risk_score, pattern_matches)
        
        # Generate behavioral summary
        behavioral_summary = self._generate_behavioral_summary(
            entity_id, baseline_deviation, pattern_matches, has_baseline
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            result_type, risk_score, baseline_deviation, pattern_matches
        )
        
        # Create result
        result = BehavioralAnalysisResult(
            entity_id=entity_id,
            timestamp=datetime.now(),
            result_type=result_type,
            risk_score=risk_score,
            baseline_deviation=baseline_deviation,
            pattern_matches=pattern_matches,
            behavioral_summary=behavioral_summary,
            recommendations=recommendations
        )
        
        # Store in history
        self.analysis_history.append(result)
        
        logger.info(
            f"Behavioral analysis complete for {entity_id}: "
            f"risk={risk_score:.2f}, type={result_type.value}"
        )
        
        return result
    
    def _calculate_risk_score(self, 
                             baseline_deviation: Optional[DeviationResult],
                             pattern_matches: Dict[str, Any],
                             has_baseline: bool) -> float:
        """Calculate overall risk score from multiple factors."""
        scores = []
        
        # Baseline deviation contribution (40% weight)
        if baseline_deviation:
            deviation_score = baseline_deviation.deviation_score
            scores.append(deviation_score * 0.4)
        elif not has_baseline:
            # No baseline = higher uncertainty
            scores.append(0.2)
        
        # Pattern match contribution (50% weight)
        pattern_risk = pattern_matches.get("risk_score", 0.0)
        scores.append(pattern_risk * 0.5)
        
        # Anomalous pattern count contribution (10% weight)
        anomalous_count = len(pattern_matches.get("anomalous", []))
        suspicious_count = len(pattern_matches.get("suspicious", []))
        pattern_score = min(1.0, (anomalous_count * 0.3 + suspicious_count * 0.1))
        scores.append(pattern_score * 0.1)
        
        # Combine scores
        total_risk = sum(scores)
        
        # Adjust based on baseline confidence
        if baseline_deviation and baseline_deviation.context:
            baseline_confidence = baseline_deviation.context.get("baseline_confidence", 0.5)
            # Reduce risk if baseline has low confidence
            if baseline_confidence < 0.5:
                total_risk *= 0.7
        
        return min(1.0, max(0.0, total_risk))
    
    def _determine_result_type(self, risk_score: float, 
                              pattern_matches: Dict[str, Any]) -> AnalysisResultType:
        """Determine analysis result type based on risk score and patterns."""
        anomalous_count = len(pattern_matches.get("anomalous", []))
        suspicious_count = len(pattern_matches.get("suspicious", []))
        
        if risk_score >= self.risk_thresholds["critical"] or anomalous_count >= 3:
            return AnalysisResultType.ANOMALOUS
        elif risk_score >= self.risk_thresholds["high"] or anomalous_count >= 1:
            return AnalysisResultType.ANOMALOUS
        elif risk_score >= self.risk_thresholds["medium"] or suspicious_count >= 2:
            return AnalysisResultType.SUSPICIOUS
        elif risk_score >= self.risk_thresholds["low"]:
            return AnalysisResultType.SUSPICIOUS
        else:
            return AnalysisResultType.NORMAL
    
    def _generate_behavioral_summary(self, entity_id: str,
                                      baseline_deviation: Optional[DeviationResult],
                                      pattern_matches: Dict[str, Any],
                                      has_baseline: bool) -> Dict[str, Any]:
        """Generate summary of behavioral analysis."""
        summary = {
            "entity_id": entity_id,
            "has_baseline": has_baseline,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        # Baseline information
        if baseline_deviation:
            summary["baseline_deviation_score"] = baseline_deviation.deviation_score
            summary["baseline_severity"] = baseline_deviation.severity
            summary["deviated_features_count"] = len(baseline_deviation.deviated_features)
        
        # Pattern information
        summary["normal_patterns"] = len(pattern_matches.get("normal", []))
        summary["suspicious_patterns"] = len(pattern_matches.get("suspicious", []))
        summary["anomalous_patterns"] = len(pattern_matches.get("anomalous", []))
        
        # Dimension scores
        dimension_scores = self.pattern_matcher.get_dimension_summary({})
        summary["dimension_risk_scores"] = {
            dim.value: score for dim, score in dimension_scores.items()
        }
        
        return summary
    
    def _generate_recommendations(self, result_type: AnalysisResultType,
                                   risk_score: float,
                                   baseline_deviation: Optional[DeviationResult],
                                   pattern_matches: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis results."""
        recommendations = []
        
        if result_type == AnalysisResultType.ANOMALOUS:
            recommendations.extend([
                "Immediate investigation required",
                "Consider isolating affected entity",
                "Review recent activity logs",
                "Check for indicators of compromise"
            ])
        elif result_type == AnalysisResultType.SUSPICIOUS:
            recommendations.extend([
                "Schedule investigation within 24 hours",
                "Increase monitoring on this entity",
                "Review access patterns"
            ])
        
        # Baseline-specific recommendations
        if not baseline_deviation:
            recommendations.append("Establish baseline profile for better detection")
        elif baseline_deviation.context.get("baseline_confidence", 0) < 0.5:
            recommendations.append("Collect more baseline data to improve detection accuracy")
        
        # Pattern-specific recommendations
        anomalous_patterns = pattern_matches.get("anomalous", [])
        for pattern in anomalous_patterns:
            recommendations.append(f"Investigate anomalous pattern: {pattern['pattern']}")
        
        return recommendations
    
    async def update_baseline(self, entity_id: str, 
                             entity_type: BaselineType,
                             data: Dict[str, Any]) -> bool:
        """
        Update or create baseline for an entity.
        
        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            data: New behavior data
            
        Returns:
            True if successful
        """
        try:
            if entity_id in self.baseline_profiler.profiles:
                # Update existing baseline
                await self.baseline_profiler.update_baseline(entity_id, data)
            else:
                # Create new baseline from single data point
                # In practice, you'd want multiple data points
                await self.baseline_profiler.create_baseline(
                    entity_id, entity_type, [data]
                )
            return True
        except Exception as e:
            logger.error(f"Failed to update baseline for {entity_id}: {e}")
            return False
    
    def get_analysis_history(self, entity_id: Optional[str] = None,
                            count: int = 100) -> List[BehavioralAnalysisResult]:
        """Get analysis history, optionally filtered by entity."""
        history = list(self.analysis_history)
        
        if entity_id:
            history = [h for h in history if h.entity_id == entity_id]
        
        return history[-count:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        history = list(self.analysis_history)
        
        if not history:
            return {"status": "no_analysis_yet"}
        
        return {
            "total_analyses": len(history),
            "by_result_type": {
                "normal": sum(1 for h in history if h.result_type == AnalysisResultType.NORMAL),
                "suspicious": sum(1 for h in history if h.result_type == AnalysisResultType.SUSPICIOUS),
                "anomalous": sum(1 for h in history if h.result_type == AnalysisResultType.ANOMALOUS),
            },
            "average_risk_score": np.mean([h.risk_score for h in history]),
            "high_risk_count": sum(1 for h in history if h.risk_score > 0.7),
            "entities_analyzed": len(set(h.entity_id for h in history))
        }


# Global instance
_analyzer: Optional[BehavioralAnalyzer] = None


def get_behavioral_analyzer() -> BehavioralAnalyzer:
    """Get global behavioral analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = BehavioralAnalyzer()
    return _analyzer
