"""
Metrics and monitoring for database connection pooling.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """Tracks connection pool metrics."""
    
    total_connections_created: int = 0
    total_acquisitions: int = 0
    total_releases: int = 0
    total_timeouts: int = 0
    total_errors: int = 0
    acquisition_times: List[float] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    
    async def record_acquisition(self, wait_time: float) -> None:
        """
        Record a successful connection acquisition.
        
        Args:
            wait_time: Time in seconds waited for connection
        """
        async with self._lock:
            self.total_acquisitions += 1
            self.acquisition_times.append(wait_time)
            
            # Keep only last 1000 acquisition times to prevent memory growth
            if len(self.acquisition_times) > 1000:
                self.acquisition_times = self.acquisition_times[-1000:]
    
    async def record_timeout(self) -> None:
        """Record a connection acquisition timeout."""
        async with self._lock:
            self.total_timeouts += 1
    
    async def record_error(self) -> None:
        """Record a connection error."""
        async with self._lock:
            self.total_errors += 1
    
    async def record_connection_created(self) -> None:
        """Record a new connection creation."""
        async with self._lock:
            self.total_connections_created += 1
    
    async def record_release(self) -> None:
        """Record a connection release."""
        async with self._lock:
            self.total_releases += 1
    
    async def get_average_wait_time(self) -> float:
        """
        Calculate average connection wait time.
        
        Returns:
            Average wait time in seconds, or 0.0 if no acquisitions
        """
        async with self._lock:
            if not self.acquisition_times:
                return 0.0
            return sum(self.acquisition_times) / len(self.acquisition_times)


@dataclass
class PoolStats:
    """Current pool statistics snapshot."""
    
    active_connections: int
    idle_connections: int
    total_connections: int
    max_size: int
    total_created: int
    total_timeouts: int
    average_wait_time: float
    total_acquisitions: int = 0
    total_releases: int = 0
    total_errors: int = 0
