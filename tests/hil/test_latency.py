"""Unit tests for latency.py module."""

import pytest
import tempfile
import os
from unittest.mock import patch
from src.astraguard.hil.metrics.latency import LatencyCollector, LatencyMeasurement


class TestLatencyMeasurement:
    """Test LatencyMeasurement dataclass."""

    def test_latency_measurement_creation(self):
        """Test creating a LatencyMeasurement instance."""
        measurement = LatencyMeasurement(
            timestamp=1234567890.0,
            metric_type="fault_detection",
            satellite_id="SAT1",
            duration_ms=150.5,
            scenario_time_s=100.0
        )

        assert measurement.timestamp == 1234567890.0
        assert measurement.metric_type == "fault_detection"
        assert measurement.satellite_id == "SAT1"
        assert measurement.duration_ms == 150.5
        assert measurement.scenario_time_s == 100.0

    def test_latency_measurement_asdict(self):
        """Test asdict conversion for CSV export."""
        measurement = LatencyMeasurement(
            timestamp=1234567890.0,
            metric_type="agent_decision",
            satellite_id="SAT2",
            duration_ms=200.0,
            scenario_time_s=150.0
        )

        data = measurement.__dict__
        expected = {
            "timestamp": 1234567890.0,
            "metric_type": "agent_decision",
            "satellite_id": "SAT2",
            "duration_ms": 200.0,
            "scenario_time_s": 150.0
        }
        assert data == expected


