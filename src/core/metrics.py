"""
Prometheus Metrics for AstraGuard AI

Exposes metrics for:
- Circuit breaker states and transitions
- Failure and success counts
- Recovery attempts and latency
- System health indicators
"""

from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    CollectorRegistry, generate_latest,
    CONTENT_TYPE_LATEST
)
import time
from functools import wraps
from typing import Callable, Any

# Create a registry for AstraGuard metrics
REGISTRY = CollectorRegistry()

# ============================================================================
# Circuit Breaker Metrics
# ============================================================================

CIRCUIT_STATE = Gauge(
    'astraguard_circuit_state',
    'Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)',
    ['circuit_name'],
    registry=REGISTRY
)

CIRCUIT_FAILURES_TOTAL = Counter(
    'astraguard_circuit_failures_total',
    'Total failures detected by circuit breaker',
    ['circuit_name'],
    registry=REGISTRY
)

CIRCUIT_SUCCESSES_TOTAL = Counter(
    'astraguard_circuit_successes_total',
    'Total successful calls through circuit breaker',
    ['circuit_name'],
    registry=REGISTRY
)

CIRCUIT_TRIPS_TOTAL = Counter(
    'astraguard_circuit_trips_total',
    'Total times circuit breaker transitioned to OPEN',
    ['circuit_name'],
    registry=REGISTRY
)

CIRCUIT_RECOVERIES_TOTAL = Counter(
    'astraguard_circuit_recoveries_total',
    'Total times circuit breaker recovered from OPEN',
    ['circuit_name'],
    registry=REGISTRY
)

CIRCUIT_OPEN_DURATION_SECONDS = Gauge(
    'astraguard_circuit_open_duration_seconds',
    'How long circuit has been open',
    ['circuit_name'],
    registry=REGISTRY
)

CIRCUIT_FAILURE_RATIO = Gauge(
    'astraguard_circuit_failure_ratio',
    'Recent failure ratio (failures / (failures + successes))',
    ['circuit_name'],
    registry=REGISTRY
)

# ============================================================================
# Anomaly Detection Metrics
# ============================================================================

ANOMALY_DETECTIONS_TOTAL = Counter(
    'astraguard_anomaly_detections_total',
    'Total anomalies detected',
    ['detector_type'],  # 'model' or 'heuristic'
    registry=REGISTRY
)

ANOMALY_DETECTION_LATENCY = Histogram(
    'astraguard_anomaly_detection_latency_seconds',
    'Latency of anomaly detection',
    ['detector_type'],
    registry=REGISTRY
)

ANOMALY_MODEL_LOAD_ERRORS_TOTAL = Counter(
    'astraguard_anomaly_model_load_errors_total',
    'Total model loading failures',
    registry=REGISTRY
)

ANOMALY_MODEL_FALLBACK_ACTIVATIONS = Counter(
    'astraguard_anomaly_model_fallback_activations_total',
    'Total times fallback to heuristic was used',
    registry=REGISTRY
)

# ============================================================================
# Predictive Maintenance Metrics
# ============================================================================

PREDICTIVE_MAINTENANCE_PREDICTIONS_TOTAL = Counter(
    'astraguard_predictive_maintenance_predictions_total',
    'Total predictive maintenance predictions made',
    ['failure_type', 'model_type'],
    registry=REGISTRY
)

PREDICTIVE_MAINTENANCE_ACCURACY = Gauge(
    'astraguard_predictive_maintenance_accuracy',
    'Accuracy of predictive maintenance models',
    ['failure_type', 'model_type'],
    registry=REGISTRY
)

PREDICTIVE_MAINTENANCE_PREVENTIVE_ACTIONS_TOTAL = Counter(
    'astraguard_predictive_maintenance_preventive_actions_total',
    'Total preventive actions triggered by predictions',
    ['failure_type', 'action_type'],
    registry=REGISTRY
)

PREDICTIVE_MAINTENANCE_MODEL_TRAINING_DURATION = Histogram(
    'astraguard_predictive_maintenance_model_training_duration_seconds',
    'Time spent training predictive maintenance models',
    ['failure_type', 'model_type'],
    registry=REGISTRY
)

PREDICTIVE_MAINTENANCE_DATA_POINTS_TOTAL = Gauge(
    'astraguard_predictive_maintenance_data_points_total',
    'Total data points available for training',
    registry=REGISTRY
)

