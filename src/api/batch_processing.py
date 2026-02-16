import logging
from typing import Dict, List, Any
from datetime import datetime

# Local imports
from anomaly.anomaly_detector import detect_anomaly_batch, load_model_sync
from classifier.fault_classifier import classify_batch

logger = logging.getLogger(__name__)

def process_telemetry_chunk(chunk_data: Dict[str, List[float]], timestamps: List[datetime]) -> List[Dict[str, Any]]:
    """
    Process a chunk of telemetry data for anomaly detection and classification.
    Executed in a worker process.

    Args:
        chunk_data: Dictionary of feature lists (voltage, temperature, etc.)
        timestamps: List of timestamps corresponding to the data points

    Returns:
        List of result dictionaries containing anomaly status, score, and type.
    """
    try:
        # 1. Ensure model is loaded (cached in worker process)
        load_model_sync()

        # 2. Vectorized Anomaly Detection
        is_anomalous_list, anomaly_scores = detect_anomaly_batch(chunk_data)

        # 3. Vectorized Fault Classification
        anomaly_types = classify_batch(chunk_data)

        # 4. Combine results
        results = []
        n = len(is_anomalous_list)

        # Ensure alignment (should be aligned by caller)
        if len(anomaly_types) != n:
            logger.warning(f"Mismatch in batch sizes: {n} vs {len(anomaly_types)}")
            n = min(n, len(anomaly_types))

        for i in range(n):
            results.append({
                "is_anomaly": is_anomalous_list[i],
                "anomaly_score": anomaly_scores[i],
                "anomaly_type": anomaly_types[i],
                "timestamp": timestamps[i] if i < len(timestamps) else datetime.now()
            })

        return results

    except Exception as e:
        logger.error(f"Error in process_telemetry_chunk: {e}", exc_info=True)
        raise e
