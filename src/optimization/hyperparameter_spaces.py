"""
Hyperparameter Space Definitions for Bayesian Optimization

Defines search spaces for various ML models and ensemble configurations
used in threat detection.
"""

from typing import Dict, Tuple, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ParameterType(Enum):
    """Types of hyperparameters."""
    INTEGER = "int"
    CONTINUOUS = "float"
    CATEGORICAL = "categorical"
    LOG_SCALE = "log"


@dataclass
class ParameterSpace:
    """Definition of a parameter search space."""
    name: str
    param_type: ParameterType
    bounds: Tuple[Any, ...]
    default_value: Optional[Any] = None
    description: str = ""
    
    def validate_value(self, value: Any) -> bool:
        """Validate if value is within bounds."""
        if self.param_type == ParameterType.CATEGORICAL:
            return value in self.bounds
        elif self.param_type in [ParameterType.INTEGER, ParameterType.CONTINUOUS, ParameterType.LOG_SCALE]:
            return self.bounds[0] <= value <= self.bounds[1]
        return False


class IsolationForestSpace:
    """
    Hyperparameter space for Isolation Forest model.
    
    Key parameters:
    - n_estimators: Number of base estimators
    - contamination: Expected proportion of outliers
    - max_samples: Number of samples to draw for training
    - max_features: Number of features to draw
    """
    
    @staticmethod
    def get_space() -> Dict[str, Tuple[float, float]]:
        """Get parameter bounds for Bayesian optimization."""
        return {
            'n_estimators': (50.0, 500.0),      # Will be converted to int
            'contamination': (0.01, 0.2),        # Expected anomaly rate
            'max_samples_ratio': (0.5, 1.0),     # Ratio of samples to use
            'max_features_ratio': (0.5, 1.0),   # Ratio of features to use
        }
    
    @staticmethod
    def get_parameter_definitions() -> List[ParameterSpace]:
        """Get detailed parameter definitions."""
        return [
            ParameterSpace(
                name='n_estimators',
                param_type=ParameterType.INTEGER,
                bounds=(50, 500),
                default_value=200,
                description="Number of base estimators in the ensemble"
            ),
            ParameterSpace(
                name='contamination',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.01, 0.2),
                default_value=0.05,
                description="Expected proportion of outliers in the data"
            ),
            ParameterSpace(
                name='max_samples_ratio',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.5, 1.0),
                default_value=1.0,
                description="Ratio of training samples to use"
            ),
            ParameterSpace(
                name='max_features_ratio',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.5, 1.0),
                default_value=1.0,
                description="Ratio of features to use"
            ),
        ]
    
    @staticmethod
    def convert_params(params: Dict[str, float], n_samples: int, n_features: int) -> Dict[str, Any]:
        """
        Convert optimized parameters to model parameters.
        
        Args:
            params: Raw optimized parameters
            n_samples: Number of samples in dataset
            n_features: Number of features
            
        Returns:
            Dictionary with properly typed parameters
        """
        converted = {
            'n_estimators': int(params['n_estimators']),
            'contamination': float(params['contamination']),
            'random_state': 42,
            'n_jobs': -1,
        }
        
        # Convert max_samples
        max_samples_ratio = params['max_samples_ratio']
        if max_samples_ratio >= 1.0:
            converted['max_samples'] = 'auto'
        else:
            converted['max_samples'] = int(n_samples * max_samples_ratio)
        
        # Convert max_features
        max_features_ratio = params['max_features_ratio']
        if max_features_ratio >= 1.0:
            converted['max_features'] = 1.0
        else:
            converted['max_features'] = max(1, int(n_features * max_features_ratio))
        
        return converted


