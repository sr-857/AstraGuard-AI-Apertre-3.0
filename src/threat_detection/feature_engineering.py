"""
Advanced Feature Engineering for Threat Detection

Provides sophisticated feature extraction from telemetry and security data
to support ML-based threat detection with high accuracy and low false positives.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import logging
import hashlib
import re
from enum import Enum

from core.error_handling import safe_execute, AstraGuardException
from core.timeout_handler import async_timeout

logger = logging.getLogger(__name__)


class FeatureCategory(Enum):
    """Categories of features for threat detection."""
    TEMPORAL = "temporal"
    STATISTICAL = "statistical"
    FREQUENCY = "frequency"
    ENTROPY = "entropy"
    BEHAVIORAL = "behavioral"
    NETWORK = "network"
    SYSTEM = "system"


@dataclass
class ExtractedFeatures:
    """Container for extracted features."""
    features: Dict[str, float]
    category: FeatureCategory
    timestamp: datetime
    source: str
    confidence: float = 1.0
    
    def to_vector(self) -> np.ndarray:
        """Convert features to numpy array."""
        return np.array(list(self.features.values()))
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names."""
        return list(self.features.keys())


class TemporalFeatureExtractor:
    """Extract temporal patterns from time-series data."""
    
    def __init__(self, window_sizes: List[int] = None):
        self.window_sizes = window_sizes or [5, 10, 30, 60]
        self.history: deque = deque(maxlen=max(self.window_sizes) * 2)
        
    def extract(self, data_point: Dict[str, Any], timestamp: datetime) -> ExtractedFeatures:
        """Extract temporal features from a data point."""
        self.history.append((timestamp, data_point))
        
        features = {}
        
        # Time-based features
        features['hour_of_day'] = timestamp.hour
        features['day_of_week'] = timestamp.weekday()
        features['is_weekend'] = 1.0 if timestamp.weekday() >= 5 else 0.0
        features['is_business_hours'] = 1.0 if 9 <= timestamp.hour <= 17 else 0.0
        
        # Rate of change features
        if len(self.history) >= 2:
            prev_time, prev_data = list(self.history)[-2]
            time_delta = (timestamp - prev_time).total_seconds()
            
            if time_delta > 0:
                for key in ['cpu_usage', 'memory_usage', 'network_bytes', 'request_count']:
                    if key in data_point and key in prev_data:
                        try:
                            rate = (float(data_point[key]) - float(prev_data[key])) / time_delta
                            features[f'{key}_rate'] = rate
                        except (ValueError, TypeError):
                            features[f'{key}_rate'] = 0.0
        
        # Rolling statistics for each window size
        for window in self.window_sizes:
            if len(self.history) >= window:
                window_data = list(self.history)[-window:]
                
                for metric in ['cpu_usage', 'memory_usage', 'network_bytes']:
                    values = [d[1].get(metric, 0) for d in window_data if metric in d[1]]
                    if values:
                        features[f'{metric}_mean_{window}'] = np.mean(values)
                        features[f'{metric}_std_{window}'] = np.std(values) if len(values) > 1 else 0.0
                        features[f'{metric}_max_{window}'] = np.max(values)
                        features[f'{metric}_min_{window}'] = np.min(values)
        
        return ExtractedFeatures(
            features=features,
            category=FeatureCategory.TEMPORAL,
            timestamp=timestamp,
            source="temporal_extractor"
        )