# ============================================================================
# Component Health Metrics
# ============================================================================

COMPONENT_HEALTH_STATUS = Gauge(
    'astraguard_component_health_status',
    'Component health status (0=HEALTHY, 1=DEGRADED, 2=FAILED)',
    ['component_name'],
    registry=REGISTRY
)

COMPONENT_ERROR_COUNT = Counter(
    'astraguard_component_error_count_total',
    'Total errors per component',
    ['component_name'],
    registry=REGISTRY
)

COMPONENT_WARNING_COUNT = Counter(
    'astraguard_component_warning_count_total',
    'Total warnings per component',
    ['component_name'],
    registry=REGISTRY
)

# ============================================================================
# System Metrics
# ============================================================================

MEMORY_STORE_SIZE_BYTES = Gauge(
    'astraguard_memory_store_size_bytes',
    'Memory store size in bytes',
    registry=REGISTRY
)

MEMORY_STORE_ENTRIES = Gauge(
    'astraguard_memory_store_entries',
    'Number of entries in memory store',
    registry=REGISTRY
)

MEMORY_STORE_RETRIEVALS = Counter(
    'astraguard_memory_store_retrievals_total',
    'Total memory store retrievals',
    registry=REGISTRY
)

MEMORY_STORE_PRUNINGS = Counter(
    'astraguard_memory_store_prunings_total',
    'Total memory store pruning operations',
    registry=REGISTRY
)

# ============================================================================
# Mission & Recovery Metrics (New)
# ============================================================================

MISSION_PHASE = Gauge(
    'astraguard_mission_phase',
    'Current mission phase (1=Active)',
    ['phase'],
    registry=REGISTRY
)

ANOMALIES_BY_TYPE = Counter(
    'astraguard_anomalies_by_type_total',
    'Total anomalies by type and severity',
    ['type', 'severity'],
    registry=REGISTRY
)

RECOVERY_ACTIONS_TOTAL = Counter(
    'astraguard_recovery_actions_total',
    'Total recovery actions executed',
    ['action'],
    registry=REGISTRY
)

RECOVERY_SUCCESS_RATE = Gauge(
    'astraguard_recovery_success_rate',
    'Success rate of recovery actions (0-1)',
    registry=REGISTRY
)

MTTR_SECONDS = Histogram(
    'astraguard_mttr_seconds',
    'Mean Time To Recovery in seconds',
    buckets=(1, 5, 10, 30, 60, 120, 300),
    registry=REGISTRY
)

# ============================================================================
# Threat Detection Metrics
# ============================================================================

THREAT_DETECTIONS_TOTAL = Counter(
    'astraguard_threat_detections_total',
    'Total threat detections by severity and category',
    ['severity', 'category'],
    registry=REGISTRY
)

THREAT_DETECTION_LATENCY = Histogram(
    'astraguard_threat_detection_latency_seconds',
    'Threat detection processing latency',
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY
)

THREAT_FALSE_POSITIVES_TOTAL = Counter(
    'astraguard_threat_false_positives_total',
    'Total false positive detections',
    ['category'],
    registry=REGISTRY
)

THREAT_HUNTS_TOTAL = Counter(
    'astraguard_threat_hunts_total',
    'Total threat hunts executed',
    ['hunt_type', 'status'],
    registry=REGISTRY
)

THREAT_HUNT_FINDINGS = Counter(
    'astraguard_threat_hunt_findings_total',
    'Total findings from threat hunts',
    ['hunt_type', 'severity'],
    registry=REGISTRY
)

IOC_MATCHES_TOTAL = Counter(
    'astraguard_ioc_matches_total',
    'Total IoC matches detected',
    ['ioc_type', 'severity'],
    registry=REGISTRY
)

IOC_DATABASE_SIZE = Gauge(
    'astraguard_ioc_database_size',
    'Number of active IoCs in database',
    ['ioc_type'],
    registry=REGISTRY
)

AUTOMATED_RESPONSES_TOTAL = Counter(
    'astraguard_automated_responses_total',
    'Total automated responses triggered',
    ['response_type', 'severity'],
    registry=REGISTRY
)

AUTOMATED_RESPONSE_LATENCY = Histogram(
    'astraguard_automated_response_latency_seconds',
    'Automated response execution latency',
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=REGISTRY
)

MITIGATION_ACTIONS_TOTAL = Counter(
    'astraguard_mitigation_actions_total',
    'Total mitigation actions executed',
    ['action_type', 'status'],
    registry=REGISTRY
)

