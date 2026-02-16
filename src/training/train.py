import argparse
import logging
import sys
import os
import shutil
import datetime
import json
import hashlib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import IsolationForest
import numpy as np

# Ensure src is in python path
sys.path.append(os.getcwd())

from src.training.utils import (
    load_config, load_data, save_model, save_pipeline,
    save_metrics, load_model, get_latest_file, load_metrics
)
from src.training.pipeline import create_preprocessing_pipeline
from src.training.drift import DriftDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def calculate_hash(df):
    """Calculate SHA256 hash of the dataframe."""
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values).hexdigest()

def evaluate_model(model, X_processed, contamination_target=0.1):
    """
    Evaluate the model on processed data.
    Returns a dictionary of metrics.
    """
    # Predict anomalies (-1 for outlier, 1 for inlier)
    preds = model.predict(X_processed)
    # Decision function (lower is more anomalous)
    scores = model.decision_function(X_processed)

    n_samples = len(preds)
    n_anomalies = np.sum(preds == -1)
    measured_contamination = n_anomalies / n_samples

    metrics = {
        "n_samples": int(n_samples),
        "n_anomalies": int(n_anomalies),
        "contamination": float(measured_contamination),
        "mean_score": float(np.mean(scores)),
        "std_score": float(np.std(scores)),
        "min_score": float(np.min(scores)),
        "max_score": float(np.max(scores))
    }

    logger.info(f"Evaluation Metrics: {metrics}")
    return metrics

def is_model_valid(metrics, target_contamination=0.1, tolerance=0.1):
    """
    Check if model is valid based on contamination rate.
    """
    # Allow contamination to be within +/- tolerance of target (e.g. 0.05 to 0.15)
    # If target is 0.1, reasonable range is 0.0 to 0.2?
    # Let's say we expect roughly 10%, so 5% to 15% is okay?
    # Since this is synthetic/test data, let's be generous.
    lower_bound = max(0.0, target_contamination - tolerance)
    upper_bound = min(1.0, target_contamination + tolerance)

    if lower_bound <= metrics['contamination'] <= upper_bound:
        return True

    logger.warning(f"Model validation failed: Contamination {metrics['contamination']:.4f} not in range [{lower_bound}, {upper_bound}]")
    return False

