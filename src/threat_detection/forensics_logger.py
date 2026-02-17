"""
Forensics Logger for Extended Security Event Logging

Provides comprehensive forensics logging for security events,
threat detections, and incident response activities.
"""

import json
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from collections import deque
import os
from pathlib import Path

from core.error_handling import safe_execute, AstraGuardException

logger = logging.getLogger(__name__)


class ForensicsEventType(Enum):
    """Types of forensics events."""
    THREAT_DETECTION = "threat_detection"
    SECURITY_ALERT = "security_alert"
    INCIDENT_CREATED = "incident_created"
    RESPONSE_ACTION = "response_action"
    MITIGATION_EXECUTED = "mitigation_executed"
    EVIDENCE_COLLECTED = "evidence_collected"
    USER_ACTION = "user_action"
    SYSTEM_CHANGE = "system_change"
    NETWORK_ACTIVITY = "network_activity"
    FILE_ACCESS = "file_access"
    AUTHENTICATION = "authentication"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class ForensicsSeverity(Enum):
    """Severity levels for forensics events."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ForensicsEvent:
    """Forensics event record."""
    event_id: str
    event_type: ForensicsEventType
    severity: ForensicsSeverity
    timestamp: datetime
    source: str
    description: str
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    related_events: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    chain_of_custody: Dict[str, Any] = field(default_factory=dict)
    integrity_hash: Optional[str] = None
    
    def __post_init__(self):
        if not self.integrity_hash:
            self.integrity_hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate integrity hash for the event."""
        data = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "description": self.description,
            "entity_id": self.entity_id,
            "raw_data": self.raw_data
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "description": self.description,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "related_events": self.related_events,
            "evidence_refs": self.evidence_refs,
            "raw_data": self.raw_data,
            "chain_of_custody": self.chain_of_custody,
            "integrity_hash": self.integrity_hash
        }
    
    def verify_integrity(self) -> bool:
        """Verify event integrity."""
        return self.integrity_hash == self._calculate_hash()


