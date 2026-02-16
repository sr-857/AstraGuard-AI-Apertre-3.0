"""
Unit tests for ConfidenceScorer

Tests cover:
- Boundary cases (0.0, 1.0)
- Dominance of anomaly score
- Phase/policy penalties
- Recurrence boost
- Temporal decay
- Weight normalization
"""

import pytest
from src.anomaly_agent.confidence_scorer import (
    ConfidenceScorer,
    ConfidenceFactors,
    calculate_confidence,
)


class TestConfidenceScorerBasics:
    """Test basic functionality and initialization."""
    
    def test_initialization_default_weights(self):
        """Test scorer initializes with default weights."""
        scorer = ConfidenceScorer()
        assert scorer.weight_anomaly == 0.40
        assert scorer.weight_recurrence == 0.20
        assert scorer.weight_phase == 0.15
        assert scorer.weight_policy == 0.15
        assert scorer.weight_temporal == 0.10
    
    def test_initialization_custom_weights(self):
        """Test scorer initializes with custom weights."""
        scorer = ConfidenceScorer(
            weight_anomaly=0.5,
            weight_recurrence=0.2,
            weight_phase=0.1,
            weight_policy=0.1,
            weight_temporal=0.1,
        )
        assert scorer.weight_anomaly == 0.5
        assert scorer.weight_recurrence == 0.2
    
    def test_weight_normalization(self):
        """Test weights are normalized if they don't sum to 1.0."""
        scorer = ConfidenceScorer(
            weight_anomaly=0.5,
            weight_recurrence=0.5,
            weight_phase=0.5,
            weight_policy=0.5,
            weight_temporal=0.5,
        )
        # Weights should be normalized to sum to 1.0
        total = (
            scorer.weight_anomaly +
            scorer.weight_recurrence +
            scorer.weight_phase +
            scorer.weight_policy +
            scorer.weight_temporal
        )
        assert 0.99 <= total <= 1.01


class TestBoundaryCases:
    """Test boundary values (0.0 and 1.0)."""
    
    def test_minimum_confidence_all_zeros(self):
        """Test confidence with all zero inputs."""
        scorer = ConfidenceScorer()
        confidence = scorer.calculate_confidence(
            anomaly_score=0.0,
            recurrence_count=0,
            mission_phase="LAUNCH",  # Highest risk
            policy_allowed=False,
            temporal_decay=0.0,
        )
        assert 0.0 <= confidence <= 1.0
        # Should be very low but not necessarily 0.0 due to phase calculation
        assert confidence < 0.2
    
    def test_maximum_confidence_all_ones(self):
        """Test confidence with all maximum inputs."""
        scorer = ConfidenceScorer()
        confidence = scorer.calculate_confidence(
            anomaly_score=1.0,
            recurrence_count=100,  # High recurrence
            mission_phase="NOMINAL_OPS",  # Low risk
            policy_allowed=True,
            temporal_decay=1.0,
        )
        assert 0.0 <= confidence <= 1.0
        # Should be very high
        assert confidence > 0.8
    
    def test_confidence_clamped_to_range(self):
        """Test confidence is always in [0.0, 1.0] range."""
        scorer = ConfidenceScorer()
        # Try with out-of-range inputs
        confidence = scorer.calculate_confidence(
            anomaly_score=2.0,  # Invalid, should be clamped
            recurrence_count=-5,  # Invalid, should be clamped
            temporal_decay=1.5,  # Invalid, should be clamped
        )
        assert 0.0 <= confidence <= 1.0


class TestAnomalyScoreDominance:
    """Test that anomaly score is the strongest contributor."""
    
    def test_high_anomaly_score_high_confidence(self):
        """Test high anomaly score produces high confidence."""
        scorer = ConfidenceScorer()
        confidence = scorer.calculate_confidence(
            anomaly_score=0.95,
            recurrence_count=0,
            mission_phase="NOMINAL_OPS",
            policy_allowed=True,
            temporal_decay=1.0,
        )
        # With 40% weight, 0.95 anomaly should give ~0.38 + other factors
        assert confidence > 0.6
    
    def test_low_anomaly_score_low_confidence(self):
        """Test low anomaly score produces low confidence."""
        scorer = ConfidenceScorer()
        confidence = scorer.calculate_confidence(
            anomaly_score=0.1,
            recurrence_count=10,  # Even with recurrence
            mission_phase="NOMINAL_OPS",
            policy_allowed=True,
            temporal_decay=1.0,
        )
        # Low anomaly score should dominate (but recurrence adds some boost)
        assert confidence < 0.6  # Adjusted for recurrence boost
    
    def test_anomaly_score_variation(self):
        """Test confidence increases with anomaly score."""
        scorer = ConfidenceScorer()
        scores = []
        for anomaly_score in [0.2, 0.4, 0.6, 0.8, 1.0]:
            confidence = scorer.calculate_confidence(
                anomaly_score=anomaly_score,
                recurrence_count=5,
                mission_phase="NOMINAL_OPS",
                policy_allowed=True,
                temporal_decay=1.0,
            )
            scores.append(confidence)
        
        # Confidence should increase monotonically with anomaly score
        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1]


