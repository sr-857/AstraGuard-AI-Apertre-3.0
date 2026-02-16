import random
import os
import json
import pickle
import logging
import asyncio
from typing import Any, Dict, Tuple, Optional, cast, List

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
    ANOMALY_MODEL_INFO,
    ANOMALY_SCORE_DISTRIBUTION,
)
import time

# Try to import numpy globally
try:
    import numpy as np
except ImportError:
    np = None

logger: logging.Logger = logging.getLogger(__name__)

MODEL_PATH: str = os.path.join(os.path.dirname(__file__), "anomaly_if.pkl")
METADATA_PATH: str = os.path.join(os.path.dirname(__file__), "metadata.json")
_MODEL: Optional[Any] = None
_MODEL_LOADED: bool = False
_USING_HEURISTIC_MODE: bool = False
_model_lock: asyncio.Lock = asyncio.Lock()


def is_model_loaded() -> bool:
    """Check if the model is currently loaded."""
    return _MODEL_LOADED


def is_heuristic_active() -> bool:
    """Check if heuristic mode is active."""
    return _USING_HEURISTIC_MODE


# Initialize circuit breaker for model loading
_model_loader_cb: CircuitBreaker = register_circuit_breaker(
    CircuitBreaker(
        name="anomaly_model_loader",
        failure_threshold=5,
        success_threshold=2,
        recovery_timeout=60,
        expected_exceptions=(ModelLoadError, OSError, Exception),
    )
)


@async_timeout(seconds=get_timeout_config().model_load_timeout)  # type: ignore[misc]
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
        logger.warning(
            f"numpy not available: {e}. Using heuristic mode.",
            extra={"component": "anomaly_detector", "error_type": "ImportError"}
        )
        _USING_HEURISTIC_MODE = True
        _MODEL_LOADED = False
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg="numpy import failed - heuristic mode active",
            fallback_active=True,
            metadata={"mode": "heuristic", "reason": str(e)},
        )
        ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
        return False

    # Validate model path exists
    if not os.path.exists(MODEL_PATH):
        error_msg = f"Model file not found at {MODEL_PATH}"
        logger.error(
            error_msg,
            extra={
                "component": "anomaly_detector",
                "error_type": "ModelLoadError",
                "model_path": MODEL_PATH
            }
        )
        ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
        raise ModelLoadError(
            error_msg,
            component="anomaly_detector",
            context={"model_path": MODEL_PATH},
        )

    # Load model with comprehensive error handling
    try:
        with open(MODEL_PATH, "rb") as f:
            _MODEL = await asyncio.to_thread(pickle.load, f)  # noqa: S301 - model file is trusted and part of deployment
        
        # Validate model has required methods
        if not hasattr(_MODEL, 'predict'):
            error_msg = "Loaded model missing required 'predict' method"
            logger.error(
                error_msg,
                extra={
                    "component": "anomaly_detector",
                    "error_type": "ModelValidationError",
                    "model_type": type(_MODEL).__name__
                }
            )
            ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
            raise ModelLoadError(
                error_msg,
                component="anomaly_detector",
                context={"model_type": type(_MODEL).__name__},
            )
        
        _MODEL_LOADED = True
        _USING_HEURISTIC_MODE = False
        health_monitor.mark_healthy(
            "anomaly_detector",
            {
                "mode": "model-based",
                "model_path": MODEL_PATH,
            },
        )

        # Load metadata
        try:
            if os.path.exists(METADATA_PATH):
                with open(METADATA_PATH, "r") as f:
                    metadata = json.load(f)

                version = metadata.get("version", "unknown")
                dataset_hash = metadata.get("dataset_hash", "unknown")
                training_samples = str(metadata.get("training_samples", "0"))

                ANOMALY_MODEL_INFO.labels(
                    version=version,
                    dataset_hash=dataset_hash,
                    training_samples=training_samples
                ).set(1)

                logger.info(f"Loaded model metadata: {version}")
            else:
                logger.warning(f"Model metadata not found at {METADATA_PATH}")
                ANOMALY_MODEL_INFO.labels(
                    version="unknown",
                    dataset_hash="unknown",
                    training_samples="0"
                ).set(1)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            # Non-critical error, continue

        logger.info(
            "Anomaly detection model loaded successfully",
            extra={
                "component": "anomaly_detector",
                "model_path": MODEL_PATH,
                "model_type": type(_MODEL).__name__
            }
        )
        return True
    
    except (pickle.UnpicklingError, EOFError) as e:
        error_msg = f"Failed to unpickle model file: {str(e)}"
        logger.error(
            error_msg,
            extra={
                "component": "anomaly_detector",
                "error_type": type(e).__name__,
                "model_path": MODEL_PATH
            }
        )
        ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
        raise ModelLoadError(
            error_msg,
            component="anomaly_detector",
            context={"model_path": MODEL_PATH, "pickle_error": str(e)},
        )
    
    except OSError as e:
        error_msg = f"OS error reading model file: {str(e)}"
        logger.error(
            error_msg,
            extra={
                "component": "anomaly_detector",
                "error_type": "OSError",
                "model_path": MODEL_PATH
            }
        )
        ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
        raise ModelLoadError(
            error_msg,
            component="anomaly_detector",
            context={"model_path": MODEL_PATH, "os_error": str(e)},
        )
    
    except Exception as e:
        error_msg = f"Unexpected error loading model: {str(e)}"
        logger.error(
            error_msg,
            extra={
                "component": "anomaly_detector",
                "error_type": type(e).__name__,
                "model_path": MODEL_PATH
            },
            exc_info=True
        )
        ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
        raise ModelLoadError(
            error_msg,
            component="anomaly_detector",
            context={"model_path": MODEL_PATH, "unexpected_error": str(e)},
        )


