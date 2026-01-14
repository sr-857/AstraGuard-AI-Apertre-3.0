"""Tests for HIL test orchestration and parallel execution."""

import asyncio
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from astraguard.hil.scenarios.orchestrator import (
    ScenarioOrchestrator,
    execute_campaign,
    execute_all_scenarios,
)
from astraguard.hil.scenarios.schema import Scenario, SatelliteConfig, SuccessCriteria

# Import directly from storage module
import astraguard.hil.results.storage as storage_module
ResultStorage = storage_module.ResultStorage


@pytest.fixture
def orchestrator():
    """Create orchestrator instance."""
    return ScenarioOrchestrator(
        scenario_dir="astraguard/hil/scenarios/sample_scenarios"
    )


@pytest.fixture
def results_storage():
    """Create results storage instance."""
    return ResultStorage()


@pytest.fixture
def mock_scenario():
    """Create mock scenario."""
    return Scenario(
        name="test_scenario",
        satellites=[
            SatelliteConfig(sat_id=1, initial_altitude_km=400),
            SatelliteConfig(sat_id=2, initial_altitude_km=400),
        ],
        duration_s=60,
        faults=[],
        success_criteria=SuccessCriteria(
            required_nadir_error_m=100.0,
            required_battery_soc=0.7,
            required_temp_c=50.0,
            required_packet_loss_pct=0.1,
        ),
    )


class TestOrchestratorDiscovery:
    """Test scenario discovery functionality."""

    @pytest.mark.asyncio
    async def test_discover_scenarios(self, orchestrator):
        """Test discovering YAML scenarios in directory."""
        scenarios = await orchestrator.discover_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) >= 2  # At least nominal + cascade_fail
        for path, scenario in scenarios:
            assert isinstance(path, str)
            assert isinstance(scenario, Scenario)
            assert scenario.name

    @pytest.mark.asyncio
    async def test_discover_scenarios_empty_dir(self):
        """Test discovery with empty directory."""
        orchestrator = ScenarioOrchestrator(scenario_dir="/tmp/nonexistent_dir_xyz")
        scenarios = await orchestrator.discover_scenarios()
        assert scenarios == []

    @pytest.mark.asyncio
    async def test_discover_scenarios_invalid_yaml(self, tmp_path):
        """Test discovery skips invalid YAML files."""
        scenario_dir = tmp_path / "scenarios"
        scenario_dir.mkdir()

        # Valid scenario (matching schema requirements)
        valid_yaml = scenario_dir / "valid.yaml"
        valid_yaml.write_text("""name: valid
description: A valid test scenario
satellites:
  - id: sat_1
    sat_id: 1
    initial_altitude_km: 400
duration_s: 60
faults: []
success_criteria:
  required_nadir_error_m: 100
  required_battery_soc: 0.7
  required_temp_c: 50
  required_packet_loss_pct: 0.1
""")

        # Invalid YAML (bad syntax)
        invalid_yaml = scenario_dir / "invalid.yaml"
        invalid_yaml.write_text("this: is: invalid: yaml: syntax:")

        orchestrator = ScenarioOrchestrator(scenario_dir=str(scenario_dir))
        scenarios = await orchestrator.discover_scenarios()

        # Should have at least one scenario (valid one)
        assert len(scenarios) >= 1


class TestOrchestratorExecution:
    """Test campaign execution functionality."""

    @pytest.mark.asyncio
    async def test_run_campaign_single_scenario(self, orchestrator):
        """Test running a single scenario campaign."""
        discovered = await orchestrator.discover_scenarios()
        if not discovered:
            pytest.skip("No scenarios available")

        scenario_paths = [discovered[0][0]]
        results = await orchestrator.run_campaign(
            scenario_paths, parallel=1, speed=100.0, verbose=False
        )

        assert isinstance(results, dict)
        assert len(results) == 1
        for result in results.values():
            assert "success" in result
            assert "execution_time_s" in result
            assert "scenario_name" in result

    @pytest.mark.asyncio
    async def test_run_campaign_multiple_scenarios(self, orchestrator):
        """Test running multiple scenarios in parallel."""
        discovered = await orchestrator.discover_scenarios()
        if len(discovered) < 2:
            pytest.skip("Need at least 2 scenarios")

        scenario_paths = [path for path, _ in discovered[:2]]
        results = await orchestrator.run_campaign(
            scenario_paths, parallel=2, speed=100.0, verbose=False
        )

        assert len(results) == 2
        for result in results.values():
            assert "success" in result

    @pytest.mark.asyncio
    async def test_run_campaign_empty_list(self, orchestrator):
        """Test running campaign with empty scenario list."""
        results = await orchestrator.run_campaign(
            [], parallel=1, speed=10.0, verbose=False
        )
        assert results == {}

    @pytest.mark.asyncio
    async def test_run_all_scenarios(self, orchestrator):
        """Test running all discovered scenarios."""
        summary = await orchestrator.run_all_scenarios(
            parallel=2, speed=100.0, verbose=False
        )

        assert isinstance(summary, dict)
        assert "total_scenarios" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "pass_rate" in summary
        assert "results" in summary
        assert "campaign_id" in summary

        if summary["total_scenarios"] > 0:
            assert 0 <= summary["pass_rate"] <= 1.0

    @pytest.mark.asyncio
    async def test_run_all_scenarios_empty(self):
        """Test run_all_scenarios with no scenarios."""
        orchestrator = ScenarioOrchestrator(
            scenario_dir="/tmp/nonexistent_dir_xyz"
        )
        summary = await orchestrator.run_all_scenarios(parallel=1, speed=10.0)

        assert summary["total_scenarios"] == 0
        assert summary["results"] == {}


