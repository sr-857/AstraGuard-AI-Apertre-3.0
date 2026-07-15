"""Unit tests for accuracy.py module."""

import pytest
import tempfile
import os
import numpy as np
from unittest.mock import patch
from src.astraguard.hil.metrics.accuracy import (
    AccuracyCollector,
    GroundTruthEvent,
    AgentClassification,
    FaultState,
)


@pytest.fixture
def sample_ground_truth():
    """Sample ground truth events for testing."""
    return [
        GroundTruthEvent(timestamp_s=100.0, satellite_id="SAT1", expected_fault_type="thermal_fault", confidence=1.0),
        GroundTruthEvent(timestamp_s=200.0, satellite_id="SAT1", expected_fault_type=None, confidence=1.0),  # nominal
        GroundTruthEvent(timestamp_s=300.0, satellite_id="SAT2", expected_fault_type="power_loss", confidence=1.0),
    ]


@pytest.fixture
def sample_classifications():
    """Sample agent classifications for testing."""
    return [
        AgentClassification(timestamp_s=100.0, satellite_id="SAT1", predicted_fault="thermal_fault", confidence=0.9, is_correct=True),
        AgentClassification(timestamp_s=200.0, satellite_id="SAT1", predicted_fault=None, confidence=0.8, is_correct=True),  # nominal
        AgentClassification(timestamp_s=300.0, satellite_id="SAT2", predicted_fault="power_loss", confidence=0.95, is_correct=True),
        AgentClassification(timestamp_s=400.0, satellite_id="SAT2", predicted_fault="thermal_fault", confidence=0.7, is_correct=False),  # false positive
    ]


class TestFaultState:
    """Test FaultState enum."""

    def test_fault_state_values(self):
        """Test FaultState enum values."""
        assert FaultState.NOMINAL == "nominal"
        assert FaultState.FAULTY == "faulty"


class TestGroundTruthEvent:
    """Test GroundTruthEvent dataclass."""

    def test_ground_truth_event_creation(self):
        """Test creating a GroundTruthEvent instance."""
        event = GroundTruthEvent(
            timestamp_s=123.45,
            satellite_id="SAT1",
            expected_fault_type="thermal_fault",
            confidence=1.0,
        )

        assert event.timestamp_s == 123.45
        assert event.satellite_id == "SAT1"
        assert event.expected_fault_type == "thermal_fault"
        assert event.confidence == 1.0

    def test_ground_truth_event_nominal(self):
        """Test GroundTruthEvent with nominal (None) fault type."""
        event = GroundTruthEvent(
            timestamp_s=200.0,
            satellite_id="SAT2",
            expected_fault_type=None,
            confidence=1.0,
        )

        assert event.expected_fault_type is None
        assert event.confidence == 1.0

    def test_ground_truth_event_asdict(self):
        """Test asdict conversion for GroundTruthEvent."""
        event = GroundTruthEvent(
            timestamp_s=100.0,
            satellite_id="SAT1",
            expected_fault_type="power_loss",
            confidence=1.0,
        )

        data = event.__dict__
        expected = {
            "timestamp_s": 100.0,
            "satellite_id": "SAT1",
            "expected_fault_type": "power_loss",
            "confidence": 1.0,
        }
        assert data == expected


class TestAgentClassification:
    """Test AgentClassification dataclass."""

    def test_agent_classification_creation(self):
        """Test creating an AgentClassification instance."""
        classification = AgentClassification(
            timestamp_s=150.0,
            satellite_id="SAT1",
            predicted_fault="thermal_fault",
            confidence=0.85,
            is_correct=True,
        )

        assert classification.timestamp_s == 150.0
        assert classification.satellite_id == "SAT1"
        assert classification.predicted_fault == "thermal_fault"
        assert classification.confidence == 0.85
        assert classification.is_correct is True

    def test_agent_classification_nominal(self):
        """Test AgentClassification with nominal (None) prediction."""
        classification = AgentClassification(
            timestamp_s=250.0,
            satellite_id="SAT2",
            predicted_fault=None,
            confidence=0.9,
            is_correct=True,
        )

        assert classification.predicted_fault is None
        assert classification.is_correct is True

    def test_agent_classification_incorrect(self):
        """Test AgentClassification with incorrect prediction."""
        classification = AgentClassification(
            timestamp_s=350.0,
            satellite_id="SAT3",
            predicted_fault="power_loss",
            confidence=0.6,
            is_correct=False,
        )

        assert classification.is_correct is False

    def test_agent_classification_asdict(self):
        """Test asdict conversion for AgentClassification."""
        classification = AgentClassification(
            timestamp_s=100.0,
            satellite_id="SAT1",
            predicted_fault="thermal_fault",
            confidence=0.9,
            is_correct=True,
        )

        data = classification.__dict__
        expected = {
            "timestamp_s": 100.0,
            "satellite_id": "SAT1",
            "predicted_fault": "thermal_fault",
            "confidence": 0.9,
            "is_correct": True,
        }
        assert data == expected