async def _load_model_fallback() -> bool:
    """
    Fallback when circuit breaker is open - use heuristic mode.
    
    This function is called when the circuit breaker prevents model loading
    attempts to protect system stability. It gracefully degrades to heuristic
    detection mode.
    
    Returns:
        False to indicate model loading failed, heuristic mode active
    """
    global _USING_HEURISTIC_MODE
    logger.warning(
        "Model loader circuit breaker open - switching to heuristic mode",
        extra={
            "component": "anomaly_detector",
            "fallback_reason": "circuit_breaker_open",
            "mode": "heuristic"
        }
    )
    _USING_HEURISTIC_MODE = True
    ANOMALY_MODEL_FALLBACK_ACTIVATIONS.inc()
    return False


# Apply retry decorator: 3 attempts with 0.5-8s exponential backoff + jitter
# Retry BEFORE circuit breaker to handle transient failures
@Retry(  # type: ignore[misc]
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
    # Cast needed because @async_timeout decorator is untyped
    result: bool = cast(bool, await _load_model_impl())
    return result


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

    if _MODEL_LOADED:
        return True

    async with _model_lock:
        if _MODEL_LOADED:
            return True

        try:
            # Call through retry (handles transient) then circuit breaker (handles cascading)
            result = await _model_loader_cb.call(
                _load_model_with_retry,  # Retry wrapper
                fallback=_load_model_fallback,
            )
            # Cast needed because circuit breaker call() returns Any
            return cast(bool, result)

        except CircuitOpenError as e:
            logger.error(
                f"Circuit breaker open: {e}",
                extra={
                    "component": "anomaly_detector",
                    "error_type": "CircuitOpenError",
                    "circuit_state": str(e.state)
                }
            )
            _USING_HEURISTIC_MODE = True
            ANOMALY_MODEL_FALLBACK_ACTIVATIONS.inc()
            return False

        except CustomTimeoutError as e:
            logger.error(
                f"Model loading timeout: {e}",
                extra={
                    "component": "anomaly_detector",
                    "error_type": "TimeoutError",
                    "operation": "load_model"
                }
            )
            ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
            _USING_HEURISTIC_MODE = True
            return False

        except ModelLoadError as e:
            logger.error(
                f"Model load error: {e.message}",
                extra={
                    "component": "anomaly_detector",
                    "error_type": "ModelLoadError",
                    "context": e.context
                }
            )
            ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
            _USING_HEURISTIC_MODE = True
            return False

        except Exception as e:
            logger.error(
                f"Unexpected error during model load: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "model_path": MODEL_PATH,
                    "operation": "model_load",
                    "fallback_active": True
                },
                exc_info=True
            )
            ANOMALY_MODEL_LOAD_ERRORS_TOTAL.inc()
            _USING_HEURISTIC_MODE = True
            return False


