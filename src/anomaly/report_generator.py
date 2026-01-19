"""
Anomaly Report Generator

Generates structured reports for anomaly detection events and recovery actions.
Supports both text and JSON export formats for integration with external tools.

Features:
- Collect anomaly detection events
- Track recovery actions and outcomes
- Generate comprehensive reports
- Export in JSON format for API integration
- Maintain historical data for analysis
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import os

logger = logging.getLogger(__name__)


@dataclass
class AnomalyEvent:
    """Represents a single anomaly detection event."""
    timestamp: datetime
    anomaly_type: str
    severity: str
    confidence: float
    mission_phase: str
    telemetry_data: Dict[str, Any]
    explanation: Optional[str] = None
    recovery_actions: List[Dict[str, Any]] = None
    resolved: bool = False
    resolution_time: Optional[datetime] = None

    def __post_init__(self):
        if self.recovery_actions is None:
            self.recovery_actions = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        data['timestamp'] = self.timestamp.isoformat()
        if self.resolution_time:
            data['resolution_time'] = self.resolution_time.isoformat()
        return data


@dataclass
class RecoveryAction:
    """Represents a recovery action taken in response to an anomaly."""
    timestamp: datetime
    action_type: str
    anomaly_type: str
    success: bool
    duration_seconds: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class AnomalyReportGenerator:
    """
    Generates comprehensive anomaly reports with JSON export capability.

    Collects anomaly events and recovery actions, then generates structured
    reports that can be exported as JSON for integration with external tools.
    """

    def __init__(self, max_history_days: int = 30):
        """
        Initialize the report generator.

        Args:
            max_history_days: Maximum days to keep historical data
        """
        self.anomalies: List[AnomalyEvent] = []
        self.recovery_actions: List[RecoveryAction] = []
        self.max_history_days = max_history_days
        logger.info("Anomaly report generator initialized")

    def record_anomaly(self,
                       anomaly_type: str,
                       severity: str,
                       confidence: float,
                       mission_phase: str,
                       telemetry_data: Dict[str, Any],
                       explanation: Optional[str] = None) -> None:
        """
        Record a new anomaly detection event.

        Args:
            anomaly_type: Type of anomaly detected
            severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
            confidence: Confidence score (0.0 to 1.0)
            mission_phase: Current mission phase
            telemetry_data: Telemetry data that triggered the anomaly
            explanation: Optional explanation of the anomaly
        """
        event = AnomalyEvent(
            timestamp=datetime.now(),
            anomaly_type=anomaly_type,
            severity=severity,
            confidence=confidence,
            mission_phase=mission_phase,
            telemetry_data=telemetry_data,
            explanation=explanation
        )

        self.anomalies.append(event)
        self._cleanup_old_data()

        logger.info(f"Recorded anomaly: {anomaly_type} ({severity}) in {mission_phase} phase")

    def record_recovery_action(self,
                              action_type: str,
                              anomaly_type: str,
                              success: bool,
                              duration_seconds: float,
                              error_message: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a recovery action.

        Args:
            action_type: Type of recovery action
            anomaly_type: Related anomaly type
            success: Whether the action succeeded
            duration_seconds: How long the action took
            error_message: Error message if failed
            metadata: Additional metadata about the action
        """
        action = RecoveryAction(
            timestamp=datetime.now(),
            action_type=action_type,
            anomaly_type=anomaly_type,
            success=success,
            duration_seconds=duration_seconds,
            error_message=error_message,
            metadata=metadata or {}
        )

        self.recovery_actions.append(action)
        self._cleanup_old_data()

        status = "succeeded" if success else "failed"
        logger.info(f"Recorded recovery action: {action_type} for {anomaly_type} ({status})")

    def resolve_anomaly(self, anomaly_index: int) -> None:
        """
        Mark an anomaly as resolved.

        Args:
            anomaly_index: Index of the anomaly in the list
        """
        if 0 <= anomaly_index < len(self.anomalies):
            self.anomalies[anomaly_index].resolved = True
            self.anomalies[anomaly_index].resolution_time = datetime.now()
            logger.info(f"Marked anomaly {anomaly_index} as resolved")

    def generate_report(self,
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Generate a comprehensive anomaly report.

        Args:
            start_time: Start time for the report (default: 24 hours ago)
            end_time: End time for the report (default: now)

        Returns:
            Dictionary containing the complete report
        """
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(hours=24)

        # Filter anomalies and recovery actions by time range
        filtered_anomalies = [
            a for a in self.anomalies
            if start_time <= a.timestamp <= end_time
        ]

        filtered_recoveries = [
            r for r in self.recovery_actions
            if start_time <= r.timestamp <= end_time
        ]

        # Calculate statistics
        total_anomalies = len(filtered_anomalies)
        resolved_anomalies = sum(1 for a in filtered_anomalies if a.resolved)
        critical_anomalies = sum(1 for a in filtered_anomalies if a.severity == "CRITICAL")

        anomaly_types = {}
        for anomaly in filtered_anomalies:
            anomaly_types[anomaly.anomaly_type] = anomaly_types.get(anomaly.anomaly_type, 0) + 1

        recovery_stats = {}
        for recovery in filtered_recoveries:
            recovery_stats[recovery.action_type] = recovery_stats.get(recovery.action_type, 0) + 1

        # Calculate MTTR (Mean Time To Resolution) for resolved anomalies
        resolution_times = []
        for anomaly in filtered_anomalies:
            if anomaly.resolved and anomaly.resolution_time:
                mttr = (anomaly.resolution_time - anomaly.timestamp).total_seconds()
                resolution_times.append(mttr)

        avg_mttr = sum(resolution_times) / len(resolution_times) if resolution_times else None

        report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "generator_version": "1.0.0"
            },
            "summary": {
                "total_anomalies": total_anomalies,
                "resolved_anomalies": resolved_anomalies,
                "resolution_rate": resolved_anomalies / total_anomalies if total_anomalies > 0 else 0,
                "critical_anomalies": critical_anomalies,
                "average_mttr_seconds": avg_mttr,
                "anomaly_types": anomaly_types,
                "recovery_actions": recovery_stats
            },
            "anomalies": [a.to_dict() for a in filtered_anomalies],
            "recovery_actions": [r.to_dict() for r in filtered_recoveries]
        }

        return report

    def export_json(self,
                   file_path: str,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   pretty: bool = True) -> str:
        """
        Export anomaly report as JSON file.

        Args:
            file_path: Path to save the JSON file
            start_time: Start time for the report
            end_time: End time for the report
            pretty: Whether to format JSON with indentation

        Returns:
            The file path where the report was saved
        """
        report = self.generate_report(start_time, end_time)

        # Ensure directory exists (only if there's a directory path)
        dir_path = os.path.dirname(file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(report, f, indent=2, ensure_ascii=False)
            else:
                json.dump(report, f, ensure_ascii=False)

        logger.info(f"Exported anomaly report to {file_path}")
        return file_path

    def export_text(self,
                   file_path: str,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> str:
        """
        Export anomaly report as human-readable text file.

        Args:
            file_path: Path to save the text file
            start_time: Start time for the report
            end_time: End time for the report

        Returns:
            The file path where the report was saved
        """
        report = self.generate_report(start_time, end_time)

        # Ensure directory exists (only if there's a directory path)
        dir_path = os.path.dirname(file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("ASTRA GUARD AI - ANOMALY REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {report['report_metadata']['generated_at']}\n")
            f.write(f"Time Range: {report['report_metadata']['time_range']['start']} to {report['report_metadata']['time_range']['end']}\n\n")

            # Summary section
            f.write("SUMMARY\n")
            f.write("-" * 40 + "\n")
            summary = report['summary']
            f.write(f"Total Anomalies: {summary['total_anomalies']}\n")
            f.write(f"Resolved Anomalies: {summary['resolved_anomalies']}\n")
            f.write(f"Resolution Rate: {summary['resolution_rate']:.1%}\n")
            f.write(f"Critical Anomalies: {summary['critical_anomalies']}\n")
            if summary['average_mttr_seconds']:
                f.write(f"Average MTTR: {summary['average_mttr_seconds']:.1f} seconds\n")
            f.write("\n")

            # Anomaly types
            f.write("Anomaly Types:\n")
            for anomaly_type, count in summary['anomaly_types'].items():
                f.write(f"  {anomaly_type}: {count}\n")
            f.write("\n")

            # Recovery actions
            f.write("Recovery Actions:\n")
            for action_type, count in summary['recovery_actions'].items():
                f.write(f"  {action_type}: {count}\n")
            f.write("\n")

            # Detailed anomalies
            f.write("ANOMALY DETAILS\n")
            f.write("-" * 40 + "\n")
            for i, anomaly in enumerate(report['anomalies'], 1):
                f.write(f"{i}. {anomaly['anomaly_type']} ({anomaly['severity']})\n")
                f.write(f"   Time: {anomaly['timestamp']}\n")
                f.write(f"   Phase: {anomaly['mission_phase']}\n")
                f.write(f"   Confidence: {anomaly['confidence']:.2f}\n")
                f.write(f"   Resolved: {anomaly['resolved']}\n")
                if anomaly['explanation']:
                    f.write(f"   Explanation: {anomaly['explanation']}\n")
                f.write("\n")

        logger.info(f"Exported text anomaly report to {file_path}")
        return file_path

    def _cleanup_old_data(self) -> None:
        """Remove data older than max_history_days."""
        cutoff = datetime.now() - timedelta(days=self.max_history_days)

        self.anomalies = [a for a in self.anomalies if a.timestamp > cutoff]
        self.recovery_actions = [r for r in self.recovery_actions if r.timestamp > cutoff]

    def clear_history(self) -> None:
        """Clear all historical data."""
        self.anomalies.clear()
        self.recovery_actions.clear()
        logger.info("Anomaly report history cleared")


# Global instance for easy access
_report_generator = None

def get_report_generator() -> AnomalyReportGenerator:
    """Get the global anomaly report generator instance."""
    global _report_generator
    if _report_generator is None:
        _report_generator = AnomalyReportGenerator()
    return _report_generator