class RandomForestSpace:
    """
    Hyperparameter space for Random Forest classifier.
    
    Key parameters:
    - n_estimators: Number of trees
    - max_depth: Maximum depth of trees
    - min_samples_split: Minimum samples to split a node
    - min_samples_leaf: Minimum samples in leaf node
    """
    
    @staticmethod
    def get_space() -> Dict[str, Tuple[float, float]]:
        """Get parameter bounds for Bayesian optimization."""
        return {
            'n_estimators': (50.0, 500.0),       # Will be converted to int
            'max_depth': (5.0, 50.0),            # Will be converted to int
            'min_samples_split': (2.0, 20.0),    # Will be converted to int
            'min_samples_leaf': (1.0, 10.0),     # Will be converted to int
            'max_features_ratio': (0.3, 1.0),   # Ratio of features to consider
        }
    
    @staticmethod
    def get_parameter_definitions() -> List[ParameterSpace]:
        """Get detailed parameter definitions."""
        return [
            ParameterSpace(
                name='n_estimators',
                param_type=ParameterType.INTEGER,
                bounds=(50, 500),
                default_value=200,
                description="Number of trees in the forest"
            ),
            ParameterSpace(
                name='max_depth',
                param_type=ParameterType.INTEGER,
                bounds=(5, 50),
                default_value=15,
                description="Maximum depth of the trees"
            ),
            ParameterSpace(
                name='min_samples_split',
                param_type=ParameterType.INTEGER,
                bounds=(2, 20),
                default_value=10,
                description="Minimum samples required to split a node"
            ),
            ParameterSpace(
                name='min_samples_leaf',
                param_type=ParameterType.INTEGER,
                bounds=(1, 10),
                default_value=5,
                description="Minimum samples required in a leaf node"
            ),
            ParameterSpace(
                name='max_features_ratio',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.3, 1.0),
                default_value=1.0,
                description="Ratio of features to consider for best split"
            ),
        ]
    
    @staticmethod
    def convert_params(params: Dict[str, float], n_features: int) -> Dict[str, Any]:
        """
        Convert optimized parameters to model parameters.
        
        Args:
            params: Raw optimized parameters
            n_features: Number of features
            
        Returns:
            Dictionary with properly typed parameters
        """
        converted = {
            'n_estimators': int(params['n_estimators']),
            'max_depth': int(params['max_depth']),
            'min_samples_split': int(params['min_samples_split']),
            'min_samples_leaf': int(params['min_samples_leaf']),
            'random_state': 42,
            'n_jobs': -1,
            'class_weight': 'balanced',
        }
        
        # Convert max_features
        max_features_ratio = params['max_features_ratio']
        if max_features_ratio >= 1.0:
            converted['max_features'] = 'auto'
        else:
            converted['max_features'] = max(1, int(n_features * max_features_ratio))
        
        return converted


class AutoencoderSpace:
    """
    Hyperparameter space for Autoencoder neural network.
    
    Key parameters:
    - encoding_dim: Size of encoded representation
    - learning_rate: Learning rate for optimizer
    - dropout_rate: Dropout regularization
    - num_layers: Number of hidden layers
    - hidden_units: Units per hidden layer
    """
    
    @staticmethod
    def get_space() -> Dict[str, Tuple[float, float]]:
        """Get parameter bounds for Bayesian optimization."""
        return {
            'encoding_dim_ratio': (0.1, 0.5),    # Ratio of input dimension
            'learning_rate': (1e-4, 1e-2),       # Log scale
            'dropout_rate': (0.0, 0.5),
            'num_layers': (1.0, 4.0),             # Will be converted to int
            'hidden_units_ratio': (0.5, 2.0),    # Multiplier of encoding_dim
        }
    
    @staticmethod
    def get_parameter_definitions() -> List[ParameterSpace]:
        """Get detailed parameter definitions."""
        return [
            ParameterSpace(
                name='encoding_dim_ratio',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.1, 0.5),
                default_value=0.16,  # 8/50 for default input_dim=50
                description="Ratio of input dimension for encoding layer"
            ),
            ParameterSpace(
                name='learning_rate',
                param_type=ParameterType.LOG_SCALE,
                bounds=(1e-4, 1e-2),
                default_value=1e-3,
                description="Learning rate for Adam optimizer"
            ),
            ParameterSpace(
                name='dropout_rate',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.0, 0.5),
                default_value=0.2,
                description="Dropout rate for regularization"
            ),
            ParameterSpace(
                name='num_layers',
                param_type=ParameterType.INTEGER,
                bounds=(1, 4),
                default_value=2,
                description="Number of hidden layers in encoder/decoder"
            ),
            ParameterSpace(
                name='hidden_units_ratio',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.5, 2.0),
                default_value=1.0,
                description="Multiplier for hidden layer units relative to encoding_dim"
            ),
        ]
    
    @staticmethod
    def convert_params(params: Dict[str, float], input_dim: int) -> Dict[str, Any]:
        """
        Convert optimized parameters to model parameters.
        
        Args:
            params: Raw optimized parameters
            input_dim: Input dimension
            
        Returns:
            Dictionary with properly typed parameters
        """
        encoding_dim = max(2, int(input_dim * params['encoding_dim_ratio']))
        hidden_units = int(encoding_dim * params['hidden_units_ratio'])
        
        return {
            'encoding_dim': encoding_dim,
            'learning_rate': float(params['learning_rate']),
            'dropout_rate': float(params['dropout_rate']),
            'num_layers': int(params['num_layers']),
            'hidden_units': hidden_units,
            'input_dim': input_dim,
        }


