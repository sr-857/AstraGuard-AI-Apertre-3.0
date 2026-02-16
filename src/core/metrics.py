"""
Dummy Prometheus Metrics for AstraGuard AI
"""

from typing import Any, Callable

# Dummy Registry
class Registry:
    pass

REGISTRY = Registry()

# Dummy Metrics
class DummyMetric:
    def __init__(self, *args, **kwargs):
        pass
    def labels(self, *args, **kwargs):
        return self
    def inc(self, *args, **kwargs):
        pass
    def set(self, *args, **kwargs):
        pass
    def observe(self, *args, **kwargs):
        pass
    def time(self, *args, **kwargs):
        def decorator(func):
            async def wrapper(*a, **kw):
                return await func(*a, **kw)
            return wrapper
        return decorator

Counter = Gauge = Histogram = Summary = DummyMetric
CONTENT_TYPE_LATEST = "text/plain"

def generate_latest(registry):
    return b"# Dummy metrics"

# Recreate all the metric names expected by imports
CIRCUIT_STATE = DummyMetric()
CIRCUIT_FAILURES_TOTAL = DummyMetric()
CIRCUIT_SUCCESSES_TOTAL = DummyMetric()
CIRCUIT_TRIPS_TOTAL = DummyMetric()
CIRCUIT_RECOVERIES_TOTAL = DummyMetric()
CIRCUIT_OPEN_DURATION_SECONDS = DummyMetric()
CIRCUIT_FAILURE_RATIO = DummyMetric()
ANOMALY_DETECTIONS_TOTAL = DummyMetric()
ANOMALY_DETECTION_LATENCY = DummyMetric()
ANOMALY_MODEL_LOAD_ERRORS_TOTAL = DummyMetric()
ANOMALY_MODEL_FALLBACK_ACTIVATIONS = DummyMetric()
PREDICTIVE_MAINTENANCE_PREDICTIONS_TOTAL = DummyMetric()
PREDICTIVE_MAINTENANCE_ACCURACY = DummyMetric()
PREDICTIVE_MAINTENANCE_PREVENTIVE_ACTIONS_TOTAL = DummyMetric()
PREDICTIVE_MAINTENANCE_MODEL_TRAINING_DURATION = DummyMetric()
PREDICTIVE_MAINTENANCE_DATA_POINTS_TOTAL = DummyMetric()
COMPONENT_HEALTH_STATUS = DummyMetric()
COMPONENT_ERROR_COUNT = DummyMetric()
COMPONENT_WARNING_COUNT = DummyMetric()
MEMORY_STORE_SIZE_BYTES = DummyMetric()
MEMORY_STORE_ENTRIES = DummyMetric()
MEMORY_STORE_RETRIEVALS = DummyMetric()
MEMORY_STORE_PRUNINGS = DummyMetric()
MISSION_PHASE = DummyMetric()
ANOMALIES_BY_TYPE = DummyMetric()
RECOVERY_ACTIONS_TOTAL = DummyMetric()
RECOVERY_SUCCESS_RATE = DummyMetric()
MTTR_SECONDS = DummyMetric()

def track_circuit_breaker_metrics(circuit_breaker):
    pass

def track_latency(metric_name: str, labels: dict = None):
    def decorator(func: Callable) -> Callable:
        return func
    return decorator

def get_metrics_text() -> str:
    return "# Dummy metrics"

def get_metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST
