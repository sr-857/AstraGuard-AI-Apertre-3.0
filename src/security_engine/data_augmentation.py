"""
Data Augmentation Module for Predictive Maintenance

Provides techniques to generate synthetic training data for time-series analysis
to improve model robustness and handle data scarcity.
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Union
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

class DataAugmenter:
    """
    Data augmentation strategies for time-series telemetry data.
    """

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)

    def augment_dataframe(self, df: pd.DataFrame, multiplier: int = 1, noise_level: float = 0.05) -> pd.DataFrame:
        """
        Augment the dataframe by creating variations of existing data points.
        
        Args:
            df: Source DataFrame containing telemetry data.
            multiplier: Number of augmented copies to create per original record.
            noise_level: Standard deviation of Gaussian noise to add (relative to value).

        Returns:
            DataFrame containing original + synthetic data.
        """
        if df.empty:
            return df
            
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        # Exclude boolean or target flags if they are encoded as numbers but shouldn't be jittered
        # Assuming 'failure_occurred' might be boolean or int 0/1, we shouldn't jitter it.
        exclude_cols = ['failure_occurred', 'is_anomaly', 'timestamp']
        target_cols = [c for c in numeric_cols if c not in exclude_cols]

        augmented_dfs = [df]

        for i in range(multiplier):
            synthetic_df = df.copy()
            
            # Apply Gaussian noise (Jittering)
            for col in target_cols:
                # Add noise proportional to the standard deviation of the column, or the value itself
                # Here we use noise relative to the value itself (multiplicative noise) or additive?
                # Additive noise based on column std is safer for 0 values.
                
                std_dev = synthetic_df[col].std()
                if std_dev == 0:
                    std_dev = 1.0 # Fallback
                
                noise = np.random.normal(0, std_dev * noise_level, size=len(synthetic_df))
                synthetic_df[col] += noise

            # Mark as synthetic if we want to track it (optional column)
            synthetic_df['is_synthetic'] = True
            
            augmented_dfs.append(synthetic_df)

        result_df = pd.concat(augmented_dfs, ignore_index=True)
        
        # If timestamp is present, we might want to shift synthetic data or keep it same?
        # For training, if we treat rows as independent samples (Random Forest), timestamp doesn't matter much.
        # For LSTM (sequences), exact timestamp might matter less than relative order.
        # Let's keep timestamps as is, essentially treating them as "alternate concurrent realities".
        
        return result_df

    def jitter(self, data: np.ndarray, sigma: float = 0.05) -> np.ndarray:
        """Apply additive Gaussian noise."""
        noise = np.random.normal(loc=0, scale=sigma, size=data.shape)
        return data + noise

    def scaling(self, data: np.ndarray, sigma: float = 0.1) -> np.ndarray:
        """Apply random scaling."""
        if data.ndim == 1:
            scaling_factor = np.random.normal(loc=1.0, scale=sigma, size=data.shape)
        else:
            scaling_factor = np.random.normal(loc=1.0, scale=sigma, size=(data.shape[0], 1))
        
        return data * scaling_factor

    def apply_augmentation_pipeline(self, df: pd.DataFrame, min_samples: int = 1000) -> pd.DataFrame:
        """
        Automatically augment DataFrame if it has fewer than min_samples.
        """
        current_samples = len(df)
        if current_samples >= min_samples:
            return df
        
        # Calculate how multiple times we need to duplicate
        multiplier = int(np.ceil((min_samples - current_samples) / current_samples))
        
        logger.info(f"Augmenting data: increasing from {current_samples} to cover {min_samples} required (Multiplier: {multiplier})")
        
        return self.augment_dataframe(df, multiplier=multiplier)

