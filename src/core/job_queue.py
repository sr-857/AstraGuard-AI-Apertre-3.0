"""
Job Queue Monitoring for AstraGuard

Monitors job queue depth, wait times, and processing rates.
Alerts when queue depth exceeds thresholds.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class QueueStatus(str, Enum):
    """Queue health status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class QueueMetrics:
    """Queue metrics snapshot"""
    queue_depth: int
    avg_wait_time_seconds: float
    processing_rate_per_minute: float
    oldest_job_age_seconds: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "queue_depth": self.queue_depth,
            "avg_wait_time_seconds": round(self.avg_wait_time_seconds, 2),
            "processing_rate_per_minute": round(self.processing_rate_per_minute, 2),
            "oldest_job_age_seconds": round(self.oldest_job_age_seconds, 2),
            "timestamp": self.timestamp.isoformat()
        }


class JobQueue:
    """
    Monitor job queue depth and performance.
    
    Features:
    - Track queue depth over time
    - Calculate wait times and processing rates
    - Alert on queue depth thresholds
    - Historical metrics tracking
    """
    
    def __init__(
        self,
        warning_depth: int = 100,
        critical_depth: int = 500,
        metrics_window_minutes: int = 5
    ):
        """Initialize job queue monitor."""
        self.warning_depth = warning_depth
        self.critical_depth = critical_depth
        self.metrics_window = timedelta(minutes=metrics_window_minutes)
        
        self._queue: deque = deque()
        self._processed_count = 0
        self._metrics_history: deque = deque(maxlen=100)
        self._lock = threading.Lock()
        
        logger.info(
            f"JobQueue initialized: warning={warning_depth}, "
            f"critical={critical_depth}"
        )
    
    def enqueue(self, job_id: str, metadata: Optional[Dict] = None):
        """Add job to queue."""
        with self._lock:
            job = {
                "id": job_id,
                "enqueued_at": datetime.now(),
                "metadata": metadata or {}
            }
            self._queue.append(job)
            logger.debug(f"Job enqueued: {job_id}, depth: {len(self._queue)}")
    
    def dequeue(self) -> Optional[Dict]:
        """Remove and return next job from queue."""
        with self._lock:
            if self._queue:
                job = self._queue.popleft()
                self._processed_count += 1
                logger.debug(f"Job dequeued: {job['id']}")
                return job
            return None
    
    def get_metrics(self) -> QueueMetrics:
        """Get current queue metrics."""
        with self._lock:
            depth = len(self._queue)
            
            # Calculate average wait time
            now = datetime.now()
            if self._queue:
                wait_times = [
                    (now - job["enqueued_at"]).total_seconds()
                    for job in self._queue
                ]
                avg_wait = sum(wait_times) / len(wait_times)
                oldest_age = max(wait_times)
            else:
                avg_wait = 0.0
                oldest_age = 0.0
            
            # Calculate processing rate (jobs/minute)
            cutoff = now - self.metrics_window
            recent_metrics = [
                m for m in self._metrics_history
                if m.timestamp >= cutoff
            ]
            
            if len(recent_metrics) >= 2:
                time_span = (recent_metrics[-1].timestamp - recent_metrics[0].timestamp).total_seconds() / 60.0
                if time_span > 0:
                    processing_rate = self._processed_count / time_span
                else:
                    processing_rate = 0.0
            else:
                processing_rate = 0.0
            
            metrics = QueueMetrics(
                queue_depth=depth,
                avg_wait_time_seconds=avg_wait,
                processing_rate_per_minute=processing_rate,
                oldest_job_age_seconds=oldest_age
            )
            
            self._metrics_history.append(metrics)
            return metrics
    
    def get_status(self) -> QueueStatus:
        """Get queue health status based on depth."""
        metrics = self.get_metrics()
        
        if metrics.queue_depth >= self.critical_depth:
            logger.warning(f"Queue CRITICAL: depth={metrics.queue_depth}")
            return QueueStatus.CRITICAL
        elif metrics.queue_depth >= self.warning_depth:
            logger.info(f"Queue WARNING: depth={metrics.queue_depth}")
            return QueueStatus.WARNING
        else:
            return QueueStatus.HEALTHY
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        metrics = self.get_metrics()
        status = self.get_status()
        
        return {
            "current_metrics": metrics.to_dict(),
            "status": status.value,
            "total_processed": self._processed_count,
            "thresholds": {
                "warning_depth": self.warning_depth,
                "critical_depth": self.critical_depth
            }
        }


# Global singleton
_job_queue: Optional[JobQueue] = None
_queue_lock = threading.Lock()


def get_job_queue() -> JobQueue:
    """Get global job queue singleton."""
    global _job_queue
    if _job_queue is None:
        with _queue_lock:
            if _job_queue is None:
                _job_queue = JobQueue()
    return _job_queue
