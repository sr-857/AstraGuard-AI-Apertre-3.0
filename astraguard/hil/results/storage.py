"""Test result persistence and retrieval."""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime


class ResultStorage:
    """Manages persistent storage and retrieval of test results."""

    def __init__(self, results_dir: str = "astraguard/hil/results"):
        """
        Initialize result storage.

        Args:
            results_dir: Directory for result files
        """
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def save_scenario_result(
        self, scenario_name: str, result: Dict[str, Any]
    ) -> str:
        """
        Save individual scenario result to file.

        Args:
            scenario_name: Name of scenario (without .yaml)
            result: Execution result dict

        Returns:
            Path to saved result file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{scenario_name}_{timestamp}.json"
        filepath = self.results_dir / filename

        # Ensure result has metadata
        result_with_metadata = {
            "scenario_name": scenario_name,
            "timestamp": datetime.now().isoformat(),
            **result,
        }

        filepath.write_text(json.dumps(result_with_metadata, indent=2, default=str))
        return str(filepath)

    def get_scenario_results(
        self, scenario_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent results for a specific scenario.

        Args:
            scenario_name: Name of scenario
            limit: Maximum results to return

        Returns:
            List of result dicts (newest first)
        """
        results = []
        pattern = f"{scenario_name}_*.json"
        result_files = sorted(self.results_dir.glob(pattern), reverse=True)[:limit]

        for result_file in result_files:
            try:
                result_data = json.loads(result_file.read_text())
                results.append(result_data)
            except Exception as e:
                print(f"[WARN] Failed to load result {result_file.name}: {e}")

        return results

    def get_recent_campaigns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent campaign summaries.

        Args:
            limit: Maximum campaigns to return

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

    def get_result_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate statistics across all results.

        Returns:
            Dict with statistics
        """
        campaigns = self.get_recent_campaigns(limit=999)
        if not campaigns:
            return {
                "total_campaigns": 0,
                "total_scenarios": 0,
                "avg_pass_rate": 0.0,
            }

        total_campaigns = len(campaigns)
        total_scenarios = sum(c.get("total_scenarios", 0) for c in campaigns)
        total_passed = sum(c.get("passed", 0) for c in campaigns)
        avg_pass_rate = total_passed / total_scenarios if total_scenarios > 0 else 0.0

        return {
            "total_campaigns": total_campaigns,
            "total_scenarios": total_scenarios,
            "total_passed": total_passed,
            "avg_pass_rate": avg_pass_rate,
        }

    def clear_results(self, older_than_days: int = 30) -> int:
        """
        Remove old result files.

        Args:
            older_than_days: Delete files older than this many days

        Returns:
            Number of files deleted
        """
        from time import time

        cutoff_time = time() - (older_than_days * 86400)
        deleted_count = 0

        for result_file in self.results_dir.glob("*.json"):
            if result_file.stat().st_mtime < cutoff_time:
                result_file.unlink()
                deleted_count += 1

        return deleted_count