class EnsembleWeightSpace:
    """
    Hyperparameter space for ensemble model weights.
    
    Optimizes the voting weights for each model in the ensemble.
    """
    
    @staticmethod
    def get_space() -> Dict[str, Tuple[float, float]]:
        """Get parameter bounds for Bayesian optimization."""
        return {
            'isolation_forest_weight': (0.1, 0.6),
            'random_forest_weight': (0.1, 0.6),
            'autoencoder_weight': (0.1, 0.6),
        }
    
    @staticmethod
    def get_parameter_definitions() -> List[ParameterSpace]:
        """Get detailed parameter definitions."""
        return [
            ParameterSpace(
                name='isolation_forest_weight',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.1, 0.6),
                default_value=0.3,
                description="Weight for Isolation Forest predictions"
            ),
            ParameterSpace(
                name='random_forest_weight',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.1, 0.6),
                default_value=0.4,
                description="Weight for Random Forest predictions"
            ),
            ParameterSpace(
                name='autoencoder_weight',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.1, 0.6),
                default_value=0.3,
                description="Weight for Autoencoder predictions"
            ),
        ]
    
    @staticmethod
    def convert_params(params: Dict[str, float]) -> Dict[str, float]:
        """
        Convert and normalize weights to sum to 1.0.
        
        Args:
            params: Raw optimized parameters
            
        Returns:
            Dictionary with normalized weights
        """
        total = (
            params['isolation_forest_weight'] +
            params['random_forest_weight'] +
            params['autoencoder_weight']
        )
        
        return {
            'isolation_forest': params['isolation_forest_weight'] / total,
            'random_forest': params['random_forest_weight'] / total,
            'autoencoder': params['autoencoder_weight'] / total,
        }


class DetectionThresholdSpace:
    """
    Hyperparameter space for detection thresholds.
    
    Optimizes thresholds for each model to achieve target false positive rate.
    """
    
    @staticmethod
    def get_space() -> Dict[str, Tuple[float, float]]:
        """Get parameter bounds for Bayesian optimization."""
        return {
            'isolation_forest_threshold': (0.3, 0.9),
            'random_forest_threshold': (0.3, 0.9),
            'autoencoder_threshold': (0.3, 0.9),
            'ensemble_threshold': (0.5, 0.95),
        }
    
    @staticmethod
    def get_parameter_definitions() -> List[ParameterSpace]:
        """Get detailed parameter definitions."""
        return [
            ParameterSpace(
                name='isolation_forest_threshold',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.3, 0.9),
                default_value=0.6,
                description="Threshold for Isolation Forest anomaly detection"
            ),
            ParameterSpace(
                name='random_forest_threshold',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.3, 0.9),
                default_value=0.5,
                description="Threshold for Random Forest anomaly detection"
            ),
            ParameterSpace(
                name='autoencoder_threshold',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.3, 0.9),
                default_value=0.7,
                description="Threshold for Autoencoder anomaly detection"
            ),
            ParameterSpace(
                name='ensemble_threshold',
                param_type=ParameterType.CONTINUOUS,
                bounds=(0.5, 0.95),
                default_value=0.85,
                description="Final ensemble decision threshold"
            ),
        ]
    
    @staticmethod
    def convert_params(params: Dict[str, float]) -> Dict[str, float]:
        """Convert optimized parameters to threshold dictionary."""
        return {
            'isolation_forest': float(params['isolation_forest_threshold']),
            'random_forest': float(params['random_forest_threshold']),
            'autoencoder': float(params['autoencoder_threshold']),
            'ensemble': float(params['ensemble_threshold']),
        }


