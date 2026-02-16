"""
Job Failure Handling for AstraGuard

Implements retry logic with exponential backoff and dead letter queue for failed jobs.
Tracks failure history and provides failure analytics.
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


class FailureReason(str, Enum):
    """Reasons for job failure"""
    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"


@dataclass
class JobFailure:
    """Record of a job failure"""
    failure_id: str
    job_id: str
    job_name: str
    reason: FailureReason
    error_message: str
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "job_id": self.job_id,
            "job_name": self.job_name,
            "reason": self.reason.value,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "metadata": self.metadata
        }


class JobFailureHandler:
    """
    Handle job failures with retry logic and dead letter queue.
    
    Features:
    - Exponential backoff retry strategy
    - Configurable max retries
    - Dead letter queue for permanently failed jobs
    - Failure analytics and reporting
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_retry_delay_seconds: float = 1.0,
        max_retry_delay_seconds: float = 60.0,
        backoff_multiplier: float = 2.0
    ):
        """Initialize failure handler."""
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay_seconds
        self.max_retry_delay = max_retry_delay_seconds
        self.backoff_multiplier = backoff_multiplier
        
        self._failures: Dict[str, JobFailure] = {}
        self._dead_letter_queue: List[JobFailure] = []
        self._lock = threading.Lock()
        
        logger.info(
            f"JobFailureHandler initialized: max_retries={max_retries}, "
            f"initial_delay={initial_retry_delay_seconds}s"
        )
    
    async def handle_failure(
        self,
        job_id: str,
        job_name: str,
        handler: Callable,
        error: Exception,
        reason: FailureReason = FailureReason.EXCEPTION,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Handle a job failure with retry logic.
        
        Args:
            job_id: Job identifier
            job_name: Job name
            handler: Job handler function to retry
            error: The exception that occurred
            reason: Failure reason
            metadata: Optional failure metadata
            
        Returns:
            True if retry succeeded, False if moved to dead letter queue
        """
        failure_id = str(uuid.uuid4())
        
        with self._lock:
            # Check if we've seen this job before
            existing_failure = self._failures.get(job_id)
            retry_count = existing_failure.retry_count + 1 if existing_failure else 0
            
            failure = JobFailure(
                failure_id=failure_id,
                job_id=job_id,
                job_name=job_name,
                reason=reason,
                error_message=str(error),
                retry_count=retry_count,
                metadata=metadata or {}
            )
            self._failures[job_id] = failure
        
        logger.warning(
            f"Job failed: {job_name} ({job_id}), "
            f"retry {retry_count}/{self.max_retries}, "
            f"reason: {reason.value}, error: {error}"
        )
        
        # Check if we should retry
        if retry_count < self.max_retries:
            # Calculate retry delay with exponential backoff
            delay = min(
                self.initial_retry_delay * (self.backoff_multiplier ** retry_count),
                self.max_retry_delay
            )
            
            logger.info(f"Retrying job {job_name} in {delay:.2f}s")
            await asyncio.sleep(delay)
            
            try:
                # Retry the job
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    await asyncio.to_thread(handler)
                
                logger.info(f"Job retry succeeded: {job_name} ({job_id})")
                
                # Remove from failures on success
                with self._lock:
                    if job_id in self._failures:
                        del self._failures[job_id]
                
                return True
                
            except Exception as retry_error:
                logger.error(f"Job retry failed: {job_name}, error: {retry_error}")
                return await self.handle_failure(
                    job_id, job_name, handler, retry_error, reason, metadata
                )
        else:
            # Max retries exceeded, move to dead letter queue
            logger.error(
                f"Job permanently failed after {retry_count} retries: "
                f"{job_name} ({job_id})"
            )
            
            with self._lock:
                self._dead_letter_queue.append(failure)
                if job_id in self._failures:
                    del self._failures[job_id]
            
            return False
    
    def get_failure(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get failure details for a job."""
        with self._lock:
            failure = self._failures.get(job_id)
            return failure.to_dict() if failure else None
    
    def get_dead_letter_queue(self) -> List[Dict[str, Any]]:
        """Get all permanently failed jobs."""
        with self._lock:
            return [f.to_dict() for f in self._dead_letter_queue]
    
    def get_failure_statistics(self) -> Dict[str, Any]:
        """Get failure statistics."""
        with self._lock:
            total_failures = len(self._failures)
            dead_letter_count = len(self._dead_letter_queue)
            
            # Count failures by reason
            reason_counts = {}
            for failure in self._failures.values():
                reason = failure.reason.value
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            
            return {
                "active_failures": total_failures,
                "dead_letter_queue_size": dead_letter_count,
                "failures_by_reason": reason_counts,
                "max_retries": self.max_retries
            }
    
    def clear_dead_letter_queue(self):
        """Clear the dead letter queue."""
        with self._lock:
            count = len(self._dead_letter_queue)
            self._dead_letter_queue.clear()
            logger.info(f"Cleared {count} items from dead letter queue")


# Global singleton
_failure_handler: Optional[JobFailureHandler] = None
_handler_lock = threading.Lock()


def get_failure_handler() -> JobFailureHandler:
    """Get global failure handler singleton."""
    global _failure_handler
    if _failure_handler is None:
        with _handler_lock:
            if _failure_handler is None:
                _failure_handler = JobFailureHandler()
    return _failure_handler
