"""
AstraGuard Prometheus Metrics Module
Core business and reliability metrics for production monitoring
"""

from prometheus_client import (
    Counter, Histogram, Gauge, Summary,
    start_http_server, REGISTRY, CollectorRegistry
)
from contextlib import contextmanager, asynccontextmanager
import time
import logging
import asyncio
from typing import Optional, Dict, Any, Generator, AsyncGenerator, cast
from prometheus_client.metrics_core import MetricWrapperBase
import socket
import errno

logger: logging.Logger = logging.getLogger(__name__)

# Cache for metrics to avoid repeated registry lookups
# NOTE: Bounded to prevent unbounded memory growth in long-running services.
# Label cardinality must be bounded and safe for production use.
_metric_cache: Dict[str, Any] = {}
_MAX_METRIC_CACHE_SIZE = 1000  # Maximum number of metrics to cache

# Cache for labeled metrics to avoid repeated label object creation
# Key: (id(metric), tuple(sorted(label_items)))
# Value: labeled_metric
# NOTE: Bounded cache with LRU eviction to prevent memory exhaustion.
# Label cardinality must be bounded and safe for production use.
_labeled_metric_cache: Dict[tuple, Any] = {}
_MAX_LABELED_CACHE_SIZE = 5000  # Maximum number of labeled metrics to cache



def _get_cached_labels(metric: Any, **labels: Any) -> Any:
    """
    Get or create a cached labeled metric to avoid repeated label object creation.
    
    Args:
        metric: The base metric object (e.g., Histogram, Counter)
        **labels: Label key-value pairs
        
    Returns:
        The labeled metric object
        
    Note:
        Cache key includes both label names and values to prevent collisions
        when different label sets share the same values.
    """
    # Create a hashable key from metric id and label name-value pairs
    # Use items() to include both names and values, preventing collisions
    label_items = tuple(sorted(labels.items()))
    cache_key = (id(metric), label_items)
    
    # Check cache size and evict if necessary (simple LRU-like behavior)
    if len(_labeled_metric_cache) >= _MAX_LABELED_CACHE_SIZE:
        # Remove oldest entry (first key)
        try:
            oldest_key = next(iter(_labeled_metric_cache))
            del _labeled_metric_cache[oldest_key]
        except StopIteration:
            pass
    
    if cache_key not in _labeled_metric_cache:
        _labeled_metric_cache[cache_key] = metric.labels(**labels)
    
    return _labeled_metric_cache[cache_key]



# Cache for labeled metrics to avoid repeated label object creation
# Key: (id(metric), tuple(sorted(label_values)))
# Value: labeled_metric
_labeled_metric_cache: Dict[tuple, Any] = {}


def _get_cached_labels(metric: Any, **labels: Any) -> Any:
    """
    Get or create a cached labeled metric to avoid repeated label object creation.
    
    Args:
        metric: The base metric object (e.g., Histogram, Counter)
        **labels: Label key-value pairs
        
    Returns:
        The labeled metric object
    """
    # Create a hashable key from metric id and label values
    label_values = tuple(sorted(labels.values()))
    cache_key = (id(metric), label_values)
    
    if cache_key not in _labeled_metric_cache:
        _labeled_metric_cache[cache_key] = metric.labels(**labels)
    
    return _labeled_metric_cache[cache_key]


# ============================================================================
# SAFE METRIC INITIALIZATION (handles test reruns gracefully)
# ============================================================================

