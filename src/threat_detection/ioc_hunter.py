"""
IoC Hunter for Indicator of Compromise Based Threat Hunting

Specialized threat hunting focused on IoC matching and hunting.
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict

from .ioc_manager import IoCManager, IoCRecord, IoCType, IoCSeverity, get_ioc_manager
from .advanced_anomaly_detector import ThreatDetection, ThreatSeverity, ThreatCategory
from core.error_handling import safe_execute, AstraGuardException

logger = logging.getLogger(__name__)


class IoCHuntStatus(Enum):
    """Status of IoC hunt."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IoCMatch:
    """Single IoC match result."""
    match_id: str
    ioc_id: str
    ioc_type: IoCType
    ioc_value: str
    matched_value: str
    match_context: str
    entity_id: str
    entity_type: str
    match_time: datetime
    confidence: float
    severity: IoCSeverity
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "match_id": self.match_id,
            "ioc_id": self.ioc_id,
            "ioc_type": self.ioc_type.value,
            "ioc_value": self.ioc_value,
            "matched_value": self.matched_value,
            "match_context": self.match_context,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "match_time": self.match_time.isoformat(),
            "confidence": self.confidence,
            "severity": self.severity.value,
            "metadata": self.metadata
        }


@dataclass
class IoCHuntResult:
    """Result of an IoC hunt."""
    hunt_id: str
    hunt_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: IoCHuntStatus = IoCHuntStatus.PENDING
    iocs_searched: int = 0
    entities_searched: int = 0
    matches_found: int = 0
    matches: List[IoCMatch] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hunt_id": self.hunt_id,
            "hunt_name": self.hunt_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "iocs_searched": self.iocs_searched,
            "entities_searched": self.entities_searched,
            "matches_found": self.matches_found,
            "matches": [m.to_dict() for m in self.matches],
            "statistics": self.statistics
        }


