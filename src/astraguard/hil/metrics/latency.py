"""High-resolution latency tracking for HIL validation."""

import time
import csv
import heapq
import logging
import heapq
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LatencyMeasurement:
    """Single latency measurement point."""

    timestamp: float  # Unix timestamp
    metric_type: str  # fault_detection, agent_decision, recovery_action
    satellite_id: str  # SAT1, SAT2, etc.
    duration_ms: float  # Measured latency in milliseconds
    scenario_time_s: float  # Simulation time when measured


class LatencyCollector:
    """Captures high-resolution timing data across swarm (10Hz cadence)."""

    def __init__(self) -> None:
        """Initialize collector with empty measurements."""
        self.measurements: List[LatencyMeasurement] = []
        self._start_time: float = time.time()
        self._measurement_log: Dict[str, int] = defaultdict(int)

    def record_fault_detection(
        self, sat_id: str, scenario_time_s: float, detection_delay_ms: float
    ) -> None:
        """
        Record the latency of a fault detection event.

        Captures the precise time elapsed between the injection of a fault and
        its initial detection by the anomaly system.

        Args:
            sat_id (str): Satellite identifier (e.g., "SAT1").
            scenario_time_s (float): Simulation time (seconds) when detection occurred.
            detection_delay_ms (float): Time elapsed (milliseconds) from fault injection
                                        to detection. Must be non-negative.

        Raises:
            ValueError: If inputs are invalid (empty ID, negative metrics).
        """
        if not isinstance(sat_id, str) or not sat_id.strip():
            raise ValueError(f"Invalid sat_id: must be non-empty string, got {sat_id}")

        if not isinstance(scenario_time_s, (int, float)) or scenario_time_s < 0:
            raise ValueError(f"Invalid scenario_time_s: must be non-negative number, got {scenario_time_s}")

        if not isinstance(detection_delay_ms, (int, float)) or detection_delay_ms < 0:
            raise ValueError(f"Invalid detection_delay_ms: must be non-negative number, got {detection_delay_ms}")

        measurement = LatencyMeasurement(
            timestamp=time.time(),
            metric_type="fault_detection",
            satellite_id=sat_id,
            duration_ms=float(detection_delay_ms),
            scenario_time_s=float(scenario_time_s),
        )
        self.measurements.append(measurement)
        self._measurement_log["fault_detection"] += 1
        logger.debug(f"Recorded fault detection latency: {sat_id}, {detection_delay_ms}ms")

    def record_agent_decision(
        self, sat_id: str, scenario_time_s: float, decision_time_ms: float
    ) -> None:
        """
        Record agent decision latency.

        Args:
            sat_id: Satellite identifier
            scenario_time_s: Simulation time of decision
            decision_time_ms: Time for agent to process and decide
        """
        if not isinstance(sat_id, str) or not sat_id.strip():
            raise ValueError(f"Invalid sat_id: must be non-empty string, got {sat_id}")
        
        if not isinstance(scenario_time_s, (int, float)) or scenario_time_s < 0:
            raise ValueError(f"Invalid scenario_time_s: must be non-negative number, got {scenario_time_s}")
        
        if not isinstance(decision_time_ms, (int, float)) or decision_time_ms < 0:
            raise ValueError(f"Invalid decision_time_ms: must be non-negative number, got {decision_time_ms}")

        measurement = LatencyMeasurement(
            timestamp=time.time(),
            metric_type="agent_decision",
            satellite_id=sat_id,
            duration_ms=float(decision_time_ms),
            scenario_time_s=float(scenario_time_s),
        )
        self.measurements.append(measurement)
        self._measurement_log["agent_decision"] += 1
        logger.debug(f"Recorded agent decision latency: {sat_id}, {decision_time_ms}ms")

    def record_recovery_action(
        self, sat_id: str, scenario_time_s: float, action_time_ms: float
    ) -> None:
        """
        Record recovery action execution latency.

        Args:
            sat_id: Satellite identifier
            scenario_time_s: Simulation time of action
            action_time_ms: Time to execute recovery action
        """
        if not isinstance(sat_id, str) or not sat_id.strip():
            raise ValueError(f"Invalid sat_id: must be non-empty string, got {sat_id}")
        
        if not isinstance(scenario_time_s, (int, float)) or scenario_time_s < 0:
            raise ValueError(f"Invalid scenario_time_s: must be non-negative number, got {scenario_time_s}")
        
        if not isinstance(action_time_ms, (int, float)) or action_time_ms < 0:
            raise ValueError(f"Invalid action_time_ms: must be non-negative number, got {action_time_ms}")

        measurement = LatencyMeasurement(
            timestamp=time.time(),
            metric_type="recovery_action",
            satellite_id=sat_id,
            duration_ms=float(action_time_ms),
            scenario_time_s=float(scenario_time_s),
        )
        self.measurements.append(measurement)
        self._measurement_log["recovery_action"] += 1
        logger.debug(f"Recorded recovery action latency: {sat_id}, {action_time_ms}ms")

    def get_stats(self) -> Dict[str, Any]:
        """
        Calculate aggregate latency statistics.

        Returns:
            Dict with per-metric-type statistics (count, mean, p50, p95, max)
        """
        if not self.measurements:
            return {}

        by_type = defaultdict(list)
        for m in self.measurements:
            by_type[m.metric_type].append(m.duration_ms)

        stats = {}
        for metric_type, latencies in by_type.items():
            if not latencies:
                continue
                
            sorted_latencies = sorted(latencies)
            count = len(sorted_latencies)

            stats[metric_type] = {
                "count": count,
                "mean_ms": sum(latencies) / count,
                "p50_ms": sorted_latencies[count // 2],
                "p95_ms": sorted_latencies[int(count * 0.95)],
                "p99_ms": sorted_latencies[int(count * 0.99)],
                "max_ms": max(latencies),
                "min_ms": min(latencies),
            }

        logger.debug(f"Calculated statistics for {len(stats)} metric types")
        return stats

    def get_stats_by_satellite(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate statistics per satellite.

        Returns:
            Dict mapping satellite ID to stats
        """
        if not self.measurements:
            return {}

        by_satellite: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

        for m in self.measurements:
            by_satellite[m.satellite_id][m.metric_type].append(m.duration_ms)

        stats: Dict[str, Dict[str, Any]] = {}
        for sat_id, metrics in by_satellite.items():
            stats[sat_id] = {}
            for metric_type, latencies in metrics.items():
                if not latencies:
                    continue
                    
                sorted_latencies = sorted(latencies)
                count = len(sorted_latencies)

                stats[sat_id][metric_type] = {
                    "count": count,
                    "mean_ms": sum(latencies) / count,
                    "p50_ms": sorted_latencies[count // 2],
                    "p95_ms": sorted_latencies[int(count * 0.95)],
                    "max_ms": max(latencies),
                }

        logger.debug(f"Calculated statistics for {len(stats)} satellites")
        return stats

    def export_csv(self, filename: str) -> None:
        """
        Export raw measurements to CSV with buffering for better I/O performance.

        Args:
            filename: Path to output CSV file
            
        Raises:
            ValueError: If filename is invalid or no measurements to export
            OSError: If file cannot be created or written (permissions, disk space, etc.)
        """
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError(f"Invalid filename: must be non-empty string, got {filename}")
        
        if not self.measurements:
            raise ValueError("No measurements to export")

        filepath = Path(filename)
        
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(
                f"Failed to create directory for CSV export: {e}",
                extra={
                    "directory": str(filepath.parent),
                    "error_type": "OSError",
                    "operation": "mkdir"
                },
                exc_info=True
            )
            raise

        try:
            with open(filepath, "w", newline="", encoding='utf-8') as f:
                fieldnames = [
                    "timestamp",
                    "metric_type",
                    "satellite_id",
                    "duration_ms",
                    "scenario_time_s",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                # Write in batches for better performance
                batch_size = 1000
                for i in range(0, len(self.measurements), batch_size):
                    batch = self.measurements[i:i + batch_size]
                    for m in batch:
                        writer.writerow(asdict(m))

            logger.info(f"Exported {len(self.measurements)} measurements to {filepath}")
            
        except OSError as e:
            logger.error(
                f"Failed to write CSV file: {e}",
                extra={
                    "filepath": str(filepath),
                    "measurement_count": len(self.measurements),
                    "error_type": "OSError",
                    "operation": "file_write"
                },
                exc_info=True
            )
            raise
        except Exception as e:
            # Catch unexpected errors during CSV serialization
            logger.error(
                f"Unexpected error during CSV export: {e}",
                extra={
                    "filepath": str(filepath),
                    "error_type": type(e).__name__,
                    "operation": "csv_export"
                },
                exc_info=True
            )
            raise

    def get_summary(self) -> Dict[str, Any]:
        """
        Get human-readable summary with optimized single-pass computation.

        Returns:
            Dict with high-level metrics summary
        """
        if not self.measurements:
            return {"total_measurements": 0, "metrics": {}}

        # Single-pass computation for both stats and stats_by_satellite
        by_type = defaultdict(list)
        by_satellite = defaultdict(lambda: defaultdict(list))

        for m in self.measurements:
            by_type[m.metric_type].append(m.duration_ms)
            by_satellite[m.satellite_id][m.metric_type].append(m.duration_ms)

        # Calculate stats by type
        stats = {}
        for metric_type, latencies in by_type.items():
            if not latencies:
                continue
            sorted_latencies = sorted(latencies)
            count = len(sorted_latencies)
            stats[metric_type] = {
                "count": count,
                "mean_ms": sum(latencies) / count,
                "p50_ms": sorted_latencies[count // 2],
                "p95_ms": sorted_latencies[int(count * 0.95)],
                "p99_ms": sorted_latencies[int(count * 0.99)],
                "max_ms": max(latencies),
                "min_ms": min(latencies),
            }

        # Calculate stats by satellite
        stats_by_satellite = {}
        for sat_id, metrics in by_satellite.items():
            stats_by_satellite[sat_id] = {}
            for metric_type, latencies in metrics.items():
                if not latencies:
                    continue
                sorted_latencies = sorted(latencies)
                count = len(sorted_latencies)
                stats_by_satellite[sat_id][metric_type] = {
                    "count": count,
                    "mean_ms": sum(latencies) / count,
                    "p50_ms": sorted_latencies[count // 2],
                    "p95_ms": sorted_latencies[int(count * 0.95)],
                    "max_ms": max(latencies),
                }

        return {
            "total_measurements": len(self.measurements),
            "measurement_types": dict(self._measurement_log),
            "stats": stats,
            "stats_by_satellite": stats_by_satellite,
        }

    def reset(self) -> None:
        """Clear all measurements."""
        self.measurements.clear()
        self._measurement_log.clear()

    def _calculate_percentiles(self, latencies: List[float]) -> Dict[str, float]:
        """
        Calculate percentiles using single sort for better performance.

        Args:
            latencies: List of latency values

        Returns:
            Dict with p50_ms, p95_ms, p99_ms
        """
        if not latencies:
            return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}

        count = len(latencies)

        # Use heapq to find percentiles without full sort
        def nth_smallest(n: int) -> float:
            return heapq.nsmallest(n, latencies)[-1] if n <= count else latencies[-1]

        p50_index = count // 2 + 1
        p95_index = int(count * 0.95) + 1
        p99_index = int(count * 0.99) + 1

        return {
            "p50_ms": sorted_latencies[p50_index],
            "p95_ms": sorted_latencies[p95_index],
            "p99_ms": sorted_latencies[p99_index],
        }

    def __len__(self) -> int:
        """Return number of measurements."""
        return len(self.measurements)
