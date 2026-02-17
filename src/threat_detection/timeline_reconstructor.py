"""
Timeline Reconstructor for Security Incidents

Reconstructs chronological timelines of security incidents
from forensics events and evidence.
"""

import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict

from .forensics_logger import ForensicsEvent, ForensicsEventType, get_forensics_logger
from .evidence_collector import EvidenceItem, get_evidence_collector

logger = logging.getLogger(__name__)


class TimelineEntryType(Enum):
    """Types of timeline entries."""
    EVENT = "event"
    EVIDENCE = "evidence"
    STATE_CHANGE = "state_change"
    USER_ACTION = "user_action"
    SYSTEM_ACTION = "system_action"
    ALERT = "alert"
    MITIGATION = "mitigation"


@dataclass
class TimelineEntry:
    """Single entry in an incident timeline."""
    entry_id: str
    entry_type: TimelineEntryType
    timestamp: datetime
    description: str
    source: str
    entity_id: Optional[str] = None
    related_entries: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type.value,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "source": self.source,
            "entity_id": self.entity_id,
            "related_entries": self.related_entries,
            "metadata": self.metadata,
            "evidence_refs": self.evidence_refs
        }


@dataclass
class IncidentTimeline:
    """Complete timeline for a security incident."""
    incident_id: str
    title: str
    description: str
    created_at: datetime
    entries: List[TimelineEntry] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    entities_involved: List[str] = field(default_factory=list)
    timeline_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.get_duration(),
            "entities_involved": self.entities_involved,
            "entry_count": len(self.entries),
            "entries": [e.to_dict() for e in sorted(self.entries, key=lambda x: x.timestamp)],
            "metadata": self.timeline_metadata
        }
    
    def get_duration(self) -> Optional[float]:
        """Get incident duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def add_entry(self, entry: TimelineEntry):
        """Add an entry to the timeline."""
        self.entries.append(entry)
        
        # Update time bounds
        if not self.start_time or entry.timestamp < self.start_time:
            self.start_time = entry.timestamp
        if not self.end_time or entry.timestamp > self.end_time:
            self.end_time = entry.timestamp
        
        # Track entities
        if entry.entity_id and entry.entity_id not in self.entities_involved:
            self.entities_involved.append(entry.entity_id)
    
    def get_entries_in_range(self, 
                           start: datetime, 
                           end: datetime) -> List[TimelineEntry]:
        """Get entries within a time range."""
        return [
            e for e in self.entries
            if start <= e.timestamp <= end
        ]
    
    def get_critical_path(self) -> List[TimelineEntry]:
        """Get critical path entries (most important events)."""
        # Filter for high-priority entries
        critical_types = [
            TimelineEntryType.ALERT,
            TimelineEntryType.MITIGATION,
            TimelineEntryType.STATE_CHANGE
        ]
        
        return [
            e for e in sorted(self.entries, key=lambda x: x.timestamp)
            if e.entry_type in critical_types
        ]


class TimelineReconstructor:
    """
    Timeline reconstruction system for security incidents.
    
    Reconstructs chronological timelines from forensics events,
    evidence, and other security data sources.
    """
    
    def __init__(self):
        self.forensics_logger = get_forensics_logger()
        self.evidence_collector = get_evidence_collector()
        
        # Active timelines
        self.timelines: Dict[str, IncidentTimeline] = {}
        
        # Reconstruction statistics
        self.reconstruction_count = 0
        
    def create_timeline(self,
                       incident_id: str,
                       title: str,
                       description: str,
                       initial_events: Optional[List[ForensicsEvent]] = None) -> IncidentTimeline:
        """
        Create a new incident timeline.
        
        Args:
            incident_id: Unique incident identifier
            title: Incident title
            description: Incident description
            initial_events: Optional initial events to populate
            
        Returns:
            IncidentTimeline
        """
        timeline = IncidentTimeline(
            incident_id=incident_id,
            title=title,
            description=description,
            created_at=datetime.now(),
            entries=[],
            timeline_metadata={
                "reconstructed": False,
                "sources": []
            }
        )
        
        # Add initial events
        if initial_events:
            for event in initial_events:
                entry = self._convert_event_to_entry(event)
                timeline.add_entry(entry)
            
            timeline.timeline_metadata["sources"].append("initial_events")
        
        self.timelines[incident_id] = timeline
        self.reconstruction_count += 1
        
        logger.info(f"Created timeline for incident: {incident_id}")
        
        return timeline
    
    def _convert_event_to_entry(self, event: ForensicsEvent) -> TimelineEntry:
        """Convert a forensics event to timeline entry."""
        entry_type = self._map_event_type(event.event_type)
        
        return TimelineEntry(
            entry_id=f"TL-{event.event_id}",
            entry_type=entry_type,
            timestamp=event.timestamp,
            description=event.description,
            source=event.source,
            entity_id=event.entity_id,
            related_entries=event.related_events,
            metadata=event.raw_data,
            evidence_refs=event.evidence_refs
        )
    
    def _map_event_type(self, event_type: ForensicsEventType) -> TimelineEntryType:
        """Map forensics event type to timeline entry type."""
        mapping = {
            ForensicsEventType.THREAT_DETECTION: TimelineEntryType.ALERT,
            ForensicsEventType.SECURITY_ALERT: TimelineEntryType.ALERT,
            ForensicsEventType.RESPONSE_ACTION: TimelineEntryType.SYSTEM_ACTION,
            ForensicsEventType.MITIGATION_EXECUTED: TimelineEntryType.MITIGATION,
            ForensicsEventType.EVIDENCE_COLLECTED: TimelineEntryType.EVIDENCE,
            ForensicsEventType.USER_ACTION: TimelineEntryType.USER_ACTION,
            ForensicsEventType.SYSTEM_CHANGE: TimelineEntryType.STATE_CHANGE,
            ForensicsEventType.INCIDENT_CREATED: TimelineEntryType.EVENT
        }
        return mapping.get(event_type, TimelineEntryType.EVENT)
    
    async def reconstruct_from_entity(self,
                                      incident_id: str,
                                      entity_id: str,
                                      time_range: Tuple[datetime, datetime]) -> IncidentTimeline:
        """
        Reconstruct timeline from entity activity.
        
        Args:
            incident_id: Incident identifier
            entity_id: Entity to trace
            time_range: (start, end) time range
            
        Returns:
            IncidentTimeline
        """
        start_time, end_time = time_range
        
        # Get forensics events for entity
        events = self.forensics_logger.get_events(
            entity_id=entity_id,
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        
        # Get evidence for entity
        evidence_items = self.evidence_collector.get_evidence_by_entity(entity_id)
        
        # Create timeline
        timeline = self.create_timeline(
            incident_id=incident_id,
            title=f"Incident Timeline: {entity_id}",
            description=f"Reconstructed timeline for entity {entity_id}",
            initial_events=events
        )
        
        # Add evidence entries
        for evidence in evidence_items:
            if start_time <= evidence.collection_time <= end_time:
                entry = TimelineEntry(
                    entry_id=f"TL-EVID-{evidence.evidence_id}",
                    entry_type=TimelineEntryType.EVIDENCE,
                    timestamp=evidence.collection_time,
                    description=f"Evidence collected: {evidence.evidence_type.value}",
                    source=evidence.collector,
                    entity_id=entity_id,
                    evidence_refs=[evidence.evidence_id],
                    metadata=evidence.metadata
                )
                timeline.add_entry(entry)
        
        timeline.timeline_metadata["reconstructed"] = True
        timeline.timeline_metadata["sources"].extend(["forensics_events", "evidence"])
        
        logger.info(f"Reconstructed timeline for {entity_id}: {len(timeline.entries)} entries")
        
        return timeline
    
    async def reconstruct_from_detection(self,
                                        detection_id: str,
                                        time_window_minutes: int = 60) -> Optional[IncidentTimeline]:
        """
        Reconstruct timeline from a threat detection.
        
        Args:
            detection_id: Detection event ID
            time_window_minutes: Time window around detection
            
        Returns:
            IncidentTimeline or None
        """
        # Find the detection event
        detection_events = self.forensics_logger.get_events(
            event_type=ForensicsEventType.THREAT_DETECTION,
            limit=1000
        )
        
        detection_event = None
        for event in detection_events:
            raw_data = event.raw_data or {}
            if raw_data.get("detection_id") == detection_id:
                detection_event = event
                break
        
        if not detection_event:
            logger.warning(f"Detection event not found: {detection_id}")
            return None
        
        # Calculate time range
        center_time = detection_event.timestamp
        time_delta = timedelta(minutes=time_window_minutes)
        start_time = center_time - time_delta
        end_time = center_time + time_delta
        
        # Get related events
        entity_id = detection_event.entity_id
        related_events = self.forensics_logger.get_events(
            entity_id=entity_id,
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        
        # Create timeline
        incident_id = f"INC-{detection_id}"
        timeline = self.create_timeline(
            incident_id=incident_id,
            title=f"Incident from Detection: {detection_id}",
            description=detection_event.description,
            initial_events=related_events
        )
        
        timeline.timeline_metadata["detection_id"] = detection_id
        timeline.timeline_metadata["reconstructed"] = True
        timeline.timeline_metadata["sources"].append("detection_centric")
        
        return timeline
    
    def add_event_to_timeline(self,
                             incident_id: str,
                             event: ForensicsEvent) -> bool:
        """Add a forensics event to an existing timeline."""
        timeline = self.timelines.get(incident_id)
        if not timeline:
            return False
        
        entry = self._convert_event_to_entry(event)
        timeline.add_entry(entry)
        
        return True
    
    def add_manual_entry(self,
                        incident_id: str,
                        entry_type: TimelineEntryType,
                        timestamp: datetime,
                        description: str,
                        source: str = "manual",
                        entity_id: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> Optional[TimelineEntry]:
        """Add a manual entry to a timeline."""
        timeline = self.timelines.get(incident_id)
        if not timeline:
            return None
        
        entry = TimelineEntry(
            entry_id=f"TL-MANUAL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            entry_type=entry_type,
            timestamp=timestamp,
            description=description,
            source=source,
            entity_id=entity_id,
            metadata=metadata or {}
        )
        
        timeline.add_entry(entry)
        
        return entry
    
    def correlate_timelines(self, 
                           timeline_ids: List[str]) -> Dict[str, Any]:
        """
        Correlate multiple timelines to find connections.
        
        Args:
            timeline_ids: List of timeline IDs to correlate
            
        Returns:
            Correlation analysis results
        """
        timelines = [self.timelines.get(tid) for tid in timeline_ids]
        timelines = [t for t in timelines if t]
        
        if len(timelines) < 2:
            return {"error": "Need at least 2 timelines to correlate"}
        
        # Find common entities
        all_entities = set()
        for timeline in timelines:
            all_entities.update(timeline.entities_involved)
        
        # Find temporal overlaps
        time_ranges = []
        for timeline in timelines:
            if timeline.start_time and timeline.end_time:
                time_ranges.append((timeline.start_time, timeline.end_time))
        
        # Find common events
        common_event_types = defaultdict(int)
        for timeline in timelines:
            for entry in timeline.entries:
                key = f"{entry.entry_type.value}:{entry.source}"
                common_event_types[key] += 1
        
        # Find potential causal chains
        causal_chains = []
        for i, timeline1 in enumerate(timelines):
            for timeline2 in timelines[i+1:]:
                # Check if one timeline's end is near another's start
                if (timeline1.end_time and timeline2.start_time and
                    abs((timeline1.end_time - timeline2.start_time).total_seconds()) < 300):
                    causal_chains.append({
                        "from": timeline1.incident_id,
                        "to": timeline2.incident_id,
                        "time_gap_seconds": (timeline2.start_time - timeline1.end_time).total_seconds()
                    })
        
        return {
            "timelines_analyzed": len(timelines),
            "common_entities": list(all_entities),
            "temporal_overlaps": len(time_ranges) > 1,
            "common_event_patterns": dict(common_event_types),
            "potential_causal_chains": causal_chains,
            "correlation_strength": len(all_entities) / max(1, sum(len(t.entities_involved) for t in timelines))
        }
    
    def generate_narrative(self, incident_id: str) -> str:
        """
        Generate human-readable narrative of incident.
        
        Args:
            incident_id: Timeline identifier
            
        Returns:
            Narrative text
        """
        timeline = self.timelines.get(incident_id)
        if not timeline:
            return f"Timeline not found: {incident_id}"
        
        # Sort entries chronologically
        entries = sorted(timeline.entries, key=lambda e: e.timestamp)
        
        lines = [
            f"=== INCIDENT TIMELINE: {timeline.title} ===",
            f"Description: {timeline.description}",
            f"Duration: {timeline.get_duration() or 'Unknown'} seconds",
            f"Entities Involved: {', '.join(timeline.entities_involved)}",
            "",
            "CHRONOLOGY OF EVENTS:",
            ""
        ]
        
        for i, entry in enumerate(entries, 1):
            time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"{i}. [{time_str}] {entry.entry_type.value.upper()}: {entry.description}")
            lines.append(f"   Source: {entry.source}")
            if entry.entity_id:
                lines.append(f"   Entity: {entry.entity_id}")
            lines.append("")
        
        return "\n".join(lines)
    
    def export_timeline(self, 
                       incident_id: str,
                       format: str = "json") -> str:
        """
        Export timeline in various formats.
        
        Args:
            incident_id: Timeline identifier
            format: Export format (json, html, markdown)
            
        Returns:
            Exported timeline string
        """
        timeline = self.timelines.get(incident_id)
        if not timeline:
            raise ValueError(f"Timeline not found: {incident_id}")
        
        if format == "json":
            return json.dumps(timeline.to_dict(), indent=2)
        
        elif format == "html":
            # Generate HTML report
            entries = sorted(timeline.entries, key=lambda e: e.timestamp)
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Incident Timeline: {timeline.title}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .header {{ background: #f0f0f0; padding: 20px; margin-bottom: 20px; }}
                    .entry {{ border-left: 3px solid #007bff; padding: 10px; margin: 10px 0; }}
                    .timestamp {{ color: #666; font-size: 0.9em; }}
                    .type {{ font-weight: bold; color: #007bff; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>{timeline.title}</h1>
                    <p>{timeline.description}</p>
                    <p>Duration: {timeline.get_duration() or 'Unknown'} seconds</p>
                </div>
            """
            
            for entry in entries:
                html += f"""
                <div class="entry">
                    <div class="timestamp">{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</div>
                    <div class="type">{entry.entry_type.value.upper()}</div>
                    <div>{entry.description}</div>
                </div>
                """
            
            html += "</body></html>"
            return html
        
        elif format == "markdown":
            return self.generate_narrative(incident_id)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_timeline(self, incident_id: str) -> Optional[IncidentTimeline]:
        """Get timeline by ID."""
        return self.timelines.get(incident_id)
    
    def list_timelines(self) -> List[Dict[str, Any]]:
        """List all timelines."""
        return [
            {
                "incident_id": t.incident_id,
                "title": t.title,
                "created_at": t.created_at.isoformat(),
                "entry_count": len(t.entries),
                "duration": t.get_duration()
            }
            for t in self.timelines.values()
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get reconstructor statistics."""
        total_entries = sum(len(t.entries) for t in self.timelines.values())
        
        by_type = defaultdict(int)
        for timeline in self.timelines.values():
            for entry in timeline.entries:
                by_type[entry.entry_type.value] += 1
        
        return {
            "total_timelines": len(self.timelines),
            "total_entries": total_entries,
            "reconstructions_performed": self.reconstruction_count,
            "by_entry_type": dict(by_type),
            "average_entries_per_timeline": total_entries / max(1, len(self.timelines))
        }


# Global instance
_timeline_reconstructor: Optional[TimelineReconstructor] = None


def get_timeline_reconstructor() -> TimelineReconstructor:
    """Get global timeline reconstructor instance."""
    global _timeline_reconstructor
    if _timeline_reconstructor is None:
        _timeline_reconstructor = TimelineReconstructor()
    return _timeline_reconstructor
