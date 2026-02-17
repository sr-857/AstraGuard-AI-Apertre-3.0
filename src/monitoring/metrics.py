import time
import psutil
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    REGISTRY
)

def _safe_create_metric(metric_class, name, documentation, labels=None):
    """Safely create a metric, returning existing one if it's already registered."""
    try:
        if labels:
            return metric_class(name, documentation, labels)
        return metric_class(name, documentation)
    except ValueError:
        # If duplicated, find it in registry (hacky but effective for tests)
        # In a real app, we should avoid re-importing this module.
        # But unit tests often reload modules.
        # This is a simplified fallback; actual retrieval from registry is complex
        # because the registry API doesn't expose a simple "get by name".
        # We will assume that if it fails, it's because of duplication, and we
        # can't easily retrieve the original object without more hacks.
        # So we just suppress the error if possible, or re-raise if we can't handle it.
        # However, for CI stability, let's try to unregister first? No, that's racey.

        # Better approach: Check if it's already registered by iterating registry
        for collector in REGISTRY._collector_to_names:
            if name in REGISTRY._collector_to_names[collector]:
                return collector

        # If we can't find it but it failed, maybe we should just create it
        # with a new registry? No, we want the global one.
        # Let's try to unregister strictly by name if we can.
        # Actually, prometheus_client 0.21.0 doesn't support 'get'.

        # Fallback: Just return a dummy or the existing one if we can find it.
        pass
    return None # Should not happen if logic is correct, but effectively swallows error

# Helper to avoid duplication
def create_or_get(cls, name, doc, labels=()):
    try:
        return cls(name, doc, labels)
    except ValueError:
        # Already registered
        pass

    # Try to find it
    for c in REGISTRY._collector_to_names:
        if name in REGISTRY._collector_to_names[c]:
            return c

    # Should not reach here if ValueError was raised
    return cls(name, doc, labels)

# --- Application Start Time ---
START_TIME = time.time()

# --- Uptime Gauge ---
APP_UPTIME_SECONDS = create_or_get(
    Gauge,
    "app_uptime_seconds",
    "Application uptime in seconds"
)

# --- HTTP Metrics ---
HTTP_REQUEST_COUNT = create_or_get(
    Counter,
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

HTTP_REQUEST_LATENCY = create_or_get(
    Histogram,
    "http_request_latency_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

# --- Active Requests ---
ACTIVE_REQUESTS = create_or_get(
    Gauge,
    "http_active_requests",
    "Number of active HTTP requests"
)

# --- System Metrics ---
SYSTEM_CPU_USAGE = create_or_get(
    Gauge,
    "system_cpu_usage_percent",
    "CPU usage percentage"
)

SYSTEM_MEMORY_USAGE = create_or_get(
    Gauge,
    "system_memory_usage_percent",
    "Memory usage percentage"
)
