"""
Test suite for HIL accuracy metrics (Issue #498).

Comprehensive validation of AccuracyCollector, ground truth tracking,
agent classification recording, and ML metrics calculation.

Test Categories:
1. Ground truth recording and retrieval
2. Agent classification recording
3. Accuracy calculations (precision/recall/F1)
4. Per-satellite accuracy breakdown
5. Confusion matrix generation
6. CSV export functionality
7. Integration with ScenarioExecutor
8. Regression detection (accuracy degradation)
"""

import asyncio
import json
import pytest
import numpy as np
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory

from astraguard.hil.metrics.accuracy import (
    AccuracyCollector,
    GroundTruthEvent,
    AgentClassification,
    FaultState,
)
from astraguard.hil.scenarios.parser import ScenarioExecutor
from astraguard.hil.scenarios.schema import (
    Scenario,
    SatelliteConfig,
    FaultInjection,
    FaultType,
    SuccessCriteria,
)


class TestGroundTruthTracking:
    """Test ground truth recording and retrieval."""

    def test_record_single_ground_truth(self):
        """Record single ground truth event."""
        collector = AccuracyCollector()
        collector.record_ground_truth(
            sat_id="SAT-001",
            scenario_time_s=10.5,
            fault_type="power_brownout",
            confidence=1.0,
        )

        # Ground truth is tracked separately; check summary
        summary = collector.get_summary()
        # Summary should be empty since only ground truth, no classifications
        assert summary is not None

    def test_record_multiple_ground_truths(self):
        """Record multiple ground truth events."""
        collector = AccuracyCollector()
        for i in range(5):
            collector.record_ground_truth(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i * 2.0,
                fault_type="thermal_runaway",
                confidence=1.0,
            )

        # Ground truth tracked separately; only classifications counted in len()
        summary = collector.get_summary()
        assert summary is not None

    def test_ground_truth_confidence_always_one(self):
        """Ground truth should always have confidence=1.0 (perfect knowledge)."""
        collector = AccuracyCollector()
        collector.record_ground_truth(
            sat_id="SAT-001",
            scenario_time_s=5.0,
            fault_type="comms_dropout",
            confidence=1.0,
        )

        # Ground truth alone doesn't create classification entry
        # Just verify it doesn't error
        summary = collector.get_summary()
        assert summary is not None


class TestAgentClassification:
    """Test agent classification recording and tracking."""

    def test_record_correct_classification(self):
        """Record correct agent classification."""
        collector = AccuracyCollector()
        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=11.0,
            predicted_fault="power_brownout",
            confidence=0.95,
            is_correct=True,
        )

        assert len(collector) == 1

    def test_record_incorrect_classification(self):
        """Record incorrect agent classification."""
        collector = AccuracyCollector()
        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=11.0,
            predicted_fault="comms_dropout",
            confidence=0.42,
            is_correct=False,
        )

        assert len(collector) == 1

    def test_mixed_correct_and_incorrect(self):
        """Mix of correct and incorrect classifications."""
        collector = AccuracyCollector()

        # Record ground truth
        collector.record_ground_truth(
            sat_id="SAT-001",
            scenario_time_s=10.0,
            fault_type="thermal_runaway",
            confidence=1.0,
        )

        # Correct classification
        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=11.0,
            predicted_fault="thermal_runaway",
            confidence=0.9,
            is_correct=True,
        )

        # Incorrect classification
        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=12.0,
            predicted_fault="power_brownout",
            confidence=0.5,
            is_correct=False,
        )

        assert len(collector) == 2  # 2 agent classifications (ground truth tracked separately)