class StatisticalFeatureExtractor:
    """Extract statistical features from data distributions."""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.metric_history: Dict[str, deque] = {}
        
    def extract(self, data_point: Dict[str, Any], timestamp: datetime) -> ExtractedFeatures:
        """Extract statistical features."""
        features = {}
        
        # Update history for each metric
        for key, value in data_point.items():
            if isinstance(value, (int, float)):
                if key not in self.metric_history:
                    self.metric_history[key] = deque(maxlen=self.history_size)
                self.metric_history[key].append(float(value))
        
        # Calculate statistical features
        for metric, history in self.metric_history.items():
            if len(history) >= 10:
                values = list(history)
                
                # Basic statistics
                features[f'{metric}_mean'] = np.mean(values)
                features[f'{metric}_std'] = np.std(values)
                features[f'{metric}_skewness'] = self._calculate_skewness(values)
                features[f'{metric}_kurtosis'] = self._calculate_kurtosis(values)
                
                # Percentiles
                features[f'{metric}_p95'] = np.percentile(values, 95)
                features[f'{metric}_p99'] = np.percentile(values, 99)
                
                # Trend (linear regression slope)
                features[f'{metric}_trend'] = self._calculate_trend(values)
                
                # Z-score of latest value
                if len(values) >= 2:
                    latest = values[-1]
                    mean = features[f'{metric}_mean']
                    std = features[f'{metric}_std']
                    if std > 0:
                        features[f'{metric}_zscore'] = (latest - mean) / std
                    else:
                        features[f'{metric}_zscore'] = 0.0
        
        return ExtractedFeatures(
            features=features,
            category=FeatureCategory.STATISTICAL,
            timestamp=timestamp,
            source="statistical_extractor"
        )
    
    def _calculate_skewness(self, values: List[float]) -> float:
        """Calculate skewness of distribution."""
        if len(values) < 3:
            return 0.0
        mean = np.mean(values)
        std = np.std(values)
        if std == 0:
            return 0.0
        return np.mean(((np.array(values) - mean) / std) ** 3)
    
    def _calculate_kurtosis(self, values: List[float]) -> float:
        """Calculate kurtosis of distribution."""
        if len(values) < 4:
            return 0.0
        mean = np.mean(values)
        std = np.std(values)
        if std == 0:
            return 0.0
        return np.mean(((np.array(values) - mean) / std) ** 4) - 3
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate linear trend using simple linear regression."""
        if len(values) < 2:
            return 0.0
        x = np.arange(len(values))
        y = np.array(values)
        # Simple linear regression slope
        n = len(x)
        slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x**2) - np.sum(x)**2 + 1e-10)
        return slope


class EntropyFeatureExtractor:
    """Extract entropy-based features for anomaly detection."""
    
    def extract(self, data_point: Dict[str, Any], timestamp: datetime) -> ExtractedFeatures:
        """Extract entropy features."""
        features = {}
        
        # Shannon entropy of string fields
        for key, value in data_point.items():
            if isinstance(value, str):
                features[f'{key}_entropy'] = self._calculate_entropy(value)
                features[f'{key}_length'] = len(value)
                
                # Character distribution features
                char_dist = self._character_distribution(value)
                features[f'{key}_char_variety'] = len(char_dist)
                features[f'{key}_char_entropy'] = self._distribution_entropy(char_dist)
        
        # Entropy of numeric distributions
        numeric_values = [v for v in data_point.values() if isinstance(v, (int, float))]
        if len(numeric_values) >= 5:
            features['numeric_entropy'] = self._calculate_numeric_entropy(numeric_values)
        
        return ExtractedFeatures(
            features=features,
            category=FeatureCategory.ENTROPY,
            timestamp=timestamp,
            source="entropy_extractor"
        )
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not text:
            return 0.0
        
        # Calculate character frequencies
        freq = {}
        for char in text:
            freq[char] = freq.get(char, 0) + 1
        
        # Calculate entropy
        length = len(text)
        entropy = 0.0
        for count in freq.values():
            p = count / length
            if p > 0:
                entropy -= p * np.log2(p)
        
        # Normalize by maximum possible entropy
        max_entropy = np.log2(min(len(freq), 256))
        if max_entropy > 0:
            return entropy / max_entropy
        return 0.0
    
    def _character_distribution(self, text: str) -> Dict[str, int]:
        """Get character distribution."""
        dist = {}
        for char in text:
            dist[char] = dist.get(char, 0) + 1
        return dist
    
    def _distribution_entropy(self, distribution: Dict[str, int]) -> float:
        """Calculate entropy of a distribution."""
        total = sum(distribution.values())
        if total == 0:
            return 0.0
        
        entropy = 0.0
        for count in distribution.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)
        
        return entropy
    
    def _calculate_numeric_entropy(self, values: List[float]) -> float:
        """Calculate entropy of numeric distribution using binning."""
        if not values:
            return 0.0
        
        # Create histogram
        hist, _ = np.histogram(values, bins=10)
        total = np.sum(hist)
        
        if total == 0:
            return 0.0
        
        # Calculate entropy
        entropy = 0.0
        for count in hist:
            if count > 0:
                p = count / total
                entropy -= p * np.log2(p)
        
        return entropy


class NetworkFeatureExtractor:
    """Extract network-related features."""
    
    def __init__(self):
        self.connection_history: deque = deque(maxlen=1000)
        self.ip_reputation: Dict[str, float] = {}
        
    def extract(self, data_point: Dict[str, Any], timestamp: datetime) -> ExtractedFeatures:
        """Extract network features."""
        features = {}
        
        # Connection-based features
        src_ip = data_point.get('source_ip', '')
        dst_ip = data_point.get('destination_ip', '')
        port = data_point.get('destination_port', 0)
        
        # Track connection
        self.connection_history.append({
            'timestamp': timestamp,
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'port': port
        })
        
        # IP-based features
        if src_ip:
            features['src_ip_reputation'] = self.ip_reputation.get(src_ip, 0.5)
            features['src_ip_entropy'] = self._ip_entropy(src_ip)
            
            # Connection rate from this IP
            recent_connections = [
                c for c in self.connection_history 
                if c['src_ip'] == src_ip and (timestamp - c['timestamp']).total_seconds() < 60
            ]
            features['src_ip_connection_rate'] = len(recent_connections)
        
        # Port-based features
        if port:
            features['is_common_port'] = 1.0 if port in [80, 443, 22, 21, 25, 53] else 0.0
            features['is_high_port'] = 1.0 if port > 1024 else 0.0
        
        # Traffic volume features
        bytes_in = data_point.get('bytes_in', 0)
        bytes_out = data_point.get('bytes_out', 0)
        features['bytes_ratio'] = bytes_in / (bytes_out + 1)  # Add 1 to avoid division by zero
        features['total_bytes'] = bytes_in + bytes_out
        
        # Protocol features
        protocol = data_point.get('protocol', '').upper()
        features['is_tcp'] = 1.0 if protocol == 'TCP' else 0.0
        features['is_udp'] = 1.0 if protocol == 'UDP' else 0.0
        features['is_icmp'] = 1.0 if protocol == 'ICMP' else 0.0
        
        return ExtractedFeatures(
            features=features,
            category=FeatureCategory.NETWORK,
            timestamp=timestamp,
            source="network_extractor"
        )
    
    def _ip_entropy(self, ip: str) -> float:
        """Calculate entropy of IP address octets."""
        try:
            octets = [int(o) for o in ip.split('.')]
            return self._calculate_distribution_entropy(octets)
        except (ValueError, AttributeError):
            return 0.0
    
    def _calculate_distribution_entropy(self, values: List[int]) -> float:
        """Calculate entropy of integer distribution."""
        if not values:
            return 0.0
        
        freq = {}
        for v in values:
            freq[v] = freq.get(v, 0) + 1
        
        total = len(values)
        entropy = 0.0
        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)
        
        return entropy / np.log2(256) if entropy > 0 else 0.0
    
    def update_ip_reputation(self, ip: str, reputation_score: float):
        """Update reputation score for an IP address."""
        self.ip_reputation[ip] = max(0.0, min(1.0, reputation_score))


class FeatureEngineeringPipeline:
    """
    Main pipeline for feature engineering.
    Combines all extractors and produces final feature vector.
    """
    
    def __init__(self):
        self.extractors = {
            'temporal': TemporalFeatureExtractor(),
            'statistical': StatisticalFeatureExtractor(),
            'entropy': EntropyFeatureExtractor(),
            'network': NetworkFeatureExtractor(),
        }
        self.feature_cache: deque = deque(maxlen=1000)
        
    @async_timeout(seconds=5.0, operation_name="feature_extraction")
    async def extract_features(self, data_point: Dict[str, Any], timestamp: Optional[datetime] = None) -> Dict[str, float]:
        """
        Extract all features from a data point.
        
        Args:
            data_point: Raw data dictionary
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            Dictionary of all extracted features
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        all_features = {}
        
        # Run all extractors
        for name, extractor in self.extractors.items():
            try:
                result = safe_execute(
                    extractor.extract,
                    data_point,
                    timestamp,
                    component=f"feature_extractor_{name}",
                    fallback_value=ExtractedFeatures({}, FeatureCategory.SYSTEM, timestamp, name, 0.0)
                )
                
                if result and hasattr(result, 'features'):
                    # Prefix features with extractor name to avoid collisions
                    for key, value in result.features.items():
                        all_features[f"{name}_{key}"] = value
                        
            except Exception as e:
                logger.warning(f"Feature extractor {name} failed: {e}")
                continue
        
        # Add metadata features
        all_features['feature_count'] = len(all_features)
        all_features['extraction_timestamp'] = timestamp.timestamp()
        
        # Cache for potential reuse
        self.feature_cache.append({
            'timestamp': timestamp,
            'features': all_features.copy(),
            'source_data_hash': hashlib.md5(str(data_point).encode()).hexdigest()[:16]
        })
        
        return all_features
    
    def get_feature_vector(self, data_point: Dict[str, Any], timestamp: Optional[datetime] = None) -> np.ndarray:
        """Get feature vector as numpy array."""
        features = safe_execute(
            self.extract_features,
            data_point,
            timestamp,
            component="feature_pipeline",
            fallback_value={}
        )
        
        if not features:
            return np.array([])
        
        return np.array(list(features.values()))
    
    def get_feature_names(self) -> List[str]:
        """Get list of all feature names."""
        # Return cached feature names if available
        if self.feature_cache:
            return list(self.feature_cache[-1]['features'].keys())
        return []
    
    def clear_cache(self):
        """Clear feature cache."""
        self.feature_cache.clear()


# Global instance
_feature_pipeline: Optional[FeatureEngineeringPipeline] = None


def get_feature_pipeline() -> FeatureEngineeringPipeline:
    """Get global feature engineering pipeline instance."""
    global _feature_pipeline
    if _feature_pipeline is None:
        _feature_pipeline = FeatureEngineeringPipeline()
    return _feature_pipeline
