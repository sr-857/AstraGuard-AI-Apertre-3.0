"""
IoC (Indicators of Compromise) Manager

Manages IoC data including storage, retrieval, expiration,
and correlation between related indicators.
"""

import json
import hashlib
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict
import re

from core.error_handling import safe_execute, AstraGuardException

logger = logging.getLogger(__name__)


class IoCStatus(Enum):
    """Status of an IoC in the system."""
    ACTIVE = "active"
    EXPIRED = "expired"
    FALSE_POSITIVE = "false_positive"
    WHITELISTED = "whitelisted"
    UNDER_REVIEW = "under_review"


@dataclass
class IoCRecord:
    """Complete IoC record with metadata."""
    ioc_id: str
    ioc_type: str
    value: str
    threat_type: str
    severity: str
    confidence: float
    status: IoCStatus
    first_seen: datetime
    last_seen: datetime
    expiration_date: Optional[datetime]
    source: str
    description: str
    tags: List[str] = field(default_factory=list)
    related_iocs: List[str] = field(default_factory=list)
    match_count: int = 0
    false_positive_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ioc_id": self.ioc_id,
            "ioc_type": self.ioc_type,
            "value": self.value,
            "threat_type": self.threat_type,
            "severity": self.severity,
            "confidence": self.confidence,
            "status": self.status.value,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
            "source": self.source,
            "description": self.description,
            "tags": self.tags,
            "related_iocs": self.related_iocs,
            "match_count": self.match_count,
            "false_positive_count": self.false_positive_count,
            "metadata": self.metadata
        }
    
    def is_expired(self) -> bool:
        """Check if IoC has expired."""
        if self.expiration_date:
            return datetime.now() > self.expiration_date
        return False
    
    def get_reliability_score(self) -> float:
        """Calculate reliability score based on history."""
        if self.match_count == 0:
            return self.confidence * 0.5
        
        fp_rate = self.false_positive_count / self.match_count
        reliability = self.confidence * (1 - fp_rate)
        
        # Reduce reliability if expired
        if self.is_expired():
            reliability *= 0.5
        
        return max(0.0, min(1.0, reliability))


