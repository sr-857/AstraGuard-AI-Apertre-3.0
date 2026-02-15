"""
Unit tests for anomaly/report_generator.py

Tests cover:
- AnomalyEvent dataclass functionality
- RecoveryAction dataclass functionality
- AnomalyReportGenerator core methods
- Report generation and filtering
- JSON and text export
- Data cleanup and historical management
"""

import json
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the module to test
from src.anomaly.report_generator import (
    AnomalyEvent,
    RecoveryAction,
    AnomalyReportGenerator,
    get_report_generator
)
from src.core.input_validation import ValidationError


class TestAnomalyEvent:
    """Test suite for AnomalyEvent dataclass."""

    def test_anomaly_event_initialization(self):
        """Test basic initialization of AnomalyEvent."""
        timestamp = datetime.now()
        telemetry = {"temperature": 45.5, "voltage": 12.3}
        
        event = AnomalyEvent(
            timestamp=timestamp,
            anomaly_type="temperature_spike",
            severity="HIGH",
            confidence=0.95,
            mission_phase="orbit_maintenance",
            telemetry_data=telemetry
        )
        
        assert event.timestamp == timestamp
        assert event.anomaly_type == "temperature_spike"
        assert event.severity == "HIGH"
        assert event.confidence == 0.95
        assert event.mission_phase == "orbit_maintenance"
        assert event.telemetry_data == telemetry
        assert event.explanation is None
        assert event.recovery_actions == []
        assert event.resolved is False
        assert event.resolution_time is None

    def test_anomaly_event_with_optional_fields(self):
        """Test AnomalyEvent with optional fields populated."""
        timestamp = datetime.now()
        resolution_time = datetime.now() + timedelta(minutes=5)
        recovery_actions = [{"action": "restart", "status": "success"}]
        
        event = AnomalyEvent(
            timestamp=timestamp,
            anomaly_type="sensor_drift",
            severity="MEDIUM",
            confidence=0.85,
            mission_phase="data_collection",
            telemetry_data={"sensor_id": "S123"},
            explanation="Gradual drift detected in sensor S123",
            recovery_actions=recovery_actions,
            resolved=True,
            resolution_time=resolution_time
        )
        
        assert event.explanation == "Gradual drift detected in sensor S123"
        assert event.recovery_actions == recovery_actions
        assert event.resolved is True
        assert event.resolution_time == resolution_time

    def test_anomaly_event_to_dict(self):
        """Test conversion of AnomalyEvent to dictionary."""
        timestamp = datetime(2025, 2, 11, 10, 30, 0)
        resolution_time = datetime(2025, 2, 11, 10, 35, 0)
        
        event = AnomalyEvent(
            timestamp=timestamp,
            anomaly_type="power_anomaly",
            severity="CRITICAL",
            confidence=0.98,
            mission_phase="eclipse",
            telemetry_data={"power": 8.5},
            resolved=True,
            resolution_time=resolution_time
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["timestamp"] == timestamp.isoformat()
        assert event_dict["anomaly_type"] == "power_anomaly"
        assert event_dict["severity"] == "CRITICAL"
        assert event_dict["confidence"] == 0.98
        assert event_dict["resolution_time"] == resolution_time.isoformat()
        assert event_dict["resolved"] is True

    def test_anomaly_event_post_init_recovery_actions(self):
        """Test that recovery_actions is initialized as empty list if None."""
        event = AnomalyEvent(
            timestamp=datetime.now(),
            anomaly_type="test",
            severity="LOW",
            confidence=0.5,
            mission_phase="test_phase",
            telemetry_data={},
            recovery_actions=None
        )
        
        assert event.recovery_actions == []
        assert isinstance(event.recovery_actions, list)


class TestRecoveryAction:
    """Test suite for RecoveryAction dataclass."""

    def test_recovery_action_initialization(self):
        """Test basic initialization of RecoveryAction."""
        timestamp = datetime.now()
        
        action = RecoveryAction(
            timestamp=timestamp,
            action_type="system_restart",
            anomaly_type="cpu_overload",
            success=True,
            duration_seconds=12.5
        )
        
        assert action.timestamp == timestamp
        assert action.action_type == "system_restart"
        assert action.anomaly_type == "cpu_overload"
        assert action.success is True
        assert action.duration_seconds == 12.5
        assert action.error_message is None
        assert action.metadata == {}

    def test_recovery_action_with_failure(self):
        """Test RecoveryAction for a failed action."""
        timestamp = datetime.now()
        metadata = {"attempt": 2, "reason": "timeout"}
        
        action = RecoveryAction(
            timestamp=timestamp,
            action_type="sensor_recalibration",
            anomaly_type="calibration_drift",
            success=False,
            duration_seconds=30.0,
            error_message="Timeout during recalibration",
            metadata=metadata
        )
        
        assert action.success is False
        assert action.error_message == "Timeout during recalibration"
        assert action.metadata == metadata

    def test_recovery_action_to_dict(self):
        """Test conversion of RecoveryAction to dictionary."""
        timestamp = datetime(2025, 2, 11, 11, 0, 0)
        
        action = RecoveryAction(
            timestamp=timestamp,
            action_type="power_cycle",
            anomaly_type="voltage_spike",
            success=True,
            duration_seconds=5.3,
            metadata={"cycles": 1}
        )
        
        action_dict = action.to_dict()
        
        assert action_dict["timestamp"] == timestamp.isoformat()
        assert action_dict["action_type"] == "power_cycle"
        assert action_dict["success"] is True
        assert action_dict["duration_seconds"] == 5.3
        assert action_dict["metadata"] == {"cycles": 1}

    def test_recovery_action_post_init_metadata(self):
        """Test that metadata is initialized as empty dict if None."""
        action = RecoveryAction(
            timestamp=datetime.now(),
            action_type="test_action",
            anomaly_type="test_anomaly",
            success=True,
            duration_seconds=1.0,
            metadata=None
        )
        
        assert action.metadata == {}
        assert isinstance(action.metadata, dict)


class TestAnomalyReportGenerator:
    """Test suite for AnomalyReportGenerator class."""

    @pytest.fixture
    def generator(self):
        """Fixture to create a fresh generator for each test."""
        return AnomalyReportGenerator(max_history_days=30)

    def test_initialization(self, generator):
        """Test generator initialization."""
        assert generator.anomalies == []
        assert generator.recovery_actions == []
        assert generator.max_history_days == 30

    def test_record_anomaly_basic(self, generator):
        """Test recording a basic anomaly."""
        telemetry = {"temp": 55.0, "voltage": 11.8}
        
        generator.record_anomaly(
            anomaly_type="temperature_spike",
            severity="HIGH",
            confidence=0.92,
            mission_phase="data_collection",
            telemetry_data=telemetry
        )
        
        assert len(generator.anomalies) == 1
        anomaly = generator.anomalies[0]
        assert anomaly.anomaly_type == "temperature_spike"
        assert anomaly.severity == "HIGH"
        assert anomaly.confidence == 0.92
        assert anomaly.mission_phase == "data_collection"
        assert anomaly.telemetry_data == telemetry
        assert anomaly.explanation is None

    def test_record_anomaly_with_explanation(self, generator):
        """Test recording an anomaly with explanation."""
        generator.record_anomaly(
            anomaly_type="sensor_drift",
            severity="MEDIUM",
            confidence=0.85,
            mission_phase="orbit_maintenance",
            telemetry_data={"sensor": "S001"},
            explanation="Sensor reading drifting beyond threshold"
        )
        
        assert len(generator.anomalies) == 1
        assert generator.anomalies[0].explanation == "Sensor reading drifting beyond threshold"

    def test_record_multiple_anomalies(self, generator):
        """Test recording multiple anomalies."""
        for i in range(5):
            generator.record_anomaly(
                anomaly_type=f"anomaly_{i}",
                severity="LOW",
                confidence=0.7,
                mission_phase="test",
                telemetry_data={"index": i}
            )
        
        assert len(generator.anomalies) == 5

    def test_record_recovery_action_success(self, generator):
        """Test recording a successful recovery action."""
        generator.record_recovery_action(
            action_type="system_restart",
            anomaly_type="cpu_overload",
            success=True,
            duration_seconds=8.5
        )
        
        assert len(generator.recovery_actions) == 1
        action = generator.recovery_actions[0]
        assert action.action_type == "system_restart"
        assert action.anomaly_type == "cpu_overload"
        assert action.success is True
        assert action.duration_seconds == 8.5

    def test_record_recovery_action_failure(self, generator):
        """Test recording a failed recovery action."""
        metadata = {"attempt": 3}
        
        generator.record_recovery_action(
            action_type="sensor_reset",
            anomaly_type="sensor_malfunction",
            success=False,
            duration_seconds=15.0,
            error_message="Sensor not responding",
            metadata=metadata
        )
        
        assert len(generator.recovery_actions) == 1
        action = generator.recovery_actions[0]
        assert action.success is False
        assert action.error_message == "Sensor not responding"
        assert action.metadata == metadata

    def test_resolve_anomaly_valid_index(self, generator):
        """Test resolving an anomaly with valid index."""
        generator.record_anomaly(
            anomaly_type="test_anomaly",
            severity="LOW",
            confidence=0.7,
            mission_phase="test",
            telemetry_data={}
        )
        
        assert generator.anomalies[0].resolved is False
        assert generator.anomalies[0].resolution_time is None
        
        generator.resolve_anomaly(0)
        
        assert generator.anomalies[0].resolved is True
        assert generator.anomalies[0].resolution_time is not None
        assert isinstance(generator.anomalies[0].resolution_time, datetime)

    def test_resolve_anomaly_invalid_index(self, generator):
        """Test resolving an anomaly with invalid index (should raise ValidationError)."""
        generator.record_anomaly(
            anomaly_type="test_anomaly",
            severity="LOW",
            confidence=0.7,
            mission_phase="test",
            telemetry_data={}
        )
        
        # Should raise ValidationError for out of bounds index
        with pytest.raises(ValidationError):
            generator.resolve_anomaly(10)  # Out of bounds
        
        # Should raise ValidationError for negative index
        with pytest.raises(ValidationError):
            generator.resolve_anomaly(-1)  # Negative index (out of range)
        
        # Original anomaly should be unaffected
        assert generator.anomalies[0].resolved is False

    def test_generate_report_default_time_range(self, generator):
        """Test generating a report with default time range (last 24 hours)."""
        # Add some anomalies
        generator.record_anomaly(
            anomaly_type="spike",
            severity="HIGH",
            confidence=0.9,
            mission_phase="test",
            telemetry_data={}
        )
        
        report = generator.generate_report()
        
        assert "report_metadata" in report
        assert "summary" in report
        assert "anomalies" in report
        assert "recovery_actions" in report
        assert report["summary"]["total_anomalies"] == 1

    def test_generate_report_custom_time_range(self, generator):
        """Test generating a report with custom time range."""
        # Create anomalies at different times
        now = datetime.now()
        
        # Create an old anomaly and manually set its timestamp
        generator.record_anomaly(
            anomaly_type="old_anomaly",
            severity="LOW",
            confidence=0.5,
            mission_phase="test",
            telemetry_data={}
        )
        # Manually set timestamp for the old anomaly (5 days ago)
        generator.anomalies[0].timestamp = now - timedelta(days=5)
        
        # Create a recent anomaly
        generator.record_anomaly(
            anomaly_type="recent_anomaly",
            severity="HIGH",
            confidence=0.95,
            mission_phase="test",
            telemetry_data={}
        )
        # Ensure the recent anomaly timestamp is current
        generator.anomalies[1].timestamp = now
        
        # Generate report for last 24 hours
        start_time = now - timedelta(hours=24)
        end_time = now + timedelta(minutes=1)  # Add small buffer for test timing
        report = generator.generate_report(start_time, end_time)
        
        # Should only include recent anomaly
        assert report["summary"]["total_anomalies"] == 1
        assert report["anomalies"][0]["anomaly_type"] == "recent_anomaly"

    def test_generate_report_statistics(self, generator):
        """Test that report generates correct statistics."""
        # Add multiple anomalies
        generator.record_anomaly("spike", "CRITICAL", 0.95, "test", {})
        generator.record_anomaly("drift", "HIGH", 0.85, "test", {})
        generator.record_anomaly("spike", "MEDIUM", 0.75, "test", {})
        
        # Resolve one
        generator.resolve_anomaly(0)
        
        # Add recovery actions
        generator.record_recovery_action("restart", "spike", True, 5.0)
        generator.record_recovery_action("recalibrate", "drift", True, 10.0)
        
        report = generator.generate_report()
        
        summary = report["summary"]
        assert summary["total_anomalies"] == 3
        assert summary["resolved_anomalies"] == 1
        assert summary["resolution_rate"] == pytest.approx(1/3)
        assert summary["critical_anomalies"] == 1
        assert summary["anomaly_types"]["spike"] == 2
        assert summary["anomaly_types"]["drift"] == 1
        assert summary["recovery_actions"]["restart"] == 1
        assert summary["recovery_actions"]["recalibrate"] == 1

    def test_generate_report_mttr_calculation(self, generator):
        """Test Mean Time To Resolution (MTTR) calculation."""
        # Create anomalies with known resolution times
        base_time = datetime.now()
        
        # Anomaly 1: resolved in 60 seconds
        generator.record_anomaly("test1", "HIGH", 0.9, "test", {})
        generator.anomalies[0].timestamp = base_time
        generator.anomalies[0].resolved = True
        generator.anomalies[0].resolution_time = base_time + timedelta(seconds=60)
        
        # Anomaly 2: resolved in 120 seconds
        generator.record_anomaly("test2", "HIGH", 0.9, "test", {})
        generator.anomalies[1].timestamp = base_time
        generator.anomalies[1].resolved = True
        generator.anomalies[1].resolution_time = base_time + timedelta(seconds=120)
        
        # Anomaly 3: not resolved (should not affect MTTR)
        generator.record_anomaly("test3", "HIGH", 0.9, "test", {})
        
        report = generator.generate_report()
        
        # MTTR should be (60 + 120) / 2 = 90 seconds
        assert report["summary"]["average_mttr_seconds"] == 90.0

    def test_generate_report_no_anomalies(self, generator):
        """Test generating a report with no anomalies."""
        report = generator.generate_report()
        
        summary = report["summary"]
        assert summary["total_anomalies"] == 0
        assert summary["resolved_anomalies"] == 0
        assert summary["resolution_rate"] == 0
        assert summary["critical_anomalies"] == 0
        assert summary["average_mttr_seconds"] is None
        assert summary["anomaly_types"] == {}
        assert summary["recovery_actions"] == {}

    def test_export_json_creates_file(self, generator):
        """Test that JSON export creates a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "report.json")
            
            generator.record_anomaly("test", "HIGH", 0.9, "test", {"value": 123})
            
            result_path = generator.export_json(file_path)
            
            assert result_path == file_path
            assert os.path.exists(file_path)
            
            # Verify JSON is valid
            with open(file_path, 'r') as f:
                data = json.load(f)
                assert "report_metadata" in data
                assert "summary" in data
                assert data["summary"]["total_anomalies"] == 1

    def test_export_json_pretty_formatting(self, generator):
        """Test that pretty JSON export is properly formatted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "pretty.json")
            
            generator.record_anomaly("test", "HIGH", 0.9, "test", {})
            generator.export_json(file_path, pretty=True)
            
            with open(file_path, 'r') as f:
                content = f.read()
                # Pretty JSON should have indentation
                assert "  " in content or "\n" in content

    def test_export_json_compact_formatting(self, generator):
        """Test that compact JSON export has no extra whitespace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "compact.json")
            
            generator.record_anomaly("test", "HIGH", 0.9, "test", {})
            generator.export_json(file_path, pretty=False)
            
            with open(file_path, 'r') as f:
                content = f.read()
                # Verify it's still valid JSON
                data = json.loads(content)
                assert "summary" in data

    def test_export_json_creates_directory(self, generator):
        """Test that JSON export creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "subdir", "nested", "report.json")
            
            generator.record_anomaly("test", "HIGH", 0.9, "test", {})
            generator.export_json(file_path)
            
            assert os.path.exists(file_path)

    def test_export_text_creates_file(self, generator):
        """Test that text export creates a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "report.txt")
            
            generator.record_anomaly("test_anomaly", "CRITICAL", 0.95, "test_phase", {"temp": 60})
            
            result_path = generator.export_text(file_path)
            
            assert result_path == file_path
            assert os.path.exists(file_path)
            
            # Verify content
            with open(file_path, 'r') as f:
                content = f.read()
                assert "ASTRA GUARD AI - ANOMALY REPORT" in content
                assert "SUMMARY" in content
                assert "test_anomaly" in content

    def test_export_text_formatting(self, generator):
        """Test text export formatting and content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "report.txt")
            
            # Add anomaly and recovery action
            generator.record_anomaly(
                "sensor_drift",
                "HIGH",
                0.88,
                "data_collection",
                {"sensor": "S123"},
                explanation="Gradual drift detected"
            )
            generator.resolve_anomaly(0)
            generator.record_recovery_action("recalibrate", "sensor_drift", True, 15.5)
            
            generator.export_text(file_path)
            
            with open(file_path, 'r') as f:
                content = f.read()
                
                # Check for key sections
                assert "=" * 80 in content
                assert "SUMMARY" in content
                assert "-" * 40 in content
                assert "Total Anomalies:" in content
                assert "Resolved Anomalies:" in content
                assert "Resolution Rate:" in content
                assert "Anomaly Types:" in content
                assert "Recovery Actions:" in content
                assert "ANOMALY DETAILS" in content
                
                # Check for specific data
                assert "sensor_drift" in content
                assert "HIGH" in content
                assert "data_collection" in content
                assert "Gradual drift detected" in content

    def test_export_text_creates_directory(self, generator):
        """Test that text export creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "reports", "2025", "report.txt")
            
            generator.record_anomaly("test", "LOW", 0.6, "test", {})
            generator.export_text(file_path)
            
            assert os.path.exists(file_path)

    def test_cleanup_old_data(self, generator):
        """Test that old data is cleaned up correctly."""
        now = datetime.now()
        old_time = now - timedelta(days=35)  # Older than max_history_days
        
        # Add old anomaly
        generator.record_anomaly("old", "LOW", 0.5, "test", {})
        generator.anomalies[0].timestamp = old_time
        
        # Add old recovery action
        generator.record_recovery_action("old_action", "old", True, 1.0)
        generator.recovery_actions[0].timestamp = old_time
        
        # Add recent data
        generator.record_anomaly("recent", "HIGH", 0.9, "test", {})
        generator.record_recovery_action("recent_action", "recent", True, 2.0)
        
        # Trigger cleanup
        generator._cleanup_old_data()
        
        # Should only have recent data
        assert len(generator.anomalies) == 1
        assert generator.anomalies[0].anomaly_type == "recent"
        assert len(generator.recovery_actions) == 1
        assert generator.recovery_actions[0].action_type == "recent_action"

    def test_clear_history(self, generator):
        """Test clearing all history."""
        # Add some data
        generator.record_anomaly("test1", "HIGH", 0.9, "test", {})
        generator.record_anomaly("test2", "MEDIUM", 0.8, "test", {})
        generator.record_recovery_action("action1", "test1", True, 5.0)
        
        assert len(generator.anomalies) == 2
        assert len(generator.recovery_actions) == 1
        
        # Clear history
        generator.clear_history()
        
        assert len(generator.anomalies) == 0
        assert len(generator.recovery_actions) == 0

    def test_custom_max_history_days(self):
        """Test initializing generator with custom max_history_days."""
        generator = AnomalyReportGenerator(max_history_days=7)
        assert generator.max_history_days == 7


class TestGlobalReportGenerator:
    """Test suite for global report generator singleton."""

    def test_get_report_generator_creates_instance(self):
        """Test that get_report_generator creates an instance."""
        generator = get_report_generator()
        assert isinstance(generator, AnomalyReportGenerator)

    def test_get_report_generator_returns_same_instance(self):
        """Test that get_report_generator returns the same instance."""
        generator1 = get_report_generator()
        generator2 = get_report_generator()
        assert generator1 is generator2


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    @pytest.fixture
    def generator(self):
        """Fixture to create a fresh generator for each test."""
        return AnomalyReportGenerator()

    def test_empty_telemetry_data(self, generator):
        """Test handling of empty telemetry data."""
        generator.record_anomaly("test", "LOW", 0.5, "test", {})
        assert generator.anomalies[0].telemetry_data == {}

    def test_zero_confidence(self, generator):
        """Test handling of zero confidence."""
        generator.record_anomaly("test", "LOW", 0.0, "test", {})
        assert generator.anomalies[0].confidence == 0.0

    def test_max_confidence(self, generator):
        """Test handling of maximum confidence."""
        generator.record_anomaly("test", "CRITICAL", 1.0, "test", {})
        assert generator.anomalies[0].confidence == 1.0

    def test_zero_duration_recovery(self, generator):
        """Test handling of zero duration recovery action."""
        generator.record_recovery_action("instant", "test", True, 0.0)
        assert generator.recovery_actions[0].duration_seconds == 0.0

    def test_report_with_only_recovery_actions(self, generator):
        """Test generating report with only recovery actions, no anomalies."""
        generator.record_recovery_action("test_action", "phantom", True, 5.0)
        
        report = generator.generate_report()
        
        assert report["summary"]["total_anomalies"] == 0
        assert len(report["recovery_actions"]) == 1

    def test_unicode_in_explanations(self, generator):
        """Test handling of Unicode characters in explanations."""
        generator.record_anomaly(
            "test",
            "LOW",
            0.7,
            "test",
            {},
            explanation="Temperature exceeded threshold by 5°C ± 0.5"
        )
        
        assert "°C" in generator.anomalies[0].explanation

    def test_special_characters_in_metadata(self, generator):
        """Test handling of special characters in metadata."""
        metadata = {
            "path": "/var/log/system.log",
            "message": "Error: <critical> failure",
            "value": "50%"
        }
        
        generator.record_recovery_action("test", "test", True, 1.0, metadata=metadata)
        
        assert generator.recovery_actions[0].metadata == metadata


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.fixture
    def generator(self):
        """Fixture to create a fresh generator for each test."""
        return AnomalyReportGenerator()

    def test_complete_anomaly_lifecycle(self, generator):
        """Test complete lifecycle: detect -> record -> recover -> resolve -> report."""
        # 1. Detect and record anomaly
        generator.record_anomaly(
            anomaly_type="power_surge",
            severity="CRITICAL",
            confidence=0.96,
            mission_phase="eclipse_exit",
            telemetry_data={"voltage": 28.5, "current": 12.3},
            explanation="Voltage spike during eclipse exit"
        )
        
        # 2. Attempt recovery
        generator.record_recovery_action(
            action_type="load_shedding",
            anomaly_type="power_surge",
            success=True,
            duration_seconds=3.5,
            metadata={"loads_shed": 2}
        )
        
        # 3. Resolve anomaly
        generator.resolve_anomaly(0)
        
        # 4. Generate report
        report = generator.generate_report()
        
        # Verify complete workflow
        assert report["summary"]["total_anomalies"] == 1
        assert report["summary"]["resolved_anomalies"] == 1
        assert report["summary"]["resolution_rate"] == 1.0
        assert report["summary"]["critical_anomalies"] == 1
        assert report["anomalies"][0]["resolved"] is True
        assert len(report["recovery_actions"]) == 1

    def test_multiple_anomalies_with_actions(self, generator):
        """Test handling multiple concurrent anomalies with various outcomes."""
        # Anomaly 1: Detected and resolved
        generator.record_anomaly("thermal", "HIGH", 0.9, "data_collection", {"temp": 65})
        generator.record_recovery_action("cooling_boost", "thermal", True, 10.0)
        generator.resolve_anomaly(0)
        
        # Anomaly 2: Detected, failed recovery, still unresolved
        generator.record_anomaly("sensor_fault", "MEDIUM", 0.85, "orbit", {"sensor": "S456"})
        generator.record_recovery_action("sensor_reset", "sensor_fault", False, 5.0, 
                                       error_message="Reset failed")
        
        # Anomaly 3: Detected, no action yet
        generator.record_anomaly("comm_degradation", "LOW", 0.7, "downlink", {"snr": 8.2})
        
        report = generator.generate_report()
        
        assert report["summary"]["total_anomalies"] == 3
        assert report["summary"]["resolved_anomalies"] == 1
        assert report["summary"]["resolution_rate"] == pytest.approx(1/3)
        assert len(report["recovery_actions"]) == 2

    def test_export_both_formats(self, generator):
        """Test exporting the same data in both JSON and text formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "report.json")
            text_path = os.path.join(tmpdir, "report.txt")
            
            # Add test data
            generator.record_anomaly("test", "HIGH", 0.92, "test_phase", {"value": 100})
            generator.record_recovery_action("test_action", "test", True, 7.5)
            
            # Export both formats
            generator.export_json(json_path)
            generator.export_text(text_path)
            
            # Verify both files exist and contain data
            assert os.path.exists(json_path)
            assert os.path.exists(text_path)
            
            with open(json_path, 'r') as f:
                json_data = json.load(f)
                assert json_data["summary"]["total_anomalies"] == 1
            
            with open(text_path, 'r') as f:
                text_data = f.read()
                assert "test" in text_data


# Test configuration for pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=report_generator", "--cov-report=term-missing"])