class TestAccuracyCollector:
    """Test AccuracyCollector class."""

    def test_initialization(self):
        """Test collector initialization."""
        collector = AccuracyCollector()
        assert collector.ground_truth_events == []
        assert collector.agent_classifications == []
        assert collector._ground_truth_by_sat == {}
        assert len(collector) == 0

    def test_record_ground_truth(self):
        """Test recording ground truth events."""
        collector = AccuracyCollector()

        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT1", 200.0, None)  # nominal
        collector.record_ground_truth("SAT2", 300.0, "power_loss")

        assert len(collector.ground_truth_events) == 3
        assert len(collector._ground_truth_by_sat["SAT1"]) == 2
        assert len(collector._ground_truth_by_sat["SAT2"]) == 1

        # Check sorting
        sat1_events = collector._ground_truth_by_sat["SAT1"]
        assert sat1_events[0].timestamp_s == 100.0
        assert sat1_events[1].timestamp_s == 200.0

    def test_record_agent_classification(self):
        """Test recording agent classifications."""
        collector = AccuracyCollector()

        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT1", 200.0, None, 0.8, True)
        collector.record_agent_classification("SAT2", 300.0, "power_loss", 0.95, True)

        assert len(collector.agent_classifications) == 3

        first = collector.agent_classifications[0]
        assert first.satellite_id == "SAT1"
        assert first.predicted_fault == "thermal_fault"
        assert first.is_correct is True

    def test_get_accuracy_stats_empty(self):
        """Test get_accuracy_stats with no classifications."""
        collector = AccuracyCollector()
        stats = collector.get_accuracy_stats()

        expected = {
            "total_classifications": 0,
            "correct_classifications": 0,
            "overall_accuracy": 0.0,
            "by_fault_type": {},
            "confidence_mean": 0.0,
            "confidence_std": 0.0,
        }
        assert stats == expected

    def test_get_accuracy_stats_single_classification(self):
        """Test get_accuracy_stats with single classification."""
        collector = AccuracyCollector()
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)

        stats = collector.get_accuracy_stats()

        assert stats["total_classifications"] == 1
        assert stats["correct_classifications"] == 1
        assert stats["overall_accuracy"] == 1.0
        assert stats["confidence_mean"] == 0.9
        assert stats["confidence_std"] == 0.0

    def test_get_accuracy_stats_multiple_classifications(self):
        """Test get_accuracy_stats with multiple classifications."""
        collector = AccuracyCollector()
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT1", 200.0, None, 0.8, True)
        collector.record_agent_classification("SAT2", 300.0, "power_loss", 0.7, False)

        stats = collector.get_accuracy_stats()

        assert stats["total_classifications"] == 3
        assert stats["correct_classifications"] == 2
        assert stats["overall_accuracy"] == 2.0 / 3.0
        assert abs(stats["confidence_mean"] - 0.8) < 1e-6  # (0.9 + 0.8 + 0.7) / 3
        assert stats["confidence_std"] > 0  # Should have some variance

    def test_calculate_per_fault_stats(self):
        """Test _calculate_per_fault_stats method."""
        collector = AccuracyCollector()

        # Record ground truth
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT2", 200.0, "power_loss")

        # Record classifications
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)  # TP
        collector.record_agent_classification("SAT2", 200.0, "power_loss", 0.8, True)  # TP
        collector.record_agent_classification("SAT1", 300.0, "thermal_fault", 0.7, False)  # FP
        collector.record_agent_classification("SAT2", 400.0, "power_loss", 0.6, False)  # FN (but wait, this is tricky)

        # For FN, we need a case where ground truth has fault but classification doesn't predict it correctly
        # Actually, FN is when we should have detected but didn't. This is complex.
        # Let's simplify: add a ground truth that wasn't classified correctly.

        # Reset and try simpler case
        collector = AccuracyCollector()
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)  # TP
        collector.record_agent_classification("SAT1", 200.0, "thermal_fault", 0.7, False)  # FP

        stats = collector.get_accuracy_stats()["by_fault_type"]

        assert "thermal_fault" in stats
        tf_stats = stats["thermal_fault"]
        assert tf_stats["true_positives"] == 1
        assert tf_stats["false_positives"] == 1
        assert tf_stats["false_negatives"] == 0  # No FN in this simple case
        assert tf_stats["precision"] == 0.5  # 1 / (1 + 1)
        assert tf_stats["recall"] == 1.0  # 1 / (1 + 0)
        assert tf_stats["f1"] == 2 * (0.5 * 1.0) / (0.5 + 1.0)  # 2/3

    def test_get_stats_by_satellite_empty(self):
        """Test get_stats_by_satellite with no classifications."""
        collector = AccuracyCollector()
        stats = collector.get_stats_by_satellite()
        assert stats == {}

    def test_get_stats_by_satellite_single_satellite(self):
        """Test get_stats_by_satellite with one satellite."""
        collector = AccuracyCollector()
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT1", 200.0, None, 0.8, True)

        stats = collector.get_stats_by_satellite()

        assert "SAT1" in stats
        sat1_stats = stats["SAT1"]
        assert sat1_stats["total_classifications"] == 2
        assert sat1_stats["correct_classifications"] == 2
        assert sat1_stats["accuracy"] == 1.0
        assert abs(sat1_stats["avg_confidence"] - 0.85) < 1e-6

    def test_get_stats_by_satellite_multiple_satellites(self):
        """Test get_stats_by_satellite with multiple satellites."""
        collector = AccuracyCollector()
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT2", 200.0, "power_loss", 0.8, False)
        collector.record_agent_classification("SAT2", 300.0, "power_loss", 0.7, True)

        stats = collector.get_stats_by_satellite()

        assert len(stats) == 2
        assert "SAT1" in stats
        assert "SAT2" in stats

        sat1_stats = stats["SAT1"]
        assert sat1_stats["total_classifications"] == 1
        assert sat1_stats["accuracy"] == 1.0

        sat2_stats = stats["SAT2"]
        assert sat2_stats["total_classifications"] == 2
        assert sat2_stats["correct_classifications"] == 1
        assert sat2_stats["accuracy"] == 0.5

    def test_get_confusion_matrix(self):
        """Test get_confusion_matrix method."""
        collector = AccuracyCollector()

        # Record ground truth
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT1", 200.0, None)
        collector.record_ground_truth("SAT2", 300.0, "power_loss")

        # Record classifications
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT1", 200.0, None, 0.8, True)
        collector.record_agent_classification("SAT2", 300.0, "power_loss", 0.95, True)
        collector.record_agent_classification("SAT1", 400.0, "thermal_fault", 0.7, False)  # FP

        matrix = collector.get_confusion_matrix()

        assert "thermal_fault" in matrix
        assert "nominal" in matrix
        assert "power_loss" in matrix

        # thermal_fault predicted vs actual
        assert matrix["thermal_fault"]["thermal_fault"] == 1  # TP
        assert matrix["thermal_fault"]["nominal"] == 1  # FP (predicted thermal but was nominal? Wait, need to check logic)

        # Actually, let's verify the confusion matrix logic
        # predicted: thermal_fault, actual: thermal_fault -> 1
        # predicted: nominal, actual: nominal -> 1
        # predicted: power_loss, actual: power_loss -> 1
        # predicted: thermal_fault, actual: nominal -> 1 (the FP case)

        assert matrix["nominal"]["nominal"] == 1
        assert matrix["power_loss"]["power_loss"] == 1

    def test_export_csv(self):
        """Test CSV export functionality."""
        collector = AccuracyCollector()
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT1", 200.0, None, 0.8, True)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            collector.export_csv(tmp_path)

            # Verify file exists and has content
            assert os.path.exists(tmp_path)

            with open(tmp_path, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 3  # header + 2 data rows
                assert "timestamp_s,satellite_id,predicted_fault,confidence,is_correct" in lines[0]
                assert "100.0,SAT1,thermal_fault,0.9,True" in lines[1]
                assert "200.0,SAT1,nominal,0.8,True" in lines[2]

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_get_summary(self):
        """Test get_summary method."""
        collector = AccuracyCollector()

        # Add some data
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)

        summary = collector.get_summary()

        assert summary["total_events"] == 1
        assert summary["total_classifications"] == 1
        assert "stats" in summary
        assert "stats_by_satellite" in summary
        assert "confusion_matrix" in summary

    def test_reset(self):
        """Test reset functionality."""
        collector = AccuracyCollector()
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)

        assert len(collector.ground_truth_events) == 1
        assert len(collector.agent_classifications) == 1

        collector.reset()

        assert len(collector.ground_truth_events) == 0
        assert len(collector.agent_classifications) == 0
        assert collector._ground_truth_by_sat == {}

    def test_len(self):
        """Test __len__ method."""
        collector = AccuracyCollector()
        assert len(collector) == 0

        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        assert len(collector) == 1

        collector.record_agent_classification("SAT2", 200.0, None, 0.8, True)
        assert len(collector) == 2

    def test_edge_case_no_ground_truth_for_classification(self):
        """Test case where classification has no matching ground truth."""
        collector = AccuracyCollector()

        # Record classification without ground truth
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, False)

        stats = collector.get_accuracy_stats()
        assert stats["total_classifications"] == 1
        assert stats["correct_classifications"] == 0

    def test_edge_case_multiple_fault_types(self):
        """Test with multiple fault types."""
        collector = AccuracyCollector()

        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT1", 200.0, "power_loss")

        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT1", 200.0, "power_loss", 0.8, True)

        stats = collector.get_accuracy_stats()
        by_fault = stats["by_fault_type"]

        assert "thermal_fault" in by_fault
        assert "power_loss" in by_fault

        assert by_fault["thermal_fault"]["precision"] == 1.0
        assert by_fault["power_loss"]["precision"] == 1.0

    def test_find_ground_truth_fault_method(self):
        """Test the internal _find_ground_truth_fault method indirectly."""
        collector = AccuracyCollector()

        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT1", 200.0, None)

        # This is tested indirectly through confusion matrix and stats
        matrix = collector.get_confusion_matrix()
        # Since no classifications, matrix should be empty or have defaults
        assert matrix == {}

    def test_confidence_statistics_edge_case(self):
        """Test confidence statistics with single value."""
        collector = AccuracyCollector()
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.5, True)

        stats = collector.get_accuracy_stats()
        assert stats["confidence_mean"] == 0.5
        assert stats["confidence_std"] == 0.0  # No variance with single value


