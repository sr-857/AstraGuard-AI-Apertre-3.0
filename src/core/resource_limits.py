"""
Resource Limit Enforcement for AstraGuard

Enforces configurable resource limits to prevent resource exhaustion.
Provides quotas for CPU, memory, and connections.
"""

import logging
import psutil
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    """Types of resources that can be limited"""
    CPU = "cpu"
    MEMORY = "memory"
    CONNECTIONS = "connections"


@dataclass
class ResourceQuota:
    """Resource quota configuration"""
    max_cpu_percent: float = 80.0  # Max CPU usage allowed
    max_memory_mb: float = 1024.0  # Max memory in MB
    max_connections: int = 100  # Max concurrent connections
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_cpu_percent": self.max_cpu_percent,
            "max_memory_mb": self.max_memory_mb,
            "max_connections": self.max_connections
        }


class ResourceLimitExceeded(Exception):
    """Raised when a resource limit is exceeded"""
    def __init__(self, resource_type: ResourceType, current: float, limit: float):
        self.resource_type = resource_type
        self.current = current
        self.limit = limit
        super().__init__(
            f"{resource_type.value} limit exceeded: {current:.2f} > {limit:.2f}"
        )


class ResourceLimiter:
    """
    Enforce resource limits to prevent exhaustion.
    
    Features:
    - Configurable CPU, memory, and connection quotas
    - Pre-operation limit checking
    - Automatic rejection when limits exceeded
    - Thread-safe operation
    """
    
    def __init__(self, quota: Optional[ResourceQuota] = None):
        """
        Initialize resource limiter.
        
        Args:
            quota: Resource quota configuration (uses defaults if None)
        """
        self.quota = quota or ResourceQuota()
        self._active_connections = 0
        self._connection_lock = threading.Lock()
        self._process = psutil.Process()
        
        logger.info(
            f"ResourceLimiter initialized: "
            f"CPU={self.quota.max_cpu_percent}%, "
            f"Memory={self.quota.max_memory_mb}MB, "
            f"Connections={self.quota.max_connections}"
        )
    
    def check_cpu_limit(self) -> bool:
        """
        Check if CPU usage is within limits.
        
        Returns:
            True if within limits
            
        Raises:
            ResourceLimitExceeded: If CPU limit exceeded
        """
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        if cpu_percent > self.quota.max_cpu_percent:
            logger.warning(
                f"CPU limit exceeded: {cpu_percent:.1f}% > {self.quota.max_cpu_percent}%"
            )
            raise ResourceLimitExceeded(
                ResourceType.CPU,
                cpu_percent,
                self.quota.max_cpu_percent
            )
        
        return True
    
    def check_memory_limit(self) -> bool:
        """
        Check if memory usage is within limits.
        
        Returns:
            True if within limits
            
        Raises:
            ResourceLimitExceeded: If memory limit exceeded
        """
        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        
        if memory_mb > self.quota.max_memory_mb:
            logger.warning(
                f"Memory limit exceeded: {memory_mb:.1f}MB > {self.quota.max_memory_mb}MB"
            )
            raise ResourceLimitExceeded(
                ResourceType.MEMORY,
                memory_mb,
                self.quota.max_memory_mb
            )
        
        return True
    
    def check_connection_limit(self) -> bool:
        """
        Check if connection count is within limits.
        
        Returns:
            True if within limits
            
        Raises:
            ResourceLimitExceeded: If connection limit exceeded
        """
        with self._connection_lock:
            if self._active_connections >= self.quota.max_connections:
                logger.warning(
                    f"Connection limit exceeded: "
                    f"{self._active_connections} >= {self.quota.max_connections}"
                )
                raise ResourceLimitExceeded(
                    ResourceType.CONNECTIONS,
                    self._active_connections,
                    self.quota.max_connections
                )
        
        return True
    
    def check_all_limits(self) -> bool:
        """
        Check all resource limits.
        
        Returns:
            True if all limits are satisfied
            
        Raises:
            ResourceLimitExceeded: If any limit is exceeded
        """
        self.check_cpu_limit()
        self.check_memory_limit()
        self.check_connection_limit()
        return True
    
    def acquire_connection(self) -> None:
        """
        Acquire a connection slot.
        
        Raises:
            ResourceLimitExceeded: If connection limit exceeded
        """
        self.check_connection_limit()
        with self._connection_lock:
            self._active_connections += 1
            logger.debug(f"Connection acquired: {self._active_connections}/{self.quota.max_connections}")
    
    def release_connection(self) -> None:
        """Release a connection slot."""
        with self._connection_lock:
            if self._active_connections > 0:
                self._active_connections -= 1
                logger.debug(f"Connection released: {self._active_connections}/{self.quota.max_connections}")
    
    def get_current_usage(self) -> Dict[str, Any]:
        """
        Get current resource usage.
        
        Returns:
            Dictionary with current usage and limits
        """
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        
        with self._connection_lock:
            connections = self._active_connections
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "current_percent": round(cpu_percent, 2),
                "limit_percent": self.quota.max_cpu_percent,
                "usage_ratio": round(cpu_percent / self.quota.max_cpu_percent, 2)
            },
            "memory": {
                "current_mb": round(memory_mb, 2),
                "limit_mb": self.quota.max_memory_mb,
                "usage_ratio": round(memory_mb / self.quota.max_memory_mb, 2)
            },
            "connections": {
                "current": connections,
                "limit": self.quota.max_connections,
                "usage_ratio": round(connections / self.quota.max_connections, 2) if self.quota.max_connections > 0 else 0
            }
        }
    
    def update_quota(self, quota: ResourceQuota) -> None:
        """
        Update resource quota configuration.
        
        Args:
            quota: New quota configuration
        """
        self.quota = quota
        logger.info(
            f"Resource quota updated: "
            f"CPU={quota.max_cpu_percent}%, "
            f"Memory={quota.max_memory_mb}MB, "
            f"Connections={quota.max_connections}"
        )


# Global singleton instance
_resource_limiter: Optional[ResourceLimiter] = None
_limiter_lock = threading.Lock()


def get_resource_limiter() -> ResourceLimiter:
    """
    Get global resource limiter singleton.
    
    Returns:
        ResourceLimiter instance
    """
    global _resource_limiter
    
    if _resource_limiter is None:
        with _limiter_lock:
            if _resource_limiter is None:
                _resource_limiter = ResourceLimiter()
    
    return _resource_limiter
