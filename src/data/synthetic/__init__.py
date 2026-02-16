from .generator import generate_normal_data, load_config
from .anomaly_injector import inject_anomalies
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def generate_dataset(config_path: str = None) -> pd.DataFrame:
    """
    Generates a complete synthetic dataset with normal data and injected anomalies.
    """
    # Load config explicitly to pass to injector
    config = load_config(config_path)

    # 1. Generate Normal Data
    df_normal = generate_normal_data(config_path)

    # 2. Inject Anomalies
    df_final = inject_anomalies(df_normal, config)

    logger.info(f"Dataset generation complete. Shape: {df_final.shape}")
    return df_final
