import pytest
import asyncio
import pickle
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock, mock_open
from typing import Dict

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from anomaly import anomaly_detector
from core.error_handling import ModelLoadError, AnomalyEngineError
from core.input_validation import ValidationError
from core.timeout_handler import TimeoutError as CustomTimeoutError
from core.circuit_breaker import CircuitOpenError


class SimpleModel:
    def predict(self, X):
        return [False]
    
    def score_samples(self, X):
        return [0.3]


@pytest.fixture
def sample_telemetry_data():
    return {
        "voltage": 8.0,
        "temperature": 25.0,
        "gyro": 0.05,
        "current": 1.0,
        "wheel_speed": 5.0,
    }


@pytest.fixture
def anomalous_telemetry_data():
    return {
        "voltage": 6.5,
        "temperature": 45.0,
        "gyro": 0.15,
        "current": 1.0,
        "wheel_speed": 5.0,
    }


@pytest.fixture
def invalid_telemetry_data():
    return {
        "voltage": "invalid",
        "temperature": None,
        "gyro": "not_a_number",
    }


@pytest.fixture(autouse=True)
def reset_module_state():
    anomaly_detector._MODEL = None
    anomaly_detector._MODEL_LOADED = False
    anomaly_detector._USING_HEURISTIC_MODE = False
    yield
    anomaly_detector._MODEL = None
    anomaly_detector._MODEL_LOADED = False
    anomaly_detector._USING_HEURISTIC_MODE = False


@pytest.fixture
def mock_model():
    model = Mock()
    model.predict = Mock(return_value=[False])
    model.score_samples = Mock(return_value=[0.3])
    return model


@pytest.fixture
def mock_health_monitor():
    monitor = Mock()
    monitor.register_component = Mock()
    monitor.mark_healthy = Mock()
    monitor.mark_degraded = Mock()
    return monitor


@pytest.fixture
def mock_resource_monitor():
    monitor = Mock()
    monitor.check_resource_health = Mock(return_value={'overall': 'healthy'})
    return monitor


class TestHeuristicDetection:

    def test_heuristic_normal_data(self, sample_telemetry_data):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(
            sample_telemetry_data
        )
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert not is_anomalous or score < 0.7

    def test_heuristic_anomalous_voltage(self):
        data = {"voltage": 6.0, "temperature": 25.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score >= 0.4

    def test_heuristic_anomalous_temperature(self):
        data = {"voltage": 8.0, "temperature": 50.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score >= 0.3

    def test_heuristic_anomalous_gyro(self):
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.2}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score >= 0.3

    def test_heuristic_multiple_anomalies(self, anomalous_telemetry_data):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(
            anomalous_telemetry_data
        )
        assert is_anomalous
        assert score > 0.8

    def test_heuristic_missing_fields(self):
        data = {}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_heuristic_invalid_data_types(self, invalid_telemetry_data):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(
            invalid_telemetry_data
        )
        assert isinstance(is_anomalous, bool)
        assert score >= 0.5

    def test_heuristic_non_dict_input(self):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic("not a dict")
        assert not is_anomalous
        assert score == 0.0

    def test_heuristic_score_capped_at_one(self):
        data = {"voltage": 5.0, "temperature": 60.0, "gyro": 0.5}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score <= 1.0


class TestModelLoading:

    @pytest.mark.asyncio
    async def test_load_model_success(self, mock_health_monitor):
        simple_model = SimpleModel()
        pickled_data = pickle.dumps(simple_model)
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=pickled_data)), \
             patch('asyncio.to_thread', return_value=simple_model), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            result = await anomaly_detector._load_model_impl()
            
            assert result is True
            assert anomaly_detector._MODEL_LOADED is True
            assert anomaly_detector._USING_HEURISTIC_MODE is False
            mock_health_monitor.mark_healthy.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_file_not_found(self, mock_health_monitor):
        with patch('os.path.exists', return_value=False), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            with pytest.raises(ModelLoadError) as exc_info:
                await anomaly_detector._load_model_impl()
            
            assert "Model file not found" in str(exc_info.value)
            assert anomaly_detector._MODEL_LOADED is False

    @pytest.mark.asyncio
    async def test_load_model_numpy_import_error(self, mock_health_monitor):
        with patch('builtins.__import__', side_effect=ImportError("No module named 'numpy'")), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            result = await anomaly_detector._load_model_impl()
            
            assert result is False
            assert anomaly_detector._USING_HEURISTIC_MODE is True
            assert anomaly_detector._MODEL_LOADED is False
            mock_health_monitor.mark_degraded.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_pickle_error(self, mock_health_monitor):
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('asyncio.to_thread', side_effect=pickle.UnpicklingError("Bad pickle")), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            with pytest.raises(pickle.UnpicklingError):
                await anomaly_detector._load_model_impl()

    @pytest.mark.asyncio
    async def test_load_model_fallback(self):
        result = await anomaly_detector._load_model_fallback()
        
        assert result is False
        assert anomaly_detector._USING_HEURISTIC_MODE is True

    @pytest.mark.asyncio
    async def test_load_model_circuit_breaker_open(self):
        mock_cb = Mock()
        mock_cb.call = AsyncMock(side_effect=CircuitOpenError("Circuit open"))
        
        with patch.object(anomaly_detector, '_model_loader_cb', mock_cb):
            result = await anomaly_detector.load_model()
            
            assert result is False
            assert anomaly_detector._USING_HEURISTIC_MODE is True

    @pytest.mark.asyncio
    async def test_load_model_unexpected_error(self):
        mock_cb = Mock()
        mock_cb.call = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        
        with patch.object(anomaly_detector, '_model_loader_cb', mock_cb):
            result = await anomaly_detector.load_model()
            
            assert result is False
            assert anomaly_detector._USING_HEURISTIC_MODE is True


