"""High-resolution latency tracking for HIL validation."""

import time
import csv
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict
from pathlib import Path


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

    def __init__(self):
        """Initialize collector with empty measurements."""
        self.measurements: List[LatencyMeasurement] = []
        self._start_time = time.time()
        self._measurement_log: Dict[str, int] = defaultdict(int)

    def record_fault_detection(
        self, sat_id: str, scenario_time_s: float, detection_delay_ms: float
    ) -> None:
        """
        Record fault detection latency.

        Args:
            sat_id: Satellite identifier (e.g., "SAT1")
            scenario_time_s: Simulation time when detected
            detection_delay_ms: Time from fault injection to detection
        """
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            metric_type="fault_detection",
            satellite_id=sat_id,
            duration_ms=detection_delay_ms,
            scenario_time_s=scenario_time_s,
        )
        self.measurements.append(measurement)
        self._measurement_log["fault_detection"] += 1

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
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            metric_type="agent_decision",
            satellite_id=sat_id,
            duration_ms=decision_time_ms,
            scenario_time_s=scenario_time_s,
        )
        self.measurements.append(measurement)
        self._measurement_log["agent_decision"] += 1

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
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            metric_type="recovery_action",
            satellite_id=sat_id,
            duration_ms=action_time_ms,
            scenario_time_s=scenario_time_s,
        )
        self.measurements.append(measurement)
        self._measurement_log["recovery_action"] += 1

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
            sorted_latencies = sorted(latencies)
            count = len(sorted_latencies)

            stats[metric_type] = {
                "count": count,
                "mean_ms": sum(latencies) / count if count > 0 else 0,
                "p50_ms": sorted_latencies[count // 2],
                "p95_ms": sorted_latencies[int(count * 0.95)] if count > 0 else 0,
                "p99_ms": sorted_latencies[int(count * 0.99)] if count > 0 else 0,
                "max_ms": max(latencies),
                "min_ms": min(latencies),
            }

        return stats

    def get_stats_by_satellite(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate statistics per satellite.

        Returns:
            Dict mapping satellite ID to stats
        """
        by_satellite = defaultdict(lambda: defaultdict(list))

        for m in self.measurements:
            by_satellite[m.satellite_id][m.metric_type].append(m.duration_ms)

        stats = {}
        for sat_id, metrics in by_satellite.items():
            stats[sat_id] = {}
            for metric_type, latencies in metrics.items():
                sorted_latencies = sorted(latencies)
                count = len(sorted_latencies)

                stats[sat_id][metric_type] = {
                    "count": count,
                    "mean_ms": sum(latencies) / count if count > 0 else 0,
                    "p50_ms": sorted_latencies[count // 2],
                    "p95_ms": sorted_latencies[int(count * 0.95)] if count > 0 else 0,
                    "max_ms": max(latencies) if latencies else 0,
                }

        return stats

    def export_csv(self, filename: str) -> None:
        """
        Export raw measurements to CSV.

        Args:
            filename: Path to output CSV file
        """
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        with open(filename, "w", newline="") as f:
            fieldnames = [
                "timestamp",
                "metric_type",
                "satellite_id",
                "duration_ms",
                "scenario_time_s",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for m in self.measurements:
                writer.writerow(asdict(m))

    def get_summary(self) -> Dict[str, Any]:
        """
        Get human-readable summary.

        Returns:
            Dict with high-level metrics summary
        """
        if not self.measurements:
            return {"total_measurements": 0, "metrics": {}}

        return {
            "total_measurements": len(self.measurements),
            "measurement_types": dict(self._measurement_log),
            "stats": self.get_stats(),
            "stats_by_satellite": self.get_stats_by_satellite(),
        }

    def reset(self) -> None:
        """Clear all measurements."""
        self.measurements.clear()
        self._measurement_log.clear()

    def __len__(self) -> int:
        """Return number of measurements."""
        return len(self.measurements)
