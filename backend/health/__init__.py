"""
Health Monitor & Monitoring Integrations Package

Provides centralized health monitoring with pluggable abstractions:
- HealthCheck: Protocol for defining health checks
- MetricsSink: Interface for metric emission
- HealthMonitor: Aggregates checks and exposes status

Example usage:
    from backend.health import HealthMonitor, NoOpMetricsSink, HealthCheckResult
    
    monitor = HealthMonitor(metrics_sink=NoOpMetricsSink())
    status = await monitor.get_comprehensive_state()
"""

from backend.health.checks import (
    HealthCheck,
    HealthCheckResult,
    HealthCheckStatus,
    RedisHealthCheck,
    DownstreamServiceCheck,
    DiskSpaceCheck,
    ComponentHealthCheck,
)
from backend.health.sinks import (
    MetricsSink,
    NoOpMetricsSink,
    LoggingMetricsSink,
    PrometheusMetricsSink,
)
from backend.health.monitor import (
    HealthMonitor,
    FallbackMode,
    router,
    set_health_monitor,
    get_health_monitor,
)

__all__ = [
    # Checks
    "HealthCheck",
    "HealthCheckResult",
    "HealthCheckStatus",
    "RedisHealthCheck",
    "DownstreamServiceCheck",
    "DiskSpaceCheck",
    "ComponentHealthCheck",
    # Sinks
    "MetricsSink",
    "NoOpMetricsSink",
    "LoggingMetricsSink",
    "PrometheusMetricsSink",
    # Monitor
    "HealthMonitor",
    "FallbackMode",
    "router",
    "set_health_monitor",
    "get_health_monitor",
]
