"""Persistent metrics storage."""

import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from astraguard.hil.metrics.latency import LatencyCollector


class MetricsStorage:
    """Manages persistent storage of latency metrics."""

    def __init__(self, run_id: str, results_dir: str = "astraguard/hil/results"):
        """
        Initialize metrics storage.

        Args:
            run_id: Unique identifier for this run
            results_dir: Base directory for results
        """
        self.run_id = run_id
        self.metrics_dir = Path(results_dir) / run_id
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def save_latency_stats(self, collector: LatencyCollector) -> Dict[str, str]:
        """
        Save aggregated and raw latency metrics.

        Args:
            collector: LatencyCollector with measurements

        Returns:
            Dict with paths to saved files
        """
        stats = collector.get_stats()
        summary = collector.get_summary()

        # Summary JSON with all statistics
        summary_dict = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "total_measurements": len(collector.measurements),
            "measurement_types": summary.get("measurement_types", {}),
            "stats": stats,
            "stats_by_satellite": summary.get("stats_by_satellite", {}),
        }

        summary_path = self.metrics_dir / "latency_summary.json"
        summary_path.write_text(json.dumps(summary_dict, indent=2, default=str))

        # Raw CSV for external analysis
        csv_path = self.metrics_dir / "latency_raw.csv"
        collector.export_csv(str(csv_path))

        return {"summary": str(summary_path), "raw": str(csv_path)}

    def get_run_metrics(self) -> Dict[str, Any]:
        """
        Load metrics from this run.

        Returns:
            Parsed metrics dictionary or None if not found
        """
        summary_path = self.metrics_dir / "latency_summary.json"
        if not summary_path.exists():
            return None

        try:
            return json.loads(summary_path.read_text())
        except Exception as e:
            print(f"[ERROR] Failed to load metrics from {summary_path}: {e}")
            return None

    def compare_runs(self, other_run_id: str) -> Dict[str, Any]:
        """
        Compare metrics between two runs.

        Args:
            other_run_id: Other run ID to compare against

        Returns:
            Comparison results
        """
        other_storage = MetricsStorage(other_run_id)
        other_metrics = other_storage.get_run_metrics()

        if other_metrics is None:
            return {"error": f"Could not load metrics for run {other_run_id}", "metrics": {}}

        this_metrics = self.get_run_metrics()
        if this_metrics is None:
            return {"error": f"Could not load metrics for run {self.run_id}", "metrics": {}}

        comparison = {
            "run1": self.run_id,
            "run2": other_run_id,
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
        }

        # Compare each metric type
        this_stats = this_metrics.get("stats", {})
        other_stats = other_metrics.get("stats", {})

        for metric_type in set(list(this_stats.keys()) + list(other_stats.keys())):
            this_data = this_stats.get(metric_type, {})
            other_data = other_stats.get(metric_type, {})

            if not this_data or not other_data:
                continue

            comparison["metrics"][metric_type] = {
                "this_mean_ms": this_data.get("mean_ms", 0),
                "other_mean_ms": other_data.get("mean_ms", 0),
                "diff_ms": this_data.get("mean_ms", 0) - other_data.get("mean_ms", 0),
                "this_p95_ms": this_data.get("p95_ms", 0),
                "other_p95_ms": other_data.get("p95_ms", 0),
            }

        return comparison

    @staticmethod
    def get_recent_runs(
        results_dir: str = "astraguard/hil/results", limit: int = 10
    ) -> list:
        """
        Get recent metric runs.

        Args:
            results_dir: Base results directory
            limit: Maximum number of runs to return

        Returns:
            List of recent run IDs
        """
        results_path = Path(results_dir)
        if not results_path.exists():
            return []

        # Find directories with latency metrics
        runs = []
        for run_dir in sorted(results_path.iterdir(), reverse=True):
            if run_dir.is_dir() and (run_dir / "latency_summary.json").exists():
                runs.append(run_dir.name)
                if len(runs) >= limit:
                    break

        return runs
