"""
Health Check Protocol and Common Check Implementations

Provides:
- HealthCheck protocol for defining checks
- Common health check helpers (Redis, downstream service, disk space)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class HealthCheckStatus(str, Enum):
    """Status values for health checks."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check execution."""
    name: str
    status: HealthCheckStatus
    message: str = ""
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@runtime_checkable
class HealthCheck(Protocol):
    """Protocol for health checks.

    Implementations should provide a check() method that returns
    a HealthCheckResult with the current health status.
    """

    @property
    def name(self) -> str:
        """Name of the health check."""
        ...

    async def check(self) -> HealthCheckResult:
        """Execute the health check and return result."""
        ...


class BaseHealthCheck(ABC):
    """Base class for health checks with common functionality."""

    def __init__(self, name: str, timeout_seconds: float = 5.0):
        self._name = name
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    async def _perform_check(self) -> HealthCheckResult:
        """Perform the actual health check."""
        ...

    async def check(self) -> HealthCheckResult:
        """Execute the health check with timeout handling."""
        start_time = datetime.utcnow()
        try:
            result = await asyncio.wait_for(
                self._perform_check(),
                timeout=self.timeout_seconds
            )
            # Update latency
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result.latency_ms = latency_ms
            return result
        except asyncio.TimeoutError:
            latency_ms = self.timeout_seconds * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout_seconds}s",
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.warning(f"Health check {self.name} failed: {e}")
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.UNHEALTHY,
                message=str(e),
                latency_ms=latency_ms,
            )


class RedisHealthCheck(BaseHealthCheck):
    """Health check for Redis connection."""

    def __init__(
        self,
        redis_client: Any,
        name: str = "redis",
        timeout_seconds: float = 2.0
    ):
        super().__init__(name, timeout_seconds)
        self.redis_client = redis_client

    async def _perform_check(self) -> HealthCheckResult:
        """Ping Redis and check connection."""
        try:
            if hasattr(self.redis_client, 'ping'):
                await self.redis_client.ping()
            elif hasattr(self.redis_client, 'get'):
                # Fallback: try a simple get
                await self.redis_client.get("__health_check__")

            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.HEALTHY,
                message="Redis connection healthy",
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.UNHEALTHY,
                message=f"Redis connection failed: {e}",
            )


class DownstreamServiceCheck(BaseHealthCheck):
    """Health check for downstream HTTP services."""

    def __init__(
        self,
        url: str,
        name: str = "downstream",
        timeout_seconds: float = 5.0,
        expected_status: int = 200
    ):
        super().__init__(name, timeout_seconds)
        self.url = url
        self.expected_status = expected_status

    async def _perform_check(self) -> HealthCheckResult:
        """Ping downstream service via HTTP."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
                ) as response:
                    if response.status == self.expected_status:
                        return HealthCheckResult(
                            name=self.name,
                            status=HealthCheckStatus.HEALTHY,
                            message=f"Downstream service healthy (status={response.status})",
                            metadata={"url": self.url, "status_code": response.status},
                        )
                    else:
                        return HealthCheckResult(
                            name=self.name,
                            status=HealthCheckStatus.DEGRADED,
                            message=f"Unexpected status code: {response.status}",
                            metadata={"url": self.url, "status_code": response.status},
                        )
        except ImportError:
            # aiohttp not available, try httpx
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.url, timeout=self.timeout_seconds)
                    if response.status_code == self.expected_status:
                        return HealthCheckResult(
                            name=self.name,
                            status=HealthCheckStatus.HEALTHY,
                            message=f"Downstream service healthy (status={response.status_code})",
                            metadata={"url": self.url, "status_code": response.status_code},
                        )
                    else:
                        return HealthCheckResult(
                            name=self.name,
                            status=HealthCheckStatus.DEGRADED,
                            message=f"Unexpected status code: {response.status_code}",
                            metadata={"url": self.url, "status_code": response.status_code},
                        )
            except ImportError:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthCheckStatus.UNKNOWN,
                    message="No HTTP client available (install aiohttp or httpx)",
                )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.UNHEALTHY,
                message=f"Downstream service check failed: {e}",
                metadata={"url": self.url},
            )


class DiskSpaceCheck(BaseHealthCheck):
    """Health check for disk space availability."""

    def __init__(
        self,
        path: str = "/",
        name: str = "disk",
        warning_threshold_percent: float = 80.0,
        critical_threshold_percent: float = 95.0,
        timeout_seconds: float = 2.0
    ):
        super().__init__(name, timeout_seconds)
        self.path = path
        self.warning_threshold = warning_threshold_percent
        self.critical_threshold = critical_threshold_percent

    async def _perform_check(self) -> HealthCheckResult:
        """Check disk space usage."""
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.path)
            usage_percent = (used / total) * 100

            metadata = {
                "path": self.path,
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "usage_percent": round(usage_percent, 2),
            }

            if usage_percent >= self.critical_threshold:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthCheckStatus.UNHEALTHY,
                    message=f"Disk usage critical: {usage_percent:.1f}%",
                    metadata=metadata,
                )
            elif usage_percent >= self.warning_threshold:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthCheckStatus.DEGRADED,
                    message=f"Disk usage warning: {usage_percent:.1f}%",
                    metadata=metadata,
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthCheckStatus.HEALTHY,
                    message=f"Disk usage healthy: {usage_percent:.1f}%",
                    metadata=metadata,
                )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.UNKNOWN,
                message=f"Failed to check disk space: {e}",
            )


class ComponentHealthCheck(BaseHealthCheck):
    """Wrap existing component health tracking as a health check."""

    def __init__(
        self,
        component_name: str,
        health_monitor: Any,
        name: Optional[str] = None,
        timeout_seconds: float = 1.0
    ):
        super().__init__(name or component_name, timeout_seconds)
        self.component_name = component_name
        self.health_monitor = health_monitor

    async def _perform_check(self) -> HealthCheckResult:
        """Get health status from component health monitor."""
        try:
            from core.component_health import HealthStatus
            
            health = self.health_monitor.get_component_health(self.component_name)
            
            # Map HealthStatus to HealthCheckStatus
            status_map = {
                HealthStatus.HEALTHY: HealthCheckStatus.HEALTHY,
                HealthStatus.DEGRADED: HealthCheckStatus.DEGRADED,
                HealthStatus.FAILED: HealthCheckStatus.UNHEALTHY,
                HealthStatus.UNKNOWN: HealthCheckStatus.UNKNOWN,
            }
            
            check_status = status_map.get(health.status, HealthCheckStatus.UNKNOWN)
            
            return HealthCheckResult(
                name=self.name,
                status=check_status,
                message=health.last_error or f"Component status: {health.status.value}",
                metadata={
                    "error_count": health.error_count,
                    "warning_count": health.warning_count,
                    "fallback_active": health.fallback_active,
                },
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.UNKNOWN,
                message=f"Failed to get component health: {e}",
            )