class TestDetectAnomaly:

    @pytest.mark.asyncio
    async def test_detect_anomaly_with_model(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[
                 [False],
                 [0.3]
             ]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0
            assert not is_anomalous
            mock_health_monitor.mark_healthy.assert_called()

    @pytest.mark.asyncio
    async def test_detect_anomaly_heuristic_mode(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = None
        anomaly_detector._MODEL_LOADED = False
        anomaly_detector._USING_HEURISTIC_MODE = True
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('anomaly.anomaly_detector.load_model', return_value=False):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_detect_anomaly_critical_resources(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        mock_resource_monitor.check_resource_health.return_value = {'overall': 'critical'}
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            mock_health_monitor.mark_degraded.assert_called()

    @pytest.mark.asyncio
    async def test_detect_anomaly_validation_error(
        self, mock_health_monitor, mock_resource_monitor
    ):
        invalid_data = {"invalid": "data"}
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', side_effect=ValidationError("Invalid data")), \
             patch('anomaly.anomaly_detector.load_model', return_value=False):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(invalid_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_detect_anomaly_model_prediction_error(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=RuntimeError("Model error")):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            assert anomaly_detector._USING_HEURISTIC_MODE is True
            mock_health_monitor.mark_degraded.assert_called()

    @pytest.mark.asyncio
    async def test_detect_anomaly_model_without_score_samples(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        mock_model = Mock()
        mock_model.predict = Mock(return_value=[True])
        
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[[True], [0.5]]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_detect_anomaly_score_normalization(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[
                 [False],
                 [1.5]
             ]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_detect_anomaly_none_score(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[
                 [False],
                 [None]
             ]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert score == 0.5

    @pytest.mark.asyncio
    async def test_detect_anomaly_loads_model_if_needed(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL_LOADED = False
        
        async def mock_load_model():
            anomaly_detector._MODEL = mock_model
            anomaly_detector._MODEL_LOADED = True
            return True
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('anomaly.anomaly_detector.load_model', side_effect=mock_load_model), \
             patch('asyncio.to_thread', side_effect=[[False], [0.3]]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)


class TestIntegration:

    @pytest.mark.asyncio
    async def test_end_to_end_normal_flow(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        simple_model = SimpleModel()
        pickled_data = pickle.dumps(simple_model)
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=pickled_data)), \
             patch('asyncio.to_thread', side_effect=[
                 simple_model,
                 [False],
                 [0.3]
             ]), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data):
            
            load_result = await anomaly_detector.load_model()
            assert load_result is True
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert not is_anomalous
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_graceful_degradation(
        self, anomalous_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = Mock()
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=anomalous_telemetry_data), \
             patch('asyncio.to_thread', side_effect=RuntimeError("Model failed")):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(anomalous_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            assert anomaly_detector._USING_HEURISTIC_MODE is True


class TestEdgeCases:

    def test_heuristic_exact_threshold_voltage_low(self):
        data = {"voltage": 7.0, "temperature": 25.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_exact_threshold_voltage_high(self):
        data = {"voltage": 9.0, "temperature": 25.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_exact_threshold_temperature(self):
        data = {"voltage": 8.0, "temperature": 40.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_exact_threshold_gyro(self):
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.1}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_negative_gyro(self):
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": -0.15}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score >= 0.3

    def test_heuristic_empty_dict(self):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic({})
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_partial_data(self):
        data = {"voltage": 8.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)


class TestAdvancedHeuristics:
    """Advanced heuristic detection tests for comprehensive coverage."""

    def test_heuristic_extreme_low_voltage(self):
        """Test extremely low voltage detection."""
        data = {"voltage": 3.0, "temperature": 25.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        # Due to random noise, just verify score is elevated
        assert score >= 0.35  # Base 0.4 minus potential random variance
        assert isinstance(is_anomalous, bool)

    def test_heuristic_extreme_high_voltage(self):
        """Test extremely high voltage detection."""
        data = {"voltage": 15.0, "temperature": 25.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        # Due to random noise, just verify score is elevated
        assert score >= 0.35  # Base 0.4 minus potential random variance
        assert isinstance(is_anomalous, bool)

    def test_heuristic_extreme_temperature(self):
        """Test extreme temperature detection."""
        data = {"voltage": 8.0, "temperature": 100.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        # Due to random noise, just verify score is elevated
        assert score >= 0.25  # Base 0.3 minus potential random variance
        assert isinstance(is_anomalous, bool)

    def test_heuristic_extreme_gyro(self):
        """Test extreme gyro values."""
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 1.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        # Due to random noise, just verify score is elevated
        assert score >= 0.25  # Base 0.3 minus potential random variance
        assert isinstance(is_anomalous, bool)

    def test_heuristic_all_thresholds_exceeded(self):
        """Test when all thresholds are exceeded."""
        data = {"voltage": 5.0, "temperature": 80.0, "gyro": 0.5}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert is_anomalous
        assert score > 0.9

    def test_heuristic_with_extra_fields(self):
        """Test heuristic ignores extra fields."""
        data = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.02,
            "extra_field": "should be ignored",
            "another": 12345
        }
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_list_input(self):
        """Test heuristic with list input."""
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic([1, 2, 3])
        assert not is_anomalous
        assert score == 0.0

    def test_heuristic_none_input(self):
        """Test heuristic with None input."""
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(None)
        assert not is_anomalous
        assert score == 0.0

    def test_heuristic_string_values(self):
        """Test heuristic with string values in dict."""
        data = {
            "voltage": "eight",
            "temperature": "twenty-five",
            "gyro": "zero"
        }
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score >= 0.5

    def test_heuristic_mixed_valid_invalid(self):
        """Test heuristic with mix of valid and invalid values."""
        data = {
            "voltage": 8.0,
            "temperature": "invalid",
            "gyro": 0.02
        }
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert score >= 0.5

    def test_heuristic_zero_values(self):
        """Test heuristic with zero values."""
        data = {"voltage": 0.0, "temperature": 0.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        # Zero voltage should trigger anomaly detection
        assert score >= 0.35  # Base 0.4 minus potential random variance
        assert isinstance(is_anomalous, bool)

    def test_heuristic_negative_values(self):
        """Test heuristic with negative values."""
        data = {"voltage": -5.0, "temperature": -10.0, "gyro": -0.2}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert is_anomalous

    def test_heuristic_boundary_voltage_lower(self):
        """Test voltage at lower boundary (7.0)."""
        data = {"voltage": 7.0, "temperature": 25.0, "gyro": 0.02}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(score, float)

    def test_heuristic_boundary_voltage_upper(self):
        """Test voltage at upper boundary (9.0)."""
        data = {"voltage": 9.0, "temperature": 25.0, "gyro": 0.02}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(score, float)

    def test_heuristic_boundary_temperature(self):
        """Test temperature at boundary (40.0)."""
        data = {"voltage": 8.0, "temperature": 40.0, "gyro": 0.02}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(score, float)

    def test_heuristic_boundary_gyro(self):
        """Test gyro at boundary (0.1)."""
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.1}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(score, float)

    def test_heuristic_score_randomness(self):
        """Test that score includes random component."""
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.02}
        scores = []
        for _ in range(10):
            _, score = anomaly_detector._detect_anomaly_heuristic(data)
            scores.append(score)
        # Scores should vary slightly due to random noise
        assert len(set(scores)) > 1 or scores[0] == 0.0


class TestModelLoadingEdgeCases:
    """Additional model loading edge case tests."""

    @pytest.mark.asyncio
    async def test_load_model_permission_error(self, mock_health_monitor):
        """Test model loading with permission error."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', side_effect=PermissionError("Access denied")), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            with pytest.raises(PermissionError):
                await anomaly_detector._load_model_impl()

    @pytest.mark.asyncio
    async def test_load_model_corrupted_pickle(self, mock_health_monitor):
        """Test loading corrupted pickle file."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=b'corrupted data')), \
             patch('asyncio.to_thread', side_effect=pickle.UnpicklingError("Invalid pickle")), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            with pytest.raises(pickle.UnpicklingError):
                await anomaly_detector._load_model_impl()

    @pytest.mark.asyncio
    async def test_load_model_empty_file(self, mock_health_monitor):
        """Test loading empty model file."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=b'')), \
             patch('asyncio.to_thread', side_effect=EOFError("Empty file")), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            with pytest.raises(EOFError):
                await anomaly_detector._load_model_impl()

    @pytest.mark.asyncio
    async def test_load_model_with_retry_exhausted(self):
        """Test that retry eventually gives up after max attempts."""
        retry_count = 0
        
        async def failing_load():
            nonlocal retry_count
            retry_count += 1
            raise TimeoutError("Load timeout")
        
        with patch.object(anomaly_detector, '_load_model_impl', side_effect=failing_load):
            with pytest.raises(TimeoutError):
                await anomaly_detector._load_model_with_retry()
            
            # Should have tried max_attempts times (3)
            assert retry_count == 3

    @pytest.mark.asyncio
    async def test_load_model_idempotent(self, mock_health_monitor):
        """Test that loading model multiple times is safe."""
        simple_model = SimpleModel()
        pickled_data = pickle.dumps(simple_model)
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=pickled_data)), \
             patch('asyncio.to_thread', return_value=simple_model), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            result1 = await anomaly_detector._load_model_impl()
            result2 = await anomaly_detector._load_model_impl()
            
            assert result1 is True
            assert result2 is True
            assert anomaly_detector._MODEL_LOADED is True


class TestDetectAnomalyEdgeCases:
    """Additional detect_anomaly edge case tests."""

    @pytest.mark.asyncio
    async def test_detect_anomaly_empty_dict(
        self, mock_health_monitor, mock_resource_monitor
    ):
        """Test detection with empty dictionary."""
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value={}), \
             patch('anomaly.anomaly_detector.load_model', return_value=False):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly({})
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_detect_anomaly_model_returns_invalid_score(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        """Test when model returns invalid score type."""
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[
                 [False],
                 ["invalid_score"]  # Return string instead of float
             ]):
            
            # Should handle gracefully and fall back
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_detect_anomaly_model_negative_score(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        """Test model returning negative anomaly score."""
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[
                 [False],
                 [-2.5]
             ]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            # Score should be clamped to 0.0
            assert score >= 0.0

    @pytest.mark.asyncio
    async def test_detect_anomaly_model_score_above_one(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        """Test model returning score > 1.0."""
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[
                 [True],
                 [5.0]
             ]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            # Score should be clamped to 1.0
            assert score <= 1.0

    @pytest.mark.asyncio
    async def test_detect_anomaly_timeout(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        """Test detection timeout handling."""
        timeout_error = CustomTimeoutError(
            operation="test_operation",
            timeout_seconds=10.0
        )
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', side_effect=timeout_error), \
             patch('anomaly.anomaly_detector.load_model', return_value=False):
            
            # Should fall back to heuristic
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_detect_anomaly_concurrent_calls(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        """Test concurrent anomaly detection calls."""
        anomaly_detector._USING_HEURISTIC_MODE = True
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('anomaly.anomaly_detector.load_model', return_value=False):
            
            tasks = [
                anomaly_detector.detect_anomaly(sample_telemetry_data)
                for _ in range(5)
            ]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            for is_anomalous, score in results:
                assert isinstance(is_anomalous, bool)
                assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_detect_anomaly_resource_warning(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        """Test detection with resource warning state."""
        mock_resource_monitor.check_resource_health.return_value = {'overall': 'warning'}
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('anomaly.anomaly_detector.load_model', return_value=False):
            
            # Should continue normally
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_detect_anomaly_all_default_values(
        self, mock_health_monitor, mock_resource_monitor
    ):
        """Test detection when all values fall back to defaults."""
        data = {}  # Will use all defaults
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=data), \
             patch('anomaly.anomaly_detector.load_model', return_value=False):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)


class TestScoring:
    """Tests specifically for scoring logic."""

    def test_scoring_threshold_sensitivity(self):
        """Test scoring threshold of 0.5 for anomaly classification."""
        # Just below threshold
        data = {"voltage": 8.5, "temperature": 35.0, "gyro": 0.05}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        # Score might be below 0.5 due to random noise, but should be low
        assert score < 0.7

    def test_scoring_additive_nature(self):
        """Test that scores are additive across thresholds."""
        # Test single threshold
        data1 = {"voltage": 6.0, "temperature": 25.0, "gyro": 0.0}
        _, score1 = anomaly_detector._detect_anomaly_heuristic(data1)
        
        # Test two thresholds
        data2 = {"voltage": 6.0, "temperature": 45.0, "gyro": 0.0}
        _, score2 = anomaly_detector._detect_anomaly_heuristic(data2)
        
        # Score2 should be higher than score1
        assert score2 > score1

    def test_scoring_consistency(self):
        """Test that same input produces consistent score range."""
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.02}
        scores = []
        for _ in range(20):
            _, score = anomaly_detector._detect_anomaly_heuristic(data)
            scores.append(score)
        
        # All scores should be in similar range (accounting for random noise)
        assert max(scores) - min(scores) < 0.15  # Max variance due to random noise


class TestMetrics:
    """Test metrics recording."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_for_model_detection(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        """Test that metrics are recorded for model-based detection."""
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[[False], [0.3]]), \
             patch('anomaly.anomaly_detector.ANOMALY_DETECTIONS_TOTAL') as mock_metric:
            
            await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            # Verify metric was incremented
            mock_metric.labels.assert_called()

    @pytest.mark.asyncio
    async def test_metrics_recorded_for_heuristic_detection(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        """Test that metrics are recorded for heuristic detection."""
        anomaly_detector._USING_HEURISTIC_MODE = True
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('anomaly.anomaly_detector.load_model', return_value=False), \
             patch('anomaly.anomaly_detector.ANOMALY_DETECTIONS_TOTAL') as mock_metric:
            
            await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            # Verify metric was incremented
            mock_metric.labels.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=anomaly.anomaly_detector", "--cov-report=html", "--cov-report=term"])
