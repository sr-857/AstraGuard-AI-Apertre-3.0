"""
Threat Feed Synchronization Module

Automated synchronization of threat intelligence feeds
with scheduling, deduplication, and conflict resolution.
"""

import asyncio
import aiohttp
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict
import hashlib

from .ioc_manager import IoCManager, IoCRecord, get_ioc_manager
from .threat_intelligence import ThreatIntelligenceManager, ThreatFeedConfig
from core.error_handling import safe_execute, AstraGuardException, async_retry
from core.timeout_handler import async_timeout

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of a synchronization job."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SyncJob:
    """Threat feed synchronization job."""
    job_id: str
    feed_name: str
    status: SyncStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    iocs_added: int = 0
    iocs_updated: int = 0
    iocs_failed: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "feed_name": self.feed_name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "iocs_added": self.iocs_added,
            "iocs_updated": self.iocs_updated,
            "iocs_failed": self.iocs_failed,
            "errors": self.errors
        }


class FeedSchedule:
    """Schedule configuration for a feed."""
    
    def __init__(self,
                 feed_name: str,
                 interval_minutes: int = 60,
                 enabled: bool = True,
                 retry_on_failure: bool = True,
                 max_retries: int = 3):
        self.feed_name = feed_name
        self.interval = timedelta(minutes=interval_minutes)
        self.enabled = enabled
        self.retry_on_failure = retry_on_failure
        self.max_retries = max_retries
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.success_count: int = 0
        self.failure_count: int = 0
    
    def should_run(self) -> bool:
        """Check if feed should run now."""
        if not self.enabled:
            return False
        
        if self.next_run is None:
            return True
        
        return datetime.now() >= self.next_run
    
    def record_success(self):
        """Record successful run."""
        self.last_run = datetime.now()
        self.next_run = self.last_run + self.interval
        self.success_count += 1
    
    def record_failure(self):
        """Record failed run."""
        self.failure_count += 1
        if self.retry_on_failure:
            # Retry sooner on failure
            self.next_run = datetime.now() + timedelta(minutes=5)