class IoCHunter:
    """
    IoC-based threat hunting system.
    
    Hunts for known Indicators of Compromise across various
    data sources and entities.
    """
    
    def __init__(self):
        self.ioc_manager = get_ioc_manager()
        
        # Hunt tracking
        self.hunt_results: Dict[str, IoCHuntResult] = {}
        
        # Match history
        self.match_history: List[IoCMatch] = []
        
        # Statistics
        self.total_hunts = 0
        self.total_matches = 0
        
        # Data source mappings
        self.data_sources = {
            "network_logs": self._search_network_logs,
            "endpoint_logs": self._search_endpoint_logs,
            "dns_logs": self._search_dns_logs,
            "auth_logs": self._search_auth_logs,
            "file_logs": self._search_file_logs,
            "process_logs": self._search_process_logs
        }
    
    async def hunt_ioc(self,
                      ioc_id: str,
                      data_sources: Optional[List[str]] = None,
                      time_range: Optional[timedelta] = None) -> IoCHuntResult:
        """
        Hunt for a specific IoC across data sources.
        
        Args:
            ioc_id: IoC identifier
            data_sources: List of data sources to search (all if None)
            time_range: Time range to search
            
        Returns:
            IoCHuntResult
        """
        # Get IoC record
        ioc_record = self.ioc_manager.get_ioc(ioc_id)
        if not ioc_record:
            raise AstraGuardException(
                f"IoC not found: {ioc_id}",
                component="ioc_hunter"
            )
        
        hunt_id = f"IOCHUNT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{ioc_id}"
        
        result = IoCHuntResult(
            hunt_id=hunt_id,
            hunt_name=f"Hunt for {ioc_record.ioc_type.value}: {ioc_id}",
            started_at=datetime.now(),
            status=IoCHuntStatus.RUNNING,
            iocs_searched=1
        )
        
        self.hunt_results[hunt_id] = result
        self.total_hunts += 1
        
        logger.info(f"Starting IoC hunt: {hunt_id} for {ioc_id}")
        
        try:
            # Determine data sources
            sources_to_search = data_sources or list(self.data_sources.keys())
            
            # Search each data source
            for source in sources_to_search:
                if source in self.data_sources:
                    matches = await self.data_sources[source](ioc_record, time_range)
                    result.matches.extend(matches)
                    result.entities_searched += len(set(m.entity_id for m in matches))
            
            # Update result
            result.matches_found = len(result.matches)
            result.status = IoCHuntStatus.COMPLETED
            result.completed_at = datetime.now()
            
            # Update statistics
            self.total_matches += result.matches_found
            self.match_history.extend(result.matches)
            
            # Calculate statistics
            result.statistics = self._calculate_hunt_statistics(result)
            
            logger.info(f"IoC hunt completed: {hunt_id} - {result.matches_found} matches")
            
        except Exception as e:
            result.status = IoCHuntStatus.FAILED
            logger.error(f"IoC hunt failed: {hunt_id} - {e}")
            raise
        
        return result
    
    async def hunt_all_active_iocs(self,
                                    ioc_types: Optional[List[IoCType]] = None,
                                    data_sources: Optional[List[str]] = None) -> IoCHuntResult:
        """
        Hunt for all active IoCs.
        
        Args:
            ioc_types: Optional filter by IoC types
            data_sources: List of data sources to search
            
        Returns:
            IoCHuntResult
        """
        hunt_id = f"IOCHUNT-ALL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        result = IoCHuntResult(
            hunt_id=hunt_id,
            hunt_name="Hunt for all active IoCs",
            started_at=datetime.now(),
            status=IoCHuntStatus.RUNNING
        )
        
        self.hunt_results[hunt_id] = result
        self.total_hunts += 1
        
        logger.info(f"Starting bulk IoC hunt: {hunt_id}")
        
        try:
            # Get all active IoCs
            all_iocs = self.ioc_manager.get_all_active_iocs()
            
            # Filter by type if specified
            if ioc_types:
                all_iocs = [
                    ioc for ioc in all_iocs
                    if ioc.ioc_type in ioc_types
                ]
            
            result.iocs_searched = len(all_iocs)
            
            # Hunt each IoC
            for ioc in all_iocs:
                hunt_result = await self.hunt_ioc(
                    ioc.ioc_id,
                    data_sources=data_sources
                )
                result.matches.extend(hunt_result.matches)
            
            # Update result
            result.matches_found = len(result.matches)
            result.status = IoCHuntStatus.COMPLETED
            result.completed_at = datetime.now()
            result.statistics = self._calculate_hunt_statistics(result)
            
            self.total_matches += result.matches_found
            
            logger.info(f"Bulk IoC hunt completed: {hunt_id} - {result.matches_found} total matches")
            
        except Exception as e:
            result.status = IoCHuntStatus.FAILED
            logger.error(f"Bulk IoC hunt failed: {hunt_id} - {e}")
            raise
        
        return result
    
    async def hunt_in_entity(self,
                            entity_id: str,
                            entity_type: str,
                            ioc_types: Optional[List[IoCType]] = None) -> IoCHuntResult:
        """
        Hunt for IoCs in a specific entity.
        
        Args:
            entity_id: Entity identifier
            entity_type: Type of entity
            ioc_types: Optional filter by IoC types
            
        Returns:
            IoCHuntResult
        """
        hunt_id = f"IOCHUNT-ENT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{entity_id}"
        
        result = IoCHuntResult(
            hunt_id=hunt_id,
            hunt_name=f"IoC hunt in {entity_type}: {entity_id}",
            started_at=datetime.now(),
            status=IoCHuntStatus.RUNNING,
            entities_searched=1
        )
        
        self.hunt_results[hunt_id] = result
        self.total_hunts += 1
        
        logger.info(f"Starting entity IoC hunt: {hunt_id}")
        
        try:
            # Get relevant IoCs
            all_iocs = self.ioc_manager.get_all_active_iocs()
            
            if ioc_types:
                all_iocs = [ioc for ioc in all_iocs if ioc.ioc_type in ioc_types]
            
            result.iocs_searched = len(all_iocs)
            
            # Search for each IoC in entity context
            for ioc in all_iocs:
                # Simulate entity-specific search
                match = await self._search_entity_context(entity_id, entity_type, ioc)
                if match:
                    result.matches.append(match)
            
            # Update result
            result.matches_found = len(result.matches)
            result.status = IoCHuntStatus.COMPLETED
            result.completed_at = datetime.now()
            result.statistics = self._calculate_hunt_statistics(result)
            
            self.total_matches += result.matches_found
            self.match_history.extend(result.matches)
            
            logger.info(f"Entity IoC hunt completed: {hunt_id} - {result.matches_found} matches")
            
        except Exception as e:
            result.status = IoCHuntStatus.FAILED
            logger.error(f"Entity IoC hunt failed: {hunt_id} - {e}")
            raise
        
        return result
    
    async def _search_network_logs(self,
                                   ioc: IoCRecord,
                                   time_range: Optional[timedelta] = None) -> List[IoCMatch]:
        """Search network logs for IoC."""
        matches = []
        
        # IP address matching
        if ioc.ioc_type == IoCType.IP_ADDRESS:
            # Simulate network log search
            # In production: Query network flow logs, firewall logs, etc.
            pass
        
        # Domain matching
        elif ioc.ioc_type == IoCType.DOMAIN:
            # Simulate DNS/HTTP log search
            pass
        
        return matches
    
    async def _search_endpoint_logs(self,
                                    ioc: IoCRecord,
                                    time_range: Optional[timedelta] = None) -> List[IoCMatch]:
        """Search endpoint logs for IoC."""
        matches = []
        
        # File hash matching
        if ioc.ioc_type == IoCType.FILE_HASH:
            # Simulate file integrity monitoring search
            pass
        
        # File path matching
        elif ioc.ioc_type == IoCType.FILE_PATH:
            # Simulate file access log search
            pass
        
        return matches
    
    async def _search_dns_logs(self,
                              ioc: IoCRecord,
                              time_range: Optional[timedelta] = None) -> List[IoCMatch]:
        """Search DNS logs for IoC."""
        matches = []
        
        if ioc.ioc_type in [IoCType.DOMAIN, IoCType.IP_ADDRESS]:
            # Simulate DNS query log search
            pass
        
        return matches
    
    async def _search_auth_logs(self,
                               ioc: IoCRecord,
                               time_range: Optional[timedelta] = None) -> List[IoCMatch]:
        """Search authentication logs for IoC."""
        matches = []
        
        # Email matching
        if ioc.ioc_type == IoCType.EMAIL_ADDRESS:
            # Simulate auth log search
            pass
        
        return matches
    
    async def _search_file_logs(self,
                               ioc: IoCRecord,
                               time_range: Optional[timedelta] = None) -> List[IoCMatch]:
        """Search file logs for IoC."""
        matches = []
        
        # File hash or path matching
        if ioc.ioc_type in [IoCType.FILE_HASH, IoCType.FILE_PATH]:
            # Simulate file log search
            pass
        
        return matches
    
    async def _search_process_logs(self,
                                  ioc: IoCRecord,
                                  time_range: Optional[timedelta] = None) -> List[IoCMatch]:
        """Search process logs for IoC."""
        matches = []
        
        # Process name matching
        if ioc.ioc_type == IoCType.PROCESS_NAME:
            # Simulate process log search
            pass
        
        return matches
    
    async def _search_entity_context(self,
                                    entity_id: str,
                                    entity_type: str,
                                    ioc: IoCRecord) -> Optional[IoCMatch]:
        """Search for IoC in specific entity context."""
        # Simulate entity-specific search
        # In production: Query entity-specific data sources
        
        return None
    
    def _calculate_hunt_statistics(self, result: IoCHuntResult) -> Dict[str, Any]:
        """Calculate hunt statistics."""
        if not result.matches:
            return {
                "match_rate": 0.0,
                "by_ioc_type": {},
                "by_severity": {},
                "by_entity_type": {}
            }
        
        by_ioc_type = defaultdict(int)
        by_severity = defaultdict(int)
        by_entity_type = defaultdict(int)
        
        for match in result.matches:
            by_ioc_type[match.ioc_type.value] += 1
            by_severity[match.severity.value] += 1
            by_entity_type[match.entity_type] += 1
        
        return {
            "match_rate": result.matches_found / max(1, result.iocs_searched),
            "by_ioc_type": dict(by_ioc_type),
            "by_severity": dict(by_severity),
            "by_entity_type": dict(by_entity_type)
        }
    
    def get_match_history(self,
                         ioc_id: Optional[str] = None,
                         entity_id: Optional[str] = None,
                         limit: int = 1000) -> List[IoCMatch]:
        """Get match history with optional filtering."""
        matches = self.match_history
        
        if ioc_id:
            matches = [m for m in matches if m.ioc_id == ioc_id]
        
        if entity_id:
            matches = [m for m in matches if m.entity_id == entity_id]
        
        # Sort by match time descending
        matches.sort(key=lambda m: m.match_time, reverse=True)
        
        return matches[:limit]
    
    def get_hunt_result(self, hunt_id: str) -> Optional[IoCHuntResult]:
        """Get hunt result by ID."""
        return self.hunt_results.get(hunt_id)
    
    def get_high_confidence_matches(self, 
                                   min_confidence: float = 0.8) -> List[IoCMatch]:
        """Get high confidence matches."""
        return [
            m for m in self.match_history
            if m.confidence >= min_confidence
        ]
    
    def get_matches_by_severity(self, 
                               severity: IoCSeverity) -> List[IoCMatch]:
        """Get matches by severity level."""
        return [
            m for m in self.match_history
            if m.severity == severity
        ]
    
    def correlate_matches(self, 
                         time_window: timedelta = timedelta(hours=1)) -> List[Dict[str, Any]]:
        """
        Correlate matches to find attack patterns.
        
        Args:
            time_window: Time window for correlation
            
        Returns:
            List of correlated match groups
        """
        # Group matches by time window
        if not self.match_history:
            return []
        
        sorted_matches = sorted(self.match_history, key=lambda m: m.match_time)
        
        correlated_groups = []
        current_group = [sorted_matches[0]]
        
        for match in sorted_matches[1:]:
            last_match = current_group[-1]
            time_diff = match.match_time - last_match.match_time
            
            if time_diff <= time_window:
                current_group.append(match)
            else:
                if len(current_group) > 1:
                    correlated_groups.append(self._create_correlation_group(current_group))
                current_group = [match]
        
        if len(current_group) > 1:
            correlated_groups.append(self._create_correlation_group(current_group))
        
        return correlated_groups
    
    def _create_correlation_group(self, matches: List[IoCMatch]) -> Dict[str, Any]:
        """Create a correlation group from related matches."""
        entities = set(m.entity_id for m in matches)
        iocs = set(m.ioc_id for m in matches)
        
        return {
            "match_count": len(matches),
            "time_range": {
                "start": min(m.match_time for m in matches).isoformat(),
                "end": max(m.match_time for m in matches).isoformat()
            },
            "entities": list(entities),
            "iocs": list(iocs),
            "matches": [m.to_dict() for m in matches],
            "correlation_score": len(entities) * len(iocs) / len(matches)
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hunter statistics."""
        by_ioc_type = defaultdict(int)
        by_severity = defaultdict(int)
        
        for match in self.match_history:
            by_ioc_type[match.ioc_type.value] += 1
            by_severity[match.severity.value] += 1
        
        return {
            "total_hunts": self.total_hunts,
            "total_matches": self.total_matches,
            "by_ioc_type": dict(by_ioc_type),
            "by_severity": dict(by_severity),
            "hunt_history": len(self.hunt_results),
            "correlated_groups": len(self.correlate_matches())
        }


# Global instance
_ioc_hunter: Optional[IoCHunter] = None


def get_ioc_hunter() -> IoCHunter:
    """Get global IoC hunter instance."""
    global _ioc_hunter
    if _ioc_hunter is None:
        _ioc_hunter = IoCHunter()
    return _ioc_hunter
