"""
Baseline Profiler for Behavioral Analysis

Establishes dynamic baselines for normal behavior and detects deviations.
Uses statistical methods and machine learning to profile user and system behavior.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging
from enum import Enum
import hashlib
import json

from core.error_handling import safe_execute, AstraGuardException
from core.timeout_handler import async_timeout

logger = logging.getLogger(__name__)


class BaselineType(Enum):
    """Types of baselines that can be established."""
    USER = "user"
    SYSTEM = "system"
    APPLICATION = "application"
    NETWORK = "network"
    PEER_GROUP = "peer_group"


@dataclass
class BaselineProfile:
    """Baseline profile for an entity."""
    entity_id: str
    baseline_type: BaselineType
    created_at: datetime
    updated_at: datetime
    sample_count: int
    features: Dict[str, Dict[str, Any]]
    temporal_patterns: Dict[str, Any]
    geographic_patterns: Dict[str, Any]
    action_patterns: Dict[str, Any]
    confidence_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "baseline_type": self.baseline_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "sample_count": self.sample_count,
            "features": self.features,
            "temporal_patterns": self.temporal_patterns,
            "geographic_patterns": self.geographic_patterns,
            "action_patterns": self.action_patterns,
            "confidence_score": self.confidence_score
        }


@dataclass
class DeviationResult:
    """Result of deviation analysis."""
    entity_id: str
    timestamp: datetime
    deviation_score: float
    severity: str
    deviated_features: List[Dict[str, Any]]
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
            "deviation_score": self.deviation_score,
            "severity": self.severity,
            "deviated_features": self.deviated_features,
            "context": self.context
        }


class StatisticalProfiler:
    """Statistical profiler for feature distributions."""
    
    def __init__(self, min_samples: int = 30, max_history: int = 1000):
        self.min_samples = min_samples
        self.max_history = max_history
        self.feature_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        self.statistics: Dict[str, Dict[str, float]] = {}
        
    def add_sample(self, feature_name: str, value: float):
        """Add a sample to the profile."""
        self.feature_history[feature_name].append({
            "value": value,
            "timestamp": datetime.now()
        })
        
        # Update statistics if enough samples
        if len(self.feature_history[feature_name]) >= self.min_samples:
            self._update_statistics(feature_name)
    
    def _update_statistics(self, feature_name: str):
        """Update statistical measures for a feature."""
        values = [s["value"] for s in self.feature_history[feature_name]]
        
        self.statistics[feature_name] = {
            "mean": np.mean(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
            "median": np.median(values),
            "p5": np.percentile(values, 5),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99),
            "sample_count": len(values),
            "last_updated": datetime.now().isoformat()
        }
    
    def calculate_zscore(self, feature_name: str, value: float) -> float:
        """Calculate z-score for a value."""
        if feature_name not in self.statistics:
            return 0.0
        
        stats = self.statistics[feature_name]
        if stats["std"] == 0:
            return 0.0
        
        return (value - stats["mean"]) / stats["std"]
    
    def is_anomalous(self, feature_name: str, value: float, 
                     threshold: float = 3.0) -> Tuple[bool, float]:
        """Check if value is anomalous based on z-score."""
        zscore = self.calculate_zscore(feature_name, value)
        return abs(zscore) > threshold, zscore
    
    def get_confidence(self, feature_name: str) -> float:
        """Get confidence level for a feature's statistics."""
        if feature_name not in self.statistics:
            return 0.0
        
        sample_count = self.statistics[feature_name]["sample_count"]
        # Confidence increases with sample size, asymptotic to 1.0
        return min(1.0, sample_count / (sample_count + self.min_samples))


