import random
import os
import pickle
import logging
import asyncio
from typing import Dict, Tuple, Optional

# Import centralized error handling
from core.error_handling import (
    ModelLoadError,
    AnomalyEngineError,
)
# Import input validation
from core.input_validation import TelemetryData, ValidationError
# Import timeout and resource monitoring
from core.timeout_handler import async_timeout, get_timeout_config, TimeoutError as CustomTimeoutError
from core.resource_monitor import get_resource_monitor
from core.component_health import get_health_monitor
from core.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    register_circuit_breaker,
)
from core.retry import Retry
from core.metrics import (
    ANOMALY_DETECTIONS_TOTAL,
    ANOMALY_MODEL_LOAD_ERRORS_TOTAL,
    ANOMALY_MODEL_FALLBACK_ACTIVATIONS,
    ANOMALY_DETECTION_LATENCY,
)
import time

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "anomaly_if.pkl")
_MODEL: Optional[object] = None
_MODEL_LOADED = False
_USING_HEURISTIC_MODE = False

# Initialize circuit breaker for model loading
_model_loader_cb = register_circuit_breaker(
    CircuitBreaker(
        name="anomaly_model_loader",
        failure_threshold=5,
        success_threshold=2,
        recovery_timeout=60,
        expected_exceptions=(ModelLoadError, OSError, Exception),
    )
)


@async_timeout(seconds=get_timeout_config().model_load_timeout)
async def _load_model_impl() -> bool:
    """
    Internal implementation of model loading.
    Wrapped by retry logic first, then circuit breaker and timeout.

    Returns:
        True if model loaded successfully, False otherwise

    Raises:
        ModelLoadError: If model loading fails
        TimeoutError: If loading exceeds timeout
    """
    global _MODEL, _MODEL_LOADED, _USING_HEURISTIC_MODE

    health_monitor = get_health_monitor()
    health_monitor.register_component("anomaly_detector")

    # Try to import numpy - if it fails, use heuristic mode
    try:
        import numpy  # noqa: F401 - validate import but not used directly
    except ImportError as e:
        logger.warning(f"numpy not available: {e}. Using heuristic mode.")
        _USING_HEURISTIC_MODE = True
        _MODEL_LOADED = False
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg="numpy import failed - heuristic mode active",
            fallback_active=True,
            metadata={"mode": "heuristic", "reason": str(e)},
        )
        return False

    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            _MODEL = pickle.load(f)  # noqa: S301 - model file is trusted and part of deployment
        _MODEL_LOADED = True
        _USING_HEURISTIC_MODE = False
        health_monitor.mark_healthy(
            "anomaly_detector",
            {
                "mode": "model-based",
                "model_path": MODEL_PATH,
            },
        )
        logger.info("Anomaly detection model loaded successfully")
        return True
    else:
        raise ModelLoadError(
            f"Model file not found at {MODEL_PATH}",
            component="anomaly_detector",
            context={"model_path": MODEL_PATH},
        )


async def _load_model_fallback() -> bool:
    """Fallback when circuit breaker is open - use heuristic mode"""
    global _USING_HEURISTIC_MODE
    logger.warning("Model loader circuit breaker open - switching to heuristic mode")
    _USING_HEURISTIC_MODE = True
    ANOMALY_MODEL_FALLBACK_ACTIVATIONS.inc()
    return False


# Apply retry decorator: 3 attempts with 0.5-8s exponential backoff + jitter
# Retry BEFORE circuit breaker to handle transient failures
@Retry(
    max_attempts=3,
    base_delay=0.5,
    max_delay=8.0,
    allowed_exceptions=(TimeoutError, ConnectionError, OSError, asyncio.TimeoutError),
    jitter_type="full",
)
async def _load_model_with_retry() -> bool:
    """
    Model loading with retry wrapper.
    Retries on transient failures before circuit breaker engagement.
    """
    return await _load_model_impl()


async def load_model() -> bool:
    """
    Load the anomaly detection model with retry + circuit breaker protection.

    Pattern: Retry (transient failures) → CircuitBreaker (cascading failures)

    The retry decorator handles transient failures (timeouts, connection resets).
    The circuit breaker handles persistent failures (protection from cascading).

    Returns:
        True if model loaded successfully, False otherwise (heuristic mode)
    """
    global _MODEL, _MODEL_LOADED, _USING_HEURISTIC_MODE

    try:
        # Call through retry (handles transient) then circuit breaker (handles cascading)
        result = await _model_loader_cb.call(
            _load_model_with_retry,  # Retry wrapper
            fallback=_load_model_fallback,
        )
        return result

    except CircuitOpenError as e:
        logger.error(f"Circuit breaker open: {e}")
        _USING_HEURISTIC_MODE = True
        ANOMALY_MODEL_FALLBACK_ACTIVATIONS.inc()
        return False
    except Exception as e:
        logger.error(f"Unexpected error during model load: {e}")
        ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
        _USING_HEURISTIC_MODE = True
        return False


