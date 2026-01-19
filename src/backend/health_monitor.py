"""
Health Monitor API & Observability - Compatibility Shim

DEPRECATED: This module is maintained for backward compatibility.
Please use `backend.health` instead for new code.

Example migration:
    # OLD (deprecated)
    from backend.health_monitor import HealthMonitor, FallbackMode
    
    # NEW (recommended)
    from backend.health import HealthMonitor, FallbackMode
"""

import warnings

# Issue deprecation warning on import
warnings.warn(
    "backend.health_monitor is deprecated. Use backend.health instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from new location for backward compatibility
from backend.health.monitor import (
    HealthMonitor,
    FallbackMode,
    router,
    set_health_monitor,
    get_health_monitor,
    prometheus_metrics,
    health_state,
    trigger_cascade,
    readiness_check,
    liveness_check,
    FALLBACK_MODE_GAUGE,
    HEALTH_CHECK_DURATION,
)

__all__ = [
    "HealthMonitor",
    "FallbackMode",
    "router",
    "set_health_monitor",
    "get_health_monitor",
    "prometheus_metrics",
    "health_state",
    "trigger_cascade",
    "readiness_check",
    "liveness_check",
    "FALLBACK_MODE_GAUGE",
    "HEALTH_CHECK_DURATION",
]