class TestPhaseContextPenalty:
    """Test mission phase affects confidence."""
    
    def test_launch_phase_penalty(self):
        """Test LAUNCH phase penalizes confidence."""
        scorer = ConfidenceScorer()
        launch_confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            mission_phase="LAUNCH",
        )
        nominal_confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            mission_phase="NOMINAL_OPS",
        )
        # LAUNCH should have lower confidence due to high risk
        assert launch_confidence < nominal_confidence
    
    def test_safe_mode_penalty(self):
        """Test SAFE_MODE phase penalizes confidence."""
        scorer = ConfidenceScorer()
        safe_confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            mission_phase="SAFE_MODE",
        )
        nominal_confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            mission_phase="NOMINAL_OPS",
        )
        # SAFE_MODE should have lower confidence
        assert safe_confidence < nominal_confidence
    
    def test_nominal_ops_best_phase(self):
        """Test NOMINAL_OPS has least penalty."""
        scorer = ConfidenceScorer()
        phases = ["LAUNCH", "DEPLOYMENT", "NOMINAL_OPS", "PAYLOAD_OPS", "SAFE_MODE"]
        confidences = {}
        for phase in phases:
            confidences[phase] = scorer.calculate_confidence(
                anomaly_score=0.8,
                mission_phase=phase,
            )
        
        # NOMINAL_OPS should have highest or near-highest confidence
        assert confidences["NOMINAL_OPS"] >= confidences["LAUNCH"]
        assert confidences["NOMINAL_OPS"] >= confidences["SAFE_MODE"]


class TestPolicyAlignment:
    """Test policy alignment affects confidence."""
    
    def test_policy_allowed_boosts_confidence(self):
        """Test policy_allowed=True increases confidence."""
        scorer = ConfidenceScorer()
        allowed_confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            policy_allowed=True,
        )
        disallowed_confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            policy_allowed=False,
        )
        # Allowed should have higher confidence
        assert allowed_confidence > disallowed_confidence
    
    def test_policy_disallowed_penalty(self):
        """Test policy_allowed=False significantly reduces confidence."""
        scorer = ConfidenceScorer()
        allowed_confidence = scorer.calculate_confidence(
            anomaly_score=0.9,
            policy_allowed=True,
        )
        disallowed_confidence = scorer.calculate_confidence(
            anomaly_score=0.9,
            policy_allowed=False,
        )
        # Penalty should be significant (policy signal drops to 0.3)
        difference = allowed_confidence - disallowed_confidence
        assert difference > 0.1  # At least 10% difference


class TestRecurrenceBoost:
    """Test historical recurrence increases confidence."""
    
    def test_recurrence_increases_confidence(self):
        """Test more recurrences increase confidence."""
        scorer = ConfidenceScorer()
        no_recurrence = scorer.calculate_confidence(
            anomaly_score=0.7,
            recurrence_count=0,
        )
        some_recurrence = scorer.calculate_confidence(
            anomaly_score=0.7,
            recurrence_count=5,
        )
        high_recurrence = scorer.calculate_confidence(
            anomaly_score=0.7,
            recurrence_count=20,
        )
        # Confidence should increase with recurrence
        assert no_recurrence < some_recurrence < high_recurrence
    
    def test_recurrence_logarithmic_growth(self):
        """Test recurrence boost has diminishing returns."""
        scorer = ConfidenceScorer()
        conf_10 = scorer.calculate_confidence(
            anomaly_score=0.7,
            recurrence_count=10,
        )
        conf_20 = scorer.calculate_confidence(
            anomaly_score=0.7,
            recurrence_count=20,
        )
        conf_40 = scorer.calculate_confidence(
            anomaly_score=0.7,
            recurrence_count=40,
        )
        # Boost from 10->20 should be larger than 20->40 (diminishing returns)
        boost_1 = conf_20 - conf_10
        boost_2 = conf_40 - conf_20
        assert boost_1 > boost_2


class TestTemporalDecay:
    """Test temporal decay affects confidence."""
    
    def test_temporal_decay_reduces_confidence(self):
        """Test lower temporal decay reduces confidence."""
        scorer = ConfidenceScorer()
        fresh_confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            temporal_decay=1.0,
        )
        old_confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            temporal_decay=0.3,
        )
        # Fresh data should have higher confidence
        assert fresh_confidence > old_confidence
    
    def test_temporal_decay_range(self):
        """Test temporal decay across full range."""
        scorer = ConfidenceScorer()
        confidences = []
        for decay in [0.0, 0.25, 0.5, 0.75, 1.0]:
            confidence = scorer.calculate_confidence(
                anomaly_score=0.8,
                temporal_decay=decay,
            )
            confidences.append(confidence)
        
        # Confidence should increase with temporal decay
        for i in range(len(confidences) - 1):
            assert confidences[i] <= confidences[i + 1]