class TemporalProfiler:
    """Profiler for temporal patterns."""
    
    def __init__(self):
        self.hourly_distribution: Dict[int, int] = defaultdict(int)
        self.daily_distribution: Dict[int, int] = defaultdict(int)
        self.total_samples: int = 0
        self.typical_hours: Set[int] = set()
        self.typical_days: Set[int] = set()
        
    def add_timestamp(self, timestamp: datetime):
        """Add a timestamp to the profile."""
        hour = timestamp.hour
        day = timestamp.weekday()
        
        self.hourly_distribution[hour] += 1
        self.daily_distribution[day] += 1
        self.total_samples += 1
        
        # Update typical hours/days (top 50%)
        self._update_typical_patterns()
    
    def _update_typical_patterns(self):
        """Update typical hours and days based on distribution."""
        if self.total_samples < 10:
            return
        
        # Find median frequency
        hour_freqs = sorted(self.hourly_distribution.values())
        day_freqs = sorted(self.daily_distribution.values())
        
        hour_median = hour_freqs[len(hour_freqs) // 2] if hour_freqs else 0
        day_median = day_freqs[len(day_freqs) // 2] if day_freqs else 0
        
        # Typical = above median
        self.typical_hours = {
            h for h, f in self.hourly_distribution.items() 
            if f >= hour_median
        }
        self.typical_days = {
            d for d, f in self.daily_distribution.items() 
            if f >= day_median
        }
    
    def is_typical_time(self, timestamp: datetime) -> Tuple[bool, float]:
        """Check if timestamp is typical."""
        hour = timestamp.hour
        day = timestamp.weekday()
        
        hour_typical = hour in self.typical_hours
        day_typical = day in self.typical_days
        
        # Calculate typicality score
        hour_confidence = min(1.0, self.hourly_distribution[hour] / max(1, self.total_samples / 24))
        day_confidence = min(1.0, self.daily_distribution[day] / max(1, self.total_samples / 7))
        
        score = (hour_confidence + day_confidence) / 2
        
        return hour_typical and day_typical, score
    
    def get_schedule_variance(self, timestamp: datetime) -> float:
        """Calculate variance from typical schedule."""
        hour = timestamp.hour
        
        if not self.typical_hours:
            return 1.0
        
        # Find closest typical hour
        distances = [abs(h - hour) for h in self.typical_hours]
        min_distance = min(distances)
        
        # Normalize to 0-1
        return min(1.0, min_distance / 12.0)


class GeographicProfiler:
    """Profiler for geographic patterns."""
    
    def __init__(self):
        self.known_locations: Set[str] = set()
        self.location_frequency: Dict[str, int] = defaultdict(int)
        self.country_risk_scores: Dict[str, float] = {}
        self.total_samples: int = 0
        self.typical_locations: Set[str] = set()
        
    def add_location(self, location: str, country: str, 
                     risk_score: float = 0.0):
        """Add a location to the profile."""
        self.known_locations.add(location)
        self.location_frequency[location] += 1
        self.country_risk_scores[country] = risk_score
        self.total_samples += 1
        
        # Update typical locations (appeared more than once)
        self.typical_locations = {
            loc for loc, freq in self.location_frequency.items() 
            if freq > 1
        }
    
    def is_known_location(self, location: str) -> bool:
        """Check if location is known."""
        return location in self.known_locations
    
    def is_typical_location(self, location: str) -> bool:
        """Check if location is typical."""
        return location in self.typical_locations
    
    def get_location_typicality(self, location: str) -> float:
        """Get typicality score for a location."""
        if not self.known_locations:
            return 0.0
        
        if location not in self.location_frequency:
            return 0.0
        
        # Frequency-based score
        freq = self.location_frequency[location]
        max_freq = max(self.location_frequency.values())
        
        return freq / max_freq if max_freq > 0 else 0.0


class BaselineProfiler:
    """
    Main baseline profiler that combines all profiling components.
    """
    
    def __init__(self):
        self.profiles: Dict[str, BaselineProfile] = {}
        self.statistical_profilers: Dict[str, StatisticalProfiler] = {}
        self.temporal_profilers: Dict[str, TemporalProfiler] = {}
        self.geographic_profilers: Dict[str, GeographicProfiler] = {}
        
        # Minimum samples required for reliable baseline
        self.min_baseline_samples: int = 50
        # Maximum age of baseline before refresh
        self.baseline_max_age_days: int = 30
        
    async def create_baseline(self, entity_id: str, 
                              baseline_type: BaselineType,
                              historical_data: List[Dict[str, Any]]) -> BaselineProfile:
        """
        Create a baseline profile from historical data.
        
        Args:
            entity_id: Unique identifier for the entity
            baseline_type: Type of baseline
            historical_data: List of historical behavior records
            
        Returns:
            BaselineProfile
        """
        logger.info(f"Creating {baseline_type.value} baseline for {entity_id} "
                   f"with {len(historical_data)} samples")
        
        # Initialize profilers
        stat_profiler = StatisticalProfiler()
        temp_profiler = TemporalProfiler()
        geo_profiler = GeographicProfiler()
        
        # Process historical data
        for record in historical_data:
            # Extract features
            features = record.get("features", {})
            for feature_name, value in features.items():
                if isinstance(value, (int, float)):
                    stat_profiler.add_sample(feature_name, float(value))
            
            # Extract temporal info
            timestamp = record.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            if isinstance(timestamp, datetime):
                temp_profiler.add_timestamp(timestamp)
            
            # Extract geographic info
            location = record.get("location")
            country = record.get("country")
            if location and country:
                risk_score = record.get("country_risk_score", 0.0)
                geo_profiler.add_location(location, country, risk_score)
        
        # Build feature statistics
        feature_stats = {}
        for feature_name, stats in stat_profiler.statistics.items():
            feature_stats[feature_name] = {
                "mean": stats["mean"],
                "std": stats["std"],
                "min": stats["min"],
                "max": stats["max"],
                "p95": stats["p95"],
                "confidence": stat_profiler.get_confidence(feature_name)
            }
        
        # Calculate overall confidence
        if feature_stats:
            avg_confidence = np.mean([f["confidence"] for f in feature_stats.values()])
        else:
            avg_confidence = 0.0
        
        # Create profile
        profile = BaselineProfile(
            entity_id=entity_id,
            baseline_type=baseline_type,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sample_count=len(historical_data),
            features=feature_stats,
            temporal_patterns={
                "typical_hours": list(temp_profiler.typical_hours),
                "typical_days": list(temp_profiler.typical_days),
                "hourly_distribution": dict(temp_profiler.hourly_distribution),
                "daily_distribution": dict(temp_profiler.daily_distribution)
            },
            geographic_patterns={
                "known_locations": list(geo_profiler.known_locations),
                "typical_locations": list(geo_profiler.typical_locations),
                "location_frequency": dict(geo_profiler.location_frequency),
                "country_risk_scores": geo_profiler.country_risk_scores
            },
            action_patterns={},  # Would be populated from action analysis
            confidence_score=avg_confidence
        )
        
        # Store profile and profilers
        self.profiles[entity_id] = profile
        self.statistical_profilers[entity_id] = stat_profiler
        self.temporal_profilers[entity_id] = temp_profiler
        self.geographic_profilers[entity_id] = geo_profiler
        
        logger.info(f"Baseline created for {entity_id} with confidence {avg_confidence:.2f}")
        
        return profile
    
    async def update_baseline(self, entity_id: str, 
                              new_data: Dict[str, Any]) -> BaselineProfile:
        """
        Update an existing baseline with new data.
        
        Args:
            entity_id: Entity identifier
            new_data: New behavior record
            
        Returns:
            Updated BaselineProfile
        """
        if entity_id not in self.profiles:
            raise AstraGuardException(
                f"No existing baseline for {entity_id}",
                component="baseline_profiler"
            )
        
        profile = self.profiles[entity_id]
        stat_profiler = self.statistical_profilers[entity_id]
        temp_profiler = self.temporal_profilers[entity_id]
        geo_profiler = self.geographic_profilers[entity_id]
        
        # Update statistical profiles
        features = new_data.get("features", {})
        for feature_name, value in features.items():
            if isinstance(value, (int, float)):
                stat_profiler.add_sample(feature_name, float(value))
        
        # Update temporal profile
        timestamp = new_data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        if isinstance(timestamp, datetime):
            temp_profiler.add_timestamp(timestamp)
        
        # Update geographic profile
        location = new_data.get("location")
        country = new_data.get("country")
        if location and country:
            risk_score = new_data.get("country_risk_score", 0.0)
            geo_profiler.add_location(location, country, risk_score)
        
        # Update profile metadata
        profile.sample_count += 1
        profile.updated_at = datetime.now()
        
        # Recalculate feature statistics
        for feature_name, stats in stat_profiler.statistics.items():
            profile.features[feature_name] = {
                "mean": stats["mean"],
                "std": stats["std"],
                "min": stats["min"],
                "max": stats["max"],
                "p95": stats["p95"],
                "confidence": stat_profiler.get_confidence(feature_name)
            }
        
        # Update temporal patterns
        profile.temporal_patterns = {
            "typical_hours": list(temp_profiler.typical_hours),
            "typical_days": list(temp_profiler.typical_days),
            "hourly_distribution": dict(temp_profiler.hourly_distribution),
            "daily_distribution": dict(temp_profiler.daily_distribution)
        }
        
        # Update geographic patterns
        profile.geographic_patterns = {
            "known_locations": list(geo_profiler.known_locations),
            "typical_locations": list(geo_profiler.typical_locations),
            "location_frequency": dict(geo_profiler.location_frequency),
            "country_risk_scores": geo_profiler.country_risk_scores
        }
        
        # Recalculate confidence
        if profile.features:
            profile.confidence_score = np.mean([
                f["confidence"] for f in profile.features.values()
            ])
        
        return profile
    
    async def detect_deviation(self, entity_id: str, 
                               current_data: Dict[str, Any]) -> DeviationResult:
        """
        Detect deviation from established baseline.
        
        Args:
            entity_id: Entity identifier
            current_data: Current behavior record
            
        Returns:
            DeviationResult with analysis
        """
        if entity_id not in self.profiles:
            return DeviationResult(
                entity_id=entity_id,
                timestamp=datetime.now(),
                deviation_score=0.0,
                severity="unknown",
                deviated_features=[],
                context={"error": "No baseline established"}
            )
        
        profile = self.profiles[entity_id]
        stat_profiler = self.statistical_profilers[entity_id]
        temp_profiler = self.temporal_profilers[entity_id]
        geo_profiler = self.geographic_profilers[entity_id]
        
        deviated_features = []
        total_deviation = 0.0
        
        # Check feature deviations
        features = current_data.get("features", {})
        for feature_name, value in features.items():
            if isinstance(value, (int, float)) and feature_name in profile.features:
                is_anomalous, zscore = stat_profiler.is_anomalous(
                    feature_name, float(value), threshold=2.5
                )
                
                if is_anomalous:
                    deviated_features.append({
                        "feature": feature_name,
                        "value": value,
                        "expected_mean": profile.features[feature_name]["mean"],
                        "expected_std": profile.features[feature_name]["std"],
                        "zscore": zscore,
                        "deviation_type": "statistical"
                    })
                    total_deviation += min(1.0, abs(zscore) / 5.0)
        
        # Check temporal deviation
        timestamp = current_data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        if isinstance(timestamp, datetime):
            is_typical, typicality = temp_profiler.is_typical_time(timestamp)
            if not is_typical:
                schedule_variance = temp_profiler.get_schedule_variance(timestamp)
                deviated_features.append({
                    "feature": "temporal_pattern",
                    "value": timestamp.isoformat(),
                    "typicality_score": typicality,
                    "schedule_variance": schedule_variance,
                    "deviation_type": "temporal"
                })
                total_deviation += (1.0 - typicality) * 0.5
        
        # Check geographic deviation
        location = current_data.get("location")
        if location:
            if not geo_profiler.is_known_location(location):
                deviated_features.append({
                    "feature": "location",
                    "value": location,
                    "known": False,
                    "deviation_type": "geographic_new"
                })
                total_deviation += 0.7
            elif not geo_profiler.is_typical_location(location):
                typicality = geo_profiler.get_location_typicality(location)
                deviated_features.append({
                    "feature": "location",
                    "value": location,
                    "typicality": typicality,
                    "deviation_type": "geographic_unusual"
                })
                total_deviation += (1.0 - typicality) * 0.5
        
        # Calculate overall deviation score
        if deviated_features:
            deviation_score = min(1.0, total_deviation / len(deviated_features))
        else:
            deviation_score = 0.0
        
        # Determine severity
        if deviation_score > 0.8:
            severity = "critical"
        elif deviation_score > 0.6:
            severity = "high"
        elif deviation_score > 0.4:
            severity = "medium"
        elif deviation_score > 0.2:
            severity = "low"
        else:
            severity = "none"
        
        return DeviationResult(
            entity_id=entity_id,
            timestamp=datetime.now(),
            deviation_score=deviation_score,
            severity=severity,
            deviated_features=deviated_features,
            context={
                "baseline_confidence": profile.confidence_score,
                "baseline_age_days": (datetime.now() - profile.created_at).days,
                "sample_count": profile.sample_count
            }
        )
    
    def get_profile(self, entity_id: str) -> Optional[BaselineProfile]:
        """Get baseline profile for an entity."""
        return self.profiles.get(entity_id)
    
    def is_baseline_ready(self, entity_id: str) -> bool:
        """Check if baseline has enough samples for reliable detection."""
        if entity_id not in self.profiles:
            return False
        
        profile = self.profiles[entity_id]
        return (
            profile.sample_count >= self.min_baseline_samples and
            profile.confidence_score >= 0.7
        )
    
    def list_profiles(self) -> List[str]:
        """List all entity IDs with profiles."""
        return list(self.profiles.keys())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get profiler statistics."""
        return {
            "total_profiles": len(self.profiles),
            "ready_profiles": sum(
                1 for eid in self.profiles 
                if self.is_baseline_ready(eid)
            ),
            "average_confidence": np.mean([
                p.confidence_score for p in self.profiles.values()
            ]) if self.profiles else 0.0,
            "total_samples": sum(
                p.sample_count for p in self.profiles.values()
            )
        }


# Global instance
_profiler: Optional[BaselineProfiler] = None


def get_baseline_profiler() -> BaselineProfiler:
    """Get global baseline profiler instance."""
    global _profiler
    if _profiler is None:
        _profiler = BaselineProfiler()
    return _profiler