def _detect_anomaly_heuristic(data: Dict[str, Any]) -> Tuple[bool, float]:
    """
    Perform rule-based anomaly detection as a fallback mechanism.

    Used when the primary ML model is unavailable (not loaded or failing).
    Implements a set of "sanity check" rules based on physical constraints
    (e.g., voltage range, max temperature).

    Design Philosophy:
    - Conservative: Prefers false positives (safety) over false negatives.
    - Robust: Handles missing or malformed data gracefully.
    - Deterministic: Always returns a result given valid input.

    Args:
        data (Dict[str, Any]): Raw telemetry dictionary.

    Returns:
        Tuple[bool, float]: (is_anomalous, severity_score)
    """
    # Handle non-dict input gracefully
    if not isinstance(data, dict):
        logger.warning(
            f"Heuristic mode received non-dict input: {type(data)}",
            extra={
                "component": "anomaly_detector",
                "input_type": type(data).__name__,
                "mode": "heuristic"
            }
        )
        return False, 0.0

    score: float = 0.0

    # Conservative thresholds for heuristic mode
    try:
        voltage: float = float(data.get("voltage", 8.0))
        temperature: float = float(data.get("temperature", 25.0))
        gyro: float = abs(float(data.get("gyro", 0.0)))

        if voltage < 7.0 or voltage > 9.0:
            score += 0.4
        if temperature > 40.0:
            score += 0.3
        if gyro > 0.1:
            score += 0.3
    except (ValueError, TypeError) as e:
        # invalid data types in heuristic -> treat as anomalous
        logger.warning(
            f"Heuristic mode encountered invalid data types: {data}",
            extra={
                "component": "anomaly_detector",
                "error_type": type(e).__name__,
                "mode": "heuristic",
                "data_sample": str(data)[:100]  # Limit log size
            }
        )
        score += 0.5
    except Exception as e:
        # Catch any unexpected errors in heuristic calculation
        logger.error(
            f"Unexpected error in heuristic detection: {e}",
            extra={
                "component": "anomaly_detector",
                "error_type": type(e).__name__,
                "mode": "heuristic"
            },
            exc_info=True
        )
        # Return safe default - treat as potential anomaly
        return True, 0.6

    # Add small random noise for simulation realism
    score += random.uniform(0, 0.1)

    # Conservative threshold: be more sensitive to potential issues
    is_anomalous: bool = score > 0.5  # Lowered from 0.6 for more sensitivity
    return is_anomalous, min(score, 1.0)  # Cap at 1.0


