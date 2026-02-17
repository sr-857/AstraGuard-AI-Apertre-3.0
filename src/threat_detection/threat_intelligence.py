"""
Threat Intelligence Integration Module

Provides integration with external threat intelligence feeds
for IoC (Indicators of Compromise) matching and threat context enrichment.
"""

import asyncio
import aiohttp
import json
import hashlib
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict
import re

from core.error_handling import safe_execute, AstraGuardException, async_retry
from core.timeout_handler import async_timeout
from core.circuit_breaker import CircuitBreaker, register_circuit_breaker

logger = logging.getLogger(__name__)


class IoCType(Enum):
    """Types of Indicators of Compromise."""
    IP_ADDRESS = "ip_address"
    DOMAIN = "domain"
    URL = "url"
    FILE_HASH = "file_hash"
    EMAIL = "email"
    CVE = "cve"
    MALWARE_FAMILY = "malware_family"
    THREAT_ACTOR = "threat_actor"


class ThreatSeverity(Enum):
    """Threat severity levels from intelligence feeds."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ThreatIndicator:
    """Threat intelligence indicator."""
    ioc_type: IoCType
    value: str
    threat_type: str
    severity: ThreatSeverity
    confidence: float
    first_seen: datetime
    last_seen: datetime
    source: str
    description: str
    tags: List[str] = field(default_factory=list)
    related_iocs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ioc_type": self.ioc_type.value,
            "value": self.value,
            "threat_type": self.threat_type,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "source": self.source,
            "description": self.description,
            "tags": self.tags,
            "related_iocs": self.related_iocs
        }
    
    def get_hash(self) -> str:
        """Generate unique hash for this indicator."""
        return hashlib.sha256(
            f"{self.ioc_type.value}:{self.value}:{self.source}".encode()
        ).hexdigest()[:16]


@dataclass
class ThreatMatch:
    """Result of matching data against threat intelligence."""
    matched_ioc: ThreatIndicator
    matched_value: str
    match_type: str
    match_confidence: float
    context: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "matched_ioc": self.matched_ioc.to_dict(),
            "matched_value": self.matched_value,
            "match_type": self.match_type,
            "match_confidence": self.match_confidence,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }


class ThreatFeedConfig:
    """Configuration for a threat intelligence feed."""
    
    def __init__(self, 
                 name: str,
                 url: str,
                 api_key: Optional[str] = None,
                 update_interval_minutes: int = 60,
                 enabled: bool = True,
                 ioc_types: List[IoCType] = None,
                 timeout_seconds: int = 30):
        self.name = name
        self.url = url
        self.api_key = api_key
        self.update_interval = timedelta(minutes=update_interval_minutes)
        self.enabled = enabled
        self.ioc_types = ioc_types or list(IoCType)
        self.timeout_seconds = timeout_seconds
        self.last_update: Optional[datetime] = None


class ThreatIntelligenceManager:
    """
    Main threat intelligence manager.
    
    Integrates with multiple threat feeds, maintains IoC database,
    and provides matching capabilities.
    """
    
    def __init__(self):
        self.feeds: Dict[str, ThreatFeedConfig] = {}
        self.indicators: Dict[str, ThreatIndicator] = {}  # hash -> indicator
        self.ioc_index: Dict[IoCType, Set[str]] = defaultdict(set)  # type -> values
        self.match_history: List[ThreatMatch] = []
        
        # Statistics
        self.total_indicators = 0
        self.matches_found = 0
        self.feed_updates = 0
        
        # Circuit breaker for feed updates
        self.feed_circuit = register_circuit_breaker(
            CircuitBreaker(
                name="threat_feed_update",
                failure_threshold=5,
                success_threshold=2,
                recovery_timeout=300,
                expected_exceptions=(Exception,)
            )
        )
        
        # Background update task
        self._update_task: Optional[asyncio.Task] = None
        self._running = False
        
    def add_feed(self, config: ThreatFeedConfig):
        """Add a threat intelligence feed."""
        self.feeds[config.name] = config
        logger.info(f"Added threat feed: {config.name}")
    
    def remove_feed(self, feed_name: str):
        """Remove a threat intelligence feed."""
        if feed_name in self.feeds:
            del self.feeds[feed_name]
            logger.info(f"Removed threat feed: {feed_name}")
    
    async def start(self):
        """Start the threat intelligence manager."""
        self._running = True
        
        # Initial update
        await self.update_all_feeds()
        
        # Start background update task
        self._update_task = asyncio.create_task(self._background_update())
        
        logger.info("Threat intelligence manager started")
    
    async def stop(self):
        """Stop the threat intelligence manager."""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Threat intelligence manager stopped")
    
    async def _background_update(self):
        """Background task for periodic feed updates."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check which feeds need updating
                now = datetime.now()
                for feed_name, feed in self.feeds.items():
                    if not feed.enabled:
                        continue
                    
                    if (feed.last_update is None or 
                        now - feed.last_update >= feed.update_interval):
                        await self._update_feed(feed_name)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background update error: {e}")
    
    async def update_all_feeds(self):
        """Update all enabled feeds."""
        for feed_name in self.feeds:
            await self._update_feed(feed_name)
    
    @async_retry(max_retries=3, delay=1.0)
    async def _update_feed(self, feed_name: str):
        """Update a specific threat feed."""
        feed = self.feeds.get(feed_name)
        if not feed or not feed.enabled:
            return
        
        logger.info(f"Updating threat feed: {feed_name}")
        
        try:
            # Fetch feed data through circuit breaker
            indicators = await self.feed_circuit.call(
                self._fetch_feed_data,
                feed
            )
            
            # Process and store indicators
            for indicator_data in indicators:
                indicator = self._parse_indicator(indicator_data, feed_name)
                if indicator:
                    await self._add_indicator(indicator)
            
            feed.last_update = datetime.now()
            self.feed_updates += 1
            
            logger.info(f"Updated {feed_name}: {len(indicators)} indicators")
            
        except Exception as e:
            logger.error(f"Failed to update feed {feed_name}: {e}")
            raise
    
    async def _fetch_feed_data(self, feed: ThreatFeedConfig) -> List[Dict[str, Any]]:
        """Fetch data from a threat feed."""
        headers = {}
        if feed.api_key:
            headers["Authorization"] = f"Bearer {feed.api_key}"
            headers["X-API-Key"] = feed.api_key
        
        timeout = aiohttp.ClientTimeout(total=feed.timeout_seconds)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(feed.url, headers=headers) as response:
                if response.status != 200:
                    raise AstraGuardException(
                        f"Feed returned status {response.status}",
                        component="threat_intelligence",
                        context={"feed": feed.name, "status": response.status}
                    )
                
                data = await response.json()
                return data if isinstance(data, list) else data.get("indicators", [])
    
    def _parse_indicator(self, data: Dict[str, Any], source: str) -> Optional[ThreatIndicator]:
        """Parse indicator data from feed."""
        try:
            # Map IoC type
            ioc_type_str = data.get("type", "").lower()
            ioc_type = self._map_ioc_type(ioc_type_str)
            
            if not ioc_type:
                return None
            
            # Map severity
            severity_str = data.get("severity", "medium").lower()
            severity = self._map_severity(severity_str)
            
            # Parse dates
            first_seen = self._parse_date(data.get("first_seen"))
            last_seen = self._parse_date(data.get("last_seen"))
            
            return ThreatIndicator(
                ioc_type=ioc_type,
                value=data.get("value", ""),
                threat_type=data.get("threat_type", "unknown"),
                severity=severity,
                confidence=float(data.get("confidence", 0.7)),
                first_seen=first_seen,
                last_seen=last_seen,
                source=source,
                description=data.get("description", ""),
                tags=data.get("tags", []),
                related_iocs=data.get("related_iocs", [])
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse indicator: {e}")
            return None
    
    def _map_ioc_type(self, type_str: str) -> Optional[IoCType]:
        """Map string to IoCType."""
        type_mapping = {
            "ip": IoCType.IP_ADDRESS,
            "ip_address": IoCType.IP_ADDRESS,
            "domain": IoCType.DOMAIN,
            "hostname": IoCType.DOMAIN,
            "url": IoCType.URL,
            "hash": IoCType.FILE_HASH,
            "file_hash": IoCType.FILE_HASH,
            "md5": IoCType.FILE_HASH,
            "sha256": IoCType.FILE_HASH,
            "email": IoCType.EMAIL,
            "cve": IoCType.CVE,
            "malware": IoCType.MALWARE_FAMILY,
            "threat_actor": IoCType.THREAT_ACTOR
        }
        return type_mapping.get(type_str.lower())
    
    def _map_severity(self, severity_str: str) -> ThreatSeverity:
        """Map string to ThreatSeverity."""
        severity_mapping = {
            "critical": ThreatSeverity.CRITICAL,
            "high": ThreatSeverity.HIGH,
            "medium": ThreatSeverity.MEDIUM,
            "low": ThreatSeverity.LOW,
            "info": ThreatSeverity.INFO
        }
        return severity_mapping.get(severity_str.lower(), ThreatSeverity.MEDIUM)
    
    def _parse_date(self, date_str: Optional[str]) -> datetime:
        """Parse date string to datetime."""
        if not date_str:
            return datetime.now()
        
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except:
            return datetime.now()
    
    async def _add_indicator(self, indicator: ThreatIndicator):
        """Add an indicator to the database."""
        indicator_hash = indicator.get_hash()
        
        # Check if already exists
        if indicator_hash in self.indicators:
            # Update last_seen
            existing = self.indicators[indicator_hash]
            if indicator.last_seen > existing.last_seen:
                existing.last_seen = indicator.last_seen
                existing.confidence = max(existing.confidence, indicator.confidence)
            return
        
        # Add new indicator
        self.indicators[indicator_hash] = indicator
        self.ioc_index[indicator.ioc_type].add(indicator.value)
        self.total_indicators += 1
    
    async def check_ioc(self, ioc_type: IoCType, value: str,
                       context: Optional[Dict[str, Any]] = None) -> Optional[ThreatMatch]:
        """
        Check if an IoC is in the threat intelligence database.
        
        Args:
            ioc_type: Type of IoC
            value: IoC value to check
            context: Optional context information
            
        Returns:
            ThreatMatch if found, None otherwise
        """
        # Normalize value
        normalized_value = self._normalize_ioc(ioc_type, value)
        
        # Check if in index
        if normalized_value not in self.ioc_index[ioc_type]:
            return None
        
        # Find matching indicator
        for indicator in self.indicators.values():
            if (indicator.ioc_type == ioc_type and 
                self._normalize_ioc(ioc_type, indicator.value) == normalized_value):
                
                match = ThreatMatch(
                    matched_ioc=indicator,
                    matched_value=value,
                    match_type="exact",
                    match_confidence=indicator.confidence,
                    context=context or {},
                    timestamp=datetime.now()
                )
                
                self.matches_found += 1
                self.match_history.append(match)
                
                return match
        
        return None
    
    def _normalize_ioc(self, ioc_type: IoCType, value: str) -> str:
        """Normalize IoC value for comparison."""
        value = value.lower().strip()
        
        if ioc_type == IoCType.IP_ADDRESS:
            # Normalize IP (handle IPv4/IPv6)
            return value
        elif ioc_type == IoCType.DOMAIN:
            # Remove www. prefix, trailing dot
            value = re.sub(r'^www\.', '', value)
            value = value.rstrip('.')
        
        return value
    
    async def check_data(self, data: Dict[str, Any]) -> List[ThreatMatch]:
        """
        Check all IoCs in data against threat intelligence.
        
        Args:
            data: Dictionary containing potential IoCs
            
        Returns:
            List of threat matches
        """
        matches = []
        
        # Check IP addresses
        for ip_field in ["source_ip", "destination_ip", "ip", "client_ip"]:
            if ip_field in data:
                match = await self.check_ioc(
                    IoCType.IP_ADDRESS, 
                    data[ip_field],
                    {"field": ip_field, "data": data}
                )
                if match:
                    matches.append(match)
        
        # Check domains
        for domain_field in ["domain", "hostname", "server_name"]:
            if domain_field in data:
                match = await self.check_ioc(
                    IoCType.DOMAIN,
                    data[domain_field],
                    {"field": domain_field, "data": data}
                )
                if match:
                    matches.append(match)
        
        # Check file hashes
        for hash_field in ["file_hash", "md5", "sha256", "hash"]:
            if hash_field in data:
                match = await self.check_ioc(
                    IoCType.FILE_HASH,
                    data[hash_field],
                    {"field": hash_field, "data": data}
                )
                if match:
                    matches.append(match)
        
        # Check URLs
        for url_field in ["url", "uri", "request_url"]:
            if url_field in data:
                match = await self.check_ioc(
                    IoCType.URL,
                    data[url_field],
                    {"field": url_field, "data": data}
                )
                if match:
                    matches.append(match)
        
        return matches
    
    def get_indicator_stats(self) -> Dict[str, Any]:
        """Get statistics about stored indicators."""
        type_counts = {
            ioc_type.value: len(values) 
            for ioc_type, values in self.ioc_index.items()
        }
        
        severity_counts = defaultdict(int)
        for indicator in self.indicators.values():
            severity_counts[indicator.severity.value] += 1
        
        return {
            "total_indicators": self.total_indicators,
            "by_type": type_counts,
            "by_severity": dict(severity_counts),
            "feeds_configured": len(self.feeds),
            "feed_updates": self.feed_updates,
            "matches_found": self.matches_found
        }
    
    def get_recent_matches(self, count: int = 100) -> List[ThreatMatch]:
        """Get recent threat matches."""
        return self.match_history[-count:]


# Global instance
_ti_manager: Optional[ThreatIntelligenceManager] = None


async def get_threat_intelligence() -> ThreatIntelligenceManager:
    """Get or create global threat intelligence manager."""
    global _ti_manager
    if _ti_manager is None:
        _ti_manager = ThreatIntelligenceManager()
    return _ti_manager