def get_combined_space(
    include_isolation_forest: bool = True,
    include_random_forest: bool = True,
    include_autoencoder: bool = True,
    include_ensemble_weights: bool = True,
    include_thresholds: bool = True
) -> Dict[str, Tuple[float, float]]:
    """
    Get combined hyperparameter space for all components.
    
    Args:
        include_isolation_forest: Include Isolation Forest parameters
        include_random_forest: Include Random Forest parameters
        include_autoencoder: Include Autoencoder parameters
        include_ensemble_weights: Include ensemble weight parameters
        include_thresholds: Include threshold parameters
        
    Returns:
        Combined parameter bounds dictionary
    """
    combined = {}
    
    if include_isolation_forest:
        for name, bounds in IsolationForestSpace.get_space().items():
            combined[f'if_{name}'] = bounds
    
    if include_random_forest:
        for name, bounds in RandomForestSpace.get_space().items():
            combined[f'rf_{name}'] = bounds
    
    if include_autoencoder:
        for name, bounds in AutoencoderSpace.get_space().items():
            combined[f'ae_{name}'] = bounds
    
    if include_ensemble_weights:
        for name, bounds in EnsembleWeightSpace.get_space().items():
            combined[name] = bounds
    
    if include_thresholds:
        for name, bounds in DetectionThresholdSpace.get_space().items():
            combined[name] = bounds
    
    logger.info(f"Combined space has {len(combined)} parameters")
    return combined


def parse_combined_params(
    params: Dict[str, float],
    input_dim: int = 50,
    n_samples: int = 1000
) -> Dict[str, Dict[str, Any]]:
    """
    Parse combined parameters into component-specific dictionaries.
    
    Args:
        params: Combined parameter dictionary
        input_dim: Input dimension for autoencoder
        n_samples: Number of samples for isolation forest
        
    Returns:
        Dictionary with parsed parameters for each component
    """
    parsed = {
        'isolation_forest': {},
        'random_forest': {},
        'autoencoder': {},
        'ensemble_weights': {},
        'thresholds': {},
    }
    
    # Extract Isolation Forest parameters
    if_params = {}
    for key, value in params.items():
        if key.startswith('if_'):
            if_params[key[3:]] = value
    
    if if_params:
        parsed['isolation_forest'] = IsolationForestSpace.convert_params(
            if_params, n_samples, input_dim
        )
    
    # Extract Random Forest parameters
    rf_params = {}
    for key, value in params.items():
        if key.startswith('rf_'):
            rf_params[key[3:]] = value
    
    if rf_params:
        parsed['random_forest'] = RandomForestSpace.convert_params(
            rf_params, input_dim
        )
    
    # Extract Autoencoder parameters
    ae_params = {}
    for key, value in params.items():
        if key.startswith('ae_'):
            ae_params[key[3:]] = value
    
    if ae_params:
        parsed['autoencoder'] = AutoencoderSpace.convert_params(
            ae_params, input_dim
        )
    
    # Extract ensemble weights
    weight_params = {}
    for key in ['isolation_forest_weight', 'random_forest_weight', 'autoencoder_weight']:
        if key in params:
            weight_params[key] = params[key]
    
    if weight_params:
        parsed['ensemble_weights'] = EnsembleWeightSpace.convert_params(weight_params)
    
    # Extract thresholds
    threshold_params = {}
    for key in ['isolation_forest_threshold', 'random_forest_threshold', 
                'autoencoder_threshold', 'ensemble_threshold']:
        if key in params:
            threshold_params[key] = params[key]
    
    if threshold_params:
        parsed['thresholds'] = DetectionThresholdSpace.convert_params(threshold_params)
    
    return parsed
