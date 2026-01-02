import random
import os
import pickle
import logging
from typing import Dict, Tuple, Optional

# Import centralized error handling
from core.error_handling import (
    ModelLoadError,
    AnomalyEngineError,
    safe_execute,
)
from core.component_health import get_health_monitor, HealthStatus

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "anomaly_if.pkl")
_MODEL: Optional[object] = None
_MODEL_LOADED = False
_USING_HEURISTIC_MODE = False


def load_model() -> bool:
    """
    Load the anomaly detection model with error handling.
    
    Returns:
        True if model loaded successfully, False otherwise
    """
    global _MODEL, _MODEL_LOADED, _USING_HEURISTIC_MODE
    
    health_monitor = get_health_monitor()
    health_monitor.register_component("anomaly_detector")
    
    # Try to import numpy - if it fails, use heuristic mode
    try:
        import numpy as np
    except ImportError as e:
        logger.warning(f"numpy not available: {e}. Using heuristic mode.")
        _USING_HEURISTIC_MODE = True
        _MODEL_LOADED = False
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg="numpy import failed - heuristic mode active",
            fallback_active=True,
            metadata={"mode": "heuristic", "reason": str(e)}
        )
        return False
    
    try:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, "rb") as f:
                _MODEL = pickle.load(f)
            _MODEL_LOADED = True
            _USING_HEURISTIC_MODE = False
            health_monitor.mark_healthy("anomaly_detector", {
                "mode": "model-based",
                "model_path": MODEL_PATH,
            })
            logger.info("Anomaly detection model loaded successfully")
            return True
        else:
            raise ModelLoadError(
                f"Model file not found at {MODEL_PATH}",
                component="anomaly_detector",
                context={"model_path": MODEL_PATH}
            )
    except (pickle.PickleError, EOFError, OSError) as e:
        logger.warning(f"Failed to load anomaly model: {e}. Switching to heuristic mode.")
        _USING_HEURISTIC_MODE = True
        _MODEL_LOADED = False
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg=f"Model load failed: {str(e)}",
            fallback_active=True,
            metadata={
                "mode": "heuristic",
                "reason": str(e),
            }
        )
        return False
    except Exception as e:
        logger.error(f"Unexpected error loading anomaly model: {e}")
        _USING_HEURISTIC_MODE = True
        _MODEL_LOADED = False
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg=f"Unexpected error: {str(e)}",
            fallback_active=True,
            metadata={"mode": "heuristic"}
        )
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
    voltage = data.get("voltage", 8.0)
    temperature = data.get("temperature", 25.0)
    gyro = abs(data.get("gyro", 0.0))
    
    if voltage < 7.0 or voltage > 9.0:
        score += 0.4
    if temperature > 40.0:
        score += 0.3
    if gyro > 0.1:
        score += 0.3
    
    # Add small random noise for simulation realism
    score += random.uniform(0, 0.1)
    
    # Conservative threshold: be more sensitive to potential issues
    is_anomalous = score > 0.5  # Lowered from 0.6 for more sensitivity
    return is_anomalous, min(score, 1.0)  # Cap at 1.0


def detect_anomaly(data: Dict) -> Tuple[bool, float]:
    """
    Detect anomaly in telemetry data with centralized error handling.
    
    Falls back to heuristic detection if model is unavailable.
    
    Args:
        data: Telemetry data dictionary
    
    Returns:
        Tuple of (is_anomalous, anomaly_score) where:
        - is_anomalous: bool indicating if anomaly detected
        - anomaly_score: float between 0 and 1
    """
    global _USING_HEURISTIC_MODE
    health_monitor = get_health_monitor()
    
    # Always ensure component is registered (safe: idempotent)
    health_monitor.register_component("anomaly_detector")
    
    # Ensure model is loaded once
    if not _MODEL_LOADED:
        load_model()
    
    try:
        # Validate input
        if not isinstance(data, dict):
            raise AnomalyEngineError(
                f"Invalid data type: expected dict, got {type(data).__name__}",
                component="anomaly_detector",
                context={"data_type": str(type(data))}
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
                score = _MODEL.score_samples([features])[0] if hasattr(_MODEL, 'score_samples') else 0.5
                score = max(0, min(score, 1.0))  # Normalize to 0-1
                
                health_monitor.mark_healthy("anomaly_detector")
                return bool(is_anomalous), float(score)
            except Exception as e:
                logger.warning(f"Model prediction failed: {e}. Falling back to heuristic.")
                _USING_HEURISTIC_MODE = True
                health_monitor.mark_degraded(
                    "anomaly_detector",
                    error_msg=f"Model prediction failed: {str(e)}",
                    fallback_active=True
                )
                # Fall through to heuristic
        
        # Use heuristic fallback
        is_anomalous, score = _detect_anomaly_heuristic(data)
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg="Using heuristic detection",
            fallback_active=True,
            metadata={"mode": "heuristic"}
        ) if _USING_HEURISTIC_MODE else health_monitor.mark_healthy("anomaly_detector")
        
        return is_anomalous, score
        
    except AnomalyEngineError as e:
        logger.error(f"Anomaly detection error: {e.message}")
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg=str(e.message),
            fallback_active=True
        )
        # Fall back to heuristic on error
        return _detect_anomaly_heuristic(data)
    except Exception as e:
        logger.error(f"Unexpected error in anomaly detection: {e}")
        health_monitor.mark_degraded(
            "anomaly_detector",
            error_msg=f"Unexpected error: {str(e)}",
            fallback_active=True
        )
        # Fall back to heuristic on any error
        return _detect_anomaly_heuristic(data)

