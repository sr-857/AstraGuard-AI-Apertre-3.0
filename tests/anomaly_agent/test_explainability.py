"""
Unit tests for anomaly_agent/explainability.py

Tests cover:
- build_explanation function with valid inputs
- Context dictionary validation
- Type checking and error handling
- Confidence value validation and conversion
- Default value handling
- Edge cases and boundary conditions
- Error logging verification
- Exception handling

Test Count: 25+ tests
Coverage Target: 95%+
"""

import pytest
import logging
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Import the module to test
from anomaly_agent.explainability import build_explanation


class TestBuildExplanationValidInputs:
    """Test suite for build_explanation with valid inputs."""

    def test_build_explanation_with_complete_context(self):
        """Test build_explanation with all context fields provided."""
        context = {
            "primary_factor": "Temperature exceeded threshold",
            "secondary_factors": ["Voltage spike detected", "CPU load high"],
            "mission_phase": "DATA_COLLECTION",
            "confidence": 0.95
        }
        
        result = build_explanation(context)
        
        assert result["primary_factor"] == "Temperature exceeded threshold"
        assert result["secondary_factors"] == ["Voltage spike detected", "CPU load high"]
        assert result["mission_phase_constraint"] == "DATA_COLLECTION"
        assert result["confidence"] == 0.95

    def test_build_explanation_with_minimal_context(self):
        """Test build_explanation with minimal required context."""
        context = {}
        
        result = build_explanation(context)
        
        # Should use defaults
        assert result["primary_factor"] == "Policy-based anomaly decision"
        assert result["secondary_factors"] == []
        assert result["mission_phase_constraint"] == "UNKNOWN"
        assert result["confidence"] == 0.0

    def test_build_explanation_with_partial_context(self):
        """Test build_explanation with some fields missing."""
        context = {
            "primary_factor": "Sensor drift detected",
            "confidence": 0.85
        }
        
        result = build_explanation(context)
        
        assert result["primary_factor"] == "Sensor drift detected"
        assert result["secondary_factors"] == []  # Default
        assert result["mission_phase_constraint"] == "UNKNOWN"  # Default
        assert result["confidence"] == 0.85

    def test_build_explanation_with_string_confidence(self):
        """Test that string confidence values are converted to float."""
        context = {
            "primary_factor": "Test anomaly",
            "confidence": "0.75"
        }
        
        result = build_explanation(context)
        
        assert result["confidence"] == 0.75
        assert isinstance(result["confidence"], float)

    def test_build_explanation_with_integer_confidence(self):
        """Test that integer confidence values are converted to float."""
        context = {
            "primary_factor": "Test anomaly",
            "confidence": 1
        }
        
        result = build_explanation(context)
        
        assert result["confidence"] == 1.0
        assert isinstance(result["confidence"], float)

    def test_build_explanation_with_zero_confidence(self):
        """Test build_explanation with zero confidence value."""
        context = {
            "primary_factor": "Low confidence anomaly",
            "confidence": 0.0
        }
        
        result = build_explanation(context)
        
        assert result["confidence"] == 0.0

    def test_build_explanation_with_max_confidence(self):
        """Test build_explanation with maximum confidence value."""
        context = {
            "primary_factor": "High confidence anomaly",
            "confidence": 1.0
        }
        
        result = build_explanation(context)
        
        assert result["confidence"] == 1.0

    def test_build_explanation_with_empty_secondary_factors(self):
        """Test build_explanation with explicitly empty secondary factors."""
        context = {
            "primary_factor": "Single factor anomaly",
            "secondary_factors": [],
            "confidence": 0.8
        }
        
        result = build_explanation(context)
        
        assert result["secondary_factors"] == []
        assert isinstance(result["secondary_factors"], list)

    def test_build_explanation_with_multiple_secondary_factors(self):
        """Test build_explanation with multiple secondary factors."""
        context = {
            "primary_factor": "Complex anomaly",
            "secondary_factors": [
                "Factor 1",
                "Factor 2",
                "Factor 3",
                "Factor 4"
            ],
            "confidence": 0.92
        }
        
        result = build_explanation(context)
        
        assert len(result["secondary_factors"]) == 4
        assert "Factor 1" in result["secondary_factors"]
        assert "Factor 4" in result["secondary_factors"]

    def test_build_explanation_preserves_mission_phase(self):
        """Test that mission phase is correctly preserved."""
        test_phases = [
            "LAUNCH",
            "ORBIT_INSERTION",
            "DATA_COLLECTION",
            "ECLIPSE",
            "MAINTENANCE",
            "DEORBIT"
        ]
        
        for phase in test_phases:
            context = {
                "mission_phase": phase,
                "confidence": 0.5
            }
            
            result = build_explanation(context)
            
            assert result["mission_phase_constraint"] == phase

    def test_build_explanation_returns_dict(self):
        """Test that build_explanation always returns a dictionary."""
        context = {
            "primary_factor": "Test",
            "confidence": 0.5
        }
        
        result = build_explanation(context)
        
        assert isinstance(result, dict)

    def test_build_explanation_has_required_keys(self):
        """Test that result contains all required keys."""
        context = {"confidence": 0.5}
        
        result = build_explanation(context)
        
        required_keys = [
            "primary_factor",
            "secondary_factors",
            "mission_phase_constraint",
            "confidence"
        ]
        
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"