MITIGATION_EFFECTIVENESS = Gauge(
    'astraguard_mitigation_effectiveness',
    'Effectiveness score of mitigation actions (0-1)',
    ['action_type'],
    registry=REGISTRY
)

FORENSICS_EVENTS_TOTAL = Counter(
    'astraguard_forensics_events_total',
    'Total forensics events logged',
    ['event_type', 'severity'],
    registry=REGISTRY
)

EVIDENCE_COLLECTED_TOTAL = Counter(
    'astraguard_evidence_collected_total',
    'Total evidence items collected',
    ['evidence_type'],
    registry=REGISTRY
)

TIMELINE_RECONSTRUCTIONS_TOTAL = Counter(
    'astraguard_timeline_reconstructions_total',
    'Total timeline reconstructions performed',
    registry=REGISTRY
)

THREAT_INTELLIGENCE_FEEDS = Gauge(
    'astraguard_threat_intelligence_feeds',
    'Number of active threat intelligence feeds',
    ['feed_type'],
    registry=REGISTRY
)

THREAT_INTELLIGENCE_UPDATES = Counter(
    'astraguard_threat_intelligence_updates_total',
    'Total threat intelligence feed updates',
    ['feed_type', 'status'],
    registry=REGISTRY
)

BEHAVIORAL_PROFILES = Gauge(
    'astraguard_behavioral_profiles',
    'Number of active behavioral profiles',
    ['entity_type'],
    registry=REGISTRY
)

BEHAVIORAL_ANOMALIES = Counter(
    'astraguard_behavioral_anomalies_total',
    'Total behavioral anomalies detected',
    ['entity_type', 'severity'],
    registry=REGISTRY
)

# ============================================================================
# Helper Functions
# ============================================================================


def track_circuit_breaker_metrics(circuit_breaker):
    """
    Update Prometheus metrics with current circuit breaker state.

    Extracts internal state (failures, successes, open state duration) from
    a CircuitBreaker instance and updates the corresponding Prometheus gauges
    and counters.

    Should be called periodically (e.g., via a background task) or triggered
    by state change events to ensure observability dashboards are accurate.

    Args:
        circuit_breaker: The CircuitBreaker instance to monitor.
    """
    metrics = circuit_breaker.get_metrics()
    
    # State mapping: CLOSED=0, OPEN=1, HALF_OPEN=2
    state_map = {'CLOSED': 0, 'OPEN': 1, 'HALF_OPEN': 2}
    
    CIRCUIT_STATE.labels(circuit_name=circuit_breaker.name).set(
        state_map.get(metrics.state.value, 0)
    )
    
    # Calculate failure ratio
    total_calls = metrics.failures_total + metrics.successes_total
    if total_calls > 0:
        failure_ratio = metrics.failures_total / total_calls
        CIRCUIT_FAILURE_RATIO.labels(circuit_name=circuit_breaker.name).set(
            failure_ratio
        )
    
    # Track open duration
    if metrics.state.value == 'OPEN' and metrics.last_failure_time:
        open_duration = time.time() - metrics.last_failure_time.timestamp()
        CIRCUIT_OPEN_DURATION_SECONDS.labels(
            circuit_name=circuit_breaker.name
        ).set(open_duration)


def track_latency(metric_name: str, labels: dict = None):
    """
    Decorator to measure and record the execution time of async functions.

    Automatically calculates the duration of the decorated function and observes
    it using the specified Prometheus Histogram metric.

    Args:
        metric_name (str): The name of the Prometheus metric to update.
        labels (dict, optional): A dictionary of labels to apply to the metric.
                                 Defaults to None.

    Example:
        @track_latency('anomaly_detection_latency_seconds', {'detector_type': 'model'})
        async def detect_anomaly(data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start
                # Update histogram
                if metric_name == 'anomaly_detection_latency_seconds':
                    detector_type = labels.get('detector_type', 'unknown')
                    ANOMALY_DETECTION_LATENCY.labels(
                        detector_type=detector_type
                    ).observe(elapsed)
        return wrapper
    return decorator


def get_metrics_text() -> str:
    """Get all metrics in Prometheus text format"""
    return generate_latest(REGISTRY).decode('utf-8')


def get_metrics_content_type() -> str:
    """Get content type for Prometheus metrics"""
    return CONTENT_TYPE_LATEST
