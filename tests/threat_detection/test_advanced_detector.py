"""
Tests for Advanced Anomaly Detector

Tests the multi-model ensemble detection system.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

from threat_detection.advanced_anomaly_detector import (
    AdvancedAnomalyDetector, ThreatDetection, ThreatSeverity,
    ThreatCategory, get_advanced_detector
)
from threat_detection.feature_engineering import FeatureExtractor


@pytest.fixture
def detector():
    """Create a detector instance for testing."""
    return AdvancedAnomalyDetector()


@pytest.fixture
def sample_telemetry():
    """Create sample telemetry data."""
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_usage": 85.5,
        "memory_usage": 70.2,
        "network_latency": 150.0,
        "error_rate": 0.05,
        "source_ip": "192.168.1.100",
        "destination_ip": "10.0.0.50"
    }


@pytest.mark.asyncio
async def test_detector_initialization(detector):
    """Test detector initializes correctly."""
    assert detector is not None
    assert detector.models == {}
    assert detector.is_ready is False


@pytest.mark.asyncio
async def test_feature_extraction(detector, sample_telemetry):
    """Test feature extraction from telemetry."""
    features = detector._extract_features(sample_telemetry)
    
    assert features is not None
    assert "cpu_usage" in features
    assert "memory_usage" in features
    assert "network_latency" in features
    assert "error_rate" in features


@pytest.mark.asyncio
async def test_statistical_detection(detector, sample_telemetry):
    """Test statistical anomaly detection."""
    # Set up baseline
    detector.baseline_stats = {
        "cpu_usage": {"mean": 50.0, "std": 10.0},
        "memory_usage": {"mean": 60.0, "std": 5.0},
        "network_latency": {"mean": 50.0, "std": 20.0}
    }
    
    # Test detection
    detections = await detector.analyze(sample_telemetry)
    
    assert isinstance(detections, list)
    # Should detect anomalies given the high values in sample data


@pytest.mark.asyncio
async def test_threat_detection_creation():
    """Test ThreatDetection dataclass."""
    detection = ThreatDetection(
        detection_id="TEST-001",
        threat_type="malware",
        category=ThreatCategory.MALWARE,
        severity=ThreatSeverity.HIGH,
        confidence=0.85,
        description="Test detection",
        affected_entities=["host-001"],
        source_data={},
        timestamp=datetime.now()
    )
    
    assert detection.detection_id == "TEST-001"
    assert detection.threat_type == "malware"
    assert detection.severity == ThreatSeverity.HIGH
    assert detection.confidence == 0.85


def test_threat_severity_enum():
    """Test ThreatSeverity enum values."""
    assert ThreatSeverity.CRITICAL.value == "critical"
    assert ThreatSeverity.HIGH.value == "high"
    assert ThreatSeverity.MEDIUM.value == "medium"
    assert ThreatSeverity.LOW.value == "low"


def test_threat_category_enum():
    """Test ThreatCategory enum values."""
    assert ThreatCategory.MALWARE.value == "malware"
    assert ThreatCategory.INTRUSION.value == "intrusion"
    assert ThreatCategory.UNKNOWN.value == "unknown"


@pytest.mark.asyncio
async def test_detector_with_empty_data(detector):
    """Test detector handles empty data gracefully."""
    detections = await detector.analyze({})
    assert isinstance(detections, list)


@pytest.mark.asyncio
async def test_detector_with_none_values(detector):
    """Test detector handles None values."""
    data = {
        "cpu_usage": None,
        "memory_usage": 50.0,
        "network_latency": None
    }
    
    detections = await detector.analyze(data)
    assert isinstance(detections, list)


@pytest.mark.asyncio
async def test_global_detector_instance():
    """Test global detector singleton."""
    detector1 = get_advanced_detector()
    detector2 = get_advanced_detector()
    
    assert detector1 is detector2


@pytest.mark.asyncio
async def test_detection_latency_requirement():
    """Test that detection completes within 100ms requirement."""
    detector = get_advanced_detector()
    
    data = {"cpu_usage": 90.0, "memory_usage": 80.0}
    
    start = datetime.now()
    await detector.analyze(data)
    elapsed = (datetime.now() - start).total_seconds() * 1000
    
    assert elapsed < 100, f"Detection took {elapsed}ms, exceeds 100ms requirement"


@pytest.mark.asyncio
async def test_false_positive_rate():
    """Test false positive rate is below 1%."""
    detector = get_advanced_detector()
    
    # Generate 1000 normal data points
    normal_detections = 0
    total = 1000
    
    for i in range(total):
        # Normal system data
        data = {
            "cpu_usage": 45.0 + (i % 10),  # Normal range 45-55
            "memory_usage": 60.0 + (i % 5),  # Normal range 60-65
            "network_latency": 30.0 + (i % 10)  # Normal range 30-40
        }
        
        detections = await detector.analyze(data)
        if detections:
            normal_detections += 1
    
    false_positive_rate = normal_detections / total
    assert false_positive_rate < 0.01, f"False positive rate {false_positive_rate} exceeds 1%"