class TestConfidenceBreakdown:
    """Test confidence breakdown functionality."""
    
    def test_breakdown_returns_factors(self):
        """Test calculate_confidence_with_breakdown returns factors."""
        scorer = ConfidenceScorer()
        confidence, factors = scorer.calculate_confidence_with_breakdown(
            anomaly_score=0.8,
            recurrence_count=5,
            mission_phase="NOMINAL_OPS",
            policy_allowed=True,
            temporal_decay=0.9,
        )
        
        assert isinstance(confidence, float)
        assert isinstance(factors, ConfidenceFactors)
        assert 0.0 <= confidence <= 1.0
    
    def test_breakdown_factors_sum_to_confidence(self):
        """Test factor contributions sum to total confidence."""
        scorer = ConfidenceScorer()
        confidence, factors = scorer.calculate_confidence_with_breakdown(
            anomaly_score=0.8,
            recurrence_count=5,
            mission_phase="NOMINAL_OPS",
            policy_allowed=True,
            temporal_decay=0.9,
        )
        
        factor_sum = (
            factors.anomaly_score +
            factors.recurrence_boost +
            factors.phase_penalty +
            factors.policy_alignment +
            factors.temporal_weight
        )
        
        # Should be approximately equal (within floating point tolerance)
        assert abs(confidence - factor_sum) < 0.01


class TestConvenienceFunction:
    """Test convenience function."""
    
    def test_convenience_function_works(self):
        """Test calculate_confidence convenience function."""
        confidence = calculate_confidence(
            anomaly_score=0.8,
            recurrence_count=5,
            mission_phase="NOMINAL_OPS",
            policy_allowed=True,
            temporal_decay=0.9,
        )
        assert 0.0 <= confidence <= 1.0
        assert isinstance(confidence, float)
    
    def test_convenience_function_matches_class(self):
        """Test convenience function matches class method."""
        scorer = ConfidenceScorer()
        class_confidence = scorer.calculate_confidence(
            anomaly_score=0.75,
            recurrence_count=3,
        )
        func_confidence = calculate_confidence(
            anomaly_score=0.75,
            recurrence_count=3,
        )
        # Should be identical (using default weights)
        assert abs(class_confidence - func_confidence) < 0.001


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    def test_high_confidence_scenario(self):
        """Test scenario that should produce high confidence."""
        scorer = ConfidenceScorer()
        # Strong anomaly, seen before, nominal ops, policy allows, fresh data
        confidence = scorer.calculate_confidence(
            anomaly_score=0.92,
            recurrence_count=8,
            mission_phase="NOMINAL_OPS",
            policy_allowed=True,
            temporal_decay=0.95,
        )
        assert confidence > 0.8
    
    def test_low_confidence_scenario(self):
        """Test scenario that should produce low confidence."""
        scorer = ConfidenceScorer()
        # Weak anomaly, never seen, risky phase, policy blocks, old data
        confidence = scorer.calculate_confidence(
            anomaly_score=0.25,
            recurrence_count=0,
            mission_phase="LAUNCH",
            policy_allowed=False,
            temporal_decay=0.2,
        )
        assert confidence < 0.4
    
    def test_medium_confidence_scenario(self):
        """Test scenario that should produce medium confidence."""
        scorer = ConfidenceScorer()
        # Moderate anomaly, some history, payload ops, policy allows
        confidence = scorer.calculate_confidence(
            anomaly_score=0.65,
            recurrence_count=3,
            mission_phase="PAYLOAD_OPS",
            policy_allowed=True,
            temporal_decay=0.7,
        )
        assert 0.4 < confidence < 0.8


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_negative_recurrence_count(self):
        """Test negative recurrence count is handled."""
        scorer = ConfidenceScorer()
        confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            recurrence_count=-5,  # Invalid
        )
        # Should not crash, should clamp to 0
        assert 0.0 <= confidence <= 1.0
    
    def test_unknown_mission_phase(self):
        """Test unknown mission phase uses default risk."""
        scorer = ConfidenceScorer()
        confidence = scorer.calculate_confidence(
            anomaly_score=0.8,
            mission_phase="UNKNOWN_PHASE",
        )
        # Should not crash, should use default risk (0.5)
        assert 0.0 <= confidence <= 1.0
    
    def test_out_of_range_anomaly_score(self):
        """Test out-of-range anomaly score is clamped."""
        scorer = ConfidenceScorer()
        high_confidence = scorer.calculate_confidence(
            anomaly_score=5.0,  # Should be clamped to 1.0
        )
        low_confidence = scorer.calculate_confidence(
            anomaly_score=-2.0,  # Should be clamped to 0.0
        )
        assert 0.0 <= high_confidence <= 1.0
        assert 0.0 <= low_confidence <= 1.0