class IoCManager:
    """
    Manager for Indicators of Compromise.
    
    Provides CRUD operations, expiration management,
    and correlation analysis for IoCs.
    """
    
    def __init__(self):
        self.iocs: Dict[str, IoCRecord] = {}  # ioc_id -> record
        self.value_index: Dict[str, Set[str]] = defaultdict(set)  # value -> ioc_ids
        self.type_index: Dict[str, Set[str]] = defaultdict(set)  # type -> ioc_ids
        self.tag_index: Dict[str, Set[str]] = defaultdict(set)  # tag -> ioc_ids
        
        # Default expiration periods by severity
        self.expiration_periods = {
            "critical": timedelta(days=365),  # Long expiration for critical
            "high": timedelta(days=180),
            "medium": timedelta(days=90),
            "low": timedelta(days=30),
            "info": timedelta(days=7)
        }
        
        # Whitelist for false positives
        self.whitelist: Set[str] = set()
        
    def add_ioc(self, 
                ioc_type: str,
                value: str,
                threat_type: str,
                severity: str,
                source: str,
                description: str = "",
                confidence: float = 0.7,
                tags: List[str] = None,
                related_iocs: List[str] = None,
                expiration_days: Optional[int] = None) -> IoCRecord:
        """
        Add a new IoC to the manager.
        
        Args:
            ioc_type: Type of IoC (ip, domain, hash, etc.)
            value: IoC value
            threat_type: Type of threat (malware, phishing, etc.)
            severity: Severity level
            source: Source of the IoC
            description: Description of the threat
            confidence: Confidence score (0-1)
            tags: List of tags
            related_iocs: List of related IoC IDs
            expiration_days: Custom expiration period
            
        Returns:
            Created IoCRecord
        """
        # Check whitelist
        if self._is_whitelisted(ioc_type, value):
            logger.warning(f"IoC {ioc_type}:{value} is whitelisted - not adding")
            raise AstraGuardException(
                "IoC is whitelisted",
                component="ioc_manager",
                context={"ioc_type": ioc_type, "value": value}
            )
        
        # Generate ID
        ioc_id = self._generate_ioc_id(ioc_type, value, source)
        
        # Check if already exists
        if ioc_id in self.iocs:
            # Update existing
            existing = self.iocs[ioc_id]
            existing.last_seen = datetime.now()
            existing.confidence = max(existing.confidence, confidence)
            logger.info(f"Updated existing IoC: {ioc_id}")
            return existing
        
        # Calculate expiration
        if expiration_days:
            expiration_date = datetime.now() + timedelta(days=expiration_days)
        else:
            period = self.expiration_periods.get(severity.lower(), timedelta(days=30))
            expiration_date = datetime.now() + period
        
        # Create record
        record = IoCRecord(
            ioc_id=ioc_id,
            ioc_type=ioc_type,
            value=value,
            threat_type=threat_type,
            severity=severity,
            confidence=confidence,
            status=IoCStatus.ACTIVE,
            first_seen=datetime.now(),
            last_seen=datetime.now(),
            expiration_date=expiration_date,
            source=source,
            description=description,
            tags=tags or [],
            related_iocs=related_iocs or [],
            match_count=0,
            false_positive_count=0,
            metadata={}
        )
        
        # Store
        self.iocs[ioc_id] = record
        self.value_index[value].add(ioc_id)
        self.type_index[ioc_type].add(ioc_id)
        for tag in (tags or []):
            self.tag_index[tag].add(ioc_id)
        
        logger.info(f"Added IoC: {ioc_id} (type={ioc_type}, severity={severity})")
        
        return record
    
    def get_ioc(self, ioc_id: str) -> Optional[IoCRecord]:
        """Get IoC by ID."""
        return self.iocs.get(ioc_id)
    
    def find_ioc(self, ioc_type: str, value: str) -> Optional[IoCRecord]:
        """Find IoC by type and value."""
        normalized_value = self._normalize_value(ioc_type, value)
        
        for ioc_id in self.value_index.get(normalized_value, []):
            record = self.iocs.get(ioc_id)
            if record and record.ioc_type == ioc_type and record.status == IoCStatus.ACTIVE:
                if not record.is_expired():
                    return record
        
        return None
    
    def update_ioc(self, ioc_id: str, **kwargs) -> Optional[IoCRecord]:
        """Update IoC fields."""
        record = self.iocs.get(ioc_id)
        if not record:
            return None
        
        # Update allowed fields
        allowed_fields = ["threat_type", "severity", "confidence", "description", 
                         "tags", "related_iocs", "status", "metadata"]
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                if field == "status" and isinstance(value, str):
                    value = IoCStatus(value)
                setattr(record, field, value)
        
        record.last_seen = datetime.now()
        logger.info(f"Updated IoC: {ioc_id}")
        
        return record
    
    def delete_ioc(self, ioc_id: str) -> bool:
        """Delete an IoC."""
        record = self.iocs.get(ioc_id)
        if not record:
            return False
        
        # Remove from indexes
        self.value_index[record.value].discard(ioc_id)
        self.type_index[record.ioc_type].discard(ioc_id)
        for tag in record.tags:
            self.tag_index[tag].discard(ioc_id)
        
        del self.iocs[ioc_id]
        logger.info(f"Deleted IoC: {ioc_id}")
        
        return True
    
    def record_match(self, ioc_id: str, was_false_positive: bool = False):
        """Record a match against an IoC."""
        record = self.iocs.get(ioc_id)
        if not record:
            return
        
        record.match_count += 1
        
        if was_false_positive:
            record.false_positive_count += 1
            logger.warning(f"False positive recorded for IoC: {ioc_id}")
            
            # Check if should be whitelisted
            if record.false_positive_count >= 5:
                self.add_to_whitelist(record.ioc_type, record.value)
                record.status = IoCStatus.FALSE_POSITIVE
    
    def add_to_whitelist(self, ioc_type: str, value: str):
        """Add an IoC to the whitelist."""
        whitelist_key = f"{ioc_type}:{self._normalize_value(ioc_type, value)}"
        self.whitelist.add(whitelist_key)
        logger.info(f"Added to whitelist: {whitelist_key}")
    
    def remove_from_whitelist(self, ioc_type: str, value: str):
        """Remove an IoC from the whitelist."""
        whitelist_key = f"{ioc_type}:{self._normalize_value(ioc_type, value)}"
        self.whitelist.discard(whitelist_key)
        logger.info(f"Removed from whitelist: {whitelist_key}")
    
    def _is_whitelisted(self, ioc_type: str, value: str) -> bool:
        """Check if an IoC is whitelisted."""
        whitelist_key = f"{ioc_type}:{self._normalize_value(ioc_type, value)}"
        return whitelist_key in self.whitelist
    
    def _generate_ioc_id(self, ioc_type: str, value: str, source: str) -> str:
        """Generate unique IoC ID."""
        hash_input = f"{ioc_type}:{value}:{source}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return f"IOC-{hash_value.upper()}"
    
    def _normalize_value(self, ioc_type: str, value: str) -> str:
        """Normalize IoC value for comparison."""
        value = value.lower().strip()
        
        if ioc_type in ["ip", "ip_address"]:
            # Normalize IP
            return value
        elif ioc_type in ["domain", "hostname"]:
            # Remove www. and trailing dots
            value = re.sub(r'^www\.', '', value)
            value = value.rstrip('.')
        
        return value
    
    def search_iocs(self, 
                   ioc_type: Optional[str] = None,
                   severity: Optional[str] = None,
                   status: Optional[IoCStatus] = None,
                   tags: Optional[List[str]] = None,
                   threat_type: Optional[str] = None) -> List[IoCRecord]:
        """
        Search IoCs with filters.
        
        Returns:
            List of matching IoCRecords
        """
        results = list(self.iocs.values())
        
        if ioc_type:
            results = [r for r in results if r.ioc_type == ioc_type]
        
        if severity:
            results = [r for r in results if r.severity == severity]
        
        if status:
            results = [r for r in results if r.status == status]
        
        if threat_type:
            results = [r for r in results if r.threat_type == threat_type]
        
        if tags:
            results = [r for r in results if any(tag in r.tags for tag in tags)]
        
        return results
    
    def get_related_iocs(self, ioc_id: str) -> List[IoCRecord]:
        """Get IoCs related to a given IoC."""
        record = self.iocs.get(ioc_id)
        if not record:
            return []
        
        related = []
        for related_id in record.related_iocs:
            related_record = self.iocs.get(related_id)
            if related_record:
                related.append(related_record)
        
        return related
    
    def find_correlated_threats(self, ioc_ids: List[str]) -> Dict[str, Any]:
        """
        Find correlated threats across multiple IoCs.
        
        Returns:
            Dictionary with correlation analysis
        """
        # Collect all related IoCs
        all_related = set()
        threat_types = defaultdict(int)
        sources = defaultdict(int)
        
        for ioc_id in ioc_ids:
            record = self.iocs.get(ioc_id)
            if not record:
                continue
            
            threat_types[record.threat_type] += 1
            sources[record.source] += 1
            
            for related in record.related_iocs:
                all_related.add(related)
        
        # Find common threats
        common_threats = {
            threat: count for threat, count in threat_types.items() 
            if count > 1
        }
        
        return {
            "input_iocs": len(ioc_ids),
            "related_iocs_found": len(all_related),
            "common_threat_types": common_threats,
            "source_distribution": dict(sources),
            "potential_campaign": len(common_threats) > 0
        }
    
    def cleanup_expired(self) -> int:
        """
        Remove expired IoCs.
        
        Returns:
            Number of IoCs removed
        """
        expired_ids = [
            ioc_id for ioc_id, record in self.iocs.items()
            if record.is_expired() and record.status != IoCStatus.WHITELISTED
        ]
        
        for ioc_id in expired_ids:
            record = self.iocs[ioc_id]
            record.status = IoCStatus.EXPIRED
            logger.info(f"Marked IoC as expired: {ioc_id}")
        
        return len(expired_ids)
    
    def export_iocs(self, 
                   ioc_type: Optional[str] = None,
                   format: str = "json") -> str:
        """
        Export IoCs to a format.
        
        Args:
            ioc_type: Optional filter by type
            format: Export format (json, csv, stix)
            
        Returns:
            Exported data as string
        """
        records = self.search_iocs(ioc_type=ioc_type, status=IoCStatus.ACTIVE)
        
        if format == "json":
            data = [r.to_dict() for r in records]
            return json.dumps(data, indent=2)
        
        elif format == "csv":
            lines = ["ioc_id,ioc_type,value,threat_type,severity,confidence,source"]
            for r in records:
                lines.append(f"{r.ioc_id},{r.ioc_type},{r.value},{r.threat_type},{r.severity},{r.confidence},{r.source}")
            return "\n".join(lines)
        
        elif format == "stix":
            # Simplified STIX format
            stix_objects = []
            for r in records:
                stix_objects.append({
                    "type": "indicator",
                    "id": r.ioc_id,
                    "labels": [r.threat_type],
                    "pattern": f"[{r.ioc_type}:value = '{r.value}']",
                    "valid_from": r.first_seen.isoformat()
                })
            return json.dumps({"objects": stix_objects}, indent=2)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get IoC manager statistics."""
        status_counts = defaultdict(int)
        type_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for record in self.iocs.values():
            status_counts[record.status.value] += 1
            type_counts[record.ioc_type] += 1
            severity_counts[record.severity] += 1
        
        expired_count = sum(1 for r in self.iocs.values() if r.is_expired())
        
        return {
            "total_iocs": len(self.iocs),
            "by_status": dict(status_counts),
            "by_type": dict(type_counts),
            "by_severity": dict(severity_counts),
            "expired_iocs": expired_count,
            "whitelisted_count": len(self.whitelist),
            "total_matches": sum(r.match_count for r in self.iocs.values()),
            "total_false_positives": sum(r.false_positive_count for r in self.iocs.values())
        }


# Global instance
_ioc_manager: Optional[IoCManager] = None


def get_ioc_manager() -> IoCManager:
    """Get global IoC manager instance."""
    global _ioc_manager
    if _ioc_manager is None:
        _ioc_manager = IoCManager()
    return _ioc_manager
