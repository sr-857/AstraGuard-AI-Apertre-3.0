"""
Tests for Behavioral Analysis System

Tests behavioral profiling, baseline management, and pattern detection.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from threat_detection.behavioral_analyzer import (
    BehavioralAnalyzer, BehavioralAnalysisResult, AnalysisResultType,
    get_behavioral_analyzer
)
from threat_detection.baseline_profiler import (
    BaselineProfiler, BaselineProfile, get_baseline_profiler
)
from threat_detection.behavioral_patterns import (
    BehavioralPattern, PatternMatcher, get_pattern_matcher
)


@pytest.fixture
def analyzer():
    """Create a behavioral analyzer instance."""
    return BehavioralAnalyzer()


@pytest.fixture
def profiler():
    """Create a baseline profiler instance."""
    return BaselineProfiler()


@pytest.fixture
def pattern_matcher():
    """Create a pattern matcher instance."""
    return PatternMatcher()


@pytest.fixture
def sample_entity_data():
    """Create sample entity behavioral data."""
    return {
        "login_times": [8, 9, 9, 10, 9],  # Normal login hours
        "accessed_resources": ["file1", "file2", "file3"],
        "network_connections": 5,
        "data_transfer_mb": 10.5,
        "failed_auth_attempts": 0
    }


@pytest.mark.asyncio
async def test_baseline_profile_creation(profiler):
    """Test baseline profile creation."""
    profile = BaselineProfile(
        entity_id="user-001",
        entity_type="user",
        created_at=datetime.now(),
        metrics={
            "login_hour_mean": 9.0,
            "login_hour_std": 1.0,
            "network_connections_mean": 5.0,
            "network_connections_std": 2.0
        }
    )
    
    assert profile.entity_id == "user-001"
    assert profile.entity_type == "user"
    assert "login_hour_mean" in profile.metrics


@pytest.mark.asyncio
async def test_baseline_update(profiler):
    """Test baseline profile update."""
    profiler.update_baseline(
        entity_id="user-001",
        entity_type="user",
        metric_name="login_hour",
        value=9.0
    )
    
    profile = profiler.get_profile("user-001")
    assert profile is not None
    assert "login_hour" in profile.metrics


@pytest.mark.asyncio
async def test_pattern_matching(pattern_matcher):
    """Test pattern matching functionality."""
    # Register a test pattern
    pattern = BehavioralPattern(
        pattern_id="test-pattern",
        name="Off-hours access",
        description="Access outside normal hours",
        detection_func=lambda data: data.get("hour", 0) < 6 or data.get("hour", 0) > 22,
        severity="medium",
        category="time_based"
    )
    pattern_matcher.register_pattern(pattern)
    
    # Test matching
    matches = pattern_matcher.match_patterns(
        entity_id="user-001",
        data={"hour": 23, "activity": "file_access"}
    )
    
    assert len(matches) > 0
    assert matches[0].pattern_id == "test-pattern"


@pytest.mark.asyncio
async def test_behavioral_analysis(analyzer, sample_entity_data):
    """Test complete behavioral analysis."""
    # Create a profile first
    for i in range(10):
        await analyzer.analyze_entity(
            entity_id="user-001",
            entity_type="user",
            current_data={
                "login_time": 9 + (i % 3),  # Normal: 9-11
                "network_connections": 5 + (i % 2),
                "data_transfer": 10.0
            }
        )
    
    # Now test with anomalous data
    result = await analyzer.analyze_entity(
        entity_id="user-001",
        entity_type="user",
        current_data={
            "login_time": 3,  # Anomalous: 3 AM
            "network_connections": 50,  # Anomalous: 10x normal
            "data_transfer": 500.0  # Anomalous: 50x normal
        }
    )
    
    assert isinstance(result, BehavioralAnalysisResult)
    assert result.risk_score > 0.5  # Should be high risk


@pytest.mark.asyncio
async def test_risk_score_calculation(analyzer):
    """Test risk score calculation."""
    # Test with normal data
    normal_result = await analyzer._calculate_risk_score(
        entity_id="user-001",
        baseline={"login_hour_mean": 9, "login_hour_std": 1},
        current_data={"login_hour": 9},
        anomalies=[]
    )
    
    assert 0 <= normal_result <= 1
    
    # Test with anomalous data
    anomalous_result = await analyzer._calculate_risk_score(
        entity_id="user-001",
        baseline={"login_hour_mean": 9, "login_hour_std": 1},
        current_data={"login_hour": 3},
        anomalies=[{"type": "off_hours", "severity": "high"}]
    )
    
    assert anomalous_result > normal_result


@pytest.mark.asyncio
async def test_recommendation_generation(analyzer):
    """Test recommendation generation."""
    recommendations = analyzer._generate_recommendations(
        risk_score=0.8,
        pattern_matches={
            "suspicious": [{"pattern_id": "p1", "name": "Pattern 1"}],
            "anomalous": [{"pattern_id": "p2", "name": "Pattern 2"}]
        },
        anomalies=[{"type": "off_hours"}, {"type": "high_volume"}]
    )
    
    assert len(recommendations) > 0
    assert any("investigate" in r.lower() for r in recommendations)


@pytest.mark.asyncio
async def test_entity_risk_scoring(analyzer):
    """Test entity risk scoring over time."""
    # Simulate multiple observations
    risk_scores = []
    for i in range(5):
        result = await analyzer.analyze_entity(
            entity_id="user-002",
            entity_type="user",
            current_data={
                "login_time": 9,
                "network_connections": 5 + i * 10,  # Increasing
                "data_transfer": 10.0 * (i + 1)
            }
        )
        risk_scores.append(result.risk_score)
    
    # Risk should generally increase with anomalous behavior
    assert risk_scores[-1] >= risk_scores[0]


@pytest.mark.asyncio
async def test_baseline_deviation_detection(profiler):
    """Test detection of deviations from baseline."""
    # Create baseline
    for i in range(20):
        profiler.update_baseline(
            entity_id="user-003",
            entity_type="user",
            metric_name="cpu_usage",
            value=30.0 + (i % 5)  # Normal: 30-35%
        )
    
    profile = profiler.get_profile("user-003")
    
    # Check deviation
    is_anomalous, deviation = profiler.check_deviation(
        profile=profile,
        metric_name="cpu_usage",
        value=80.0  # Anomalous
    )
    
    assert is_anomalous is True
    assert deviation > 2.0  # More than 2 std devs


@pytest.mark.asyncio
async def test_pattern_registry(pattern_matcher):
    """Test pattern registration and retrieval."""
    pattern = BehavioralPattern(
        pattern_id="registry-test",
        name="Test Pattern",
        description="Test description",
        detection_func=lambda x: True,
        severity="low",
        category="test"
    )
    
    pattern_matcher.register_pattern(pattern)
    retrieved = pattern_matcher.get_pattern("registry-test")
    
    assert retrieved is not None
    assert retrieved.pattern_id == "registry-test"


@pytest.mark.asyncio
async def test_global_instances():
    """Test global singleton instances."""
    analyzer1 = get_behavioral_analyzer()
    analyzer2 = get_behavioral_analyzer()
    assert analyzer1 is analyzer2
    
    profiler1 = get_baseline_profiler()
    profiler2 = get_baseline_profiler()
    assert profiler1 is profiler2


@pytest.mark.asyncio
async def test_analysis_result_types():
    """Test different analysis result types."""
    # Normal result
    normal = BehavioralAnalysisResult(
        entity_id="user-001",
        result_type=AnalysisResultType.NORMAL,
        risk_score=0.2,
        reasoning="Normal behavior",
        timestamp=datetime.now()
    )
    assert normal.result_type == AnalysisResultType.NORMAL
    
    # Suspicious result
    suspicious = BehavioralAnalysisResult(
        entity_id="user-001",
        result_type=AnalysisResultType.SUSPICIOUS,
        risk_score=0.6,
        reasoning="Suspicious patterns detected",
        timestamp=datetime.now()
    )
    assert suspicious.result_type == AnalysisResultType.SUSPICIOUS
    
    # Anomalous result
    anomalous = BehavioralAnalysisResult(
        entity_id="user-001",
        result_type=AnalysisResultType.ANOMALOUS,
        risk_score=0.9,
        reasoning="Highly anomalous behavior",
        timestamp=datetime.now()
    )
    assert anomalous.result_type == AnalysisResultType.ANOMALOUS
