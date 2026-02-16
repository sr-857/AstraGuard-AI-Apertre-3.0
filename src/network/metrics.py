"""
Network Layer Metrics (Prometheus)
Tracks latency, failure rates, and payload sizes.
"""

from prometheus_client import Summary, Counter, Histogram
import time
from functools import wraps

# Step 8: Network Metrics
# Using Histogram for Latency (better for quantiles/percentiles)
REQUEST_LATENCY = Histogram("network_request_latency_seconds", "Network request latency", ["method", "endpoint"])
REQUEST_FAILURES = Counter("network_request_failures_total", "Network request failures", ["method", "endpoint", "error_type"])
REQUEST_COUNT = Counter("network_requests_total", "Total network requests", ["method", "endpoint"])
PAYLOAD_SIZE = Histogram("network_payload_size_bytes", "Request payload size", ["direction"]) # inbound/outbound

def track_network_request(method: str, endpoint: str):
    """Decorator to track request latency and failures."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
            try:
                response = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(elapsed)

                # Check response size if available (approximation)
                if hasattr(response, 'content'):
                    size = len(response.content)
                    PAYLOAD_SIZE.labels(direction="inbound").observe(size)

                return response
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(elapsed)
                REQUEST_FAILURES.labels(method=method, endpoint=endpoint, error_type=type(e).__name__).inc()
                raise
        return wrapper
    return decorator
