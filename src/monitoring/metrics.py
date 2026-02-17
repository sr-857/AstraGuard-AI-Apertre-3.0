import time
import psutil
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
)
from astraguard.observability import _safe_create_metric

# --- Application Start Time ---
START_TIME = time.time()

# --- Uptime Gauge ---
APP_UPTIME_SECONDS = _safe_create_metric(
    Gauge,
    "app_uptime_seconds",
    "Application uptime in seconds"
)

# --- HTTP Metrics ---
HTTP_REQUEST_COUNT = _safe_create_metric(
    Counter,
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status_code"]
)

HTTP_REQUEST_LATENCY = _safe_create_metric(
    Histogram,
    "http_request_latency_seconds",
    "HTTP request latency",
    labelnames=["method", "endpoint"]
)

# --- Active Requests ---
ACTIVE_REQUESTS = _safe_create_metric(
    Gauge,
    "http_active_requests",
    "Number of active HTTP requests"
)

# --- System Metrics ---
SYSTEM_CPU_USAGE = _safe_create_metric(
    Gauge,
    "system_cpu_usage_percent",
    "CPU usage percentage"
)

SYSTEM_MEMORY_USAGE = _safe_create_metric(
    Gauge,
    "system_memory_usage_percent",
    "Memory usage percentage"
)
