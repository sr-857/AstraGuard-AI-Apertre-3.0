"""Monitoring integrations package - Compatibility Shim

DEPRECATED: This module is maintained for backward compatibility.
Please use `backend.health.integrations` instead for new code.

Example migration:
    # OLD (deprecated)
    from backend.monitoring_integrations import DatadogAdapter
    
    # NEW (recommended)  
    from backend.health.integrations import DatadogAdapter

Pluggable adapters for external monitoring systems (Datadog, New Relic, etc.)
"""

import warnings

# Issue deprecation warning on import
warnings.warn(
    "backend.monitoring_integrations is deprecated. Use backend.health.integrations instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from new location for backward compatibility
from backend.health.integrations import (
    MonitoringAdapter,
    AdapterParseError,
    DatadogAdapter,
    NewRelicAdapter,
    router,
)

__all__ = [
    "MonitoringAdapter",
    "AdapterParseError",
    "DatadogAdapter",
    "NewRelicAdapter",
    "router",
]
