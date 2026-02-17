"""
Tests for hyperparameter space definitions.
"""

import pytest
import numpy as np

from optimization.hyperparameter_spaces import (
    IsolationForestSpace,
    RandomForestSpace,
    AutoencoderSpace,
    EnsembleWeightSpace,
    DetectionThresholdSpace,
    get_combined_space,
    parse_combined_params,
    ParameterSpace,
    ParameterType,
)


class TestIsolationForestSpace:
    """Test suite for IsolationForestSpace."""
    
    def test_get_space(self):
        """Test getting parameter bounds."""
        space = IsolationForestSpace.get_space()
        
        assert 'n_estimators' in space
        assert 'contamination' in space
        assert 'max_samples_ratio' in space
        assert 'max_features_ratio' in space
        
        # Check bounds
        assert space['n_estimators'] == (50.0, 500.0)
        assert space['contamination'] == (0.01, 0.2)
    
    def test_get_parameter_definitions(self):
        """Test getting detailed parameter definitions."""
        definitions = IsolationForestSpace.get_parameter_definitions()
        
        assert len(definitions) == 4
        
        # Check first parameter
        param = definitions[0]
        assert isinstance(param, ParameterSpace)
        assert param.name == 'n_estimators'
        assert param.param_type == ParameterType.INTEGER
    
    def test_convert_params(self):
        """Test parameter conversion."""
        raw_params = {
            'n_estimators': 150.0,
            'contamination': 0.05,
            'max_samples_ratio': 0.8,
            'max_features_ratio': 1.0,
        }
        
        converted = IsolationForestSpace.convert_params(
            raw_params, n_samples=1000, n_features=50
        )
        
        assert converted['n_estimators'] == 150
        assert converted['contamination'] == 0.05
        assert converted['max_samples'] == 800  # 0.8 * 1000
        assert converted['max_features'] == 1.0  # Full features
        assert converted['random_state'] == 42
        assert converted['n_jobs'] == -1
    
    def test_convert_params_auto_max_samples(self):
        """Test conversion with auto max_samples."""
        raw_params = {
            'n_estimators': 200.0,
            'contamination': 0.1,
            'max_samples_ratio': 1.0,  # Should become 'auto'
            'max_features_ratio': 0.5,
        }
        
        converted = IsolationForestSpace.convert_params(
            raw_params, n_samples=1000, n_features=50
        )
        
        assert converted['max_samples'] == 'auto'
        assert converted['max_features'] == 25  # 0.5 * 50


class TestRandomForestSpace:
    """Test suite for RandomForestSpace."""
    
    def test_get_space(self):
        """Test getting parameter bounds."""
        space = RandomForestSpace.get_space()
        
        assert 'n_estimators' in space
        assert 'max_depth' in space
        assert 'min_samples_split' in space
        assert 'min_samples_leaf' in space
        assert 'max_features_ratio' in space
    
    def test_convert_params(self):
        """Test parameter conversion."""
        raw_params = {
            'n_estimators': 100.0,
            'max_depth': 15.0,
            'min_samples_split': 5.0,
            'min_samples_leaf': 2.0,
            'max_features_ratio': 0.7,
        }
        
        converted = RandomForestSpace.convert_params(raw_params, n_features=50)
        
        assert converted['n_estimators'] == 100
        assert converted['max_depth'] == 15
        assert converted['min_samples_split'] == 5
        assert converted['min_samples_leaf'] == 2
        assert converted['max_features'] == 35  # 0.7 * 50
        assert converted['class_weight'] == 'balanced'


class TestAutoencoderSpace:
    """Test suite for AutoencoderSpace."""
    
    def test_get_space(self):
        """Test getting parameter bounds."""
        space = AutoencoderSpace.get_space()
        
        assert 'encoding_dim_ratio' in space
        assert 'learning_rate' in space
        assert 'dropout_rate' in space
        assert 'num_layers' in space
        assert 'hidden_units_ratio' in space
    
    def test_convert_params(self):
        """Test parameter conversion."""
        raw_params = {
            'encoding_dim_ratio': 0.16,
            'learning_rate': 0.001,
            'dropout_rate': 0.2,
            'num_layers': 2.0,
            'hidden_units_ratio': 1.0,
        }
        
        converted = AutoencoderSpace.convert_params(raw_params, input_dim=50)
        
        assert converted['encoding_dim'] == 8  # 0.16 * 50
        assert converted['learning_rate'] == 0.001
        assert converted['dropout_rate'] == 0.2
        assert converted['num_layers'] == 2
        assert converted['hidden_units'] == 8  # 1.0 * encoding_dim
        assert converted['input_dim'] == 50


class TestEnsembleWeightSpace:
    """Test suite for EnsembleWeightSpace."""
    
    def test_get_space(self):
        """Test getting parameter bounds."""
        space = EnsembleWeightSpace.get_space()
        
        assert 'isolation_forest_weight' in space
        assert 'random_forest_weight' in space
        assert 'autoencoder_weight' in space
    
    def test_convert_params(self):
        """Test weight normalization."""
        raw_params = {
            'isolation_forest_weight': 0.3,
            'random_forest_weight': 0.4,
            'autoencoder_weight': 0.3,
        }
        
        converted = EnsembleWeightSpace.convert_params(raw_params)
        
        # Should sum to 1.0
        total = sum(converted.values())
        assert abs(total - 1.0) < 1e-6
        
        assert converted['isolation_forest'] == 0.3
        assert converted['random_forest'] == 0.4
        assert converted['autoencoder'] == 0.3
    
    def test_convert_params_normalization(self):
        """Test weight normalization when sum != 1.0."""
        raw_params = {
            'isolation_forest_weight': 0.5,
            'random_forest_weight': 0.5,
            'autoencoder_weight': 0.5,  # Sum = 1.5
        }
        
        converted = EnsembleWeightSpace.convert_params(raw_params)
        
        # Should be normalized to sum to 1.0
        total = sum(converted.values())
        assert abs(total - 1.0) < 1e-6
        
        # Each should be 0.5/1.5 = 0.333...
        assert abs(converted['isolation_forest'] - 0.333) < 0.01