class TestLatencyCollector:
    """Test LatencyCollector class."""

    def test_initialization(self):
        """Test collector initialization."""
        collector = LatencyCollector()
        assert collector.measurements == []
        assert collector._measurement_log == {}
        assert len(collector) == 0

    def test_record_fault_detection(self):
        """Test recording fault detection latency."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.5)

        assert len(collector.measurements) == 1
        measurement = collector.measurements[0]
        assert measurement.metric_type == "fault_detection"
        assert measurement.satellite_id == "SAT1"
        assert measurement.duration_ms == 150.5
        assert measurement.scenario_time_s == 100.0
        assert measurement.timestamp == 1234567890.0
        assert collector._measurement_log["fault_detection"] == 1

    def test_record_agent_decision(self):
        """Test recording agent decision latency."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567891.0):
            collector.record_agent_decision("SAT2", 200.0, 75.0)

        assert len(collector.measurements) == 1
        measurement = collector.measurements[0]
        assert measurement.metric_type == "agent_decision"
        assert measurement.satellite_id == "SAT2"
        assert measurement.duration_ms == 75.0
        assert measurement.scenario_time_s == 200.0
        assert measurement.timestamp == 1234567891.0
        assert collector._measurement_log["agent_decision"] == 1

    def test_record_recovery_action(self):
        """Test recording recovery action latency."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567892.0):
            collector.record_recovery_action("SAT3", 300.0, 250.0)

        assert len(collector.measurements) == 1
        measurement = collector.measurements[0]
        assert measurement.metric_type == "recovery_action"
        assert measurement.satellite_id == "SAT3"
        assert measurement.duration_ms == 250.0
        assert measurement.scenario_time_s == 300.0
        assert measurement.timestamp == 1234567892.0
        assert collector._measurement_log["recovery_action"] == 1

    def test_multiple_recordings(self):
        """Test recording multiple measurements."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0, 1234567892.0]):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
            collector.record_agent_decision("SAT1", 200.0, 75.0)
            collector.record_recovery_action("SAT2", 300.0, 250.0)

        assert len(collector.measurements) == 3
        assert collector._measurement_log["fault_detection"] == 1
        assert collector._measurement_log["agent_decision"] == 1
        assert collector._measurement_log["recovery_action"] == 1

    def test_get_stats_empty(self):
        """Test get_stats with no measurements."""
        collector = LatencyCollector()
        stats = collector.get_stats()
        assert stats == {}

    def test_get_stats_single_measurement(self):
        """Test get_stats with single measurement per type."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)

        stats = collector.get_stats()
        assert "fault_detection" in stats
        fd_stats = stats["fault_detection"]
        assert fd_stats["count"] == 1
        assert fd_stats["mean_ms"] == 150.0
        assert fd_stats["p50_ms"] == 150.0
        assert fd_stats["p95_ms"] == 150.0
        assert fd_stats["p99_ms"] == 150.0
        assert fd_stats["max_ms"] == 150.0
        assert fd_stats["min_ms"] == 150.0

    def test_get_stats_multiple_measurements(self):
        """Test get_stats with multiple measurements."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0, 1234567892.0]):
            collector.record_fault_detection("SAT1", 100.0, 100.0)
            collector.record_fault_detection("SAT1", 200.0, 200.0)
            collector.record_fault_detection("SAT1", 300.0, 300.0)

        stats = collector.get_stats()
        fd_stats = stats["fault_detection"]
        assert fd_stats["count"] == 3
        assert fd_stats["mean_ms"] == 200.0
        assert fd_stats["p50_ms"] == 200.0  # sorted: 100, 200, 300 -> median 200
        assert fd_stats["p95_ms"] == 300.0  # 95th percentile
        assert fd_stats["p99_ms"] == 300.0  # 99th percentile
        assert fd_stats["max_ms"] == 300.0
        assert fd_stats["min_ms"] == 100.0

    def test_get_stats_by_satellite_empty(self):
        """Test get_stats_by_satellite with no measurements."""
        collector = LatencyCollector()
        stats = collector.get_stats_by_satellite()
        assert stats == {}

    def test_get_stats_by_satellite_single_satellite(self):
        """Test get_stats_by_satellite with one satellite."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0]):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
            collector.record_agent_decision("SAT1", 200.0, 75.0)

        stats = collector.get_stats_by_satellite()
        assert "SAT1" in stats
        sat1_stats = stats["SAT1"]
        assert "fault_detection" in sat1_stats
        assert "agent_decision" in sat1_stats

        fd_stats = sat1_stats["fault_detection"]
        assert fd_stats["count"] == 1
        assert fd_stats["mean_ms"] == 150.0
        assert fd_stats["p50_ms"] == 150.0
        assert fd_stats["p95_ms"] == 150.0
        assert fd_stats["max_ms"] == 150.0

    def test_get_stats_by_satellite_multiple_satellites(self):
        """Test get_stats_by_satellite with multiple satellites."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0, 1234567892.0]):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
            collector.record_fault_detection("SAT2", 200.0, 200.0)
            collector.record_agent_decision("SAT1", 300.0, 75.0)

        stats = collector.get_stats_by_satellite()
        assert len(stats) == 2
        assert "SAT1" in stats
        assert "SAT2" in stats

        sat1_fd = stats["SAT1"]["fault_detection"]
        assert sat1_fd["count"] == 1
        assert sat1_fd["mean_ms"] == 150.0

        sat2_fd = stats["SAT2"]["fault_detection"]
        assert sat2_fd["count"] == 1
        assert sat2_fd["mean_ms"] == 200.0

    def test_export_csv(self):
        """Test CSV export functionality."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.5)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            collector.export_csv(tmp_path)

            # Verify file exists and has content
            assert os.path.exists(tmp_path)

            with open(tmp_path, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 2  # header + 1 data row
                assert "timestamp,metric_type,satellite_id,duration_ms,scenario_time_s" in lines[0]
                assert "1234567890.0,fault_detection,SAT1,150.5,100.0" in lines[1]

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_get_summary_empty(self):
        """Test get_summary with no measurements."""
        collector = LatencyCollector()
        summary = collector.get_summary()
        expected = {"total_measurements": 0, "metrics": {}}
        assert summary == expected

    def test_get_summary_with_data(self):
        """Test get_summary with measurements."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=[1234567890.0, 1234567891.0]):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
            collector.record_agent_decision("SAT2", 200.0, 75.0)

        summary = collector.get_summary()
        assert summary["total_measurements"] == 2
        assert summary["measurement_types"]["fault_detection"] == 1
        assert summary["measurement_types"]["agent_decision"] == 1
        assert "stats" in summary
        assert "stats_by_satellite" in summary

    def test_reset(self):
        """Test reset functionality."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)

        assert len(collector.measurements) == 1
        assert collector._measurement_log["fault_detection"] == 1

        collector.reset()
        assert len(collector.measurements) == 0
        assert collector._measurement_log == {}

    def test_len(self):
        """Test __len__ method."""
        collector = LatencyCollector()
        assert len(collector) == 0

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)

        assert len(collector) == 1

        collector.reset()
        assert len(collector) == 0

    def test_edge_case_single_measurement_stats_by_satellite(self):
        """Test stats_by_satellite with single measurement per satellite."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)

        stats = collector.get_stats_by_satellite()
        sat1_fd = stats["SAT1"]["fault_detection"]
        assert sat1_fd["count"] == 1
        assert sat1_fd["mean_ms"] == 150.0
        assert sat1_fd["p50_ms"] == 150.0
        assert sat1_fd["p95_ms"] == 150.0
        assert sat1_fd["max_ms"] == 150.0

    def test_edge_case_empty_latencies_in_stats_by_satellite(self):
        """Test stats_by_satellite handles empty latencies gracefully."""
        collector = LatencyCollector()

        # This shouldn't happen in practice, but test robustness
        # Manually add a measurement with duration 0 to test edge
        measurement = LatencyMeasurement(
            timestamp=1234567890.0,
            metric_type="fault_detection",
            satellite_id="SAT1",
            duration_ms=0.0,
            scenario_time_s=100.0
        )
        collector.measurements.append(measurement)

        stats = collector.get_stats_by_satellite()
        sat1_fd = stats["SAT1"]["fault_detection"]
        assert sat1_fd["count"] == 1
        assert sat1_fd["mean_ms"] == 0.0
        assert sat1_fd["max_ms"] == 0.0


