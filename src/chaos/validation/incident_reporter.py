"""
Incident Reporting for Chaos Testing

Records and reports incidents from failed chaos experiments.
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class IncidentReporter:
    """
    Reports and records incidents from chaos experiments.
    
    Generates incident reports with:
    - Unique incident ID
    - Timestamp
    - Failure type and severity
    - Experiment details
    - System state at time of failure
    """

    def __init__(
        self,
        reports_dir: str = "logs/chaos/incidents",
    ):
        """
        Initialize incident reporter.
        
        Args:
            reports_dir: Directory to store incident reports
        """
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    async def report(
        self,
        experiment_name: str,
        failure_type: str,
        severity: str = "MEDIUM",
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Report an incident from a chaos experiment.
        
        Args:
            experiment_name: Name of the experiment that failed
            failure_type: Type of failure that occurred
            severity: Incident severity (LOW, MEDIUM, HIGH, CRITICAL)
            details: Additional incident details
            
        Returns:
            Incident ID
        """
        incident_id = self._generate_incident_id()
        timestamp = datetime.utcnow()
        
        incident = {
            "incident_id": incident_id,
            "timestamp": timestamp.isoformat(),
            "experiment_name": experiment_name,
            "failure_type": failure_type,
            "severity": severity,
            "status": "open",
            "details": details or {},
            "resolution": None,
            "resolved_at": None,
        }
        
        # Save incident report
        report_path = self.reports_dir / f"{incident_id}.json"
        with open(report_path, "w") as f:
            json.dump(incident, f, indent=2)
        
        logger.warning(
            f"Chaos incident reported: {incident_id} "
            f"(experiment: {experiment_name}, severity: {severity})"
        )
        
        return incident_id

    def resolve(
        self,
        incident_id: str,
        resolution_notes: str = "",
    ) -> bool:
        """
        Mark an incident as resolved.
        
        Args:
            incident_id: ID of incident to resolve
            resolution_notes: Notes about resolution
            
        Returns:
            True if incident was resolved
        """
        report_path = self.reports_dir / f"{incident_id}.json"
        
        if not report_path.exists():
            logger.error(f"Incident not found: {incident_id}")
            return False
        
        try:
            with open(report_path, "r") as f:
                incident = json.load(f)
            
            incident["status"] = "resolved"
            incident["resolution"] = resolution_notes
            incident["resolved_at"] = datetime.utcnow().isoformat()
            
            with open(report_path, "w") as f:
                json.dump(incident, f, indent=2)
            
            logger.info(f"Incident resolved: {incident_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve incident {incident_id}: {e}")
            return False

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Get incident details.
        
        Args:
            incident_id: ID of incident
            
        Returns:
            Incident dictionary or None if not found
        """
        report_path = self.reports_dir / f"{incident_id}.json"
        
        if not report_path.exists():
            return None
        
        try:
            with open(report_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load incident {incident_id}: {e}")
            return None

    def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        experiment_name: Optional[str] = None,
    ) -> list:
        """
        List incidents with optional filtering.
        
        Args:
            status: Filter by status (open, resolved)
            severity: Filter by severity
            experiment_name: Filter by experiment name
            
        Returns:
            List of incident dictionaries
        """
        incidents = []
        
        for report_file in self.reports_dir.glob("*.json"):
            try:
                with open(report_file, "r") as f:
                    incident = json.load(f)
                
                # Apply filters
                if status and incident.get("status") != status:
                    continue
                if severity and incident.get("severity") != severity:
                    continue
                if experiment_name and incident.get("experiment_name") != experiment_name:
                    continue
                
                incidents.append(incident)
                
            except Exception as e:
                logger.warning(f"Failed to load incident from {report_file}: {e}")
        
        # Sort by timestamp (newest first)
        incidents.sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        
        return incidents

    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate summary of all incidents.
        
        Returns:
            Summary dictionary
        """
        all_incidents = self.list_incidents()
        
        open_incidents = [i for i in all_incidents if i["status"] == "open"]
        resolved_incidents = [i for i in all_incidents if i["status"] == "resolved"]
        
        by_severity = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
        }
        
        for incident in all_incidents:
            severity = incident.get("severity", "MEDIUM")
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        by_experiment = {}
        for incident in all_incidents:
            exp_name = incident.get("experiment_name", "unknown")
            by_experiment[exp_name] = by_experiment.get(exp_name, 0) + 1
        
        return {
            "total_incidents": len(all_incidents),
            "open_incidents": len(open_incidents),
            "resolved_incidents": len(resolved_incidents),
            "by_severity": by_severity,
            "by_experiment": by_experiment,
            "recent_open": open_incidents[:5],
        }

    def _generate_incident_id(self) -> str:
        """Generate unique incident ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"CHAOS-{timestamp}-{unique_id}"


# Convenience function
async def report_incident(
    experiment_name: str,
    failure_type: str,
    severity: str = "MEDIUM",
    details: Optional[Dict[str, Any]] = None,
    reports_dir: str = "logs/chaos/incidents",
) -> str:
    """
    Report a chaos incident.
    
    Args:
        experiment_name: Name of experiment
        failure_type: Type of failure
        severity: Incident severity
        details: Additional details
        reports_dir: Directory for reports
        
    Returns:
        Incident ID
    """
    reporter = IncidentReporter(reports_dir)
    return await reporter.report(experiment_name, failure_type, severity, details)
