"""
Threat Hunter for Proactive Threat Detection

Implements proactive threat hunting capabilities to discover
advanced persistent threats and hidden attack patterns.
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import deque
import uuid

from .advanced_anomaly_detector import ThreatDetection, ThreatSeverity, ThreatCategory
from .behavioral_analyzer import BehavioralAnalyzer, get_behavioral_analyzer
from .ioc_manager import IoCManager, get_ioc_manager
from core.error_handling import safe_execute, AstraGuardException

logger = logging.getLogger(__name__)


class HuntStatus(Enum):
    """Status of a threat hunt."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class HuntType(Enum):
    """Types of threat hunts."""
    HYPOTHESIS_DRIVEN = "hypothesis_driven"
    INDICATOR_DRIVEN = "indicator_driven"
    ENTITY_DRIVEN = "entity_driven"
    TTP_DRIVEN = "ttp_driven"
    ANOMALY_DRIVEN = "anomaly_driven"


@dataclass
class HuntResult:
    """Result of a threat hunt."""
    finding_id: str
    hunt_id: str
    timestamp: datetime
    title: str
    description: str
    severity: ThreatSeverity
    confidence: float
    affected_entities: List[str]
    evidence: List[str]
    recommended_actions: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding_id": self.finding_id,
            "hunt_id": self.hunt_id,
            "timestamp": self.timestamp.isoformat(),
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "affected_entities": self.affected_entities,
            "evidence": self.evidence,
            "recommended_actions": self.recommended_actions,
            "metadata": self.metadata
        }


@dataclass
class ThreatHunt:
    """Threat hunt definition and execution tracking."""
    hunt_id: str
    name: str
    description: str
    hunt_type: HuntType
    status: HuntStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str = "system"
    query_params: Dict[str, Any] = field(default_factory=dict)
    scope: Dict[str, Any] = field(default_factory=dict)
    results: List[HuntResult] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hunt_id": self.hunt_id,
            "name": self.name,
            "description": self.description,
            "hunt_type": self.hunt_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_by": self.created_by,
            "query_params": self.query_params,
            "scope": self.scope,
            "result_count": len(self.results)
        }