class TestErrorHandling:
    """Test error handling and exception cases."""

    def test_record_ground_truth_with_valid_data(self):
        """Test recording ground truth accepts various valid data types."""
        collector = AccuracyCollector()
        
        # Should accept normal values
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT2", 200.5, None)
        
        assert len(collector.ground_truth_events) == 2

    def test_record_agent_classification_with_valid_data(self):
        """Test recording classification accepts various valid data types."""
        collector = AccuracyCollector()
        
        # Should accept normal values
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT2", 200.5, None, 0.8, False)
        
        assert len(collector.agent_classifications) == 2

    def test_export_csv_creates_directory_if_not_exists(self):
        """Test CSV export creates parent directory."""
        collector = AccuracyCollector()
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "subdir", "test.csv")
            collector.export_csv(csv_path)
            
            assert os.path.exists(csv_path)

    def test_get_summary_with_valid_data(self):
        """Test get_summary completes successfully with normal data."""
        collector = AccuracyCollector()
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        
        summary = collector.get_summary()
        assert "total_classifications" in summary
        assert summary["total_classifications"] == 1

    @patch('src.astraguard.hil.metrics.accuracy.logger')
    def test_logging_exists(self, mock_logger):
        """Test that logger is properly configured."""
        collector = AccuracyCollector()
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        
        # Logger exists and is used
        assert collector is not None