class TestParallelExecution:
    """Test parallelism and concurrency control."""

    @pytest.mark.asyncio
    async def test_semaphore_concurrency(self, orchestrator):
        """Test that semaphore limits concurrent executions."""
        discovered = await orchestrator.discover_scenarios()
        if len(discovered) < 3:
            pytest.skip("Need at least 3 scenarios")

        scenario_paths = [path for path, _ in discovered[:3]]

        # Run with max 2 parallel
        results = await orchestrator.run_campaign(
            scenario_paths, parallel=2, speed=100.0, verbose=False
        )

        assert len(results) == 3
        for result in results.values():
            assert "success" in result

    @pytest.mark.asyncio
    async def test_parallel_vs_serial_count(self, orchestrator):
        """Test that parallel and serial runs execute same scenarios."""
        discovered = await orchestrator.discover_scenarios()
        if len(discovered) < 2:
            pytest.skip("Need at least 2 scenarios")

        scenario_paths = [path for path, _ in discovered[:2]]

        # Run with parallelism=1 (effectively serial)
        serial_results = await orchestrator.run_campaign(
            scenario_paths, parallel=1, speed=100.0, verbose=False
        )

        # Run with parallelism=2
        parallel_results = await orchestrator.run_campaign(
            scenario_paths, parallel=2, speed=100.0, verbose=False
        )

        assert len(serial_results) == len(parallel_results)


class TestCampaignResults:
    """Test campaign result aggregation and storage."""

    @pytest.mark.asyncio
    async def test_campaign_summary_structure(self, orchestrator):
        """Test campaign summary has correct structure."""
        summary = await orchestrator.run_all_scenarios(
            parallel=1, speed=100.0, verbose=False
        )

        required_keys = [
            "campaign_id",
            "timestamp",
            "total_scenarios",
            "passed",
            "failed",
            "pass_rate",
            "results",
        ]
        for key in required_keys:
            assert key in summary, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_campaign_pass_rate_calculation(self, orchestrator):
        """Test pass rate calculation is correct."""
        summary = await orchestrator.run_all_scenarios(
            parallel=1, speed=100.0, verbose=False
        )

        if summary["total_scenarios"] > 0:
            expected_rate = summary["passed"] / summary["total_scenarios"]
            assert abs(summary["pass_rate"] - expected_rate) < 0.001

    @pytest.mark.asyncio
    async def test_get_recent_campaigns(self, orchestrator):
        """Test retrieving recent campaign summaries."""
        # Run a campaign to create results
        await orchestrator.run_all_scenarios(
            parallel=1, speed=100.0, verbose=False
        )

        campaigns = orchestrator.get_recent_campaigns(limit=5)
        assert isinstance(campaigns, list)
        if campaigns:
            assert "campaign_id" in campaigns[0]
            assert "pass_rate" in campaigns[0]

    def test_get_campaign_summary(self, orchestrator):
        """Test retrieving specific campaign."""
        # Try to get a non-existent campaign
        result = orchestrator.get_campaign_summary("99999999_999999")
        assert result is None


class TestResultStorageClass:
    """Test result storage functionality."""

    def test_save_scenario_result(self, results_storage):
        """Test saving individual scenario result."""
        result = {
            "success": True,
            "execution_time_s": 5.2,
            "simulated_time_s": 100,
        }

        path = results_storage.save_scenario_result("test_scenario", result)
        assert Path(path).exists()
        assert "test_scenario" in path

        # Load and verify
        saved_data = json.loads(Path(path).read_text())
        assert saved_data["success"] is True
        assert "timestamp" in saved_data

    def test_get_scenario_results(self, results_storage):
        """Test retrieving scenario results."""
        import time
        
        result1 = {"success": True, "execution_time_s": 5.0}
        result2 = {"success": False, "error": "test error"}

        results_storage.save_scenario_result("test_scenario", result1)
        time.sleep(1.1)  # Ensure different timestamp
        results_storage.save_scenario_result("test_scenario", result2)

        results = results_storage.get_scenario_results("test_scenario", limit=10)
        assert len(results) >= 1
        assert all("scenario_name" in r for r in results)

    def test_get_recent_campaigns(self, results_storage):
        """Test retrieving recent campaigns."""
        campaigns = results_storage.get_recent_campaigns(limit=10)
        assert isinstance(campaigns, list)

    def test_get_result_statistics(self, results_storage):
        """Test calculating result statistics."""
        stats = results_storage.get_result_statistics()

        required_keys = [
            "total_campaigns",
            "total_scenarios",
            "avg_pass_rate",
        ]
        for key in required_keys:
            assert key in stats


class TestHighLevelAPIs:
    """Test high-level convenience functions."""

    @pytest.mark.asyncio
    async def test_execute_campaign_function(self):
        """Test execute_campaign convenience function."""
        orchestrator = ScenarioOrchestrator()
        discovered = await orchestrator.discover_scenarios()

        if not discovered:
            pytest.skip("No scenarios available")

        scenario_paths = [discovered[0][0]]
        results = await execute_campaign(
            scenario_paths, parallel=1, speed=100.0
        )

        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_execute_all_scenarios_function(self):
        """Test execute_all_scenarios convenience function."""
        summary = await execute_all_scenarios(parallel=1, speed=100.0)

        assert isinstance(summary, dict)
        assert "campaign_id" in summary
        assert "pass_rate" in summary
