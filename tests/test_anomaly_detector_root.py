import pytest
import asyncio
import os
import tempfile
import pickle
from unittest.mock import patch, MagicMock, AsyncMock
from anomaly.anomaly_detector import (
    detect_anomaly,
    _detect_anomaly_heuristic,
    load_model,
    _MODEL,
    _MODEL_LOADED,
    _USING_HEURISTIC_MODE,
)



# Mock model for pickling tests
class MockModelForPickle:
    def predict(self, X): return [0]


class TestAnomalyDetector:
    """Unit tests for anomaly detector module."""

    @pytest.fixture(autouse=True)
    def reset_globals(self):
        """Reset global state before each test."""
        global _MODEL, _MODEL_LOADED, _USING_HEURISTIC_MODE
        _MODEL = None
        _MODEL_LOADED = False
        _USING_HEURISTIC_MODE = False
        yield
        # Cleanup after test
        _MODEL = None
        _MODEL_LOADED = False
        _USING_HEURISTIC_MODE = False

    def test_detect_anomaly_heuristic_normal_data(self):
        """Test heuristic detection with normal telemetry data."""
        data = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.0
        }
        is_anomalous, score = _detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        # Normal data should not be anomalous
        assert not is_anomalous

    def test_detect_anomaly_heuristic_high_voltage(self):
        """Test heuristic detection with high voltage anomaly."""
        data = {
            "voltage": 9.5,  # Above threshold
            "temperature": 25.0,
            "gyro": 0.0
        }
        is_anomalous, score = _detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert score > 0.3  # Should have significant score

    def test_detect_anomaly_heuristic_high_temperature(self):
        """Test heuristic detection with high temperature anomaly."""
        data = {
            "voltage": 8.0,
            "temperature": 45.0,  # Above threshold
            "gyro": 0.0
        }
        is_anomalous, score = _detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert score > 0.2  # Should have score

    def test_detect_anomaly_heuristic_invalid_input(self):
        """Test heuristic detection with invalid input."""
        is_anomalous, score = _detect_anomaly_heuristic("invalid")
        assert not is_anomalous
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_detect_anomaly_without_model(self):
        """Test anomaly detection falls back to heuristic when no model."""
        data = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.0,
            "current": 5.0,
            "wheel_speed": 10.0,
            "battery_level": 80.0
        }
        is_anomalous, score = await detect_anomaly(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    @patch('anomaly.anomaly_detector._MODEL_LOADED', True)
    @patch('anomaly.anomaly_detector._MODEL')
    @patch('anomaly.anomaly_detector._USING_HEURISTIC_MODE', False)
    async def test_detect_anomaly_with_model(self, mock_model):
        """Test anomaly detection using model when available."""
        # Mock model
        mock_model.predict.return_value = [1]  # Anomalous
        mock_model.score_samples.return_value = [0.8]

        data = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.0,
            "current": 5.0,
            "wheel_speed": 10.0,
            "battery_level": 80.0
        }

        with patch('anomaly.anomaly_detector._MODEL', mock_model):
            with patch('anomaly.anomaly_detector.get_resource_monitor') as mock_rm_get:
                mock_monitor = MagicMock()
                mock_monitor.check_resource_health.return_value = {'overall': 'healthy'}
                mock_rm_get.return_value = mock_monitor
                
                is_anomalous, score = await detect_anomaly(data)
                assert is_anomalous
                assert score == 0.8

    @pytest.mark.asyncio
    async def test_detect_anomaly_resource_critical(self):
        """Test anomaly detection uses heuristic when resources are critical."""
        data = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.0,
            "current": 5.0,
            "wheel_speed": 10.0,
            "battery_level": 80.0
        }

        with patch('anomaly.anomaly_detector.get_resource_monitor') as mock_rm:
            mock_monitor = MagicMock()
            mock_monitor.check_resource_health.return_value = {'overall': 'critical'}
            mock_rm.return_value = mock_monitor

            is_anomalous, score = await detect_anomaly(data)
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_load_model_success(self):
        """Test successful model loading."""
        # Create a temporary model file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            mock_model = MockModelForPickle()
            pickle.dump(mock_model, f)
            temp_path = f.name

        try:
            with patch('anomaly.anomaly_detector.MODEL_PATH', temp_path):
                result = await load_model()
                assert result is True
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_load_model_no_file(self):
        """Test model loading when file doesn't exist."""
        with patch('anomaly.anomaly_detector.MODEL_PATH', '/nonexistent/path/model.pkl'):
            result = await load_model()
            assert result is False

    @pytest.mark.asyncio
    async def test_load_model_numpy_import_error(self):
        """Test model loading falls back when numpy import fails."""
        with patch('anomaly.anomaly_detector.MODEL_PATH', '/nonexistent/path/model.pkl'):
            with patch.dict('sys.modules', {'numpy': None}):
                result = await load_model()
                assert result is False
                # Should be in heuristic mode
                from anomaly.anomaly_detector import _USING_HEURISTIC_MODE
                assert _USING_HEURISTIC_MODE

    def test_detect_anomaly_heuristic_combined_anomalies(self):
        """Test heuristic detection with multiple anomaly conditions."""
        data = {
            "voltage": 6.5,  # Low voltage
            "temperature": 50.0,  # High temperature
            "gyro": 0.2  # High gyro
        }
        is_anomalous, score = _detect_anomaly_heuristic(data)
        assert score > 0.5  # Combined score should be high
        assert is_anomalous

    @pytest.mark.asyncio
    async def test_detect_anomaly_validation_error(self):
        """Test anomaly detection handles validation errors."""
        # Invalid data that should fail validation
        data = {
            "voltage": "invalid",
            "temperature": 25.0,
            "gyro": 0.0
        }
        