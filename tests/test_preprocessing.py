import unittest
import pandas as pd
import numpy as np
from sklearn.pipeline import Pipeline
from src.training.transformers import MissingValueHandler, NumericalScaler
from src.training.pipeline import create_preprocessing_pipeline

class TestPreprocessing(unittest.TestCase):
    def setUp(self):
        self.config = {
            "data": {
                "features": ["col1", "col2"]
            }
        }
        self.data = pd.DataFrame({
            "col1": [1.0, np.nan, 3.0],
            "col2": [4.0, 5.0, 6.0],
            "col3": [7.0, 8.0, 9.0]  # Should be dropped
        })

    def test_missing_value_handler(self):
        handler = MissingValueHandler(strategy="mean")
        transformed = handler.fit_transform(self.data[["col1"]])
        # Missing value should be replaced by mean (1+3)/2 = 2
        expected = pd.DataFrame({"col1": [1.0, 2.0, 3.0]})
        pd.testing.assert_frame_equal(transformed, expected)

    def test_numerical_scaler(self):
        scaler = NumericalScaler()
        transformed = scaler.fit_transform(self.data[["col2"]])
        # Standard scaler on [4, 5, 6] -> mean=5, std=sqrt(2/3)=0.816
        # (4-5)/0.816 = -1.2247
        self.assertAlmostEqual(transformed.iloc[0, 0], -1.2247, places=4)
        self.assertAlmostEqual(transformed.iloc[1, 0], 0.0, places=4)
        self.assertAlmostEqual(transformed.iloc[2, 0], 1.2247, places=4)

    def test_pipeline_creation(self):
        pipeline = create_preprocessing_pipeline(self.config)
        self.assertIsInstance(pipeline, Pipeline)

        # Test transformation
        transformed = pipeline.fit_transform(self.data)

        # Should have 2 columns (col1, col2) and 3 rows
        # ColumnTransformer returns numpy array by default
        self.assertEqual(transformed.shape, (3, 2))

        # Check if missing value was handled
        self.assertFalse(np.isnan(transformed).any())

        # Check that col3 was dropped (shape is (3, 2), not (3, 3))
        self.assertEqual(transformed.shape[1], 2)

if __name__ == "__main__":
    unittest.main()
