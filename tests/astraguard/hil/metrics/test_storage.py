"""Tests for MetricsStorage."""

import json
from pathlib import Path
import pytest

from astraguard.hil.metrics.storage import MetricsStorage

# --- Test Data and Mocks ---

# A simple, fake LatencyCollector so we don't need a real one for testing.
class MockLatencyCollector:
    """A mock LatencyCollector for testing purposes."""
    def __init__(self):
        self.measurements = [
            {'type': 'ack', 'latency_ms': 10, 'satellite': 'sat-1'},
            {'type': 'ack', 'latency_ms': 20, 'satellite': 'sat-2'},
            {'type': 'command', 'latency_ms': 50, 'satellite': 'sat-1'},
        ]

    def get_stats(self):
        return {
            "ack": {"mean_ms": 15.0, "p95_ms": 19.0},
            "command": {"mean_ms": 50.0, "p95_ms": 50.0},
        }

    def get_summary(self):
        return {
            "measurement_types": {"ack": 2, "command": 1},
            "stats_by_satellite": {
                "sat-1": {"ack": {"mean_ms": 10.0}, "command": {"mean_ms": 50.0}},
                "sat-2": {"ack": {"mean_ms": 20.0}},
            },
        }

    def export_csv(self, path: str):
        # Just create an empty file to confirm the method was called.
        Path(path).write_text("type,latency_ms,satellite\nack,10,sat-1\n")

@pytest.fixture
def mock_collector():
    """Pytest fixture to provide a MockLatencyCollector instance."""
    return MockLatencyCollector()

# --- Tests ---

def test_metrics_storage_initialization(tmp_path: Path):
    """
    Test that MetricsStorage creates the correct directory when initialized.
    """
    run_id = "test-run-123"
    results_dir = tmp_path / "results"

    # Initialize the storage class
    storage = MetricsStorage(run_id=run_id, results_dir=str(results_dir))

    # Check if the specific run directory was created
    expected_path = results_dir / run_id
    assert expected_path.exists(), "The run directory should be created."
    assert expected_path.is_dir(), "The created path should be a directory."

def test_save_latency_stats(tmp_path: Path, mock_collector: MockLatencyCollector):
    """
    Test that latency stats are saved to JSON and CSV files correctly.
    """
    run_id = "test-run-save"
    results_dir = tmp_path / "results"
    storage = MetricsStorage(run_id=run_id, results_dir=str(results_dir))

    # Action: Save the stats from the mock collector
    saved_paths = storage.save_latency_stats(mock_collector)

    # Verification for JSON file
    summary_path = Path(saved_paths["summary"])
    assert summary_path.exists(), "The summary JSON file should be created."
    
    # Check the content of the JSON file
    data = json.loads(summary_path.read_text())
    assert data["run_id"] == run_id
    assert data["total_measurements"] == 3
    assert data["stats"]["ack"]["mean_ms"] == 15.0

    # Verification for CSV file
    raw_path = Path(saved_paths["raw"])
    assert raw_path.exists(), "The raw CSV file should be created."
    # A simple content check is enough to know it's not empty
    assert "ack,10,sat-1" in raw_path.read_text()


def test_get_run_metrics_success(tmp_path: Path):
    """
    Test loading metrics from a valid, existing summary file.
    """
    run_id = "test-run-get"
    results_dir = tmp_path / "results"
    storage = MetricsStorage(run_id=run_id, results_dir=str(results_dir))
    
    # Setup: Create a fake summary file
    summary_path = results_dir / run_id / "latency_summary.json"
    fake_metrics = {"run_id": run_id, "stats": {"test": {"mean_ms": 100}}}
    summary_path.write_text(json.dumps(fake_metrics))

    # Action: Load the metrics
    metrics = storage.get_run_metrics()

    # Verification
    assert metrics is not None
    assert metrics["run_id"] == run_id
    assert metrics["stats"]["test"]["mean_ms"] == 100

def test_get_run_metrics_not_found(tmp_path: Path):
    storage = MetricsStorage(run_id="non-existent-run", results_dir=str(tmp_path))
    
    # Action and Verification
    assert storage.get_run_metrics() is None


def test_compare_runs_success(tmp_path: Path):
    """
    Test comparing two valid runs.
    """
    results_dir = tmp_path / "results"
    
    # Setup Run 1
    run1_id = "run-1"
    storage1 = MetricsStorage(run_id=run1_id, results_dir=str(results_dir))
    summary1_path = results_dir / run1_id / "latency_summary.json"
    summary1_path.write_text(json.dumps({
        "stats": {"ack": {"mean_ms": 20, "p95_ms": 25}}
    }))

    # Setup Run 2
    run2_id = "run-2"
    storage2 = MetricsStorage(run_id=run2_id, results_dir=str(results_dir))

    summary2_path = results_dir / run2_id / "latency_summary.json"
    summary2_path.write_text(json.dumps({
        "stats": {"ack": {"mean_ms": 15, "p95_ms": 18}}
    }))

    # Action: Compare run 1 to run 2
    comparison = storage1.compare_runs(other_run_id=run2_id)

    # Verification
    assert "error" not in comparison
    assert comparison["run1"] == run1_id
    assert comparison["run2"] == run2_id
    assert comparison["metrics"]["ack"]["diff_ms"] == 5.0 # 20 - 15

def test_compare_runs_other_missing(tmp_path: Path):
    """
    Test comparing to a non-existent run.
    """
    results_dir = tmp_path / "results"
    
    # Setup: Create only one run
    run1_id = "run-1-exists"
    storage1 = MetricsStorage(run_id=run1_id, results_dir=str(results_dir))
    summary1_path = results_dir / run1_id / "latency_summary.json"
    summary1_path.write_text(json.dumps({"stats": {}}))

    # Action: Compare to a run that doesn't exist
    comparison = storage1.compare_runs(other_run_id="run-does-not-exist")
    
    # Verification
    assert "error" in comparison
    assert "Could not load metrics for run run-does-not-exist" in comparison["error"]

