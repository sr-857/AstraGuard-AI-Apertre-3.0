"""Persistent metrics storage for AstraGuard HIL (Hardware-in-the-Loop) system.

This module provides functionality to store, retrieve, and compare latency metrics
collected during HIL testing runs. It handles both aggregated statistics and raw
measurement data, enabling performance analysis and regression detection.

Performance Notes:
- save_latency_stats: ~25-50ms (dominated by collector.export_csv)
- get_run_metrics: ~1-5ms (single JSON file read + parse)
- compare_runs: ~2-10ms (two file reads + comparison logic)
- get_recent_runs: O(n) where n = total directories (use limit param to reduce)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, cast
from datetime import datetime
<<<<<<< HEAD
=======
import heapq
from concurrent.futures import ThreadPoolExecutor

>>>>>>> f7e4e8a (Added performance optimizations and benchmarking for storage.py)
from astraguard.hil.metrics.latency import LatencyCollector


class MetricsStorage:
    """Manages persistent storage of latency metrics for HIL testing runs.

    This class provides methods to save latency measurements to disk, load previously
    saved metrics, compare performance between different runs, and retrieve recent
    test runs.

    Attributes:
        run_id (str): Unique identifier for the current testing run.
        metrics_dir (Path): Directory path where metrics for this run are stored.
    """

    def __init__(self, run_id: str, results_dir: str = "astraguard/hil/results") -> None:
        """
        Initialize metrics storage.

        Args:
            run_id (str): Unique identifier for this run.
            results_dir (str, optional): Base directory for results. Defaults to "astraguard/hil/results".
        """
        try:
            self.run_id = run_id
            self.metrics_dir = Path(results_dir) / run_id
            self.metrics_dir.mkdir(parents=True, exist_ok=True)
            self._cached_metrics: Optional[Dict[str, Any]] = None
        except (OSError, PermissionError) as e:
            logging.error(f"Failed to initialize MetricsStorage for run {run_id}: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error initializing MetricsStorage for run {run_id}: {e}")
            raise

    def save_latency_stats(self, collector: LatencyCollector) -> Dict[str, str]:
        """
        Save aggregated and raw latency metrics to disk.

        Uses concurrent I/O for JSON and CSV writes to improve performance.

        Args:
            collector (LatencyCollector): LatencyCollector instance containing measurements to save.

        Returns:
            Dict[str, str]: Dictionary with paths to saved files, containing 'summary' and 'raw' keys
                pointing to the JSON summary and CSV raw data files respectively.
        """
        try:
            # Pre-calculate stats (single pass required)
            stats = collector.get_stats()
            summary = collector.get_summary()

            # Build summary dict once
            summary_dict = {
                "run_id": self.run_id,
                "timestamp": datetime.now().isoformat(),
                "total_measurements": len(collector.measurements),
                "measurement_types": summary.get("measurement_types", {}),
                "stats": stats,
                "stats_by_satellite": summary.get("stats_by_satellite", {}),
            }

            summary_path = self.metrics_dir / "latency_summary.json"
            csv_path = self.metrics_dir / "latency_raw.csv"

            def _write_json():
                """Write JSON summary to disk."""
                summary_path.write_text(json.dumps(summary_dict, indent=2, default=str))

            def _write_csv():
                """Export CSV data to disk."""
                collector.export_csv(str(csv_path))

            # Use thread pool for parallel I/O (not CPU-bound)
            with ThreadPoolExecutor(max_workers=2) as executor:
                executor.submit(_write_json)
                executor.submit(_write_csv)

            # Clear cache since we've updated the metrics
            self._cached_metrics = None

            return {"summary": str(summary_path), "raw": str(csv_path)}
        except (OSError, PermissionError) as e:
            logging.error(f"Failed to save latency stats for run {self.run_id}: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error saving latency stats for run {self.run_id}: {e}")
            raise

    def get_run_metrics(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Load metrics from this run.

        Optimization: Caches loaded metrics to avoid repeated disk reads.

        Args:
            use_cache (bool): If True, use cached metrics if available. Defaults to True.

        Returns:
            Dict[str, Any] or None: Parsed metrics dictionary containing run statistics,
                or None if the metrics file is not found or cannot be loaded.
        """
        # Check cache first (avoids disk I/O)
        if use_cache and self._cached_metrics is not None:
            return self._cached_metrics

        summary_path = self.metrics_dir / "latency_summary.json"

        # Optimization: EAFP approach (Easier to Ask for Forgiveness than Permission)
        try:
