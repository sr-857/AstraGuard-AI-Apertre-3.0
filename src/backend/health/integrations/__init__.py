"""
Monitoring Integrations Package

Provides adapters for external monitoring systems:
- MonitoringAdapter: Base class for adapters
- DatadogAdapter: Datadog webhook adapter
- NewRelicAdapter: New Relic webhook adapter
- router: FastAPI router for webhook endpoints
"""

from backend.health.integrations.base import MonitoringAdapter, AdapterParseError
from backend.health.integrations.datadog import DatadogAdapter
from backend.health.integrations.newrelic import NewRelicAdapter
from backend.health.integrations.router import router

__all__ = [
    "MonitoringAdapter",
    "AdapterParseError",
    "DatadogAdapter",
    "NewRelicAdapter",
    "router",
]