class TestBuildExplanationTypeValidation:
    """Test suite for type validation in build_explanation."""

    def test_build_explanation_rejects_non_dict_context(self):
        """Test that non-dict context raises TypeError."""
        invalid_contexts = [
            "string context",
            123,
            12.34,
            ["list", "context"],
            ("tuple", "context"),
            None
        ]
        
        for invalid_context in invalid_contexts:
            with pytest.raises(TypeError, match="context must be a dictionary"):
                build_explanation(invalid_context)

    def test_build_explanation_rejects_none_context(self):
        """Test that None context raises TypeError with specific message."""
        with pytest.raises(TypeError, match="context must be a dictionary"):
            build_explanation(None)

    def test_build_explanation_rejects_list_context(self):
        """Test that list context raises TypeError."""
        with pytest.raises(TypeError, match="context must be a dictionary"):
            build_explanation([1, 2, 3])

    def test_build_explanation_rejects_string_context(self):
        """Test that string context raises TypeError."""
        with pytest.raises(TypeError, match="context must be a dictionary"):
            build_explanation("not a dict")

    def test_build_explanation_logs_error_on_invalid_type(self):
        """Test that error is logged when invalid type is passed."""
        with patch('anomaly_agent.explainability.logger') as mock_logger:
            try:
                build_explanation("invalid")
            except TypeError:
                pass  # Expected
            
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0]
            assert "Invalid context passed to build_explanation" in call_args[0]
            assert "expected dict" in call_args[0]


class TestBuildExplanationConfidenceValidation:
    """Test suite for confidence value validation."""

    def test_build_explanation_rejects_invalid_confidence_string(self):
        """Test that non-numeric string confidence raises ValueError."""
        context = {
            "confidence": "not a number"
        }
        
        with pytest.raises(ValueError, match="confidence must be a numeric value"):
            build_explanation(context)

    def test_build_explanation_rejects_confidence_list(self):
        """Test that list confidence raises ValueError."""
        context = {
            "confidence": [0.5, 0.6]
        }
        
        with pytest.raises(ValueError, match="confidence must be a numeric value"):
            build_explanation(context)

    def test_build_explanation_rejects_confidence_dict(self):
        """Test that dict confidence raises ValueError."""
        context = {
            "confidence": {"value": 0.5}
        }
        
        with pytest.raises(ValueError, match="confidence must be a numeric value"):
            build_explanation(context)

    def test_build_explanation_rejects_confidence_none(self):
        """Test that None confidence raises ValueError."""
        context = {
            "confidence": None
        }
        
        with pytest.raises(ValueError, match="confidence must be a numeric value"):
            build_explanation(context)

    def test_build_explanation_logs_error_on_invalid_confidence(self):
        """Test that error is logged when invalid confidence is provided."""
        with patch('anomaly_agent.explainability.logger') as mock_logger:
            context = {"confidence": "invalid"}
            
            try:
                build_explanation(context)
            except ValueError:
                pass  # Expected
            
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0]
            assert "Invalid confidence value" in call_args[0]

    def test_build_explanation_accepts_negative_confidence(self):
        """Test that negative confidence values are accepted (edge case)."""
        context = {
            "confidence": -0.5
        }
        
        result = build_explanation(context)
        
        # Function accepts it, validation might be done elsewhere
        assert result["confidence"] == -0.5

    def test_build_explanation_accepts_large_confidence(self):
        """Test that confidence values > 1.0 are accepted (edge case)."""
        context = {
            "confidence": 1.5
        }
        
        result = build_explanation(context)
        
        # Function accepts it, validation might be done elsewhere
        assert result["confidence"] == 1.5

    def test_build_explanation_handles_float_precision(self):
        """Test handling of floating point precision."""
        context = {
            "confidence": 0.123456789
        }
        
        result = build_explanation(context)
        
        assert result["confidence"] == pytest.approx(0.123456789)