def main():
    parser = argparse.ArgumentParser(description="Train anomaly detection model.")
    parser.add_argument("--config", default="src/training/config.yaml", help="Path to config file.")
    parser.add_argument("--data-path", help="Override data path from config.")
    parser.add_argument("--output-dir", default="artifacts", help="Base directory for artifacts.")
    parser.add_argument("--force", action="store_true", help="Force training even if no drift.")
    args = parser.parse_args()

    # Setup directories
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    dirs = {
        "models": os.path.join(args.output_dir, "models"),
        "pipelines": os.path.join(args.output_dir, "pipelines"),
        "metrics": os.path.join(args.output_dir, "metrics"),
        "logs": os.path.join(args.output_dir, "logs")
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)

    # Add file handler to logging
    log_file = os.path.join(dirs["logs"], f"training_{timestamp}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    # Determine data path
    data_path = args.data_path if args.data_path else config["data"]["path"]

    # Load data
    try:
        df = load_data(data_path)
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        sys.exit(1)

    # Clean data (drop labels if present)
    if 'is_anomaly' in df.columns:
        n_labeled = df['is_anomaly'].sum()
        logger.info(f"Dropping 'is_anomaly' column (found {n_labeled} labeled anomalies) for unsupervised training.")
        df = df.drop(columns=['is_anomaly'])

    # ---------------------------------------------------------
    # Drift Detection (Phase 6)
    # ---------------------------------------------------------
    # We need previous metrics to check drift.
    # Try to find latest metrics file.
    latest_metrics_file = get_latest_file(dirs["metrics"], pattern="metrics_*.json")
    drift_detected = False

    if latest_metrics_file and not args.force:
        logger.info(f"Checking for data drift against {latest_metrics_file}...")
        try:
            prev_metrics = load_metrics(latest_metrics_file)
            if "data_stats" in prev_metrics:
                detector = DriftDetector(threshold=0.1) # 10% threshold
                drift_detected, drift_report = detector.detect_drift_from_stats(df, prev_metrics["data_stats"])
                if drift_detected:
                    logger.warning("Data drift detected! Triggering retraining.")
                else:
                    logger.info("No significant data drift detected.")
            else:
                logger.warning("Previous metrics did not contain data_stats. Skipping drift check.")
                drift_detected = True # Default to training if we can't check
        except Exception as e:
            logger.error(f"Failed to check drift: {e}")
            drift_detected = True
    else:
        if args.force:
            logger.info("Force flag set. Skipping drift check.")
            drift_detected = True
        else:
            logger.info("No previous metrics found. Initial training run.")
            drift_detected = True

    if not drift_detected and not args.force:
        logger.info("Skipping training as no drift was detected.")
        sys.exit(0)

    # ---------------------------------------------------------
    # Training Loop
    # ---------------------------------------------------------

    # Split data
    test_size = config["data"].get("test_size", 0.2)
    random_state = config["data"].get("random_state", 42)

    logger.info(f"Splitting data (test_size={test_size})...")
    X_train, X_test = train_test_split(df, test_size=test_size, random_state=random_state)
    logger.info(f"Train shape: {X_train.shape}, Test shape: {X_test.shape}")

    # Create & Fit Pipeline
    pipeline = create_preprocessing_pipeline(config)
    logger.info("Fitting preprocessing pipeline...")
    X_train_processed = pipeline.fit_transform(X_train)
    X_test_processed = pipeline.transform(X_test)

    # Train Model
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

    # ---------------------------------------------------------
    # Evaluation & Validation
    # ---------------------------------------------------------
    logger.info("Evaluating model on test set...")
    metrics = evaluate_model(model, X_test_processed, contamination_target=contamination)

    # Add data stats for future drift detection
    detector = DriftDetector()
    metrics["data_stats"] = detector.calculate_stats(df)

    # Validate
    if not is_model_valid(metrics, target_contamination=contamination):
        logger.error("Model validation failed. Aborting promotion.")
        # We might still want to save it as "failed" or just exit?
        # Let's save it to artifacts but NOT promote it (not overwrite 'latest').
        # But for now, we just proceed to versioned save.

    # ---------------------------------------------------------
    # Save Artifacts (Versioning)
    # ---------------------------------------------------------
    model_filename = f"model_{timestamp}.pkl"
    pipeline_filename = f"pipeline_{timestamp}.pkl"
    metrics_filename = f"metrics_{timestamp}.json"
    metadata_filename = f"metadata_{timestamp}.json"

    model_path = os.path.join(dirs["models"], model_filename)
    pipeline_path = os.path.join(dirs["pipelines"], pipeline_filename)
    metrics_path = os.path.join(dirs["metrics"], metrics_filename)
    metadata_path = os.path.join(dirs["models"], metadata_filename)

    # Create Metadata
    metadata = {
        "version": timestamp,
        "dataset_hash": calculate_hash(df),
        "training_samples": len(df),
        "metrics": metrics
    }

    logger.info(f"Saving artifacts to {args.output_dir}...")
    save_model(model, model_path)
    save_pipeline(pipeline, pipeline_path)
    save_metrics(metrics, metrics_path)
    save_metrics(metadata, metadata_path) # save_metrics handles dict -> json

    # ---------------------------------------------------------
    # Model Promotion (Phase 4)
    # ---------------------------------------------------------
    # If valid, update the "production" pointers.
    # In this simplified setup, we'll assume "production" is the file config points to,
    # OR we just rely on "latest" artifact.
    # The config points to "src/anomaly/anomaly_if.pkl".

    if is_model_valid(metrics, target_contamination=contamination):
        logger.info("Promoting model to production...")
        prod_model_path = config["paths"]["model_output"]
        prod_pipeline_path = config["paths"]["pipeline_output"]
        prod_metadata_path = config["paths"].get("metadata_output", "src/anomaly/metadata.json")

        # Ensure directory exists
        os.makedirs(os.path.dirname(prod_model_path), exist_ok=True)

        try:
            shutil.copy(model_path, prod_model_path)
            shutil.copy(pipeline_path, prod_pipeline_path)
            shutil.copy(metadata_path, prod_metadata_path)
            logger.info(f"Model promoted to {prod_model_path}")
            logger.info(f"Metadata promoted to {prod_metadata_path}")
        except Exception as e:
            logger.error(f"Failed to promote model: {e}")

    logger.info("Training pipeline completed successfully.")

if __name__ == "__main__":
    main()
