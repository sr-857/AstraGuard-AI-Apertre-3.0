import argparse
import logging
import sys
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import IsolationForest

# Ensure src is in python path if running directly
import os
sys.path.append(os.getcwd())

from src.training.utils import load_config, load_data, save_model, save_pipeline
from src.training.pipeline import create_preprocessing_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Train anomaly detection model.")
    parser.add_argument("--config", default="src/training/config.yaml", help="Path to config file.")
    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    # Load data
    try:
        # Pass the data path from config.
        # load_data handles fallback to synthetic data if path doesn't exist.
        df = load_data(config["data"]["path"])
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        sys.exit(1)

    # Split data
    test_size = config["data"].get("test_size", 0.2)
    random_state = config["data"].get("random_state", 42)

    logger.info(f"Splitting data (test_size={test_size})...")

    # For unsupervised learning, we often train on "clean" data and test on mixed,
    # or train on mixed and assume anomalies are rare (Isolation Forest approach).
    # Here we split randomly.
    X_train, X_test = train_test_split(df, test_size=test_size, random_state=random_state)
    logger.info(f"Train shape: {X_train.shape}, Test shape: {X_test.shape}")

    # Create pipeline
    pipeline = create_preprocessing_pipeline(config)

    # Fit pipeline
    logger.info("Fitting preprocessing pipeline...")
    # fit_transform on training data
    X_train_processed = pipeline.fit_transform(X_train)
    # transform test data (don't fit on test data!)
    X_test_processed = pipeline.transform(X_test)

    logger.info(f"Processed train shape: {X_train_processed.shape}")

    # Train model
    model_type = config["model"].get("type", "isolation_forest")
    if model_type == "isolation_forest":
        contamination = config["model"].get("contamination", 0.1)
        n_estimators = config["model"].get("n_estimators", 100)

        logger.info(f"Training IsolationForest (contamination={contamination}, n_estimators={n_estimators})...")
        model = IsolationForest(contamination=contamination, n_estimators=n_estimators, random_state=random_state)
        model.fit(X_train_processed)
    else:
        logger.error(f"Unsupported model type: {model_type}")
        sys.exit(1)

    # Save artifacts
    model_path = config["paths"]["model_output"]
    pipeline_path = config["paths"]["pipeline_output"]

    logger.info(f"Saving model to {model_path}...")
    save_model(model, model_path)

    logger.info(f"Saving pipeline to {pipeline_path}...")
    save_pipeline(pipeline, pipeline_path)

    logger.info("Training completed successfully.")

if __name__ == "__main__":
    main()