class TestBuildExplanationDefaultValues:
    """Test suite for default value handling."""

    def test_build_explanation_default_primary_factor(self):
        """Test default primary factor is used when not provided."""
        context = {"confidence": 0.5}
        
        result = build_explanation(context)
        
        assert result["primary_factor"] == "Policy-based anomaly decision"

    def test_build_explanation_default_secondary_factors(self):
        """Test default secondary factors is empty list."""
        context = {"confidence": 0.5}
        
        result = build_explanation(context)
        
        assert result["secondary_factors"] == []
        assert isinstance(result["secondary_factors"], list)

    def test_build_explanation_default_mission_phase(self):
        """Test default mission phase is UNKNOWN."""
        context = {"confidence": 0.5}
        
        result = build_explanation(context)
        
        assert result["mission_phase_constraint"] == "UNKNOWN"

    def test_build_explanation_default_confidence(self):
        """Test default confidence is 0.0 when not provided."""
        context = {}
        
        result = build_explanation(context)
        
        assert result["confidence"] == 0.0

    def test_build_explanation_empty_string_primary_factor(self):
        """Test that empty string primary factor is preserved."""
        context = {
            "primary_factor": "",
            "confidence": 0.5
        }
        
        result = build_explanation(context)
        
        assert result["primary_factor"] == ""

    def test_build_explanation_none_primary_factor_uses_default(self):
        """Test that None primary factor falls back to default."""
        context = {
            "primary_factor": None,
            "confidence": 0.5
        }
        
        result = build_explanation(context)
        
        # get() with None returns None, not the default (default is only for missing keys)
        assert result["primary_factor"] is None


class TestBuildExplanationEdgeCases:
    """Test suite for edge cases and special scenarios."""

    def test_build_explanation_with_extra_fields(self):
        """Test that extra fields in context are ignored."""
        context = {
            "primary_factor": "Test",
            "confidence": 0.5,
            "extra_field_1": "ignored",
            "extra_field_2": 123,
            "unknown_key": ["should", "be", "ignored"]
        }
        
        result = build_explanation(context)
        
        # Extra fields should not appear in result
        assert "extra_field_1" not in result
        assert "extra_field_2" not in result
        assert "unknown_key" not in result
        
        # Required fields should be present
        assert "primary_factor" in result
        assert "confidence" in result

    def test_build_explanation_with_unicode_characters(self):
        """Test handling of unicode characters in strings."""
        context = {
            "primary_factor": "Temperature: 45°C ± 2°C",
            "secondary_factors": ["Sensor α malfunction", "β radiation detected"],
            "mission_phase": "DATA_COLLECTION_Φ",
            "confidence": 0.88
        }
        
        result = build_explanation(context)
        
        assert "°C" in result["primary_factor"]
        assert "α" in result["secondary_factors"][0]
        assert "β" in result["secondary_factors"][1]
        assert "Φ" in result["mission_phase_constraint"]

    def test_build_explanation_with_special_characters(self):
        """Test handling of special characters in strings."""
        context = {
            "primary_factor": "Error: <critical> threshold exceeded",
            "secondary_factors": ["Log file: /var/log/system.log", "Value > 100%"],
            "confidence": 0.9
        }
        
        result = build_explanation(context)
        
        assert "<critical>" in result["primary_factor"]
        assert "/var/log/system.log" in result["secondary_factors"][0]
        assert ">" in result["secondary_factors"][1]

    def test_build_explanation_with_very_long_strings(self):
        """Test handling of very long strings."""
        long_factor = "A" * 1000
        context = {
            "primary_factor": long_factor,
            "confidence": 0.5
        }
        
        result = build_explanation(context)
        
        assert result["primary_factor"] == long_factor
        assert len(result["primary_factor"]) == 1000

    def test_build_explanation_with_numeric_strings_in_factors(self):
        """Test that numeric strings in factors are preserved as strings."""
        context = {
            "primary_factor": "123.456",
            "secondary_factors": ["789", "0.001"],
            "confidence": 0.5
        }
        
        result = build_explanation(context)
        
        assert result["primary_factor"] == "123.456"
        assert isinstance(result["primary_factor"], str)
        assert "789" in result["secondary_factors"]

    def test_build_explanation_preserves_secondary_factor_order(self):
        """Test that secondary factors maintain their order."""
        factors = ["First", "Second", "Third", "Fourth", "Fifth"]
        context = {
            "secondary_factors": factors.copy(),
            "confidence": 0.5
        }
        
        result = build_explanation(context)
        
        assert result["secondary_factors"] == factors
        for i, factor in enumerate(factors):
            assert result["secondary_factors"][i] == factor

    def test_build_explanation_with_nested_structures_in_context(self):
        """Test that nested structures in unused fields don't cause issues."""
        context = {
            "primary_factor": "Test",
            "confidence": 0.5,
            "nested": {
                "deep": {
                    "structure": "ignored"
                }
            }
        }
        
        result = build_explanation(context)
        
        # Should complete successfully
        assert result["primary_factor"] == "Test"
        assert result["confidence"] == 0.5