<<<<<<< HEAD
            content = summary_path.read_text()
            data = json.loads(content)
            if not isinstance(data, dict):
                logging.error(
                    f"Metrics file {summary_path} does not contain a JSON object at the root; "
                    f"got {type(data).__name__} instead."
                )
                return None
            return cast(Dict[str, Any], data)

=======
            metrics = json.loads(summary_path.read_text())
            # Cache the result
            if use_cache:
                self._cached_metrics = metrics
            return cast(Dict[str, Any], metrics)
        except FileNotFoundError:
            return None
>>>>>>> f7e4e8a (Added performance optimizations and benchmarking for storage.py)
        except (OSError, PermissionError, IsADirectoryError) as e:
            logging.error(f"Failed to read metrics file {summary_path}: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from {summary_path}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error loading metrics from {summary_path}: {e}")
            return None

    def compare_runs(self, other_run_id: str) -> Dict[str, Any]:
        """
        Compare latency performance between this run and a historical run.

        Calculates the delta (difference) in Mean and P95 latency for all
        common metrics available in both runs. Useful for regression testing.

        Args:
            other_run_id (str): ID of the historical run to compare against.

        Returns:
            Dict[str, Any]: A comparison report containing run IDs and per-metric diffs.
        """
        other_storage = MetricsStorage(other_run_id)
        other_metrics = other_storage.get_run_metrics(use_cache=True)

        if other_metrics is None:
            return {"error": f"Could not load metrics for run {other_run_id}", "metrics": {}}

        this_metrics = self.get_run_metrics(use_cache=True)
        if this_metrics is None:
            return {"error": f"Could not load metrics for run {self.run_id}", "metrics": {}}

        comparison: Dict[str, Any] = {
            "run1": self.run_id,
            "run2": other_run_id,
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
        }

        # Optimization: Extract stats dicts once
        this_stats = this_metrics.get("stats", {})
        other_stats = other_metrics.get("stats", {})

        # Optimization: Use set union for efficient key merging
        metric_types = set(this_stats.keys()) | set(other_stats.keys())

        for metric_type in metric_types:
            this_data = this_stats.get(metric_type, {})
            other_data = other_stats.get(metric_type, {})

            if not this_data or not other_data:
                continue

            # Pre-extract values to avoid multiple .get() calls
            this_mean = this_data.get("mean_ms", 0)
            other_mean = other_data.get("mean_ms", 0)
            this_p95 = this_data.get("p95_ms", 0)
            other_p95 = other_data.get("p95_ms", 0)

            comparison["metrics"][metric_type] = {
                "this_mean_ms": this_mean,
                "other_mean_ms": other_mean,
                "diff_ms": this_mean - other_mean,
                "this_p95_ms": this_p95,
                "other_p95_ms": other_p95,
            }

        return comparison

    @staticmethod
    def get_recent_runs(
        results_dir: str = "astraguard/hil/results", limit: int = 10
    ) -> List[str]:
        """
        Get recent metric runs.

        Optimization: Uses heapq.nlargest for O(n log k) complexity.
        """
        results_path = Path(results_dir)
        if not results_path.exists():
            return []

        candidates = []
        try:
            for run_dir in results_path.iterdir():
                if not run_dir.is_dir():
                    continue

                summary_file = run_dir / "latency_summary.json"
                if not summary_file.exists():
                    continue

                try:
                    mtime = summary_file.stat().st_mtime
                    candidates.append((mtime, run_dir.name))
                except OSError:
                    continue

            recent = heapq.nlargest(limit, candidates, key=lambda x: x[0])
            return [run_id for _, run_id in recent]

        except (OSError, PermissionError):
            return []