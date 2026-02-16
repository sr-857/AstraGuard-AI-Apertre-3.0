import numpy as np
import pandas as pd
from typing import Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class DriftDetector:
    """
    Detects data drift by comparing statistical properties of new data
    against reference statistics from a previous training run.
    """
    def __init__(self, threshold: float = 0.1):
        """
        Args:
            threshold (float): The percentage change (0.0 to 1.0) in mean or std
                               required to flag drift. Default 0.1 (10%).
        """
        self.threshold = threshold

    def detect_drift_from_stats(self, current_df: pd.DataFrame, reference_stats: Dict) -> Tuple[bool, Dict]:
        """
        Check for drift between current dataframe and reference statistics.

        Args:
            current_df: The new data to check.
            reference_stats: Dictionary containing baseline stats (mean, std) for features.
                             Structure: {'feature_name': {'mean': float, 'std': float}}

        Returns:
            drift_detected: Boolean indicating if drift was detected.
            report: Dictionary containing drift metrics per feature.
        """
        drift_detected = False
        report = {}

        # Get numeric columns
        numeric_cols = current_df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            if col not in reference_stats:
                # If feature is new, we can't check drift, but it's arguably a schema change
                continue

            cur_mean = current_df[col].mean()
            cur_std = current_df[col].std()

            ref_mean = reference_stats[col].get('mean', 0.0)
            ref_std = reference_stats[col].get('std', 1.0)

            epsilon = 1e-9

            # Metric 1: Mean shift relative to standard deviation (Z-score like)
            # This handles cases where mean is close to 0 but data has variance.
            # If ref_std is 0 (constant feature), fall back to absolute difference or strict match.
            denom = abs(ref_std) if abs(ref_std) > epsilon else 1.0
            mean_drift_score = abs(cur_mean - ref_mean) / denom

            # Metric 2: Std change ratio (percentage change)
            std_drift_score = abs(cur_std - ref_std) / (abs(ref_std) + epsilon)

            is_drifting = False

            # Check thresholds
            # For mean drift (Z-score), a threshold of 0.1 means mean shifted by 0.1 std dev.
            # For std drift, 0.1 means std changed by 10%.
            if mean_drift_score > self.threshold or std_drift_score > self.threshold:
                is_drifting = True
                drift_detected = True
                logger.info(f"Drift detected in {col}: mean_drift={mean_drift_score:.4f}, std_drift={std_drift_score:.4f}")

            report[col] = {
                "mean_current": float(cur_mean),
                "mean_ref": float(ref_mean),
                "mean_drift_score": float(mean_drift_score),
                "std_current": float(cur_std),
                "std_ref": float(ref_std),
                "std_drift_score": float(std_drift_score),
                "drift": is_drifting
            }

        return drift_detected, report

    def calculate_stats(self, df: pd.DataFrame) -> Dict:
        """
        Calculate mean and std for numeric columns in the dataframe.

        Args:
            df: The dataframe to analyze.

        Returns:
            stats: Dictionary of stats suitable for saving to JSON.
        """
        stats = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            stats[col] = {
                'mean': float(df[col].mean()),
                'std': float(df[col].std())
            }
        return stats
