"""Comprehensive tests for HIL test result storage functionality."""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open
from typing import Dict, Any

from astraguard.hil.results.storage import ResultStorage


@pytest.fixture
def results_storage():
    """Create temporary storage instance for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield ResultStorage(results_dir=temp_dir)


@pytest.fixture
def sample_result():
    """Sample result data for testing."""
    return {
        "success": True,
        "execution_time_s": 5.2,
        "simulated_time_s": 100,
        "metrics": {"cpu_usage": 45.2}
    }



class TestResultStorageInitialization:
    """Test ResultStorage initialization and setup."""

    def test_init_default_directory(self):
        """Test initialization with default directory."""
        storage = ResultStorage()
        assert storage.results_dir == Path("astraguard/hil/results")

    def test_init_custom_directory(self):
        """Test initialization with custom directory."""
        custom_dir = "custom/test/results"
        storage = ResultStorage(results_dir=custom_dir)
        assert storage.results_dir == Path(custom_dir)

    def test_init_creates_directory(self):
        """Test that initialization creates the results directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = Path(temp_dir) / "test_results"
            assert not results_dir.exists()
            
            storage = ResultStorage(results_dir=str(results_dir))
            assert results_dir.exists()
            assert results_dir.is_dir()

    def test_init_existing_directory(self):
        """Test initialization with existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = Path(temp_dir) / "existing_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            
            storage = ResultStorage(results_dir=str(results_dir))
            assert storage.results_dir == results_dir
            assert results_dir.exists()


class TestSaveScenarioResult:
    """Test saving individual scenario results."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield ResultStorage(results_dir=temp_dir)

    def test_save_scenario_result_basic(self, temp_storage):
        """Test basic scenario result saving."""
        result = {
            "success": True,
            "execution_time_s": 5.2,
            "simulated_time_s": 100,
            "metrics": {"cpu_usage": 45.2}
        }
        
        filepath = temp_storage.save_scenario_result("test_scenario", result)
        
        # Verify file was created
        assert Path(filepath).exists()
        assert "test_scenario" in filepath
        assert filepath.endswith(".json")
        
        # Verify content
        saved_data = json.loads(Path(filepath).read_text())
        assert saved_data["scenario_name"] == "test_scenario"
        assert saved_data["success"] is True
        assert saved_data["execution_time_s"] == 5.2
        assert "timestamp" in saved_data
        assert saved_data["metrics"]["cpu_usage"] == 45.2

    def test_save_scenario_result_with_metadata(self, results_storage, sample_result):
        """Test that saved result includes required metadata."""
        # Modify sample_result for this specific test if needed, or use a new one
        result_with_error = {"success": False, "error": "Test error"}
        
        filepath = results_storage.save_scenario_result("metadata_test", result_with_error)
        saved_data = json.loads(Path(filepath).read_text())
        
        # Check metadata fields
        assert saved_data["scenario_name"] == "metadata_test"
        assert "timestamp" in saved_data
        assert saved_data["success"] is False
        assert saved_data["error"] == "Test error"
        
        # Verify timestamp format
        timestamp = saved_data["timestamp"]
        datetime.fromisoformat(timestamp)  # Should not raise exception

    def test_save_scenario_result_filename_format(self, results_storage, sample_result):
        """Test that filename follows expected format."""
        with patch('astraguard.hil.results.storage.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20240101_120000"
            mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"
            
            filepath = results_storage.save_scenario_result("format_test", sample_result)
            
            expected_filename = "format_test_20240101_120000.json"
            assert Path(filepath).name == expected_filename

    def test_save_scenario_result_complex_data(self, results_storage):
        """Test saving complex nested data structures."""
        result = {
            "success": True,
            "metrics": {
                "satellites": [
                    {"id": 1, "altitude": 400.5, "battery": 0.85},
                    {"id": 2, "altitude": 401.2, "battery": 0.92}
                ],
                "faults": [],
                "performance": {
                    "cpu_usage": [10.2, 15.3, 12.1],
                    "memory_mb": 256.7
                }
            },
            "execution_details": {
                "start_time": "2024-01-01T10:00:00",
                "end_time": "2024-01-01T10:05:00"
            }
        }
        
        filepath = results_storage.save_scenario_result("complex_test", result)
        saved_data = json.loads(Path(filepath).read_text())
        
        # Verify complex data preservation
        assert len(saved_data["metrics"]["satellites"]) == 2
        assert saved_data["metrics"]["satellites"][0]["altitude"] == 400.5
        assert saved_data["metrics"]["performance"]["cpu_usage"] == [10.2, 15.3, 12.1]

    def test_save_scenario_result_special_characters(self, results_storage, sample_result):
        """Test saving scenario with special characters in name."""
        # Test with underscores, hyphens, numbers
        scenario_name = "test_scenario-v2_final"
        filepath = results_storage.save_scenario_result(scenario_name, sample_result)
        
        assert scenario_name in filepath
        assert Path(filepath).exists()

    def test_save_scenario_result_json_serialization(self, results_storage):
        """Test JSON serialization with default=str for complex objects."""
        from datetime import datetime
        
        result = {
            "success": True,
            "timestamp_obj": datetime(2024, 1, 1, 12, 0, 0),
            "path_obj": Path("/test/path")
        }
        
        filepath = results_storage.save_scenario_result("serialization_test", result)
        saved_data = json.loads(Path(filepath).read_text())
        
        # Objects should be converted to strings
        assert isinstance(saved_data["timestamp_obj"], str)
        assert isinstance(saved_data["path_obj"], str)


class TestGetScenarioResults:
    """Test retrieving scenario results."""

    @pytest.fixture
    def temp_storage_with_data(self, results_storage):
        """Create storage with sample data."""
        # Create sample result files
        results = [
            {"success": True, "execution_time_s": 5.0},
            {"success": False, "error": "Test error"},
            {"success": True, "execution_time_s": 3.2}
        ]
        
        for i, result in enumerate(results):
            # Use different timestamps to ensure ordering
            timestamp = f"2024010{i+1}_120000"
            filename = f"test_scenario_{timestamp}.json"
            filepath = results_storage.results_dir / filename
            
            result_with_metadata = {
                "scenario_name": "test_scenario",
                "timestamp": f"2024-01-0{i+1}T12:00:00",
                **result
            }
            
            filepath.write_text(json.dumps(result_with_metadata, indent=2))
        
        yield results_storage

    def test_get_scenario_results_basic(self, temp_storage_with_data):
        """Test basic scenario result retrieval."""
        results = temp_storage_with_data.get_scenario_results("test_scenario")
        
        assert isinstance(results, list)
        assert len(results) == 3
        
        # Verify all results have required fields
        for result in results:
            assert "scenario_name" in result
            assert "timestamp" in result
            assert "success" in result

    def test_get_scenario_results_ordering(self, temp_storage_with_data):
        """Test that results are returned in newest-first order."""
        results = temp_storage_with_data.get_scenario_results("test_scenario")
        
        # Should be ordered by filename (newest first)
        timestamps = [result["timestamp"] for result in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_scenario_results_limit(self, temp_storage_with_data):
        """Test limit parameter."""
        results = temp_storage_with_data.get_scenario_results("test_scenario", limit=2)
        
        assert len(results) == 2
        
        # Should get the 2 newest results
        all_results = temp_storage_with_data.get_scenario_results("test_scenario", limit=10)
        assert results == all_results[:2]

    def test_get_scenario_results_nonexistent(self, results_storage):
        """Test retrieving results for non-existent scenario."""
        results = results_storage.get_scenario_results("nonexistent_scenario")
        
        assert results == []

    def test_get_scenario_results_corrupted_file(self, results_storage):
        """Test handling of corrupted JSON files."""
        # Create a corrupted JSON file
        corrupted_file = results_storage.results_dir / "test_scenario_20240101_120000.json"
        corrupted_file.write_text("invalid json content {")
        
        # Create a valid file
        valid_file = results_storage.results_dir / "test_scenario_20240102_120000.json"
        valid_data = {
            "scenario_name": "test_scenario",
            "timestamp": "2024-01-02T12:00:00",
            "success": True
        }
        valid_file.write_text(json.dumps(valid_data))
        
        # Should skip corrupted file and return valid ones
        results = results_storage.get_scenario_results("test_scenario")
        assert len(results) == 1
        assert results[0]["success"] is True

    def test_get_scenario_results_empty_directory(self, results_storage):
        """Test retrieving results from empty directory."""
        results = results_storage.get_scenario_results("any_scenario")
        
        assert results == []


class TestGetRecentCampaigns:
    """Test retrieving recent campaign summaries."""

    @pytest.fixture
    def temp_storage_with_campaigns(self, results_storage):
        """Create storage with sample campaign data."""
        # Create sample campaign files
        campaigns = [
            {
                "campaign_id": "20240101_120000",
                "timestamp": "2024-01-01T12:00:00",
                "total_scenarios": 5,
                "passed": 4,
                "failed": 1,
                "pass_rate": 0.8
            },
            {
                "campaign_id": "20240102_120000", 
                "timestamp": "2024-01-02T12:00:00",
                "total_scenarios": 3,
                "passed": 3,
                "failed": 0,
                "pass_rate": 1.0
            }
        ]
        
        for campaign in campaigns:
            filename = f"campaign_{campaign['campaign_id']}.json"
            filepath = results_storage.results_dir / filename
            filepath.write_text(json.dumps(campaign, indent=2))
        
        yield results_storage

    def test_get_recent_campaigns_basic(self, temp_storage_with_campaigns):
        """Test basic campaign retrieval."""
        campaigns = temp_storage_with_campaigns.get_recent_campaigns()
        
        assert isinstance(campaigns, list)
        assert len(campaigns) == 2
        
        # Verify campaign structure
        for campaign in campaigns:
            assert "campaign_id" in campaign
            assert "timestamp" in campaign
            assert "total_scenarios" in campaign
            assert "pass_rate" in campaign

    def test_get_recent_campaigns_ordering(self, temp_storage_with_campaigns):
        """Test that campaigns are returned in newest-first order."""
        campaigns = temp_storage_with_campaigns.get_recent_campaigns()
        
        # Should be ordered by filename (newest first)
        campaign_ids = [c["campaign_id"] for c in campaigns]
        assert campaign_ids == sorted(campaign_ids, reverse=True)

    def test_get_recent_campaigns_limit(self, temp_storage_with_campaigns):
        """Test limit parameter."""
        campaigns = temp_storage_with_campaigns.get_recent_campaigns(limit=1)
        
        assert len(campaigns) == 1
        # Should get the newest campaign
        assert campaigns[0]["campaign_id"] == "20240102_120000"

    def test_get_recent_campaigns_empty(self, results_storage):
        """Test retrieving campaigns from empty directory."""
        campaigns = results_storage.get_recent_campaigns()
        
        assert campaigns == []

    def test_get_recent_campaigns_corrupted_file(self, results_storage):
        """Test handling of corrupted campaign files."""
        # Create corrupted file
        corrupted_file = results_storage.results_dir / "campaign_20240101_120000.json"
        corrupted_file.write_text("invalid json")
        
        # Create valid file
        valid_file = results_storage.results_dir / "campaign_20240102_120000.json"
        valid_data = {
            "campaign_id": "20240102_120000",
            "total_scenarios": 1,
            "passed": 1
        }
        valid_file.write_text(json.dumps(valid_data))
        
        campaigns = results_storage.get_recent_campaigns()
        assert len(campaigns) == 1
        assert campaigns[0]["campaign_id"] == "20240102_120000"


class TestGetCampaignSummary:
    """Test retrieving specific campaign summaries."""

    @pytest.fixture
    def temp_storage_with_campaign(self, results_storage):
        """Create storage with a specific campaign."""
        campaign_data = {
            "campaign_id": "20240101_120000",
            "timestamp": "2024-01-01T12:00:00",
            "total_scenarios": 5,
            "passed": 4,
            "failed": 1,
            "pass_rate": 0.8,
            "results": {"scenario1": {"success": True}}
        }
        
        filename = "campaign_20240101_120000.json"
        filepath = results_storage.results_dir / filename
        filepath.write_text(json.dumps(campaign_data, indent=2))
        
        yield results_storage, campaign_data

    def test_get_campaign_summary_existing(self, temp_storage_with_campaign):
        """Test retrieving existing campaign summary."""
        storage, expected_data = temp_storage_with_campaign
        
        result = storage.get_campaign_summary("20240101_120000")
        
        assert result is not None
        assert result["campaign_id"] == "20240101_120000"
        assert result["total_scenarios"] == 5
        assert result["pass_rate"] == 0.8
        assert "results" in result

    def test_get_campaign_summary_nonexistent(self, temp_storage_with_campaign):
        """Test retrieving non-existent campaign."""
        storage, _ = temp_storage_with_campaign
        
        result = storage.get_campaign_summary("99999999_999999")
        
        assert result is None

    def test_get_campaign_summary_corrupted_file(self, results_storage):
        """Test handling corrupted campaign file."""
        # Create corrupted file
        corrupted_file = results_storage.results_dir / "campaign_20240101_120000.json"
        corrupted_file.write_text("invalid json content")
        
        result = results_storage.get_campaign_summary("20240101_120000")
        
        assert result is None


class TestGetResultStatistics:
    """Test aggregate statistics calculation."""

    @pytest.fixture
    def temp_storage_with_stats_data(self, results_storage):
        """Create storage with data for statistics testing."""
        # Create multiple campaign files with different stats
        campaigns = [
            {
                "campaign_id": "20240101_120000",
                "total_scenarios": 5,
                "passed": 4,
                "failed": 1
            },
            {
                "campaign_id": "20240102_120000",
                "total_scenarios": 3,
                "passed": 3,
                "failed": 0
            },
            {
                "campaign_id": "20240103_120000",
                "total_scenarios": 2,
                "passed": 1,
                "failed": 1
            }
        ]
        
        for campaign in campaigns:
            filename = f"campaign_{campaign['campaign_id']}.json"
            filepath = results_storage.results_dir / filename
            filepath.write_text(json.dumps(campaign, indent=2))
        
        yield results_storage

    def test_get_result_statistics_basic(self, temp_storage_with_stats_data):
        """Test basic statistics calculation."""
        stats = temp_storage_with_stats_data.get_result_statistics()
        
        # Verify structure
        required_keys = ["total_campaigns", "total_scenarios", "total_passed", "avg_pass_rate"]
        for key in required_keys:
            assert key in stats
        
        # Verify calculations
        assert stats["total_campaigns"] == 3
        assert stats["total_scenarios"] == 10  # 5 + 3 + 2
        assert stats["total_passed"] == 8      # 4 + 3 + 1
        assert abs(stats["avg_pass_rate"] - 0.8) < 0.001  # 8/10 = 0.8

    def test_get_result_statistics_empty(self, results_storage):
        """Test statistics with no campaigns."""
        stats = results_storage.get_result_statistics()
        
        assert stats["total_campaigns"] == 0
        assert stats["total_scenarios"] == 0
        assert stats["avg_pass_rate"] == 0.0

    def test_get_result_statistics_missing_fields(self, results_storage):
        """Test statistics with campaigns missing some fields."""
        # Create campaign with missing fields
        campaign = {"campaign_id": "20240101_120000"}  # Missing stats fields
        filename = "campaign_20240101_120000.json"
        filepath = results_storage.results_dir / filename
        filepath.write_text(json.dumps(campaign))
        
        stats = results_storage.get_result_statistics()
        
        assert stats["total_campaigns"] == 1
        assert stats["total_scenarios"] == 0  # Default to 0 for missing field
        assert stats["avg_pass_rate"] == 0.0


class TestClearResults:
    """Test clearing old result files."""

    def test_clear_results_basic(self, results_storage):
        """Test basic result clearing functionality."""
        # Create some test files
        old_file = results_storage.results_dir / "old_result.json"
        recent_file = results_storage.results_dir / "recent_result.json"
        
        old_file.write_text('{"test": "old"}')
        recent_file.write_text('{"test": "recent"}')
        
        # Mock file modification times
        import time
        current_time = time.time()
        old_time = current_time - (35 * 86400)  # 35 days ago
        recent_time = current_time - (5 * 86400)   # 5 days ago
        
        # Set modification times
        import os
        os.utime(old_file, (old_time, old_time))
        os.utime(recent_file, (recent_time, recent_time))
        
        # Clear files older than 30 days
        deleted_count = results_storage.clear_results(older_than_days=30)
        
        assert deleted_count == 1
        assert not old_file.exists()
        assert recent_file.exists()

    def test_clear_results_no_files(self, results_storage):
        """Test clearing results when no files exist."""
        deleted_count = results_storage.clear_results(older_than_days=30)
        
        assert deleted_count == 0

    def test_clear_results_all_recent(self, results_storage):
        """Test clearing when all files are recent."""
        # Create recent files
        for i in range(3):
            test_file = results_storage.results_dir / f"recent_{i}.json"
            test_file.write_text(f'{{"test": {i}}}')
        
        deleted_count = results_storage.clear_results(older_than_days=30)
        
        assert deleted_count == 0
        assert len(list(results_storage.results_dir.glob("*.json"))) == 3

    def test_clear_results_custom_age(self, results_storage):
        """Test clearing with custom age threshold."""
        test_file = results_storage.results_dir / "test_result.json"
        test_file.write_text('{"test": "data"}')
        
        # Mock file to be 5 days old
        import time, os
        old_time = time.time() - (5 * 86400)
        os.utime(test_file, (old_time, old_time))
        
        # Clear files older than 3 days
        deleted_count = results_storage.clear_results(older_than_days=3)
        
        assert deleted_count == 1
        assert not test_file.exists()


class TestIntegrationScenarios:
    """Test integration scenarios and edge cases."""

    def test_full_workflow_integration(self, results_storage):
        """Test complete workflow from save to retrieve to clear."""
        # Save multiple scenario results with delays to ensure unique timestamps
        import time
        scenarios = ["scenario_a", "scenario_b", "scenario_a"]
        results = [
            {"success": True, "time": 5.0},
            {"success": False, "error": "test"},
            {"success": True, "time": 3.0}
        ]
        
        saved_paths = []
        for i, (scenario, result) in enumerate(zip(scenarios, results)):
            if i > 0:
                time.sleep(1.1)  # Ensure different timestamps (seconds precision)
            path = results_storage.save_scenario_result(scenario, result)
            saved_paths.append(path)
        
        # Verify all files were created
        assert all(Path(path).exists() for path in saved_paths)
        
        # Retrieve results for scenario_a (should have 2 results)
        scenario_a_results = results_storage.get_scenario_results("scenario_a")
        assert len(scenario_a_results) == 2
        
        # Retrieve results for scenario_b (should have 1 result)
        scenario_b_results = results_storage.get_scenario_results("scenario_b")
        assert len(scenario_b_results) == 1
        
        # Get statistics
        stats = results_storage.get_result_statistics()
        assert stats["total_campaigns"] == 0  # No campaigns created yet
        
        # Clear results (all should be recent, so none deleted)
        deleted = results_storage.clear_results(older_than_days=1)
        assert deleted == 0

    def test_concurrent_access_simulation(self, results_storage):
        """Test behavior under simulated concurrent access."""
        # Simulate multiple saves happening with sufficient delays
        import time
        results = []
        for i in range(5):
            result = {"success": True, "iteration": i}
            path = results_storage.save_scenario_result("concurrent_test", result)
            results.append(path)
            time.sleep(1.1)  # Ensure different timestamps (seconds precision)
        
        # Verify all files were created with unique names
        assert len(set(results)) == 5  # All paths should be unique
        assert all(Path(path).exists() for path in results)
        
        # Retrieve and verify ordering
        retrieved = results_storage.get_scenario_results("concurrent_test")
        assert len(retrieved) == 5
        
        # Should be in reverse chronological order
        iterations = [r["iteration"] for r in retrieved]
        assert iterations == [4, 3, 2, 1, 0]

    def test_large_result_handling(self, results_storage):
        """Test handling of large result data."""
        # Create a large result with nested data
        large_result = {
            "success": True,
            "telemetry_data": [
                {"timestamp": i, "value": i * 0.1, "status": "ok"}
                for i in range(1000)
            ],
            "satellite_states": {
                f"sat_{i}": {
                    "position": [i, i+1, i+2],
                    "velocity": [i*0.1, i*0.2, i*0.3],
                    "attitude": [i*0.01, i*0.02, i*0.03, 1.0]
                }
                for i in range(50)
            }
        }
        
        # Save and retrieve large result
        path = results_storage.save_scenario_result("large_test", large_result)
        assert Path(path).exists()
        
        # Verify file size is reasonable (should be substantial)
        file_size = Path(path).stat().st_size
        assert file_size > 1000
        
        # Retrieve and verify data integrity
        retrieved = results_storage.get_scenario_results("large_test")
        assert len(retrieved) == 1
        assert len(retrieved[0]["telemetry_data"]) == 1000
        assert len(retrieved[0]["satellite_states"]) == 50

    def test_error_recovery_scenarios(self):
        """Test error recovery and graceful degradation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with read-only directory (simulate permission error)
            readonly_dir = Path(temp_dir) / "readonly"
            readonly_dir.mkdir()
            
            # Create a file, then make directory read-only
            test_file = readonly_dir / "test.json"
            test_file.write_text('{"test": "data"}')
            
            try:
                # Windows might not support chmod 0444 as strictly as Linux regarding directory listings
                # but we can try mocking the storage failure instead if this is flaky
                readonly_dir.chmod(0o444) 
                
                readonly_storage = ResultStorage(results_dir=str(readonly_dir))
                
                # Should handle read-only gracefully
                # If get_scenario_results fails to write/read it should log and return something safe or raise specific error
                # Based on code: it catches specific errors and logs warning
                results = readonly_storage.get_scenario_results("test")
                # Ensure it didn't crash
                
            finally:
                # Restore permissions for cleanup
                readonly_dir.chmod(0o777)