def _detect_anomaly_heuristic(data: Dict) -> Tuple[bool, float]:
    """
    Heuristic fallback anomaly detection.
    Conservative approach that prefers false positives to false negatives.

    Args:
        data: Telemetry data dictionary

    Returns:
        Tuple of (is_anomalous, anomaly_score)
    """
    # Handle non-dict input gracefully
    if not isinstance(data, dict):
        logger.warning(f"Heuristic mode received non-dict input: {type(data)}")
        return False, 0.0

    score = 0.0

    # Conservative thresholds for heuristic mode
    try:
        voltage = float(data.get("voltage", 8.0))
        temperature = float(data.get("temperature", 25.0))
        gyro = abs(float(data.get("gyro", 0.0)))

        if voltage < 7.0 or voltage > 9.0:
            score += 0.4
        if temperature > 40.0:
            score += 0.3
        if gyro > 0.1:
            score += 0.3
    except (ValueError, TypeError):
        # invalid data types in heuristic -> treat as anomalous
        logger.warning(f"Heuristic mode encountered invalid data types: {data}")
        score += 0.5

    # Add small random noise for simulation realism
    score += random.uniform(0, 0.1)

    # Conservative threshold: be more sensitive to potential issues
    is_anomalous = score > 0.5  # Lowered from 0.6 for more sensitivity
    return is_anomalous, min(score, 1.0)  # Cap at 1.0


@async_timeout(seconds=10.0, operation_name="anomaly_detection")
async def detect_anomaly(data: Dict) -> Tuple[bool, float]:
    """
    Detect anomaly in telemetry data with resource-aware execution.

    Falls back to heuristic detection if:
    - Model is unavailable or circuit breaker is open
    - Resources are critically low
    - Operation times out

    Args:
        data: Telemetry data dictionary

    Returns:
        Tuple of (is_anomalous, anomaly_score) where:
        - is_anomalous: bool indicating if anomaly detected
        - anomaly_score: float between 0 and 1
    """
    global _USING_HEURISTIC_MODE
    health_monitor = get_health_monitor()
    resource_monitor = get_resource_monitor()

    # Track latency
    start_time = time.time()

    try:
        # Always ensure component is registered (safe: idempotent)
        health_monitor.register_component("anomaly_detector")
        
        # Check resource availability before heavy operations
        resource_status = resource_monitor.check_resource_health()
        if resource_status['overall'] == 'critical':
            logger.warning(
                "System resources critical - using lightweight heuristic mode"
            )
            health_monitor.mark_degraded(
                "anomaly_detector",
                error_msg="Resource constraints - using heuristic mode",
                fallback_active=True,
                metadata={"resource_status": resource_status}
            )
            return _detect_anomaly_heuristic(data)

        # Ensure model is loaded once
        if not _MODEL_LOADED:
            await load_model()

        # Validate input using TelemetryData
        try:
            validated_data = TelemetryData.validate(data)
        except ValidationError as e:
            logger.warning(f"Telemetry validation failed: {e}")
            raise AnomalyEngineError(
                f"Invalid telemetry data: {e}",
                component="anomaly_detector",
                context={"validation_error": str(e)},
            )

        # Use model-based detection if available
        if _MODEL and not _USING_HEURISTIC_MODE:
            try:
                # Prepare features (order matters for model consistency)
                features = [
                    data.get("voltage", 8.0),
                    data.get("temperature", 25.0),
                    abs(data.get("gyro", 0.0)),
                ]

                # Model prediction (assumes binary classifier)
                is_anomalous = _MODEL.predict([features])[0]
                score = (
                    _MODEL.score_samples([features])[0]
                    if hasattr(_MODEL, "score_samples")
                    else 0.5
                )
                # Ensure score is a valid float, default to 0.5 if None
                if score is None:
                    score = 0.5
                score = max(0.0, min(float(score), 1.0))  # Normalize to 0-1

                health_monitor.mark_healthy("anomaly_detector")

                # Record metrics
                ANOMALY_DETECTIONS_TOTAL.labels(detector_type="model").inc()
                ANOMALY_DETECTION_LATENCY.labels(detector_type="model").observe(
                    time.time() - start_time
                )

                return bool(is_anomalous), float(score)
            except Exception as e:
                logger.warning(
                    f"Model prediction failed: {e}. Falling back to heuristic."
                )
                _USING_HEURISTIC_MODE = True
                health_monitor.mark_degraded(
                    "anomaly_detector",
                    error_msg=f"Model prediction failed: {str(e)}",
                    fallback_active=True,
                )
                # Fall through to heuristic

        # Use heuristic fallback
        is_anomalous, score = _detect_anomaly_heuristic(data)
        if _USING_HEURISTIC_MODE:
            health_monitor.mark_degraded(
                "anomaly_detector",
                error_msg="Using heuristic detection",
                fallback_active=True,
                metadata={"mode": "heuristic"},
            )
        else:
            health_monitor.mark_healthy("anomaly_detector")

        # Record metrics for heuristic
        ANOMALY_DETECTIONS_TOTAL.labels(detector_type="heuristic").inc()
        ANOMALY_DETECTION_LATENCY.labels(detector_type="heuristic").observe(
            time.time() - start_time
        )

        return is_anomalous, score

    except AnomalyEngineError as e:
        logger.error(f"Anomaly detection error: {e.message}")
        health_monitor.mark_degraded(
            "anomaly_detector", error_msg=str(e.message), fallback_active=True
        )
        # Fall back to heuristic on error
        return _detect_anomaly_heuristic(data)
    except Exception as e:
        logger.error(f"Unexpected error in anomaly detection: {e}")
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg=f"Unexpected error: {str(e)}",
            fallback_active=True,
        )
        # Fall back to heuristic on any error
        return _detect_anomaly_heuristic(data)
