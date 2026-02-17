"""
Bayesian Optimization Module for AstraGuard-AI

Provides automated hyperparameter tuning using Gaussian Process-based
Bayesian optimization to achieve <1% false positive rate in threat detection.
"""

from .bayesian_optimizer import BayesianOptimizer, AcquisitionFunction
from .hyperparameter_spaces import (
    IsolationForestSpace,
    RandomForestSpace,
    AutoencoderSpace,
    EnsembleWeightSpace,
    get_combined_space
)
from .objective_functions import (
    FalsePositiveObjective,
    DetectionAccuracyObjective,
    MultiObjectiveOptimizer
)
from .optimization_service import OptimizationService, get_optimization_service

__all__ = [
    'BayesianOptimizer',
    'AcquisitionFunction',
    'IsolationForestSpace',
    'RandomForestSpace',
    'AutoencoderSpace',
    'EnsembleWeightSpace',
    'get_combined_space',
    'FalsePositiveObjective',
    'DetectionAccuracyObjective',
    'MultiObjectiveOptimizer',
    'OptimizationService',
    'get_optimization_service',
]
