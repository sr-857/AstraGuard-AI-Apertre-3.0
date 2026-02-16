"""
Background Job Scheduler for AstraGuard

Provides cron-style and interval-based job scheduling with persistence.
Supports async job execution and monitoring.
"""

import logging
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleType(str, Enum):
    """Type of schedule"""
    INTERVAL = "interval"  # Run every N seconds
    CRON = "cron"  # Cron-style schedule
    ONE_TIME = "one_time"  # Run once at specific time


@dataclass
class ScheduledJob:
    """Represents a scheduled job"""
    job_id: str
    name: str
    schedule_type: ScheduleType
    schedule_config: Dict[str, Any]
    handler: Callable
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "schedule_config": self.schedule_config,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "metadata": self.metadata
        }


class JobScheduler:
    """
    Background job scheduler with cron and interval support.
    
    Features:
    - Interval-based scheduling (run every N seconds)
    - Cron-style scheduling (future enhancement)
    - One-time scheduled jobs
    - Async job execution
    - Job cancellation
    """
    
    def __init__(self):
        """Initialize job scheduler."""
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._lock = threading.Lock()
        self._scheduler_task: Optional[asyncio.Task] = None
        
        logger.info("JobScheduler initialized")
    
    def schedule_interval(
        self,
        name: str,
        handler: Callable,
        interval_seconds: float,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Schedule a job to run at regular intervals.
        
        Args:
            name: Job name
            handler: Async function to execute
            interval_seconds: Interval between runs
            metadata: Optional job metadata
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        with self._lock:
            job = ScheduledJob(
                job_id=job_id,
                name=name,
                schedule_type=ScheduleType.INTERVAL,
                schedule_config={"interval_seconds": interval_seconds},
                handler=handler,
                next_run=datetime.now() + timedelta(seconds=interval_seconds),
                metadata=metadata or {}
            )
            self._jobs[job_id] = job
        
        logger.info(f"Scheduled interval job: {name} ({job_id}), interval={interval_seconds}s")
        return job_id
    
    def schedule_one_time(
        self,
        name: str,
        handler: Callable,
        run_at: datetime,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Schedule a one-time job.
        
        Args:
            name: Job name
            handler: Async function to execute
            run_at: When to run the job
            metadata: Optional job metadata
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        with self._lock:
            job = ScheduledJob(
                job_id=job_id,
                name=name,
                schedule_type=ScheduleType.ONE_TIME,
                schedule_config={"run_at": run_at.isoformat()},
                handler=handler,
                next_run=run_at,
                metadata=metadata or {}
            )
            self._jobs[job_id] = job
        
        logger.info(f"Scheduled one-time job: {name} ({job_id}), run_at={run_at}")
        return job_id
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a scheduled job.
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = JobStatus.CANCELLED
                logger.info(f"Job cancelled: {job_id}")
                return True
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details."""
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job else None
    
    def list_jobs(self, status: Optional[JobStatus] = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally filtered by status."""
        with self._lock:
            jobs = self._jobs.values()
            if status:
                jobs = [j for j in jobs if j.status == status]
            return [j.to_dict() for j in jobs]
    
    async def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        self._running = True
        logger.info("Scheduler started")
        
        while self._running:
            try:
                await self._process_jobs()
                await asyncio.sleep(1)  # Check every second
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False
        logger.info("Scheduler stopped")
    
    async def _process_jobs(self):
        """Process due jobs."""
        now = datetime.now()
        
        with self._lock:
            jobs_to_run = [
                job for job in self._jobs.values()
                if job.status not in [JobStatus.CANCELLED, JobStatus.RUNNING]
                and job.next_run and job.next_run <= now
            ]
        
        for job in jobs_to_run:
            asyncio.create_task(self._execute_job(job))
    
    async def _execute_job(self, job: ScheduledJob):
        """Execute a job."""
        try:
            with self._lock:
                job.status = JobStatus.RUNNING
            
            logger.info(f"Executing job: {job.name} ({job.job_id})")
            
            # Execute handler
            if asyncio.iscoroutinefunction(job.handler):
                await job.handler()
            else:
                await asyncio.to_thread(job.handler)
            
            with self._lock:
                job.status = JobStatus.COMPLETED
                job.last_run = datetime.now()
                job.run_count += 1
                
                # Schedule next run for interval jobs
                if job.schedule_type == ScheduleType.INTERVAL:
                    interval = job.schedule_config["interval_seconds"]
                    job.next_run = datetime.now() + timedelta(seconds=interval)
                    job.status = JobStatus.PENDING
                elif job.schedule_type == ScheduleType.ONE_TIME:
                    job.next_run = None
            
            logger.info(f"Job completed: {job.name} ({job.job_id})")
            
        except Exception as e:
            logger.error(f"Job failed: {job.name} ({job.job_id}), error: {e}")
            with self._lock:
                job.status = JobStatus.FAILED


# Global singleton
_job_scheduler: Optional[JobScheduler] = None
_scheduler_lock = threading.Lock()


def get_job_scheduler() -> JobScheduler:
    """Get global job scheduler singleton."""
    global _job_scheduler
    if _job_scheduler is None:
        with _scheduler_lock:
            if _job_scheduler is None:
                _job_scheduler = JobScheduler()
    return _job_scheduler