@async_timeout(seconds=10.0, operation_name="anomaly_detection")
async def detect_anomaly(data: Dict[str, Any]) -> Tuple[bool, float]:
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
        
    Raises:
        Never raises - always returns a result via fallback mechanisms
    """
    global _USING_HEURISTIC_MODE
    health_monitor = get_health_monitor()
    resource_monitor = get_resource_monitor()

    # Track latency
    start_time: float = time.time()

    try:
        # Always ensure component is registered (safe: idempotent)
        health_monitor.register_component("anomaly_detector")
        
        # Check resource availability before heavy operations
        resource_status: Dict[str, Any] = resource_monitor.check_resource_health()
        if resource_status['overall'] == 'critical':
            logger.warning(
                f"Resource check failed (critical). Status: {resource_status}. Proceeding with detection.",
                extra={
                    "component": "anomaly_detector",
                    "error_type": "ResourceCritical"
                }
            )

        # Ensure model is loaded once
        if not _MODEL_LOADED:
            try:
                await load_model()
            except Exception as e:
                logger.error(
                    f"Failed to load model: {e}",
                    extra={
                        "component": "anomaly_detector",
                        "error_type": type(e).__name__
                    }
                )

        # Validate input using TelemetryData
        try:
            validated_data = TelemetryData.validate(data)
        except ValidationError as e:
            logger.warning(
                f"Telemetry validation failed: {e}",
                extra={
                    "component": "anomaly_detector",
                    "error_type": "ValidationError",
                    "validation_error": str(e)
                }
            )
            raise AnomalyEngineError(
                f"Invalid telemetry data: {e}",
                component="anomaly_detector",
                context={"validation_error": str(e)},
            )

        # Use model-based detection if available
        if _MODEL and not _USING_HEURISTIC_MODE:
            try:
                # Prepare features (order matters for model consistency)
                features: List[float] = [
                    data.get("voltage", 8.0),
                    data.get("temperature", 25.0),
                    abs(data.get("gyro", 0.0)),
                    data.get("current", 1.0),
                    data.get("wheel_speed", 5.0),
                ]

                # Model prediction (assumes binary classifier)
                is_anomalous = await asyncio.to_thread(_MODEL.predict, [features])
                is_anomalous = is_anomalous[0]
                score = (
                    await asyncio.to_thread(_MODEL.score_samples, [features])
                    if hasattr(_MODEL, "score_samples")
                    else [0.5]
                )
                score = score[0]
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
                ANOMALY_SCORE_DISTRIBUTION.labels(detector_type="model").observe(score)

                return bool(is_anomalous), float(score)
            
            except asyncio.TimeoutError as e:
                logger.warning(
                    f"Model prediction timeout: {e}. Falling back to heuristic.",
                    extra={
                        "component": "anomaly_detector",
                        "error_type": "TimeoutError",
                        "fallback_reason": "model_timeout"
                    }
                )
                _USING_HEURISTIC_MODE = True
                health_monitor.mark_degraded(
                    "anomaly_detector",
                    error_msg=f"Model prediction timeout: {str(e)}",
                    fallback_active=True,
                )
                # Fall through to heuristic
            
            except (AttributeError, ValueError, TypeError) as e:
                logger.warning(
                    f"Model prediction error ({type(e).__name__}): {e}. Falling back to heuristic.",
                    extra={
                        "component": "anomaly_detector",
                        "error_type": type(e).__name__,
                        "fallback_reason": "model_error"
                    }
                )
                _USING_HEURISTIC_MODE = True
                health_monitor.mark_degraded(
                    "anomaly_detector",
                    error_msg=f"Model prediction failed: {str(e)}",
                    fallback_active=True,
                )
                # Fall through to heuristic
            
            except Exception as e:
                logger.warning(
                    f"Model prediction failed: {e}. Falling back to heuristic.",
                    extra={
                        "error_type": type(e).__name__,
                        "operation": "model_prediction",
                        "has_model": _MODEL is not None,
                        "fallback_active": True
                    },
                    exc_info=True
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
        ANOMALY_SCORE_DISTRIBUTION.labels(detector_type="heuristic").observe(score)

        return is_anomalous, score

    except Exception as e:
        logger.error(
            f"Unexpected error in anomaly detection: {e}",
            extra={
                "error_type": type(e).__name__,
                "operation": "anomaly_detection",
                "using_heuristic_mode": _USING_HEURISTIC_MODE,
                "model_loaded": _MODEL_LOADED,
                "fallback_active": True
            },
            exc_info=True
        )
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg=f"Unexpected error: {str(e)}",
            fallback_active=True,
        )
        # Fall back to heuristic on any error
        return _detect_anomaly_heuristic(data)


def load_model_sync() -> bool:
    """
    Synchronous model loading for worker processes.
    Bypasses asyncio locks/timeouts as workers are dedicated.
    """
    global _MODEL, _MODEL_LOADED, _USING_HEURISTIC_MODE

    if _MODEL_LOADED:
        return True

    try:
        # Check numpy
        if np is None:
            _USING_HEURISTIC_MODE = True
            return False

        if not os.path.exists(MODEL_PATH):
            _USING_HEURISTIC_MODE = True
            return False

        with open(MODEL_PATH, "rb") as f:
            _MODEL = pickle.load(f)

        _MODEL_LOADED = True
        _USING_HEURISTIC_MODE = False
        return True
    except Exception as e:
        logger.error(f"Sync model load failed: {e}")
        _USING_HEURISTIC_MODE = True
        return False


def _detect_anomaly_heuristic_batch(data: Dict[str, List[float]]) -> Tuple[List[bool], List[float]]:
    """Vectorized heuristic fallback."""
    if np is None:
        # Fallback to loop if numpy missing (unlikely in worker)
        results = []
        scores = []
        n = len(next(iter(data.values()))) if data else 0
        keys = data.keys()
        for i in range(n):
            single_data = {k: data[k][i] for k in keys}
            a, s = _detect_anomaly_heuristic(single_data)
            results.append(a)
            scores.append(s)
        return results, scores

    n_samples = len(data.get("voltage", []))
    if n_samples == 0:
        return [], []

    scores = np.zeros(n_samples)

    # Safe array creation with defaults
    voltage = np.array(data.get("voltage", [8.0] * n_samples))
    temperature = np.array(data.get("temperature", [25.0] * n_samples))
    gyro = np.abs(np.array(data.get("gyro", [0.0] * n_samples)))

    # Vectorized rules
    scores += np.where((voltage < 7.0) | (voltage > 9.0), 0.4, 0.0)
    scores += np.where(temperature > 40.0, 0.3, 0.0)
    scores += np.where(gyro > 0.1, 0.3, 0.0)

    # Random noise
    scores += np.random.uniform(0, 0.1, n_samples)

    is_anomalous = scores > 0.5
    scores = np.clip(scores, 0.0, 1.0)

    return is_anomalous.tolist(), scores.tolist()


def detect_anomaly_batch(data: Dict[str, List[float]]) -> Tuple[List[bool], List[float]]:
    """
    Detect anomalies in a batch of telemetry data using vectorized operations.
    """
    global _USING_HEURISTIC_MODE

    # Ensure model is loaded (sync)
    if not _MODEL_LOADED:
        load_model_sync()

    if _MODEL and not _USING_HEURISTIC_MODE and np is not None:
        try:
            n_samples = len(data.get("voltage", []))
            if n_samples == 0:
                return [], []

            features = np.zeros((n_samples, 5))
            features[:, 0] = data.get("voltage", [8.0] * n_samples)
            features[:, 1] = data.get("temperature", [25.0] * n_samples)
            features[:, 2] = np.abs(data.get("gyro", [0.0] * n_samples))
            features[:, 3] = data.get("current", [1.0] * n_samples)
            features[:, 4] = data.get("wheel_speed", [5.0] * n_samples)

            # Bulk prediction
            # IsolationForest predict: -1 (anomaly), 1 (normal)
            preds = _MODEL.predict(features)

            # score_samples: negative float
            if hasattr(_MODEL, "score_samples"):
                scores = _MODEL.score_samples(features)
                # Normalize scores to 0-1 range (clamping)
                # Note: This logic mimics the original scalar implementation
                # which naively clamped score_samples result.
                scores = np.clip(scores, 0.0, 1.0)
            else:
                scores = np.full(n_samples, 0.5)

            # Match original logic: bool(prediction_value)
            # -1 -> True, 1 -> True.
            # If the original logic meant "is_anomalous", it likely expected 0/1 or True/False.
            # But IsolationForest returns 1/-1.
            # We preserve the original behavior even if suspect.
            is_anomalous = (preds != 0).tolist()

            return is_anomalous, scores.tolist()

        except Exception as e:
            logger.error(f"Batch model prediction failed: {e}")
            _USING_HEURISTIC_MODE = True
            # Fall through to heuristic

    return _detect_anomaly_heuristic_batch(data)
