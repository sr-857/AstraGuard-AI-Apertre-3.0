import os
import yaml
import logging
import joblib
import pickle
import pandas as pd
import numpy as np
import json
import glob

logger = logging.getLogger(__name__)

def load_config(config_path: str) -> dict:
    """Load configuration from a YAML file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    logger.info(f"Configuration loaded from {config_path}")
    return config

def load_data(data_path: str, fallback_to_synthetic: bool = True) -> pd.DataFrame:
    """Load data from a CSV file or generate synthetic data if not found."""
    if os.path.exists(data_path):
        logger.info(f"Loading data from {data_path}")
        try:
            df = pd.read_csv(data_path)
            logger.info(f"Data loaded successfully. Shape: {df.shape}")
            return df
        except Exception as e:
            logger.error(f"Error loading data from {data_path}: {e}")
            raise
    elif fallback_to_synthetic:
        logger.warning(f"Data file not found at {data_path}. Generating synthetic data.")
        return generate_synthetic_data()
    else:
        raise FileNotFoundError(f"Data file not found at {data_path}")

def generate_synthetic_data(n_samples: int = 1000) -> pd.DataFrame:
    """Generate synthetic telemetry data for testing/demo purposes."""
    np.random.seed(42)

    data = {
        "voltage": np.random.normal(8.0, 0.5, n_samples),
        "temperature": np.random.normal(25.0, 5.0, n_samples),
        "gyro": np.random.normal(0.0, 0.05, n_samples),
        "current": np.random.normal(1.0, 0.2, n_samples),
        "wheel_speed": np.random.normal(5.0, 1.0, n_samples)
    }

    # Introduce some anomalies
    n_anomalies = int(n_samples * 0.05)
    indices = np.random.choice(n_samples, n_anomalies, replace=False)

    data["voltage"][indices] = np.random.uniform(6.0, 7.0, n_anomalies)  # Low voltage
    data["temperature"][indices] = np.random.uniform(40.0, 50.0, n_anomalies)  # High temp

    df = pd.DataFrame(data)
    logger.info(f"Generated synthetic data with {n_samples} samples.")
    return df

def save_model(model, path: str):
    """Save the model to a file using pickle (for compatibility)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)
    logger.info(f"Model saved to {path}")

def load_model(path: str):
    """Load the model from a file using pickle."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model file not found at {path}")

    with open(path, "rb") as f:
        model = pickle.load(f)
    logger.info(f"Model loaded from {path}")
    return model

def save_pipeline(pipeline, path: str):
    """Save the pipeline to a file using joblib."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(pipeline, path)
    logger.info(f"Pipeline saved to {path}")

def load_pipeline(path: str):
    """Load the pipeline from a file using joblib."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Pipeline file not found at {path}")

    pipeline = joblib.load(path)
    logger.info(f"Pipeline loaded from {path}")
    return pipeline

def save_metrics(metrics: dict, path: str):
    """Save metrics to a JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics, f, indent=4)
    logger.info(f"Metrics saved to {path}")

def load_metrics(path: str) -> dict:
    """Load metrics from a JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Metrics file not found at {path}")
    with open(path, "r") as f:
        return json.load(f)

def get_latest_file(directory: str, pattern: str = "*.pkl") -> str:
    """Find the latest file in a directory based on modification time."""
    if not os.path.exists(directory):
        return None
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        return None
    latest_file = max(files, key=os.path.getmtime)
    logger.info(f"Found latest file: {latest_file}")
    return latest_file