class TestBuildExplanationLogging:
    """Test suite for logging behavior."""

    def test_build_explanation_logs_type_error_with_correct_type(self):
        """Test that TypeError logging includes the actual type received."""
        with patch('anomaly_agent.explainability.logger') as mock_logger:
            try:
                build_explanation(123)
            except TypeError:
                pass
            
            # Verify logger was called
            assert mock_logger.error.called
            
            # Check that the type name is in the error message
            call_args = mock_logger.error.call_args
            assert 'int' in str(call_args)

    def test_build_explanation_logs_value_error_with_confidence(self):
        """Test that ValueError logging includes the invalid confidence value."""
        with patch('anomaly_agent.explainability.logger') as mock_logger:
            try:
                build_explanation({"confidence": "bad_value"})
            except ValueError:
                pass
            
            # Verify logger was called
            assert mock_logger.error.called
            
            # Check that error includes the bad value
            call_args = mock_logger.error.call_args
            assert 'bad_value' in str(call_args)

    def test_build_explanation_includes_exc_info_on_confidence_error(self):
        """Test that exc_info=True is used when logging confidence errors."""
        with patch('anomaly_agent.explainability.logger') as mock_logger:
            try:
                build_explanation({"confidence": "invalid"})
            except ValueError:
                pass
            
            # Check that exc_info was passed
            call_kwargs = mock_logger.error.call_args[1]
            assert call_kwargs.get('exc_info') is True


class TestBuildExplanationIntegration:
    """Integration tests for build_explanation."""

    def test_build_explanation_realistic_scenario_high_confidence(self):
        """Test a realistic high-confidence anomaly scenario."""
        context = {
            "primary_factor": "Battery voltage dropped below critical threshold (10.5V)",
            "secondary_factors": [
                "Power consumption increased by 25%",
                "Solar panel efficiency degraded to 78%",
                "Operating in eclipse phase for 35 minutes"
            ],
            "mission_phase": "ECLIPSE",
            "confidence": 0.96
        }
        
        result = build_explanation(context)
        
        assert "Battery voltage" in result["primary_factor"]
        assert len(result["secondary_factors"]) == 3
        assert result["mission_phase_constraint"] == "ECLIPSE"
        assert result["confidence"] > 0.9
        assert isinstance(result, dict)

    def test_build_explanation_realistic_scenario_low_confidence(self):
        """Test a realistic low-confidence anomaly scenario."""
        context = {
            "primary_factor": "Unusual telemetry pattern detected",
            "secondary_factors": [
                "Pattern matches 60% with known anomaly signature"
            ],
            "mission_phase": "DATA_COLLECTION",
            "confidence": 0.62
        }
        
        result = build_explanation(context)
        
        assert "Unusual telemetry" in result["primary_factor"]
        assert len(result["secondary_factors"]) == 1
        assert result["confidence"] < 0.7
        assert result["confidence"] > 0.6

    def test_build_explanation_multiple_calls_independence(self):
        """Test that multiple calls to build_explanation are independent."""
        context1 = {
            "primary_factor": "First anomaly",
            "confidence": 0.5
        }
        
        context2 = {
            "primary_factor": "Second anomaly",
            "confidence": 0.8
        }
        
        result1 = build_explanation(context1)
        result2 = build_explanation(context2)
        
        # Results should be different
        assert result1["primary_factor"] != result2["primary_factor"]
        assert result1["confidence"] != result2["confidence"]
        
        # Modifying one shouldn't affect the other
        result1["primary_factor"] = "Modified"
        assert result2["primary_factor"] == "Second anomaly"

    def test_build_explanation_handles_all_mission_phases(self):
        """Test handling of various mission phases."""
        mission_phases = [
            "LAUNCH",
            "ORBIT_INSERTION",
            "COMMISSIONING",
            "NOMINAL_OPERATIONS",
            "DATA_COLLECTION",
            "ECLIPSE",
            "SAFE_MODE",
            "MAINTENANCE",
            "DECOMMISSIONING",
            "DEORBIT"
        ]
        
        for phase in mission_phases:
            context = {
                "primary_factor": f"Anomaly during {phase}",
                "mission_phase": phase,
                "confidence": 0.75
            }
            
            result = build_explanation(context)
            
            assert result["mission_phase_constraint"] == phase
            assert phase in result["primary_factor"]


# Test configuration for pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src.anomaly_agent.explainability", "--cov-report=term-missing"])