class TestDetectionThresholdSpace:
    """Test suite for DetectionThresholdSpace."""
    
    def test_get_space(self):
        """Test getting parameter bounds."""
        space = DetectionThresholdSpace.get_space()
        
        assert 'isolation_forest_threshold' in space
        assert 'random_forest_threshold' in space
        assert 'autoencoder_threshold' in space
        assert 'ensemble_threshold' in space
    
    def test_convert_params(self):
        """Test threshold conversion."""
        raw_params = {
            'isolation_forest_threshold': 0.6,
            'random_forest_threshold': 0.5,
            'autoencoder_threshold': 0.7,
            'ensemble_threshold': 0.85,
        }
        
        converted = DetectionThresholdSpace.convert_params(raw_params)
        
        assert converted['isolation_forest'] == 0.6
        assert converted['random_forest'] == 0.5
        assert converted['autoencoder'] == 0.7
        assert converted['ensemble'] == 0.85


class TestCombinedSpace:
    """Test suite for combined space functions."""
    
    def test_get_combined_space_all(self):
        """Test getting combined space with all components."""
        space = get_combined_space(
            include_isolation_forest=True,
            include_random_forest=True,
            include_autoencoder=True,
            include_ensemble_weights=True,
            include_thresholds=True
        )
        
        # Should have all parameters with prefixes
        assert any(key.startswith('if_') for key in space.keys())
        assert any(key.startswith('rf_') for key in space.keys())
        assert any(key.startswith('ae_') for key in space.keys())
        assert 'isolation_forest_weight' in space
        assert 'isolation_forest_threshold' in space
    
    def test_get_combined_space_partial(self):
        """Test getting combined space with partial components."""
        space = get_combined_space(
            include_isolation_forest=True,
            include_random_forest=False,
            include_autoencoder=False,
            include_ensemble_weights=True,
            include_thresholds=False
        )
        
        # Should only have IF and weight parameters
        assert any(key.startswith('if_') for key in space.keys())
        assert not any(key.startswith('rf_') for key in space.keys())
        assert 'isolation_forest_weight' in space
        assert 'isolation_forest_threshold' not in space
    
    def test_parse_combined_params(self):
        """Test parsing combined parameters."""
        combined_params = {
            'if_n_estimators': 150.0,
            'if_contamination': 0.05,
            'if_max_samples_ratio': 0.8,
            'if_max_features_ratio': 1.0,
            'rf_n_estimators': 100.0,
            'rf_max_depth': 15.0,
            'rf_min_samples_split': 5.0,
            'rf_min_samples_leaf': 2.0,
            'rf_max_features_ratio': 0.7,
            'isolation_forest_weight': 0.3,
            'random_forest_weight': 0.4,
            'autoencoder_weight': 0.3,
            'isolation_forest_threshold': 0.6,
            'random_forest_threshold': 0.5,
            'autoencoder_threshold': 0.7,
            'ensemble_threshold': 0.85,
        }
        
        parsed = parse_combined_params(combined_params, input_dim=50, n_samples=1000)
        
        # Check isolation forest params
        assert 'n_estimators' in parsed['isolation_forest']
        assert parsed['isolation_forest']['n_estimators'] == 150
        
        # Check random forest params
        assert 'n_estimators' in parsed['random_forest']
        assert parsed['random_forest']['n_estimators'] == 100
        
        # Check ensemble weights
        assert 'isolation_forest' in parsed['ensemble_weights']
        assert 'random_forest' in parsed['ensemble_weights']
        
        # Check thresholds
        assert 'isolation_forest' in parsed['thresholds']
        assert parsed['thresholds']['ensemble'] == 0.85


class TestParameterSpace:
    """Test suite for ParameterSpace dataclass."""
    
    def test_validate_value_continuous(self):
        """Test validation of continuous parameter."""
        param = ParameterSpace(
            name='test',
            param_type=ParameterType.CONTINUOUS,
            bounds=(0.0, 10.0),
            default_value=5.0
        )
        
        assert param.validate_value(5.0) is True
        assert param.validate_value(0.0) is True
        assert param.validate_value(10.0) is True
        assert param.validate_value(-1.0) is False
        assert param.validate_value(11.0) is False
    
    def test_validate_value_integer(self):
        """Test validation of integer parameter."""
        param = ParameterSpace(
            name='test',
            param_type=ParameterType.INTEGER,
            bounds=(1, 10),
            default_value=5
        )
        
        assert param.validate_value(5) is True
        assert param.validate_value(1) is True
        assert param.validate_value(10) is True
        assert param.validate_value(0) is False
        assert param.validate_value(11) is False
    
    def test_validate_value_categorical(self):
        """Test validation of categorical parameter."""
        param = ParameterSpace(
            name='test',
            param_type=ParameterType.CATEGORICAL,
            bounds=('a', 'b', 'c'),
            default_value='a'
        )
        
        assert param.validate_value('a') is True
        assert param.validate_value('b') is True
        assert param.validate_value('d') is False
