import pytest
import pandas as pd
import numpy as np
from src.training.drift import DriftDetector

def test_detect_drift_no_drift():
    # Use higher threshold for small sample noise, or larger N
    detector = DriftDetector(threshold=0.2)

    # Same distribution
    np.random.seed(42)
    df1 = pd.DataFrame({'a': np.random.normal(0, 1, 1000)})
    stats = detector.calculate_stats(df1)

    # Another sample from same distribution
    df2 = pd.DataFrame({'a': np.random.normal(0, 1, 1000)})

    drift_detected, report = detector.detect_drift_from_stats(df2, stats)

    # At N=1000, SE is ~0.03. 0.2 threshold is > 6 sigma. Should be safe.
    assert not drift_detected, f"False positive drift: {report}"
    assert not report['a']['drift']

def test_detect_drift_mean_shift():
    detector = DriftDetector(threshold=0.1)

    # Baseline
    np.random.seed(42)
    df1 = pd.DataFrame({'a': np.random.normal(10, 1, 1000)})
    stats = detector.calculate_stats(df1)

    # Drifted (mean 12 vs 10. std=1. Shift is 2.0 sigma >> 0.1)
    df2 = pd.DataFrame({'a': np.random.normal(12, 1, 1000)})

    drift_detected, report = detector.detect_drift_from_stats(df2, stats)
    assert drift_detected
    assert report['a']['drift']
    assert report['a']['mean_drift_score'] > 0.1

def test_detect_drift_std_shift():
    detector = DriftDetector(threshold=0.1)

    # Baseline
    np.random.seed(42)
    df1 = pd.DataFrame({'a': np.random.normal(0, 1, 1000)})
    stats = detector.calculate_stats(df1)

    # Drifted (std 1.5 vs 1.0 = 50% shift > 10%)
    df2 = pd.DataFrame({'a': np.random.normal(0, 1.5, 1000)})

    drift_detected, report = detector.detect_drift_from_stats(df2, stats)
    assert drift_detected
    assert report['a']['drift']
    assert report['a']['std_drift_score'] > 0.1