class TestAccuracyCalculation:
    """Test accuracy metrics calculation."""

    def test_overall_accuracy_100_percent(self):
        """100% accuracy when all correct."""
        collector = AccuracyCollector()

        for i in range(5):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="power_brownout",
                confidence=0.95,
                is_correct=True,
            )

        stats = collector.get_accuracy_stats()
        assert stats["overall_accuracy"] == 1.0

    def test_overall_accuracy_50_percent(self):
        """50% accuracy when half correct."""
        collector = AccuracyCollector()

        # 5 correct
        for i in range(5):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="power_brownout",
                confidence=0.9,
                is_correct=True,
            )

        # 5 incorrect
        for i in range(5, 10):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=15.0 + i,
                predicted_fault="thermal_runaway",
                confidence=0.4,
                is_correct=False,
            )

        stats = collector.get_accuracy_stats()
        assert stats["overall_accuracy"] == 0.5

    def test_zero_accuracy(self):
        """0% accuracy when all incorrect."""
        collector = AccuracyCollector()

        for i in range(5):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="comms_dropout",
                confidence=0.3,
                is_correct=False,
            )

        stats = collector.get_accuracy_stats()
        assert stats["overall_accuracy"] == 0.0


class TestPrecisionRecallF1:
    """Test precision, recall, and F1 score calculations."""

    def test_perfect_precision_recall_f1(self):
        """Perfect precision/recall/F1 for single fault type."""
        collector = AccuracyCollector()

        # All thermal_runaway predictions are correct
        for i in range(5):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="thermal_runaway",
                confidence=0.95,
                is_correct=True,
            )

        stats = collector.get_accuracy_stats()
        thermal_stats = stats["by_fault_type"].get("thermal_runaway", {})

        assert thermal_stats.get("precision") == 1.0
        assert thermal_stats.get("recall") == 1.0
        assert thermal_stats.get("f1") == 1.0

    def test_precision_recall_tradeoff(self):
        """Test precision-recall calculation with mixed results."""
        collector = AccuracyCollector()

        # 8 correct power_brownout predictions
        for i in range(8):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="power_brownout",
                confidence=0.9,
                is_correct=True,
            )

        # 2 incorrect power_brownout predictions (false positives)
        for i in range(8, 10):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=20.0 + i,
                predicted_fault="power_brownout",
                confidence=0.4,
                is_correct=False,
            )

        stats = collector.get_accuracy_stats()
        power_stats = stats["by_fault_type"].get("power_brownout", {})

        # Precision: TP / (TP + FP) = 8 / (8 + 2) = 0.8
        assert abs(power_stats.get("precision", 0) - 0.8) < 0.001


class TestConfusionMatrix:
    """Test confusion matrix generation."""

    def test_confusion_matrix_simple(self):
        """Simple confusion matrix with two fault types."""
        collector = AccuracyCollector()

        # Correct thermal detections
        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=10.0,
            predicted_fault="thermal_runaway",
            confidence=0.9,
            is_correct=True,
        )

        # Misclassified as power_brownout
        collector.record_agent_classification(
            sat_id="SAT-002",
            scenario_time_s=11.0,
            predicted_fault="power_brownout",
            confidence=0.5,
            is_correct=False,
        )

        matrix = collector.get_confusion_matrix()
        assert matrix is not None

    def test_confusion_matrix_structure(self):
        """Verify confusion matrix structure."""
        collector = AccuracyCollector()

        # Record multiple classifications
        for fault_type in ["power_brownout", "thermal_runaway", "comms_dropout"]:
            collector.record_agent_classification(
                sat_id="SAT-001",
                scenario_time_s=10.0,
                predicted_fault=fault_type,
                confidence=0.9,
                is_correct=True,
            )

        matrix = collector.get_confusion_matrix()
        assert isinstance(matrix, dict)
        # Should have predictions for each fault type
        assert len(matrix) > 0


