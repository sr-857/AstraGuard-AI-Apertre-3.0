import time
import psutil
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
)

# --- Application Start Time ---
START_TIME = time.time()

# --- Uptime Gauge ---
APP_UPTIME_SECONDS = Gauge(
    "app_uptime_seconds",
    "Application uptime in seconds"
)

# --- HTTP Metrics ---
HTTP_REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

HTTP_REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

# --- Active Requests ---
ACTIVE_REQUESTS = Gauge(
    "http_active_requests",
    "Number of active HTTP requests"
)

# --- System Metrics ---
SYSTEM_CPU_USAGE = Gauge(
    "system_cpu_usage_percent",
    "CPU usage percentage"
)

SYSTEM_MEMORY_USAGE = Gauge(
    "system_memory_usage_percent",
    "Memory usage percentage"
)