class ThreatFeedSync:
    """
    Automated threat feed synchronization system.
    
    Manages scheduled updates, deduplication, and conflict
    resolution across multiple threat intelligence feeds.
    """
    
    def __init__(self):
        self.ioc_manager = get_ioc_manager()
        self.schedules: Dict[str, FeedSchedule] = {}
        self.jobs: Dict[str, SyncJob] = {}
        self.feed_configs: Dict[str, Dict[str, Any]] = {}
        
        # Background task
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Deduplication cache
        self._seen_hashes: Set[str] = set()
        self._dedup_window = timedelta(hours=24)
        
        # Conflict resolution strategy
        self.conflict_strategy = "highest_confidence"  # or "newest", "oldest"
    
    def add_feed(self, 
                 feed_name: str,
                 feed_url: str,
                 ioc_type_mapping: Dict[str, str],
                 update_interval_minutes: int = 60,
                 api_key: Optional[str] = None,
                 enabled: bool = True):
        """
        Add a threat feed for synchronization.
        
        Args:
            feed_name: Unique name for the feed
            feed_url: URL to fetch IoCs from
            ioc_type_mapping: Mapping of feed types to internal types
            update_interval_minutes: How often to sync
            api_key: Optional API key for authentication
            enabled: Whether feed is enabled
        """
        self.feed_configs[feed_name] = {
            "url": feed_url,
            "ioc_type_mapping": ioc_type_mapping,
            "api_key": api_key,
            "headers": {}
        }
        
        # Create schedule
        self.schedules[feed_name] = FeedSchedule(
            feed_name=feed_name,
            interval_minutes=update_interval_minutes,
            enabled=enabled
        )
        
        logger.info(f"Added threat feed: {feed_name} (interval={update_interval_minutes}min)")
    
    def remove_feed(self, feed_name: str):
        """Remove a threat feed."""
        if feed_name in self.feed_configs:
            del self.feed_configs[feed_name]
        
        if feed_name in self.schedules:
            del self.schedules[feed_name]
        
        logger.info(f"Removed threat feed: {feed_name}")
    
    async def start(self):
        """Start the synchronization scheduler."""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Threat feed sync scheduler started")
    
    async def stop(self):
        """Stop the synchronization scheduler."""
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Threat feed sync scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                for feed_name, schedule in self.schedules.items():
                    if schedule.should_run():
                        await self.sync_feed(feed_name)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
    
    async def sync_feed(self, feed_name: str) -> SyncJob:
        """
        Manually trigger synchronization of a feed.
        
        Args:
            feed_name: Name of the feed to sync
            
        Returns:
            SyncJob with results
        """
        # Create job
        job_id = self._generate_job_id(feed_name)
        job = SyncJob(
            job_id=job_id,
            feed_name=feed_name,
            status=SyncStatus.PENDING,
            created_at=datetime.now()
        )
        self.jobs[job_id] = job
        
        schedule = self.schedules.get(feed_name)
        if schedule:
            schedule.last_run = datetime.now()
        
        try:
            job.status = SyncStatus.RUNNING
            job.started_at = datetime.now()
            
            # Fetch feed data
            config = self.feed_configs.get(feed_name)
            if not config:
                raise AstraGuardException(
                    f"Feed configuration not found: {feed_name}",
                    component="threat_feed_sync"
                )
            
            iocs_data = await self._fetch_feed(feed_name, config)
            
            # Process IoCs
            for ioc_data in iocs_data:
                try:
                    result = await self._process_ioc(ioc_data, feed_name, config)
                    if result == "added":
                        job.iocs_added += 1
                    elif result == "updated":
                        job.iocs_updated += 1
                except Exception as e:
                    job.iocs_failed += 1
                    job.errors.append(str(e))
                    logger.warning(f"Failed to process IoC: {e}")
            
            # Determine final status
            if job.iocs_failed == 0:
                job.status = SyncStatus.SUCCESS
            elif job.iocs_added > 0 or job.iocs_updated > 0:
                job.status = SyncStatus.PARTIAL
            else:
                job.status = SyncStatus.FAILED
            
            job.completed_at = datetime.now()
            
            # Update schedule
            if schedule:
                if job.status in [SyncStatus.SUCCESS, SyncStatus.PARTIAL]:
                    schedule.record_success()
                else:
                    schedule.record_failure()
            
            logger.info(
                f"Feed sync complete: {feed_name} - "
                f"added={job.iocs_added}, updated={job.iocs_updated}, "
                f"failed={job.iocs_failed}"
            )
            
        except Exception as e:
            job.status = SyncStatus.FAILED
            job.completed_at = datetime.now()
            job.errors.append(str(e))
            
            if schedule:
                schedule.record_failure()
            
            logger.error(f"Feed sync failed: {feed_name} - {e}")
        
        return job
    
    @async_retry(max_retries=3, delay=2.0)
    async def _fetch_feed(self, feed_name: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch IoC data from a feed."""
        url = config["url"]
        headers = config.get("headers", {})
        
        if config.get("api_key"):
            headers["Authorization"] = f"Bearer {config['api_key']}"
            headers["X-API-Key"] = config["api_key"]
        
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise AstraGuardException(
                        f"Feed returned status {response.status}",
                        component="threat_feed_sync",
                        context={"feed": feed_name, "status": response.status}
                    )
                
                data = await response.json()
                
                # Handle different response formats
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("indicators", data.get("iocs", data.get("data", [])))
                else:
                    return []
    
    async def _process_ioc(self, 
                          ioc_data: Dict[str, Any], 
                          source: str,
                          config: Dict[str, Any]) -> str:
        """
        Process a single IoC from a feed.
        
        Returns:
            "added", "updated", or "skipped"
        """
        # Map IoC type
        feed_type = ioc_data.get("type", "unknown")
        type_mapping = config.get("ioc_type_mapping", {})
        ioc_type = type_mapping.get(feed_type, feed_type)
        
        # Extract fields
        value = ioc_data.get("value") or ioc_data.get("indicator")
        if not value:
            raise ValueError("IoC value missing")
        
        # Check deduplication
        ioc_hash = self._hash_ioc(ioc_type, value)
        if ioc_hash in self._seen_hashes:
            return "skipped"
        
        self._seen_hashes.add(ioc_hash)
        
        # Clean old hashes
        self._cleanup_hashes()
        
        # Check for existing IoC
        existing = self.ioc_manager.find_ioc(ioc_type, value)
        
        if existing:
            # Conflict resolution
            new_confidence = float(ioc_data.get("confidence", 0.7))
            
            if self.conflict_strategy == "highest_confidence":
                if new_confidence <= existing.confidence:
                    return "skipped"
            elif self.conflict_strategy == "newest":
                pass  # Always update
            elif self.conflict_strategy == "oldest":
                return "skipped"
            
            # Update existing
            self.ioc_manager.update_ioc(
                existing.ioc_id,
                confidence=new_confidence,
                last_seen=datetime.now()
            )
            return "updated"
        
        # Add new IoC
        severity = ioc_data.get("severity", "medium")
        threat_type = ioc_data.get("threat_type", "unknown")
        description = ioc_data.get("description", "")
        confidence = float(ioc_data.get("confidence", 0.7))
        tags = ioc_data.get("tags", [])
        
        self.ioc_manager.add_ioc(
            ioc_type=ioc_type,
            value=value,
            threat_type=threat_type,
            severity=severity,
            source=source,
            description=description,
            confidence=confidence,
            tags=tags
        )
        
        return "added"
    
    def _hash_ioc(self, ioc_type: str, value: str) -> str:
        """Generate hash for deduplication."""
        return hashlib.sha256(
            f"{ioc_type}:{value.lower()}".encode()
        ).hexdigest()[:16]
    
    def _cleanup_hashes(self):
        """Clean up old deduplication hashes."""
        # Simple size-based cleanup
        if len(self._seen_hashes) > 100000:
            # Clear half of them
            hashes_list = list(self._seen_hashes)
            self._seen_hashes = set(hashes_list[50000:])
    
    def _generate_job_id(self, feed_name: str) -> str:
        """Generate unique job ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_input = f"{feed_name}:{timestamp}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        return f"SYNC-{feed_name.upper()}-{hash_value}"
    
    def get_job(self, job_id: str) -> Optional[SyncJob]:
        """Get sync job by ID."""
        return self.jobs.get(job_id)
    
    def get_jobs(self, 
                 feed_name: Optional[str] = None,
                 status: Optional[SyncStatus] = None,
                 limit: int = 100) -> List[SyncJob]:
        """
        Get sync jobs with optional filtering.
        
        Returns:
            List of SyncJob objects
        """
        jobs = list(self.jobs.values())
        
        if feed_name:
            jobs = [j for j in jobs if j.feed_name == feed_name]
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs[:limit]
    
    def get_schedule_status(self) -> Dict[str, Any]:
        """Get status of all feed schedules."""
        return {
            feed_name: {
                "enabled": schedule.enabled,
                "last_run": schedule.last_run.isoformat() if schedule.last_run else None,
                "next_run": schedule.next_run.isoformat() if schedule.next_run else None,
                "success_count": schedule.success_count,
                "failure_count": schedule.failure_count,
                "should_run": schedule.should_run()
            }
            for feed_name, schedule in self.schedules.items()
        }
    
    def update_schedule(self, 
                       feed_name: str,
                       interval_minutes: Optional[int] = None,
                       enabled: Optional[bool] = None):
        """Update schedule for a feed."""
        schedule = self.schedules.get(feed_name)
        if not schedule:
            return False
        
        if interval_minutes is not None:
            schedule.interval = timedelta(minutes=interval_minutes)
        
        if enabled is not None:
            schedule.enabled = enabled
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics."""
        total_jobs = len(self.jobs)
        successful_jobs = sum(1 for j in self.jobs.values() if j.status == SyncStatus.SUCCESS)
        failed_jobs = sum(1 for j in self.jobs.values() if j.status == SyncStatus.FAILED)
        
        total_iocs_added = sum(j.iocs_added for j in self.jobs.values())
        total_iocs_updated = sum(j.iocs_updated for j in self.jobs.values())
        total_iocs_failed = sum(j.iocs_failed for j in self.jobs.values())
        
        return {
            "feeds_configured": len(self.feed_configs),
            "total_jobs": total_jobs,
            "successful_jobs": successful_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": successful_jobs / total_jobs if total_jobs > 0 else 0,
            "total_iocs_added": total_iocs_added,
            "total_iocs_updated": total_iocs_updated,
            "total_iocs_failed": total_iocs_failed,
            "dedup_cache_size": len(self._seen_hashes)
        }


# Global instance
_feed_sync: Optional[ThreatFeedSync] = None


def get_threat_feed_sync() -> ThreatFeedSync:
    """Get global threat feed sync instance."""
    global _feed_sync
    if _feed_sync is None:
        _feed_sync = ThreatFeedSync()
    return _feed_sync