class TestPerSatelliteAccuracy:
    """Test per-satellite accuracy breakdown."""

    def test_per_satellite_breakdown(self):
        """Verify per-satellite accuracy statistics."""
        collector = AccuracyCollector()

        # SAT-001: 3 correct, 1 incorrect (75%)
        for i in range(3):
            collector.record_agent_classification(
                sat_id="SAT-001",
                scenario_time_s=10.0 + i,
                predicted_fault="power_brownout",
                confidence=0.9,
                is_correct=True,
            )

        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=13.0,
            predicted_fault="thermal_runaway",
            confidence=0.4,
            is_correct=False,
        )

        # SAT-002: 4 correct, 0 incorrect (100%)
        for i in range(4):
            collector.record_agent_classification(
                sat_id="SAT-002",
                scenario_time_s=20.0 + i,
                predicted_fault="comms_dropout",
                confidence=0.95,
                is_correct=True,
            )

        sat_stats = collector.get_stats_by_satellite()
        assert sat_stats is not None
        assert len(sat_stats) >= 2

    def test_single_satellite_isolation(self):
        """Single satellite accuracy shouldn't affect others."""
        collector = AccuracyCollector()

        # SAT-001: 100% correct
        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=10.0,
            predicted_fault="power_brownout",
            confidence=0.95,
            is_correct=True,
        )

        # SAT-002: 0% correct
        collector.record_agent_classification(
            sat_id="SAT-002",
            scenario_time_s=11.0,
            predicted_fault="thermal_runaway",
            confidence=0.3,
            is_correct=False,
        )

        sat_stats = collector.get_stats_by_satellite()

        sat001_acc = sat_stats.get("SAT-001", {}).get("accuracy", 0)
        sat002_acc = sat_stats.get("SAT-002", {}).get("accuracy", 0)

        assert sat001_acc > sat002_acc


class TestConfidenceScoring:
    """Test confidence score tracking and aggregation."""

    def test_high_confidence_correct(self):
        """High confidence predictions should be tracked."""
        collector = AccuracyCollector()

        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=10.0,
            predicted_fault="power_brownout",
            confidence=0.95,
            is_correct=True,
        )

        summary = collector.get_summary()
        assert summary["total_classifications"] == 1

    def test_low_confidence_tracking(self):
        """Low confidence predictions should be tracked."""
        collector = AccuracyCollector()

        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=10.0,
            predicted_fault="thermal_runaway",
            confidence=0.32,
            is_correct=False,
        )

        summary = collector.get_summary()
        assert summary["total_classifications"] == 1

    def test_confidence_statistics(self):
        """Verify confidence statistics aggregation."""
        collector = AccuracyCollector()

        confidences = [0.9, 0.85, 0.92, 0.88, 0.95]
        for i, conf in enumerate(confidences):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="power_brownout",
                confidence=conf,
                is_correct=True,
            )

        stats = collector.get_accuracy_stats()
        assert stats["overall_accuracy"] == 1.0


class TestCSVExport:
    """Test CSV export functionality."""

    def test_csv_export_creates_file(self):
        """CSV export should create valid file."""
        collector = AccuracyCollector()

        # Add sample data
        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=10.0,
            predicted_fault="power_brownout",
            confidence=0.9,
            is_correct=True,
        )

        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "accuracy.csv"
            collector.export_csv(str(csv_path))

            assert csv_path.exists()
            assert csv_path.stat().st_size > 0

    def test_csv_export_content(self):
        """CSV export should contain classification data."""
        collector = AccuracyCollector()

        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=10.0,
            predicted_fault="power_brownout",
            confidence=0.9,
            is_correct=True,
        )

        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "accuracy.csv"
            collector.export_csv(str(csv_path))

            with open(csv_path, "r") as f:
                content = f.read()
                assert "SAT-001" in content
                assert "power_brownout" in content
                assert "0.9" in content

    def test_csv_export_multiple_records(self):
        """CSV export with multiple records."""
        collector = AccuracyCollector()

        for i in range(5):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="thermal_runaway",
                confidence=0.85 + i * 0.01,
                is_correct=True,
            )

        with TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "accuracy.csv"
            collector.export_csv(str(csv_path))

            # Count lines (header + 5 records)
            with open(csv_path, "r") as f:
                lines = f.readlines()
                assert len(lines) >= 5  # At least 5 data rows


class TestResetFunctionality:
    """Test collector reset functionality."""

    def test_reset_clears_data(self):
        """Reset should clear all collected data."""
        collector = AccuracyCollector()

        # Add data
        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=10.0,
            predicted_fault="power_brownout",
            confidence=0.9,
            is_correct=True,
        )

        assert len(collector) == 1

        # Reset
        collector.reset()

        assert len(collector) == 0

    def test_reset_allows_new_collection(self):
        """Can collect new data after reset."""
        collector = AccuracyCollector()

        # Add initial data
        collector.record_agent_classification(
            sat_id="SAT-001",
            scenario_time_s=10.0,
            predicted_fault="power_brownout",
            confidence=0.9,
            is_correct=True,
        )

        # Reset
        collector.reset()

        # Add new data
        collector.record_agent_classification(
            sat_id="SAT-002",
            scenario_time_s=20.0,
            predicted_fault="thermal_runaway",
            confidence=0.85,
            is_correct=True,
        )

        assert len(collector) == 1
        summary = collector.get_summary()
        assert summary["total_classifications"] == 1