class TestLatencyValidation:
    """Test input validation for LatencyCollector."""

    def test_record_fault_detection_empty_sat_id(self):
        """Test record_fault_detection raises ValueError for empty sat_id."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid sat_id: must be non-empty string"):
            collector.record_fault_detection("", 100.0, 150.0)

    def test_record_fault_detection_whitespace_sat_id(self):
        """Test record_fault_detection raises ValueError for whitespace-only sat_id."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid sat_id: must be non-empty string"):
            collector.record_fault_detection("   ", 100.0, 150.0)

    def test_record_fault_detection_none_sat_id(self):
        """Test record_fault_detection raises ValueError for None sat_id."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid sat_id"):
            collector.record_fault_detection(None, 100.0, 150.0)

    def test_record_fault_detection_negative_scenario_time(self):
        """Test record_fault_detection raises ValueError for negative scenario_time_s."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid scenario_time_s: must be non-negative number"):
            collector.record_fault_detection("SAT1", -100.0, 150.0)

    def test_record_fault_detection_negative_detection_delay(self):
        """Test record_fault_detection raises ValueError for negative detection_delay_ms."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid detection_delay_ms: must be non-negative number"):
            collector.record_fault_detection("SAT1", 100.0, -150.0)

    def test_record_fault_detection_invalid_scenario_time_type(self):
        """Test record_fault_detection raises ValueError for non-numeric scenario_time_s."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid scenario_time_s"):
            collector.record_fault_detection("SAT1", "invalid", 150.0)

    def test_record_fault_detection_invalid_delay_type(self):
        """Test record_fault_detection raises ValueError for non-numeric detection_delay_ms."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid detection_delay_ms"):
            collector.record_fault_detection("SAT1", 100.0, "invalid")

    def test_record_agent_decision_empty_sat_id(self):
        """Test record_agent_decision raises ValueError for empty sat_id."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid sat_id: must be non-empty string"):
            collector.record_agent_decision("", 100.0, 75.0)

    def test_record_agent_decision_negative_scenario_time(self):
        """Test record_agent_decision raises ValueError for negative scenario_time_s."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid scenario_time_s: must be non-negative number"):
            collector.record_agent_decision("SAT1", -100.0, 75.0)

    def test_record_agent_decision_negative_decision_time(self):
        """Test record_agent_decision raises ValueError for negative decision_time_ms."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid decision_time_ms: must be non-negative number"):
            collector.record_agent_decision("SAT1", 100.0, -75.0)

    def test_record_recovery_action_empty_sat_id(self):
        """Test record_recovery_action raises ValueError for empty sat_id."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid sat_id: must be non-empty string"):
            collector.record_recovery_action("", 100.0, 250.0)

    def test_record_recovery_action_negative_scenario_time(self):
        """Test record_recovery_action raises ValueError for negative scenario_time_s."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid scenario_time_s: must be non-negative number"):
            collector.record_recovery_action("SAT1", -100.0, 250.0)

    def test_record_recovery_action_negative_action_time(self):
        """Test record_recovery_action raises ValueError for negative action_time_ms."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="Invalid action_time_ms: must be non-negative number"):
            collector.record_recovery_action("SAT1", 100.0, -250.0)

    def test_export_csv_empty_filename(self):
        """Test export_csv raises ValueError for empty filename."""
        collector = LatencyCollector()
        
        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
        
        with pytest.raises(ValueError, match="Invalid filename: must be non-empty string"):
            collector.export_csv("")

    def test_export_csv_whitespace_filename(self):
        """Test export_csv raises ValueError for whitespace-only filename."""
        collector = LatencyCollector()
        
        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 150.0)
        
        with pytest.raises(ValueError, match="Invalid filename: must be non-empty string"):
            collector.export_csv("   ")

    def test_export_csv_no_measurements(self):
        """Test export_csv raises ValueError when no measurements exist."""
        collector = LatencyCollector()
        
        with pytest.raises(ValueError, match="No measurements to export"):
            collector.export_csv("output.csv")


class TestLatencyBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_zero_latency_values(self):
        """Test handling of zero latency values."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 0.0, 0.0)

        assert len(collector.measurements) == 1
        measurement = collector.measurements[0]
        assert measurement.duration_ms == 0.0
        assert measurement.scenario_time_s == 0.0

        stats = collector.get_stats()
        assert stats["fault_detection"]["mean_ms"] == 0.0
        assert stats["fault_detection"]["min_ms"] == 0.0

    def test_very_small_latency_values(self):
        """Test handling of very small latency values (microseconds)."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 0.0001)
            collector.record_agent_decision("SAT1", 200.0, 0.0005)

        assert len(collector.measurements) == 2
        stats = collector.get_stats()
        assert stats["fault_detection"]["mean_ms"] == 0.0001
        assert stats["agent_decision"]["mean_ms"] == 0.0005

    def test_very_large_latency_values(self):
        """Test handling of very large latency values."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            collector.record_fault_detection("SAT1", 100.0, 999999.0)
            collector.record_agent_decision("SAT1", 200.0, 888888.0)

        assert len(collector.measurements) == 2
        stats = collector.get_stats()
        assert stats["fault_detection"]["max_ms"] == 999999.0
        assert stats["agent_decision"]["max_ms"] == 888888.0

    def test_large_dataset_performance(self):
        """Test handling of large dataset (100+ measurements)."""
        collector = LatencyCollector()

        # Add 150 measurements
        with patch('time.time', return_value=1234567890.0):
            for i in range(150):
                collector.record_fault_detection(f"SAT{i % 3 + 1}", float(i), float(i * 10))

        assert len(collector.measurements) == 150
        stats = collector.get_stats()
        assert stats["fault_detection"]["count"] == 150

        # Test stats calculation doesn't fail
        sat_stats = collector.get_stats_by_satellite()
        assert len(sat_stats) == 3  # SAT1, SAT2, SAT3

    def test_percentile_calculation_accuracy(self):
        """Test accurate percentile calculation with known values."""
        collector = LatencyCollector()

        # Add 100 measurements with values 0-99
        with patch('time.time', return_value=1234567890.0):
            for i in range(100):
                collector.record_fault_detection("SAT1", 0.0, float(i))

        stats = collector.get_stats()
        fd_stats = stats["fault_detection"]
        
        # p50 should be around 50, p95 around 95, p99 around 99
        assert fd_stats["p50_ms"] == 50.0
        assert fd_stats["p95_ms"] == 95.0
        assert fd_stats["p99_ms"] == 99.0
        assert fd_stats["min_ms"] == 0.0
        assert fd_stats["max_ms"] == 99.0
        assert fd_stats["mean_ms"] == 49.5  # (0+99)*100/2 / 100

    def test_mixed_metric_types_in_stats(self):
        """Test statistics with mixed metric types."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=list(range(1234567890, 1234567890 + 9))):
            collector.record_fault_detection("SAT1", 100.0, 100.0)
            collector.record_fault_detection("SAT1", 200.0, 200.0)
            collector.record_fault_detection("SAT1", 300.0, 300.0)
            
            collector.record_agent_decision("SAT1", 100.0, 50.0)
            collector.record_agent_decision("SAT1", 200.0, 75.0)
            collector.record_agent_decision("SAT1", 300.0, 100.0)
            
            collector.record_recovery_action("SAT1", 100.0, 250.0)
            collector.record_recovery_action("SAT1", 200.0, 300.0)
            collector.record_recovery_action("SAT1", 300.0, 350.0)

        stats = collector.get_stats()
        assert len(stats) == 3
        assert "fault_detection" in stats
        assert "agent_decision" in stats
        assert "recovery_action" in stats

        assert stats["fault_detection"]["count"] == 3
        assert stats["agent_decision"]["count"] == 3
        assert stats["recovery_action"]["count"] == 3

    def test_calculate_percentiles_direct(self):
        """Test _calculate_percentiles method directly."""
        collector = LatencyCollector()
        
        # Test with known values
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        percentiles = collector._calculate_percentiles(latencies)
        
        assert "p50_ms" in percentiles
        assert "p95_ms" in percentiles
        assert "p99_ms" in percentiles
        assert percentiles["p50_ms"] == 60.0  # 50th percentile
        assert percentiles["p95_ms"] == 100.0  # 95th percentile

    def test_calculate_percentiles_empty_list(self):
        """Test _calculate_percentiles with empty list."""
        collector = LatencyCollector()
        
        percentiles = collector._calculate_percentiles([])
        assert percentiles["p50_ms"] == 0.0
        assert percentiles["p95_ms"] == 0.0
        assert percentiles["p99_ms"] == 0.0

    def test_calculate_percentiles_single_value(self):
        """Test _calculate_percentiles with single value."""
        collector = LatencyCollector()
        
        percentiles = collector._calculate_percentiles([150.0])
        assert percentiles["p50_ms"] == 150.0
        assert percentiles["p95_ms"] == 150.0
        assert percentiles["p99_ms"] == 150.0

    def test_export_csv_large_batch(self):
        """Test CSV export with large batch of measurements."""
        collector = LatencyCollector()

        # Add 2500 measurements to test batch writing (batch_size=1000)
        with patch('time.time', return_value=1234567890.0):
            for i in range(2500):
                collector.record_fault_detection(f"SAT{i % 3 + 1}", float(i), float(i * 10))

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp:
            tmp_path = tmp.name

        try:
            collector.export_csv(tmp_path)
            
            assert os.path.exists(tmp_path)
            
            with open(tmp_path, 'r') as f:
                lines = f.readlines()
                # header + 2500 data rows
                assert len(lines) == 2501
                
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_integer_values_converted_to_float(self):
        """Test that integer inputs are properly converted to float."""
        collector = LatencyCollector()

        with patch('time.time', return_value=1234567890.0):
            # Pass integers instead of floats
            collector.record_fault_detection("SAT1", 100, 150)

        measurement = collector.measurements[0]
        assert isinstance(measurement.duration_ms, float)
        assert isinstance(measurement.scenario_time_s, float)
        assert measurement.duration_ms == 150.0
        assert measurement.scenario_time_s == 100.0

    def test_multiple_satellites_comprehensive(self):
        """Test comprehensive multi-satellite scenario."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=list(range(1234567890, 1234567890 + 12))):
            # SAT1: 4 measurements
            collector.record_fault_detection("SAT1", 100.0, 100.0)
            collector.record_agent_decision("SAT1", 200.0, 50.0)
            collector.record_recovery_action("SAT1", 300.0, 200.0)
            collector.record_fault_detection("SAT1", 400.0, 150.0)
            
            # SAT2: 4 measurements
            collector.record_fault_detection("SAT2", 100.0, 120.0)
            collector.record_agent_decision("SAT2", 200.0, 60.0)
            collector.record_recovery_action("SAT2", 300.0, 220.0)
            collector.record_fault_detection("SAT2", 400.0, 140.0)
            
            # SAT3: 4 measurements
            collector.record_fault_detection("SAT3", 100.0, 110.0)
            collector.record_agent_decision("SAT3", 200.0, 55.0)
            collector.record_recovery_action("SAT3", 300.0, 210.0)
            collector.record_fault_detection("SAT3", 400.0, 130.0)

        assert len(collector.measurements) == 12

        # Check overall stats
        stats = collector.get_stats()
        assert stats["fault_detection"]["count"] == 6
        assert stats["agent_decision"]["count"] == 3
        assert stats["recovery_action"]["count"] == 3

        # Check per-satellite stats
        sat_stats = collector.get_stats_by_satellite()
        assert len(sat_stats) == 3
        assert "SAT1" in sat_stats
        assert "SAT2" in sat_stats
        assert "SAT3" in sat_stats

        # Each satellite should have all three metric types
        for sat_id in ["SAT1", "SAT2", "SAT3"]:
            assert "fault_detection" in sat_stats[sat_id]
            assert "agent_decision" in sat_stats[sat_id]
            assert "recovery_action" in sat_stats[sat_id]

    def test_summary_comprehensive(self):
        """Test get_summary with comprehensive data."""
        collector = LatencyCollector()

        with patch('time.time', side_effect=list(range(1234567890, 1234567890 + 6))):
            collector.record_fault_detection("SAT1", 100.0, 100.0)
            collector.record_fault_detection("SAT2", 200.0, 200.0)
            collector.record_agent_decision("SAT1", 300.0, 50.0)
            collector.record_agent_decision("SAT2", 400.0, 75.0)
            collector.record_recovery_action("SAT1", 500.0, 250.0)
            collector.record_recovery_action("SAT2", 600.0, 300.0)

        summary = collector.get_summary()
        
        assert summary["total_measurements"] == 6
        assert summary["measurement_types"]["fault_detection"] == 2
        assert summary["measurement_types"]["agent_decision"] == 2
        assert summary["measurement_types"]["recovery_action"] == 2
        
        assert "stats" in summary
        assert "stats_by_satellite" in summary
        assert len(summary["stats"]) == 3
        assert len(summary["stats_by_satellite"]) == 2
