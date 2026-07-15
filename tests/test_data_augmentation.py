"""
Tests for Data Augmentation Module
"""

import unittest
import pandas as pd
import numpy as np
from src.security_engine.data_augmentation import DataAugmenter

class TestDataAugmentation(unittest.TestCase):

    def setUp(self):
        # Create sample dataframe
        self.df = pd.DataFrame({
            'cpu_usage': range(100),
            'memory_usage': range(100, 200),
            'failure_occurred': [False] * 90 + [True] * 10
        })
        self.augmenter = DataAugmenter(random_seed=42)

    def test_jitter(self):
        data = np.array([1.0, 2.0, 3.0])
        jittered = self.augmenter.jitter(data)
        self.assertEqual(data.shape, jittered.shape)
        self.assertFalse(np.array_equal(data, jittered))

    def test_scaling(self):
        data = np.array([1.0, 2.0, 3.0])
        scaled = self.augmenter.scaling(data)
        self.assertEqual(data.shape, scaled.shape)
        self.assertFalse(np.array_equal(data, scaled))

    def test_augment_dataframe(self):
        original_len = len(self.df)
        augmented_df = self.augmenter.augment_dataframe(self.df, multiplier=1)
        
        # Expect original + 1 copy = 2x original length
        self.assertEqual(len(augmented_df), original_len * 2)
        
        # Check if 'is_synthetic' column exists
        self.assertIn('is_synthetic', augmented_df.columns)
        
        # Check if original data is preserved (first half)
        # Note: concat usually appends.
        self.assertTrue(pd.isna(augmented_df.iloc[0].get('is_synthetic', np.nan)) or augmented_df.iloc[0]['is_synthetic'] == False)

    def test_apply_augmentation_pipeline(self):
        # Current length is 100. Min required is 300.
        # Multiplier should be ceil((300-100)/100) = 2.
        # Total length = 100 + 2*100 = 300.
        augmented_df = self.augmenter.apply_augmentation_pipeline(self.df, min_samples=300)
        self.assertEqual(len(augmented_df), 300)

    def test_pipeline_no_augmentation_needed(self):
        augmented_df = self.augmenter.apply_augmentation_pipeline(self.df, min_samples=50)
        self.assertEqual(len(augmented_df), 100)

if __name__ == '__main__':
    unittest.main()