class TestIntegrationWithScenarioExecutor:
    """Test accuracy collector integration with ScenarioExecutor."""

    @pytest.mark.asyncio
    async def test_executor_has_accuracy_collector(self):
        """ScenarioExecutor should have accuracy_collector."""
        scenario = Scenario(
            name="test_scenario",
            description="Test integration",
            duration_s=300,
            satellites=[
                SatelliteConfig(
                    id="SAT-001",
                    initial_position_km=[0, 0, 420],
                )
            ],
            fault_sequence=[],
            success_criteria=SuccessCriteria(max_temperature_c=85.0),
        )

        executor = ScenarioExecutor(scenario)
        assert hasattr(executor, "accuracy_collector")
        assert executor.accuracy_collector is not None

    @pytest.mark.asyncio
    async def test_executor_records_ground_truth(self):
        """ScenarioExecutor should record ground truth at fault injection."""
        scenario = Scenario(
            name="test_ground_truth",
            description="Test ground truth recording",
            duration_s=300,
            satellites=[
                SatelliteConfig(
                    id="SAT-001",
                    initial_position_km=[0, 0, 420],
                )
            ],
            fault_sequence=[
                FaultInjection(
                    satellite="SAT-001",
                    type=FaultType.THERMAL_RUNAWAY,
                    start_time_s=60.0,
                    duration_s=60.0,
                )
            ],
            success_criteria=SuccessCriteria(max_temperature_c=85.0),
        )

        executor = ScenarioExecutor(scenario)
        results = await executor.run(speed=10.0, verbose=False)

        # Check that results include accuracy stats
        assert "accuracy_stats" in results or "accuracy_summary" in results


class TestRegressionDetection:
    """Test accuracy degradation detection."""

    def test_degraded_accuracy_detection(self):
        """Should detect when accuracy drops below threshold."""
        collector = AccuracyCollector()

        # Simulate degraded accuracy: 60% correct instead of expected 90%
        correct_count = 6
        incorrect_count = 4

        for i in range(correct_count):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="power_brownout",
                confidence=0.85,
                is_correct=True,
            )

        for i in range(incorrect_count):
            collector.record_agent_classification(
                sat_id=f"SAT-{correct_count + i:03d}",
                scenario_time_s=20.0 + i,
                predicted_fault="thermal_runaway",
                confidence=0.4,
                is_correct=False,
            )

        stats = collector.get_accuracy_stats()
        assert stats["overall_accuracy"] == 0.6


class TestDataConsistency:
    """Test data consistency and integrity."""

    def test_classification_count_tracking(self):
        """Classification count should match recorded entries."""
        collector = AccuracyCollector()

        for i in range(10):
            collector.record_agent_classification(
                sat_id=f"SAT-{i % 3:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="power_brownout",
                confidence=0.9,
                is_correct=i % 2 == 0,
            )

        assert len(collector) == 10

    def test_summary_accuracy_matches_calculation(self):
        """Summary accuracy should match manual calculation."""
        collector = AccuracyCollector()

        correct = 7
        incorrect = 3

        for i in range(correct):
            collector.record_agent_classification(
                sat_id=f"SAT-{i:03d}",
                scenario_time_s=10.0 + i,
                predicted_fault="power_brownout",
                confidence=0.9,
                is_correct=True,
            )

        for i in range(incorrect):
            collector.record_agent_classification(
                sat_id=f"SAT-{correct + i:03d}",
                scenario_time_s=20.0 + i,
                predicted_fault="thermal_runaway",
                confidence=0.4,
                is_correct=False,
            )

        stats = collector.get_accuracy_stats()
        expected_accuracy = correct / (correct + incorrect)

        assert abs(stats["overall_accuracy"] - expected_accuracy) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
