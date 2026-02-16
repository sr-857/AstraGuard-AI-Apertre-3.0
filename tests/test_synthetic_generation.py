import unittest
import pandas as pd
import numpy as np
import os
import sys

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.synthetic.generator import generate_normal_data
from src.data.synthetic import generate_dataset

class TestSyntheticData(unittest.TestCase):

    def test_reproducibility(self):
        """Test that the generator produces the same data with the same seed."""
        # Note: generate_dataset resets the global numpy seed via generate_normal_data -> config['random_seed']
        df1 = generate_dataset()
        df2 = generate_dataset()

        pd.testing.assert_frame_equal(df1, df2)

    def test_shape_and_columns(self):
        """Test output shape and required columns."""
        df = generate_dataset()
        # Default columns + is_anomaly
        expected_cols = ['voltage', 'temperature', 'current', 'wheel_speed', 'gyro', 'is_anomaly']

        self.assertEqual(len(df), 10000) # Default config samples
        for col in expected_cols:
            self.assertTrue(col in df.columns, f"Column {col} missing")

    def test_anomalies_present(self):
        """Test that anomalies are actually injected."""
        df = generate_dataset()
        n_anomalies = df['is_anomaly'].sum()
        self.assertGreater(n_anomalies, 0)
        # Expect roughly 5% (500)
        # Allow range 300-700
        self.assertTrue(300 < n_anomalies < 700, f"Anomalies count {n_anomalies} out of expected range (300-700)")

    def test_correlations(self):
        """Test basic physical correlations (sanity check)."""
        # We test on normal data to avoid anomalies skewing correlations
        df = generate_normal_data()

        # Check that higher speed correlates with higher current
        # In our model: Current = Mean + Factor * (Speed - MeanSpeed) + Noise
        # Factor is positive (0.4). So correlation should be positive.
        corr_speed_current = df['wheel_speed'].corr(df['current'])
        self.assertGreater(corr_speed_current, 0.3, f"Speed-Current correlation {corr_speed_current:.2f} too low")

        # Check that higher current correlates with higher temperature (or rather, integrated current/drift)
        # Our model: Temp = Mean + Drift*t + Factor*(Current - Mean) + Noise
        # Since both Drift and Current effect are positive (usually), correlation should be positive.
        # Current fluctuates, Temp has trend.
        # Detrending might be needed for pure correlation, but raw correlation should be positive.
        # However, let's verify drift dominating.
        df['time'] = np.arange(len(df))
        corr_time_temp = df['time'].corr(df['temperature'])
        self.assertGreater(corr_time_temp, 0.5, f"Time-Temp drift correlation {corr_time_temp:.2f} too low")

if __name__ == '__main__':
    unittest.main()