def _safe_create_metric(
    metric_class: Any,
    name: str,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Safely create metrics, handling duplicate registration in tests"""
    # Check cache first
    if name in _metric_cache:
        return _metric_cache[name]

    # Check cache size and evict if necessary
    if len(_metric_cache) >= _MAX_METRIC_CACHE_SIZE:
        try:
            oldest_key = next(iter(_metric_cache))
            del _metric_cache[oldest_key]
        except StopIteration:
            pass

    try:
        metric = metric_class(*args, **kwargs)
        _metric_cache[name] = metric  # Cache the metric
        return metric
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            logger.warning(f"Metric {name} already exists, attempting to retrieve from registry")
            
            # OPTIMIZED: Use internal registry dict for O(1) lookup instead of O(n) iteration
            if hasattr(REGISTRY, '_names_to_collectors'):
                collector = REGISTRY._names_to_collectors.get(name)
                if collector:
                    _metric_cache[name] = collector  # Cache it
                    return collector
            
            # Fallback to iteration (if internal API changes or name not in dict)
            for collector in REGISTRY._collector_to_names:
                if hasattr(collector, '_name') and collector._name == name:
                    _metric_cache[name] = collector  # Cache it
                    return collector
                if hasattr(collector, '_metrics'):
                    for metric_name, metric_obj in collector._metrics.items():
                        if metric_name == name:
                            _metric_cache[name] = metric_obj  # Cache it
                            return metric_obj
            
            # If not found in registry, log error and create with new registry
            logger.error(f"Metric {name} not found in registry after duplicate error, creating new")
            try:
                metric = metric_class(*args, **kwargs)
                _metric_cache[name] = metric  # Cache it
                return metric
            except (ValueError, AttributeError, TypeError) as inner_e:
                logger.error(
                    f"Failed to create metric {name} with new registry: {inner_e}",
                    exc_info=True,
                    extra={"metric_name": name, "metric_class": metric_class.__name__}
                )
                raise
            except Exception as inner_e:
                logger.critical(
                    f"Unexpected error creating metric {name}: {inner_e}",
                    exc_info=True
                )
                raise
        else:
            logger.error(f"ValueError creating metric {name}: {e}")
            raise


# ============================================================================
# CORE HTTP METRICS
# ============================================================================

try:
    REQUEST_COUNT: Optional[Counter] = Counter(
        'astra_http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )
except ValueError as e:
    logger.error(f"Failed to create REQUEST_COUNT metric: {e}")
    REQUEST_COUNT = None

try:
    REQUEST_LATENCY: Optional[Histogram] = Histogram(
        'astra_http_request_duration_seconds',
        'HTTP request latency',
        ['endpoint'],
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0)
    )
except ValueError:
    REQUEST_LATENCY = None

try:
    ACTIVE_CONNECTIONS: Optional[Gauge] = Gauge(
        'astra_active_connections',
        'Active concurrent connections'
    )
except ValueError:
    ACTIVE_CONNECTIONS = None

try:
    REQUEST_SIZE: Optional[Summary] = Summary(
        'astra_http_request_size_bytes',
        'HTTP request payload size'
    )
except ValueError:
    REQUEST_SIZE = None

try:
    RESPONSE_SIZE: Optional[Summary] = Summary(
        'astra_http_response_size_bytes',
        'HTTP response payload size'
    )
except ValueError:
    RESPONSE_SIZE = None

# ============================================================================
# RELIABILITY SUITE METRICS (#14-19)
# ============================================================================

try:
    CIRCUIT_BREAKER_STATE: Optional[Gauge] = Gauge(
        'astra_circuit_breaker_state',
        'Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)',
        ['name']
    )
except ValueError:
    CIRCUIT_BREAKER_STATE = None

try:
    CIRCUIT_BREAKER_TRANSITIONS: Optional[Counter] = Counter(
        'astra_circuit_breaker_transitions_total',
        'Circuit breaker state transitions',
        ['name', 'from_state', 'to_state']
    )
except ValueError:
    CIRCUIT_BREAKER_TRANSITIONS = None

try:
    RETRY_ATTEMPTS: Optional[Counter] = Counter(
        'astra_retry_attempts_total',
        'Total retry attempts',
        ['endpoint', 'outcome']
    )
except ValueError:
    RETRY_ATTEMPTS = None

try:
    RETRY_LATENCY: Optional[Histogram] = Histogram(
        'astra_retry_latency_seconds',
        'Latency added by retry logic',
        ['endpoint'],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
    )
except ValueError:
    RETRY_LATENCY = None

try:
    CHAOS_INJECTIONS: Optional[Counter] = Counter(
        'astra_chaos_injections_total',
        'Chaos experiment injections',
        ['type', 'status']
    )
except ValueError:
    CHAOS_INJECTIONS = None

try:
    CHAOS_RECOVERY_TIME: Optional[Histogram] = Histogram(
        'astra_chaos_recovery_time_seconds',
        'Time to recover from chaos injection',
        ['type'],
        buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0)
    )
except ValueError:
    CHAOS_RECOVERY_TIME = None

try:
    RECOVERY_ACTIONS: Optional[Counter] = Counter(
        'astra_recovery_actions_total',
        'Recovery actions executed',
        ['type', 'status']
    )
except ValueError:
    RECOVERY_ACTIONS = None

try:
    HEALTH_CHECK_FAILURES: Optional[Counter] = Counter(
        'astra_health_check_failures_total',
        'Health check failures',
        ['service']
    )
except ValueError:
    HEALTH_CHECK_FAILURES = None

# ============================================================================
# ML/ANOMALY DETECTION METRICS
# ============================================================================

try:
    ANOMALY_DETECTIONS: Optional[Counter] = Counter(
        'astra_anomalies_detected_total',
        'Total anomalies detected',
        ['severity']
    )
except ValueError:
    ANOMALY_DETECTIONS = None

try:
    DETECTION_LATENCY: Optional[Histogram] = Histogram(
        'astra_detection_latency_seconds',
        'Anomaly detection latency',
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5)
    )
except ValueError:
    DETECTION_LATENCY = None

try:
    DETECTION_ACCURACY: Optional[Summary] = Summary(
        'astra_detection_accuracy',
        'ML model detection accuracy'
    )
except ValueError:
    DETECTION_ACCURACY = None

try:
    FALSE_POSITIVES: Optional[Counter] = Counter(
        'astra_false_positives_total',
        'False positive detections',
        ['detector']
    )
except ValueError:
    FALSE_POSITIVES = None

# ============================================================================
# MEMORY ENGINE METRICS
# ============================================================================

try:
    MEMORY_ENGINE_HITS: Optional[Counter] = Counter(
        'astra_memory_engine_hits_total',
        'Memory engine cache hits',
        ['store_type']
    )
except ValueError:
    MEMORY_ENGINE_HITS = None

try:
    MEMORY_ENGINE_MISSES: Optional[Counter] = Counter(
        'astra_memory_engine_misses_total',
        'Memory engine cache misses',
        ['store_type']
    )
except ValueError:
    MEMORY_ENGINE_MISSES = None

try:
    MEMORY_ENGINE_SIZE: Optional[Gauge] = Gauge(
        'astra_memory_engine_size_bytes',
        'Memory engine storage size',
        ['store_type']
    )
except ValueError:
    MEMORY_ENGINE_SIZE = None

# ============================================================================
# ERROR METRICS
# ============================================================================

try:
    ERRORS: Optional[Counter] = Counter(
        'astra_errors_total',
        'Total application errors',
        ['type', 'endpoint']
    )
except ValueError:
    ERRORS = None

try:
    ERROR_LATENCY: Optional[Histogram] = Histogram(
        'astra_error_resolution_time_seconds',
        'Time to resolve errors',
        ['error_type'],
        buckets=(0.1, 1.0, 5.0, 10.0, 30.0)
    )
except ValueError:
    ERROR_LATENCY = None

# ============================================================================
# CONTEXT MANAGERS FOR INSTRUMENTATION
# ============================================================================

@contextmanager
def track_request(endpoint: str, method: str = "POST") -> Generator[None, None, None]:
    """
    Context manager to track HTTP request metrics (RED method).

    Automatically monitors:
    - Rate: Increments request counts (success/failure).
    - Errors: Tracks exceptions and 500 statuses.
    - Duration: Measures latency via Histogram.

    Also manages concurrent connection counts (`ACTIVE_CONNECTIONS`).

    Args:
        endpoint (str): API path or route name (e.g., "/api/v1/telemetry").
        method (str): HTTP method (GET, POST, etc.).

    Raises:
        Exception: Re-raises any exception that occurs within the block,
                   ensuring it propagates after metrics are recorded.
    """
    start = time.perf_counter()
    try:
        if ACTIVE_CONNECTIONS:
            ACTIVE_CONNECTIONS.inc()
        yield
        duration = time.perf_counter() - start
        if REQUEST_LATENCY:
            _get_cached_labels(REQUEST_LATENCY, endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="200").inc()
    except (ValueError, KeyError, TypeError) as e:
        # Expected application errors
        duration = time.time() - start
        if REQUEST_LATENCY:
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="400").inc()
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint=endpoint).inc()
        logger.warning(f"Client error on {endpoint}: {e}", extra={"endpoint": endpoint, "method": method})
        raise
    except (ConnectionError, TimeoutError, asyncio.TimeoutError) as e:
        # Network/connectivity errors
        duration = time.time() - start
        if REQUEST_LATENCY:
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="503").inc()
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint=endpoint).inc()
        logger.error(f"Service unavailable on {endpoint}: {e}", extra={"endpoint": endpoint})
        raise
    except Exception as e:
        # Unexpected errors (server errors)
        duration = time.time() - start
        if REQUEST_LATENCY:
            _get_cached_labels(REQUEST_LATENCY, endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            _get_cached_labels(REQUEST_COUNT, method=method, endpoint=endpoint, status="500").inc()
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint=endpoint).inc()
        logger.exception(f"Unexpected error on {endpoint}: {e}", extra={"endpoint": endpoint, "method": method})
        raise
    finally:
        if ACTIVE_CONNECTIONS:
            ACTIVE_CONNECTIONS.dec()



@contextmanager
def track_anomaly_detection() -> Generator[None, None, None]:
    """Track anomaly detection latency and results"""
    start = time.perf_counter()
    try:
        yield
        duration = time.perf_counter() - start
        if DETECTION_LATENCY:
            DETECTION_LATENCY.observe(duration)
    except (ValueError, KeyError) as e:
        # Invalid input data
        logger.warning(f"Invalid data for anomaly detection: {e}", exc_info=True)
        if ERRORS:
            ERRORS.labels(type="data_validation_error", endpoint="anomaly_detection").inc()
        raise
    except (ImportError, AttributeError) as e:
        # ML model/library issues
        logger.error(f"ML model error in anomaly detection: {e}", exc_info=True)
        if ERRORS:
            ERRORS.labels(type="model_error", endpoint="anomaly_detection").inc()
        raise
    except Exception as e:
        logger.exception(f"Unexpected anomaly detection failure: {e}")
        if ERRORS:
            _get_cached_labels(ERRORS, type=type(e).__name__, endpoint="anomaly_detection").inc()
        raise



@contextmanager
def track_retry_attempt(endpoint: str) -> Generator[None, None, None]:
    """Track retry latency"""
    start = time.perf_counter()
    try:
        yield
        duration = time.perf_counter() - start
        if RETRY_LATENCY:
            RETRY_LATENCY.labels(endpoint=endpoint).observe(duration)
    except (ConnectionError, TimeoutError) as e:
        # Expected retry scenarios
        logger.debug(f"Retry needed for {endpoint}: {e}")
        if RETRY_ATTEMPTS:
            RETRY_ATTEMPTS.labels(endpoint=endpoint, outcome="failed").inc()
        raise
    except Exception as e:
        # Unexpected error during retry
        logger.error(f"Unexpected error during retry for {endpoint}: {e}", exc_info=True)
        if RETRY_ATTEMPTS:
            RETRY_ATTEMPTS.labels(endpoint=endpoint, outcome="error").inc()
        raise




@contextmanager
def track_chaos_recovery(chaos_type: str) -> Generator[None, None, None]:
    """Track recovery time from chaos injection"""
    start = time.perf_counter()
    try:
        yield
        duration = time.perf_counter() - start
        if CHAOS_RECOVERY_TIME:
            CHAOS_RECOVERY_TIME.labels(type=chaos_type).observe(duration)
    except TimeoutError as e:
        # Recovery timeout
        logger.error(
            f"Chaos recovery timeout for {chaos_type}: {e}",
            extra={"chaos_type": chaos_type, "timeout_duration": time.time() - start}
        )
        if ERRORS:
            ERRORS.labels(type="recovery_timeout", endpoint="chaos_recovery").inc()
        raise
    except (ConnectionError, OSError) as e:
        # System/connectivity issues during recovery
        logger.error(
            f"System error during chaos recovery for {chaos_type}: {e}",
            exc_info=True,
            extra={"chaos_type": chaos_type}
        )
        if ERRORS:
            ERRORS.labels(type="system_error", endpoint="chaos_recovery").inc()
        raise
    except Exception as e:
        logger.exception(
            f"Unexpected chaos recovery failure for {chaos_type}: {e}",
            extra={"chaos_type": chaos_type}
        )
        if ERRORS:
            _get_cached_labels(ERRORS, type=type(e).__name__, endpoint="chaos_recovery").inc()
        raise



# ============================================================================
# ASYNC CONTEXT MANAGERS FOR INSTRUMENTATION
# ============================================================================

@asynccontextmanager
async def async_track_request(endpoint: str, method: str = "POST") -> AsyncGenerator[None, None]:
    """Async version of track_request for async contexts"""
    start = time.perf_counter()
    try:
        if ACTIVE_CONNECTIONS:
            ACTIVE_CONNECTIONS.inc()
        yield
        duration = time.perf_counter() - start
        if REQUEST_LATENCY:
            _get_cached_labels(REQUEST_LATENCY, endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            _get_cached_labels(REQUEST_COUNT, method=method, endpoint=endpoint, status="200").inc()
    except Exception as e:
        duration = time.perf_counter() - start
        if REQUEST_LATENCY:
            _get_cached_labels(REQUEST_LATENCY, endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            _get_cached_labels(REQUEST_COUNT, method=method, endpoint=endpoint, status="500").inc()
        if ERRORS:
            _get_cached_labels(ERRORS, type=type(e).__name__, endpoint=endpoint).inc()
        raise
    finally:
        if ACTIVE_CONNECTIONS:
            ACTIVE_CONNECTIONS.dec()



@asynccontextmanager
async def async_track_anomaly_detection() -> AsyncGenerator[None, None]:
    """Async version of track_anomaly_detection"""
    start = time.perf_counter()
    try:
        yield
        duration = time.perf_counter() - start
        if DETECTION_LATENCY:
            DETECTION_LATENCY.observe(duration)
    except Exception as e:
        duration = time.perf_counter() - start
        logger.error(f"Anomaly detection failed: {e}")
        if ERRORS:
            _get_cached_labels(ERRORS, type=type(e).__name__, endpoint="anomaly_detection").inc()
        raise



@asynccontextmanager
async def async_track_retry_attempt(endpoint: str) -> AsyncGenerator[None, None]:
    """Async version of track_retry_attempt"""
    start = time.perf_counter()
    try:
        yield
        duration = time.perf_counter() - start
        if RETRY_LATENCY:
            _get_cached_labels(RETRY_LATENCY, endpoint=endpoint).observe(duration)
    except Exception:
        raise



@asynccontextmanager
async def async_track_chaos_recovery(chaos_type: str) -> AsyncGenerator[None, None]:
    """Async version of track_chaos_recovery"""
    start = time.perf_counter()
    try:
        yield
        duration = time.perf_counter() - start
        if CHAOS_RECOVERY_TIME:
            _get_cached_labels(CHAOS_RECOVERY_TIME, type=chaos_type).observe(duration)
    except Exception as e:
        logger.error(f"Chaos recovery failed for {chaos_type}: {e}")
        if ERRORS:
            _get_cached_labels(ERRORS, type=type(e).__name__, endpoint="chaos_recovery").inc()
        raise



# ============================================================================
# METRICS SERVER STARTUP
# ============================================================================

def startup_metrics_server(port: int = 9090) -> None:
    """
    Start Prometheus metrics HTTP server
    
    Args:
        port: Port to expose metrics on (default: 9090)
    """
    try:
        start_http_server(port)
        logger.info(f"Metrics server started on port {port}")
        print(f"✅ Metrics server started on port {port}")
        print(f"   Access metrics: http://localhost:{port}/metrics")
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            logger.error(f"Port {port} already in use. Metrics server not started.")
            print(f"⚠️  Port {port} already in use. Choose a different port.")
        else:
            logger.error(f"OS error starting metrics server on port {port}: {e}", exc_info=True)
            print(f"⚠️  Failed to start metrics server: {e}")
    except ImportError as e:
        logger.error(f"Missing dependency for metrics server: {e}")
        print(f"⚠️  Missing required library: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error starting metrics server: {e}")
        print(f"⚠️  Unexpected error starting metrics server: {e}")



def shutdown_metrics_server() -> None:
    """Graceful shutdown of metrics server"""
    # WSGI server stops automatically when app shuts down
    pass


def get_registry() -> CollectorRegistry:
    """Get the Prometheus metrics registry"""
    return REGISTRY


# ============================================================================
# METRICS EXPORT FUNCTION
# ============================================================================

def get_metrics_endpoint() -> bytes:
    """
    Generate Prometheus-format metrics response

    Returns:
        Bytes containing all metrics in Prometheus text format
    """
    try:
        from prometheus_client import generate_latest, REGISTRY
        return generate_latest(REGISTRY)
    except ImportError as e:
        # Missing prometheus_client (should not happen if module loads)
        logger.critical(f"Prometheus client import failed: {e}")
        if ERRORS:
            ERRORS.labels(type="import_error", endpoint="metrics_endpoint").inc()
        raise RuntimeError("Prometheus client not available") from e
    except (AttributeError, TypeError) as e:
        # Registry corruption or invalid state
        logger.error(f"Registry error generating metrics: {e}", exc_info=True)
        if ERRORS:
            ERRORS.labels(type="registry_error", endpoint="metrics_endpoint").inc()
        raise
    except Exception as e:
        logger.exception(f"Unexpected error generating metrics: {e}")
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint="metrics_endpoint").inc()
        raise

