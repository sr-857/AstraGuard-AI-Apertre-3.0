"""Production HIL test orchestration + parallel execution."""

import asyncio
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from astraguard.hil.scenarios.schema import load_scenario, Scenario
from astraguard.hil.scenarios.parser import ScenarioExecutor


class ScenarioOrchestrator:
    """Manages test campaigns, parallel execution, and result aggregation."""

    def __init__(self, scenario_dir: Optional[str] = None):
        """
        Initialize orchestrator with scenario directory.

        Args:
            scenario_dir: Directory containing YAML scenario files. 
                         If None, uses 'sample_scenarios' in the same package.
        """
        if scenario_dir is None:
            self.scenario_dir = Path(__file__).parent / "sample_scenarios"
        else:
            self.scenario_dir = Path(scenario_dir)
            
        self.results_dir = Path("astraguard/hil/results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._execution_log: List[Dict[str, Any]] = []

    async def discover_scenarios(self) -> List[tuple[str, Scenario]]:
        """
        Auto-discover all *.yaml scenarios in directory.

        Returns:
            List of (file_path, Scenario) tuples
        """
        scenarios = []
        if not self.scenario_dir.exists():
            print(f"[WARN] Scenario directory not found: {self.scenario_dir}")
            return scenarios

        for yaml_file in sorted(self.scenario_dir.glob("*.yaml")):
            try:
                scenario = load_scenario(str(yaml_file))
                scenarios.append((str(yaml_file), scenario))
            except Exception as e:
                print(f"[WARN] Invalid scenario {yaml_file.name}: {e}")

        return scenarios

    async def _run_single_scenario(
        self, scenario_path: str, semaphore: asyncio.Semaphore, speed: float = 10.0
    ) -> tuple[str, Dict[str, Any]]:
        """
        Run a single scenario with semaphore control.

        Args:
            scenario_path: Path to scenario YAML file
            semaphore: Asyncio semaphore for concurrency control
            speed: Playback speed multiplier

        Returns:
            Tuple of (scenario_name, result_dict)
        """
        async with semaphore:
            scenario_name = Path(scenario_path).name
            try:
                scenario = load_scenario(scenario_path)
                executor = ScenarioExecutor(scenario)
                result = await executor.run(speed=speed, verbose=False)

                # Add metadata
                result["scenario_name"] = scenario_name
                result["scenario_path"] = scenario_path
                result["execution_timestamp"] = datetime.now().isoformat()

                self._execution_log.append({
                    "scenario": scenario_name,
                    "success": result["success"],
                    "time": result.get("execution_time_s", 0),
                })

                return scenario_name, result
            except Exception as e:
                error_result = {
                    "scenario_name": scenario_name,
                    "scenario_path": scenario_path,
                    "success": False,
                    "error": str(e),
                    "execution_timestamp": datetime.now().isoformat(),
                }
                self._execution_log.append({
                    "scenario": scenario_name,
                    "success": False,
                    "error": str(e),
                })
                return scenario_name, error_result

    async def run_campaign(
        self,
        scenario_paths: List[str],
        parallel: int = 3,
        speed: float = 10.0,
        verbose: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Execute multiple scenarios with controlled parallelism.

        Args:
            scenario_paths: List of paths to scenario YAML files
            parallel: Maximum concurrent executions
            speed: Playback speed multiplier
            verbose: Print progress updates

        Returns:
            Dict mapping scenario names to execution results
        """
        if not scenario_paths:
            print("[WARN] No scenarios to execute")
            return {}

        if verbose:
            print(f"[CAMPAIGN] Running {len(scenario_paths)} scenarios (max {parallel} parallel)")

        results = {}
        semaphore = asyncio.Semaphore(parallel)

        # Create tasks for all scenarios
        tasks = [
            self._run_single_scenario(path, semaphore, speed) for path in scenario_paths
        ]

        # Execute in parallel
        completed = await asyncio.gather(*tasks)

        # Collect results
        for scenario_name, result in completed:
            results[scenario_name] = result
            if verbose:
                status = "[OK]" if result.get("success") else "[X]"
                print(f"{status} {scenario_name}")

        return results

    async def run_all_scenarios(
        self,
        parallel: int = 3,
        speed: float = 20.0,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute entire test suite (all discovered scenarios).

        Args:
            parallel: Maximum concurrent executions
            speed: Playback speed multiplier
            verbose: Print progress updates

        Returns:
            Campaign summary dict with results
        """
        discovered = await self.discover_scenarios()
        if not discovered:
            print("[ERROR] No scenarios found")
            return {"total_scenarios": 0, "results": {}}

        scenario_paths = [path for path, _ in discovered]

        if verbose:
            print(f"[DISCOVERY] Found {len(scenario_paths)} scenarios")

        # Run campaign
        campaign_results = await self.run_campaign(
            scenario_paths, parallel=parallel, speed=speed, verbose=verbose
        )

        # Calculate statistics
        total = len(campaign_results)
        passed = sum(1 for r in campaign_results.values() if r.get("success"))
        pass_rate = passed / total if total > 0 else 0.0

        # Create campaign summary
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary = {
            "campaign_id": timestamp,
            "timestamp": datetime.now().isoformat(),
            "total_scenarios": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": pass_rate,
            "parallel_limit": parallel,
            "speed_multiplier": speed,
            "results": campaign_results,
        }

        # Save campaign summary
        summary_path = self.results_dir / f"campaign_{timestamp}.json"
        summary_path.write_text(json.dumps(summary, indent=2, default=str))

        if verbose:
            print()
            print(f"[RESULTS] Pass rate: {pass_rate:.0%} ({passed}/{total})")
            print(f"[SAVED] Campaign: {summary_path}")

        return summary

    def get_recent_campaigns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent campaign summaries.

        Args:
            limit: Maximum number of campaigns to retrieve

        Returns:
            List of campaign summary dicts (newest first)
        """
        campaigns = []
        campaign_files = sorted(
            self.results_dir.glob("campaign_*.json"), reverse=True
        )[:limit]

        for campaign_file in campaign_files:
            try:
                campaign_data = json.loads(campaign_file.read_text())
                campaigns.append(campaign_data)
            except Exception as e:
                print(f"[WARN] Failed to load campaign {campaign_file.name}: {e}")

        return campaigns

    def get_campaign_summary(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve specific campaign by ID.

        Args:
            campaign_id: Campaign timestamp ID (YYYYMMDD_HHMMSS)

        Returns:
            Campaign summary dict or None if not found
        """
        campaign_file = self.results_dir / f"campaign_{campaign_id}.json"
        if not campaign_file.exists():
            return None

        try:
            return json.loads(campaign_file.read_text())
        except Exception as e:
            print(f"[ERROR] Failed to load campaign {campaign_id}: {e}")
            return None


async def execute_campaign(
    scenario_paths: List[str],
    parallel: int = 3,
    speed: float = 10.0,
) -> Dict[str, Any]:
    """
    High-level convenience function to run a campaign.

    Args:
        scenario_paths: List of YAML scenario file paths
        parallel: Maximum concurrent executions
        speed: Playback speed multiplier

    Returns:
        Campaign results dict
    """
    orchestrator = ScenarioOrchestrator()
    return await orchestrator.run_campaign(
        scenario_paths, parallel=parallel, speed=speed
    )


async def execute_all_scenarios(
    parallel: int = 3, speed: float = 20.0
) -> Dict[str, Any]:
    """
    High-level convenience function to run all discovered scenarios.

    Args:
        parallel: Maximum concurrent executions
        speed: Playback speed multiplier

    Returns:
        Campaign summary dict
    """
    orchestrator = ScenarioOrchestrator()
    return await orchestrator.run_all_scenarios(parallel=parallel, speed=speed)