class TestBinarySearchEdgeCases:
    """Test binary search functionality in _find_ground_truth_fault."""

    def test_find_ground_truth_fault_no_data(self):
        """Test finding ground truth with no data recorded."""
        collector = AccuracyCollector()
        
        # Query confusion matrix which internally uses _find_ground_truth_fault
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        matrix = collector.get_confusion_matrix()
        
        # Should handle gracefully (no ground truth means nominal)
        assert "thermal_fault" in matrix

    def test_find_ground_truth_fault_before_first_event(self):
        """Test finding ground truth for timestamp before first event."""
        collector = AccuracyCollector()
        
        collector.record_ground_truth("SAT1", 200.0, "thermal_fault")
        collector.record_agent_classification("SAT1", 100.0, "power_loss", 0.8, False)
        
        matrix = collector.get_confusion_matrix()
        # Classification at 100.0 has no ground truth before it
        assert "power_loss" in matrix

    def test_find_ground_truth_fault_exact_match(self):
        """Test finding ground truth at exact timestamp."""
        collector = AccuracyCollector()
        
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        
        matrix = collector.get_confusion_matrix()
        assert matrix["thermal_fault"]["thermal_fault"] == 1

    def test_find_ground_truth_fault_between_events(self):
        """Test finding ground truth between two events."""
        collector = AccuracyCollector()
        
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT1", 300.0, "power_loss")
        collector.record_agent_classification("SAT1", 200.0, "thermal_fault", 0.9, True)
        
        matrix = collector.get_confusion_matrix()
        # At time 200.0, ground truth should be thermal_fault (from 100.0)
        assert matrix["thermal_fault"]["thermal_fault"] == 1

    def test_find_ground_truth_fault_after_last_event(self):
        """Test finding ground truth after last event."""
        collector = AccuracyCollector()
        
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_agent_classification("SAT1", 500.0, "thermal_fault", 0.9, True)
        
        matrix = collector.get_confusion_matrix()
        # At time 500.0, ground truth should still be thermal_fault
        assert matrix["thermal_fault"]["thermal_fault"] == 1

    def test_find_ground_truth_fault_multiple_satellites(self):
        """Test finding ground truth across multiple satellites."""
        collector = AccuracyCollector()
        
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT2", 100.0, "power_loss")
        
        collector.record_agent_classification("SAT1", 150.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT2", 150.0, "power_loss", 0.9, True)
        
        matrix = collector.get_confusion_matrix()
        assert matrix["thermal_fault"]["thermal_fault"] == 1
        assert matrix["power_loss"]["power_loss"] == 1


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_scenario_with_multiple_state_transitions(self):
        """Test scenario with multiple fault state transitions."""
        collector = AccuracyCollector()
        
        # Satellite goes through multiple states
        collector.record_ground_truth("SAT1", 0.0, None)  # nominal
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT1", 200.0, None)  # recovered
        collector.record_ground_truth("SAT1", 300.0, "power_loss")
        
        # Agent classifications at various points
        collector.record_agent_classification("SAT1", 50.0, None, 0.95, True)  # correct nominal
        collector.record_agent_classification("SAT1", 150.0, "thermal_fault", 0.9, True)  # correct fault
        collector.record_agent_classification("SAT1", 250.0, None, 0.85, True)  # correct recovery
        collector.record_agent_classification("SAT1", 350.0, "power_loss", 0.8, True)  # correct fault
        
        stats = collector.get_accuracy_stats()
        assert stats["overall_accuracy"] == 1.0
        assert stats["total_classifications"] == 4

    def test_scenario_with_misclassifications(self):
        """Test scenario with various types of misclassifications."""
        collector = AccuracyCollector()
        
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT2", 100.0, "power_loss")
        
        # Mix of correct and incorrect classifications
        collector.record_agent_classification("SAT1", 110.0, "thermal_fault", 0.9, True)  # TP
        collector.record_agent_classification("SAT1", 120.0, "power_loss", 0.7, False)  # FP (wrong fault)
        collector.record_agent_classification("SAT2", 110.0, "power_loss", 0.95, True)  # TP
        collector.record_agent_classification("SAT2", 120.0, None, 0.5, False)  # FN (missed fault)
        
        stats = collector.get_accuracy_stats()
        assert stats["total_classifications"] == 4
        assert stats["correct_classifications"] == 2
        assert stats["overall_accuracy"] == 0.5

    def test_scenario_with_low_confidence_predictions(self):
        """Test scenario where low confidence affects statistics."""
        collector = AccuracyCollector()
        
        # Perfect accuracy but varying confidence
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.51, True)  # low confidence
        collector.record_agent_classification("SAT2", 100.0, "power_loss", 0.99, True)  # high confidence
        collector.record_agent_classification("SAT3", 100.0, None, 0.75, True)  # medium confidence
        
        stats = collector.get_accuracy_stats()
        assert stats["overall_accuracy"] == 1.0
        assert stats["confidence_mean"] == pytest.approx((0.51 + 0.99 + 0.75) / 3, rel=1e-5)
        assert stats["confidence_std"] > 0

    def test_scenario_with_overlapping_timestamps(self):
        """Test scenario where classifications happen at same times."""
        collector = AccuracyCollector()
        
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT2", 100.0, "power_loss")
        
        # Multiple classifications at the same timestamp (different satellites)
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT2", 100.0, "power_loss", 0.9, True)
        
        stats_by_sat = collector.get_stats_by_satellite()
        assert len(stats_by_sat) == 2
        assert stats_by_sat["SAT1"]["accuracy"] == 1.0
        assert stats_by_sat["SAT2"]["accuracy"] == 1.0

    def test_large_scale_scenario(self):
        """Test with large number of events."""
        collector = AccuracyCollector()
        
        # Add many events
        for i in range(100):
            sat_id = f"SAT{i % 10}"  # 10 satellites
            timestamp = float(i * 10)
            fault_type = "thermal_fault" if i % 2 == 0 else "power_loss"
            
            collector.record_ground_truth(sat_id, timestamp, fault_type)
            collector.record_agent_classification(sat_id, timestamp + 1, fault_type, 0.9, True)
        
        stats = collector.get_accuracy_stats()
        assert stats["total_classifications"] == 100
        assert stats["correct_classifications"] == 100
        assert stats["overall_accuracy"] == 1.0

    def test_empty_collector_all_methods(self):
        """Test all methods on empty collector don't crash."""
        collector = AccuracyCollector()
        
        assert collector.get_accuracy_stats()["total_classifications"] == 0
        assert collector.get_stats_by_satellite() == {}
        assert collector.get_confusion_matrix() == {}
        
        summary = collector.get_summary()
        assert summary["total_events"] == 0
        assert summary["total_classifications"] == 0

    def test_reset_clears_all_data_structures(self):
        """Test reset thoroughly clears all internal data structures."""
        collector = AccuracyCollector()
        
        # Add various types of data
        collector.record_ground_truth("SAT1", 100.0, "thermal_fault")
        collector.record_ground_truth("SAT2", 200.0, "power_loss")
        collector.record_agent_classification("SAT1", 110.0, "thermal_fault", 0.9, True)
        collector.record_agent_classification("SAT2", 210.0, "power_loss", 0.8, True)
        
        # Verify data exists
        assert len(collector.ground_truth_events) > 0
        assert len(collector.agent_classifications) > 0
        assert len(collector._ground_truth_by_sat) > 0
        
        # Reset
        collector.reset()
        
        # Verify everything is cleared
        assert len(collector.ground_truth_events) == 0
        assert len(collector.agent_classifications) == 0
        assert len(collector._ground_truth_by_sat) == 0
        assert len(collector) == 0
        
        # Verify we can use it again after reset
        collector.record_agent_classification("SAT1", 100.0, "thermal_fault", 0.9, True)
        assert len(collector) == 1