class ThreatHunter:
    """
    Proactive threat hunting system.
    
    Implements various hunting methodologies to discover
    hidden threats and advanced persistent threats.
    """
    
    def __init__(self):
        self.behavioral_analyzer = get_behavioral_analyzer()
        self.ioc_manager = get_ioc_manager()
        
        # Active and completed hunts
        self.hunts: Dict[str, ThreatHunt] = {}
        self.hunt_history: deque = deque(maxlen=1000)
        
        # Hunt templates
        self.hunt_templates: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.hunts_completed = 0
        self.findings_count = 0
        
        # Register default templates
        self._register_default_templates()
    
    def _register_default_templates(self):
        """Register default hunt templates."""
        self.hunt_templates = {
            "lateral_movement": {
                "name": "Lateral Movement Detection",
                "description": "Hunt for signs of lateral movement across systems",
                "hunt_type": HuntType.TTP_DRIVEN,
                "query_params": {
                    "patterns": ["network_scan", "connection_spike", "internal_port_access"],
                    "time_range_hours": 24
                }
            },
            "persistence_mechanisms": {
                "name": "Persistence Mechanisms",
                "description": "Hunt for persistence mechanisms and backdoors",
                "hunt_type": HuntType.TTP_DRIVEN,
                "query_params": {
                    "patterns": ["startup_changes", "scheduled_tasks", "registry_modifications"],
                    "time_range_hours": 168  # 1 week
                }
            },
            "data_exfiltration": {
                "name": "Data Exfiltration Patterns",
                "description": "Hunt for data exfiltration activities",
                "hunt_type": HuntType.ANOMALY_DRIVEN,
                "query_params": {
                    "patterns": ["large_outbound_transfer", "unusual_destination", "off_hours_access"],
                    "time_range_hours": 72
                }
            },
            "privilege_escalation": {
                "name": "Privilege Escalation Attempts",
                "description": "Hunt for privilege escalation attempts",
                "hunt_type": HuntType.TTP_DRIVEN,
                "query_params": {
                    "patterns": ["sudo_usage", "permission_change", "admin_access_attempt"],
                    "time_range_hours": 24
                }
            },
            "compromised_credentials": {
                "name": "Compromised Credentials",
                "description": "Hunt for signs of compromised credentials",
                "hunt_type": HuntType.ENTITY_DRIVEN,
                "query_params": {
                    "patterns": ["auth_failure_burst", "unusual_login_time", "geo_anomaly"],
                    "time_range_hours": 48
                }
            }
        }
    
    async def create_hunt(self,
                         name: str,
                         description: str,
                         hunt_type: HuntType,
                         query_params: Dict[str, Any],
                         scope: Optional[Dict[str, Any]] = None,
                         created_by: str = "system") -> ThreatHunt:
        """
        Create a new threat hunt.
        
        Args:
            name: Hunt name
            description: Hunt description
            hunt_type: Type of hunt
            query_params: Hunt query parameters
            scope: Hunt scope (entities, time range, etc.)
            created_by: Creator identifier
            
        Returns:
            ThreatHunt
        """
        hunt_id = f"HUNT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
        
        hunt = ThreatHunt(
            hunt_id=hunt_id,
            name=name,
            description=description,
            hunt_type=hunt_type,
            status=HuntStatus.PLANNED,
            created_at=datetime.now(),
            created_by=created_by,
            query_params=query_params,
            scope=scope or {}
        )
        
        self.hunts[hunt_id] = hunt
        logger.info(f"Created threat hunt: {hunt_id} - {name}")
        
        return hunt
    
    async def execute_hunt(self, hunt_id: str) -> ThreatHunt:
        """
        Execute a threat hunt.
        
        Args:
            hunt_id: Hunt identifier
            
        Returns:
            Updated ThreatHunt
        """
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            raise AstraGuardException(
                f"Hunt not found: {hunt_id}",
                component="threat_hunter"
            )
        
        if hunt.status == HuntStatus.IN_PROGRESS:
            raise AstraGuardException(
                f"Hunt already in progress: {hunt_id}",
                component="threat_hunter"
            )
        
        hunt.status = HuntStatus.IN_PROGRESS
        hunt.started_at = datetime.now()
        
        logger.info(f"Executing threat hunt: {hunt_id}")
        
        try:
            # Execute based on hunt type
            if hunt.hunt_type == HuntType.HYPOTHESIS_DRIVEN:
                results = await self._execute_hypothesis_hunt(hunt)
            elif hunt.hunt_type == HuntType.INDICATOR_DRIVEN:
                results = await self._execute_indicator_hunt(hunt)
            elif hunt.hunt_type == HuntType.ENTITY_DRIVEN:
                results = await self._execute_entity_hunt(hunt)
            elif hunt.hunt_type == HuntType.TTP_DRIVEN:
                results = await self._execute_ttp_hunt(hunt)
            elif hunt.hunt_type == HuntType.ANOMALY_DRIVEN:
                results = await self._execute_anomaly_hunt(hunt)
            else:
                results = []
            
            hunt.results = results
            hunt.status = HuntStatus.COMPLETED
            hunt.completed_at = datetime.now()
            
            self.hunts_completed += 1
            self.findings_count += len(results)
            
            logger.info(f"Hunt completed: {hunt_id} - {len(results)} findings")
            
        except Exception as e:
            hunt.status = HuntStatus.CANCELLED
            logger.error(f"Hunt failed: {hunt_id} - {e}")
            raise
        
        finally:
            self.hunt_history.append(hunt)
        
        return hunt
    
    async def _execute_hypothesis_hunt(self, hunt: ThreatHunt) -> List[HuntResult]:
        """Execute hypothesis-driven hunt."""
        results = []
        
        # Get hypothesis from query params
        hypothesis = hunt.query_params.get("hypothesis", "")
        indicators = hunt.query_params.get("indicators", [])
        
        logger.info(f"Testing hypothesis: {hypothesis}")
        
        # Search for supporting evidence
        for indicator in indicators:
            # Check IoCs
            ioc_results = self._search_iocs(indicator)
            
            if ioc_results:
                result = HuntResult(
                    finding_id=f"FIND-{str(uuid.uuid4())[:8]}",
                    hunt_id=hunt.hunt_id,
                    timestamp=datetime.now(),
                    title=f"Hypothesis supported: {hypothesis}",
                    description=f"Found evidence supporting hypothesis: {indicator}",
                    severity=ThreatSeverity.HIGH,
                    confidence=0.7,
                    affected_entities=ioc_results,
                    evidence=[indicator],
                    recommended_actions=["Investigate affected entities", "Collect forensic evidence"]
                )
                results.append(result)
        
        return results
    
    async def _execute_indicator_hunt(self, hunt: ThreatHunt) -> List[HuntResult]:
        """Execute indicator-driven hunt."""
        results = []
        
        indicators = hunt.query_params.get("indicators", [])
        
        for indicator in indicators:
            # Search across data sources
            matches = self._search_indicator(indicator)
            
            for match in matches:
                result = HuntResult(
                    finding_id=f"FIND-{str(uuid.uuid4())[:8]}",
                    hunt_id=hunt.hunt_id,
                    timestamp=datetime.now(),
                    title=f"Indicator match: {indicator}",
                    description=f"Found match for indicator in {match['source']}",
                    severity=ThreatSeverity.MEDIUM,
                    confidence=match.get("confidence", 0.6),
                    affected_entities=[match.get("entity", "unknown")],
                    evidence=[indicator, match.get("context", "")],
                    recommended_actions=["Verify indicator", "Check for related IoCs"]
                )
                results.append(result)
        
        return results
    
    async def _execute_entity_hunt(self, hunt: ThreatHunt) -> List[HuntResult]:
        """Execute entity-driven hunt."""
        results = []
        
        entities = hunt.query_params.get("entities", [])
        patterns = hunt.query_params.get("patterns", [])
        
        for entity_id in entities:
            # Analyze entity behavior
            analysis = await self.behavioral_analyzer.analyze_entity(
                entity_id=entity_id,
                entity_type="user",  # Could be parameterized
                current_data={"entity_id": entity_id, "patterns": patterns}
            )
            
            if analysis.result_type.value in ["suspicious", "anomalous"]:
                result = HuntResult(
                    finding_id=f"FIND-{str(uuid.uuid4())[:8]}",
                    hunt_id=hunt.hunt_id,
                    timestamp=datetime.now(),
                    title=f"Suspicious entity behavior: {entity_id}",
                    description=f"Entity shows {analysis.result_type.value} behavior patterns",
                    severity=ThreatSeverity.HIGH if analysis.result_type.value == "anomalous" else ThreatSeverity.MEDIUM,
                    confidence=analysis.risk_score,
                    affected_entities=[entity_id],
                    evidence=analysis.pattern_matches.get("suspicious", []) + analysis.pattern_matches.get("anomalous", []),
                    recommended_actions=["Investigate entity activity", "Review access logs"]
                )
                results.append(result)
        
        return results
    
    async def _execute_ttp_hunt(self, hunt: ThreatHunt) -> List[HuntResult]:
        """Execute TTP (Tactics, Techniques, Procedures) driven hunt."""
        results = []
        
        ttps = hunt.query_params.get("ttps", [])
        time_range = hunt.query_params.get("time_range_hours", 24)
        
        for ttp in ttps:
            # Search for TTP patterns
            pattern_matches = self._search_ttp_patterns(ttp, time_range)
            
            for match in pattern_matches:
                result = HuntResult(
                    finding_id=f"FIND-{str(uuid.uuid4())[:8]}",
                    hunt_id=hunt.hunt_id,
                    timestamp=datetime.now(),
                    title=f"TTP match: {ttp}",
                    description=f"Detected technique: {match['description']}",
                    severity=ThreatSeverity.HIGH,
                    confidence=match.get("confidence", 0.7),
                    affected_entities=match.get("entities", []),
                    evidence=match.get("indicators", []),
                    recommended_actions=["Map to MITRE ATT&CK", "Check for related techniques"]
                )
                results.append(result)
        
        return results
    
    async def _execute_anomaly_hunt(self, hunt: ThreatHunt) -> List[HuntResult]:
        """Execute anomaly-driven hunt."""
        results = []
        
        anomaly_types = hunt.query_params.get("anomaly_types", [])
        threshold = hunt.query_params.get("threshold", 0.8)
        
        # Search for anomalies
        anomalies = self._search_anomalies(anomaly_types, threshold)
        
        for anomaly in anomalies:
            result = HuntResult(
                finding_id=f"FIND-{str(uuid.uuid4())[:8]}",
                hunt_id=hunt.hunt_id,
                timestamp=datetime.now(),
                title=f"Anomaly detected: {anomaly['type']}",
                description=anomaly.get("description", "Unusual pattern detected"),
                severity=ThreatSeverity.MEDIUM,
                confidence=anomaly.get("score", 0.6),
                affected_entities=anomaly.get("entities", []),
                evidence=[anomaly.get("details", {})],
                recommended_actions=["Investigate anomaly", "Check baseline deviations"]
            )
            results.append(result)
        
        return results
    
    def _search_iocs(self, indicator: str) -> List[str]:
        """Search for IoC matches."""
        # Check in IoC manager
        ioc_record = self.ioc_manager.find_ioc("ip_address", indicator)
        if ioc_record:
            return [ioc_record.ioc_id]
        
        # Additional IoC type searches could be added
        return []
    
    def _search_indicator(self, indicator: str) -> List[Dict[str, Any]]:
        """Search for indicator across data sources."""
        matches = []
        
        # Search in logs (placeholder implementation)
        # In production: Query SIEM, log aggregation, etc.
        
        return matches
    
    def _search_ttp_patterns(self, ttp: str, time_range_hours: int) -> List[Dict[str, Any]]:
        """Search for TTP patterns."""
        matches = []
        
        # Pattern matching logic (placeholder)
        # In production: Use behavioral analysis, log correlation, etc.
        
        return matches
    
    def _search_anomalies(self, 
                         anomaly_types: List[str], 
                         threshold: float) -> List[Dict[str, Any]]:
        """Search for anomalies."""
        anomalies = []
        
        # Anomaly detection logic (placeholder)
        # In production: Query anomaly detection results
        
        return anomalies
    
    def get_hunt(self, hunt_id: str) -> Optional[ThreatHunt]:
        """Get hunt by ID."""
        return self.hunts.get(hunt_id)
    
    def get_hunt_results(self, hunt_id: str) -> List[HuntResult]:
        """Get results for a hunt."""
        hunt = self.hunts.get(hunt_id)
        if hunt:
            return hunt.results
        return []
    
    def list_hunts(self, 
                  status: Optional[HuntStatus] = None,
                  hunt_type: Optional[HuntType] = None) -> List[ThreatHunt]:
        """List hunts with optional filtering."""
        hunts = list(self.hunts.values())
        
        if status:
            hunts = [h for h in hunts if h.status == status]
        
        if hunt_type:
            hunts = [h for h in hunts if h.hunt_type == hunt_type]
        
        # Sort by created_at descending
        hunts.sort(key=lambda h: h.created_at, reverse=True)
        
        return hunts
    
    def get_hunt_templates(self) -> Dict[str, Any]:
        """Get available hunt templates."""
        return self.hunt_templates
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hunter statistics."""
        by_status = {}
        by_type = {}
        
        for hunt in self.hunts.values():
            status = hunt.status.value
            htype = hunt.hunt_type.value
            
            by_status[status] = by_status.get(status, 0) + 1
            by_type[htype] = by_type.get(htype, 0) + 1
        
        return {
            "total_hunts": len(self.hunts),
            "hunts_completed": self.hunts_completed,
            "total_findings": self.findings_count,
            "by_status": by_status,
            "by_type": by_type,
            "templates_available": len(self.hunt_templates)
        }


# Global instance
_threat_hunter: Optional[ThreatHunter] = None


def get_threat_hunter() -> ThreatHunter:
    """Get global threat hunter instance."""
    global _threat_hunter
    if _threat_hunter is None:
        _threat_hunter = ThreatHunter()
    return _threat_hunter