class ForensicsLogger:
    """
    Forensics logging system for security events.
    
    Provides tamper-evident logging with integrity verification,
    chain of custody tracking, and compliance reporting.
    """
    
    def __init__(self, log_dir: str = "logs/forensics"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory buffer for recent events
        self.event_buffer: deque = deque(maxlen=10000)
        
        # Chain of custody tracking
        self.custody_chain: Dict[str, Dict[str, Any]] = {}
        
        # Event counters
        self.event_count = 0
        
        # Current log file
        self.current_log_file: Optional[Path] = None
        self._rotate_log()
    
    def _rotate_log(self):
        """Rotate to a new log file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = self.log_dir / f"forensics_{timestamp}.jsonl"
        logger.info(f"Rotated to new forensics log: {self.current_log_file}")
    
    def _get_log_file(self) -> Path:
        """Get current log file, rotating if necessary."""
        # Rotate daily
        if (self.current_log_file and 
            datetime.now().strftime("%Y%m%d") not in self.current_log_file.name):
            self._rotate_log()
        
        return self.current_log_file
    
    def log_event(self,
                 event_type: ForensicsEventType,
                 severity: ForensicsSeverity,
                 source: str,
                 description: str,
                 entity_id: Optional[str] = None,
                 entity_type: Optional[str] = None,
                 raw_data: Optional[Dict[str, Any]] = None,
                 related_events: Optional[List[str]] = None,
                 evidence_refs: Optional[List[str]] = None) -> ForensicsEvent:
        """
        Log a forensics event.
        
        Args:
            event_type: Type of event
            severity: Severity level
            source: Source of the event
            description: Event description
            entity_id: Optional entity identifier
            entity_type: Optional entity type
            raw_data: Optional raw event data
            related_events: Optional list of related event IDs
            evidence_refs: Optional list of evidence references
            
        Returns:
            Created ForensicsEvent
        """
        # Generate event ID
        self.event_count += 1
        timestamp = datetime.now()
        event_id = f"FEVT-{timestamp.strftime('%Y%m%d%H%M%S')}-{self.event_count:06d}"
        
        # Create chain of custody entry
        custody_entry = {
            "collected_by": "forensics_logger",
            "collected_at": timestamp.isoformat(),
            "collection_method": "automated_logging",
            "storage_location": str(self._get_log_file())
        }
        
        # Create event
        event = ForensicsEvent(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            timestamp=timestamp,
            source=source,
            description=description,
            entity_id=entity_id,
            entity_type=entity_type,
            related_events=related_events or [],
            evidence_refs=evidence_refs or [],
            raw_data=raw_data or {},
            chain_of_custody=custody_entry
        )
        
        # Store in buffer
        self.event_buffer.append(event)
        
        # Write to log file
        self._write_event(event)
        
        # Update custody chain
        self.custody_chain[event_id] = custody_entry
        
        logger.debug(f"Logged forensics event: {event_id}")
        
        return event
    
    def _write_event(self, event: ForensicsEvent):
        """Write event to log file."""
        try:
            log_file = self._get_log_file()
            with open(log_file, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to write forensics event: {e}")
    
    def log_threat_detection(self,
                            detection_id: str,
                            threat_type: str,
                            severity: str,
                            description: str,
                            source_data: Dict[str, Any],
                            entity_id: Optional[str] = None) -> ForensicsEvent:
        """Log a threat detection event."""
        severity_enum = ForensicsSeverity(severity.lower())
        
        return self.log_event(
            event_type=ForensicsEventType.THREAT_DETECTION,
            severity=severity_enum,
            source="threat_detection_engine",
            description=description,
            entity_id=entity_id or detection_id,
            entity_type="threat",
            raw_data={
                "detection_id": detection_id,
                "threat_type": threat_type,
                "severity": severity,
                "source_data": source_data
            }
        )
    
    def log_response_action(self,
                           response_id: str,
                           action_name: str,
                           detection_id: str,
                           success: bool,
                           details: Dict[str, Any]) -> ForensicsEvent:
        """Log a response action execution."""
        severity = ForensicsSeverity.INFO if success else ForensicsSeverity.HIGH
        
        return self.log_event(
            event_type=ForensicsEventType.RESPONSE_ACTION,
            severity=severity,
            source="automated_response",
            description=f"Response action '{action_name}' executed: {'success' if success else 'failed'}",
            entity_id=response_id,
            entity_type="response",
            raw_data={
                "response_id": response_id,
                "action_name": action_name,
                "detection_id": detection_id,
                "success": success,
                "details": details
            }
        )
    
    def log_mitigation(self,
                    mitigation_id: str,
                    action_id: str,
                    threat_id: str,
                    success: bool,
                    details: Dict[str, Any]) -> ForensicsEvent:
        """Log a mitigation execution."""
        severity = ForensicsSeverity.INFO if success else ForensicsSeverity.HIGH
        
        return self.log_event(
            event_type=ForensicsEventType.MITIGATION_EXECUTED,
            severity=severity,
            source="mitigation_engine",
            description=f"Mitigation '{action_id}' executed: {'success' if success else 'failed'}",
            entity_id=mitigation_id,
            entity_type="mitigation",
            raw_data={
                "mitigation_id": mitigation_id,
                "action_id": action_id,
                "threat_id": threat_id,
                "success": success,
                "details": details
            }
        )
    
    def log_evidence_collection(self,
                               evidence_id: str,
                               evidence_type: str,
                               source_entity: str,
                               collection_method: str,
                               storage_location: str) -> ForensicsEvent:
        """Log evidence collection."""
        return self.log_event(
            event_type=ForensicsEventType.EVIDENCE_COLLECTED,
            severity=ForensicsSeverity.INFO,
            source="evidence_collector",
            description=f"Evidence collected: {evidence_type} from {source_entity}",
            entity_id=evidence_id,
            entity_type="evidence",
            raw_data={
                "evidence_id": evidence_id,
                "evidence_type": evidence_type,
                "source_entity": source_entity,
                "collection_method": collection_method,
                "storage_location": storage_location
            }
        )
    
    def get_events(self,
                  event_type: Optional[ForensicsEventType] = None,
                  severity: Optional[ForensicsSeverity] = None,
                  entity_id: Optional[str] = None,
                  start_time: Optional[datetime] = None,
                  end_time: Optional[datetime] = None,
                  limit: int = 1000) -> List[ForensicsEvent]:
        """
        Get events with optional filtering.
        
        Returns:
            List of ForensicsEvent objects
        """
        events = list(self.event_buffer)
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        if entity_id:
            events = [e for e in events if e.entity_id == entity_id]
        
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        
        # Sort by timestamp descending
        events.sort(key=lambda e: e.timestamp, reverse=True)
        
        return events[:limit]
    
    def get_event_chain(self, event_id: str) -> List[ForensicsEvent]:
        """Get chain of related events."""
        # Find the root event
        root_event = None
        for event in self.event_buffer:
            if event.event_id == event_id:
                root_event = event
                break
        
        if not root_event:
            return []
        
        # Collect all related events
        chain = [root_event]
        related_ids = set(root_event.related_events)
        
        for event in self.event_buffer:
            if event.event_id in related_ids:
                chain.append(event)
            elif event.event_id == event_id:
                continue
            elif root_event.event_id in event.related_events:
                chain.append(event)
        
        # Sort by timestamp
        chain.sort(key=lambda e: e.timestamp)
        
        return chain
    
    def verify_chain_integrity(self) -> Dict[str, Any]:
        """Verify integrity of all events in buffer."""
        verified = 0
        failed = 0
        failed_events = []
        
        for event in self.event_buffer:
            if event.verify_integrity():
                verified += 1
            else:
                failed += 1
                failed_events.append(event.event_id)
        
        return {
            "total_checked": len(self.event_buffer),
            "verified": verified,
            "failed": failed,
            "failed_events": failed_events,
            "integrity_status": "ok" if failed == 0 else "compromised"
        }
    
    def export_events(self,
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None,
                     format: str = "json") -> str:
        """
        Export events for compliance/reporting.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            format: Export format (json, csv)
            
        Returns:
            Exported data as string
        """
        events = self.get_events(start_time=start_time, end_time=end_time, limit=100000)
        
        if format == "json":
            data = {
                "export_timestamp": datetime.now().isoformat(),
                "event_count": len(events),
                "events": [e.to_dict() for e in events]
            }
            return json.dumps(data, indent=2)
        
        elif format == "csv":
            lines = ["event_id,event_type,severity,timestamp,source,description,entity_id"]
            for e in events:
                lines.append(
                    f"{e.event_id},{e.event_type.value},{e.severity.value},"
                    f"{e.timestamp.isoformat()},{e.source},{e.description},{e.entity_id or ''}"
                )
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get forensics logger statistics."""
        by_type = {}
        by_severity = {}
        
        for event in self.event_buffer:
            etype = event.event_type.value
            severity = event.severity.value
            
            by_type[etype] = by_type.get(etype, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        return {
            "total_events": self.event_count,
            "buffered_events": len(self.event_buffer),
            "by_type": by_type,
            "by_severity": by_severity,
            "log_directory": str(self.log_dir),
            "current_log_file": str(self.current_log_file) if self.current_log_file else None,
            "integrity_status": self.verify_chain_integrity()
        }


# Global instance
_forensics_logger: Optional[ForensicsLogger] = None


def get_forensics_logger() -> ForensicsLogger:
    """Get global forensics logger instance."""
    global _forensics_logger
    if _forensics_logger is None:
        _forensics_logger = ForensicsLogger()
    return _forensics_logger
