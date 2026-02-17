"""
Tests for objective functions module.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
import asyncio

from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import make_classification

from optimization.objective_functions import (
    FalsePositiveObjective,
    DetectionAccuracyObjective,
    LatencyAwareObjective,
    EnsembleObjective,
    MultiObjectiveOptimizer,
    ObjectiveResult,
    create_default_objective,
)


class TestFalsePositiveObjective:
    """Test suite for FalsePositiveObjective."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample classification data."""
        X, y = make_classification(
            n_samples=200,
            n_features=10,
            n_informative=5,
            n_redundant=2,
            n_classes=2,
            weights=[0.9, 0.1],  # Imbalanced
            random_state=42
        )
        
        # Split into train/val
        split = 150
        return X[:split], y[:split], X[split:], y[split:]
    
    @pytest.fixture
    def model_trainer(self):
        """Create model trainer function."""
        def trainer(params, X, y):
            model = RandomForestClassifier(
                n_estimators=int(params.get('n_estimators', 100)),
                max_depth=int(params.get('max_depth', 10)) if params.get('max_depth') else None,
                random_state=42
            )
            model.fit(X, y)
            return model
        
        return trainer
    
    def test_initialization(self, sample_data, model_trainer):
        """Test objective function initialization."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = FalsePositiveObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            target_fpr=0.01,
            min_recall=0.8
        )
        
        assert objective.target_fpr == 0.01
        assert objective.min_recall == 0.8
        assert objective.evaluation_count == 0
    
    def test_evaluate(self, sample_data, model_trainer):
        """Test objective evaluation."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = FalsePositiveObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            target_fpr=0.01,
            min_recall=0.8
        )
        
        params = {'n_estimators': 50, 'max_depth': 5}
        value = objective.evaluate(params)
        
        # Should return a float value
        assert isinstance(value, float)
        assert value >= 0.0
        assert objective.evaluation_count == 1
        
        # Should have recorded result
        assert len(objective.results_history) == 1
        result = objective.results_history[0]
        assert isinstance(result, ObjectiveResult)
        assert 'fpr' in result.metrics
        assert 'recall' in result.metrics
    
    def test_evaluate_with_penalty(self, sample_data, model_trainer):
        """Test penalty for high FPR or low recall."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = FalsePositiveObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            target_fpr=0.01,
            min_recall=0.8,
            penalty_weight=10.0
        )
        
        # Evaluate with some parameters
        params = {'n_estimators': 10, 'max_depth': 2}
        value = objective.evaluate(params)
        
        # Value should include penalties if targets not met
        assert isinstance(value, float)
    
    def test_get_best_result(self, sample_data, model_trainer):
        """Test getting best result."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = FalsePositiveObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val
        )
        
        # Evaluate multiple times
        for n_est in [10, 50, 100]:
            params = {'n_estimators': n_est, 'max_depth': 5}
            objective.evaluate(params)
        
        best = objective.get_best_result()
        assert best is not None
        assert best.value == min(r.value for r in objective.results_history)
    
    @pytest.mark.asyncio
    async def test_evaluate_async(self, sample_data, model_trainer):
        """Test async evaluation."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = FalsePositiveObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val
        )
        
        params = {'n_estimators': 50, 'max_depth': 5}
        value = await objective.evaluate_async(params)
        
        assert isinstance(value, float)
        assert objective.evaluation_count == 1


class TestDetectionAccuracyObjective:
    """Test suite for DetectionAccuracyObjective."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample classification data."""
        X, y = make_classification(
            n_samples=200,
            n_features=10,
            n_classes=2,
            random_state=42
        )
        return X[:150], y[:150], X[150:], y[150:]
    
    @pytest.fixture
    def model_trainer(self):
        """Create model trainer."""
        def trainer(params):
            return RandomForestClassifier(
                n_estimators=int(params.get('n_estimators', 100)),
                random_state=42
            )
        return trainer
    
    def test_evaluate_without_cv(self, sample_data, model_trainer):
        """Test evaluation without cross-validation."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = DetectionAccuracyObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            use_cross_validation=False
        )
        
        params = {'n_estimators': 50}
        value = objective.evaluate(params)
        
        assert isinstance(value, float)
        assert 0 <= value <= 1  # F1 score range
        assert 'f1' in objective.results_history[0].metrics
    
    def test_evaluate_with_cv(self, sample_data, model_trainer):
        """Test evaluation with cross-validation."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = DetectionAccuracyObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            use_cross_validation=True,
            cv_folds=3
        )
        
        params = {'n_estimators': 50}
        value = objective.evaluate(params)
        
        assert isinstance(value, float)
        assert objective.evaluation_count == 1
        assert 'f1_mean' in objective.results_history[0].metrics
    
    def test_get_best_result_maximization(self, sample_data, model_trainer):
        """Test that best result maximizes objective."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = DetectionAccuracyObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            use_cross_validation=False
        )
        
        # Evaluate with different parameters
        for n_est in [10, 100]:
            params = {'n_estimators': n_est}
            objective.evaluate(params)
        
        best = objective.get_best_result()
        assert best is not None
        assert best.value == max(r.value for r in objective.results_history)


class TestLatencyAwareObjective:
    """Test suite for LatencyAwareObjective."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        X, y = make_classification(
            n_samples=100,
            n_features=10,
            random_state=42
        )
        return X[:70], y[:70], X[70:], y[70:]
    
    @pytest.fixture
    def model_trainer(self):
        """Create model trainer."""
        def trainer(params, X, y):
            return RandomForestClassifier(
                n_estimators=int(params.get('n_estimators', 10)),
                random_state=42
            )
        return trainer
    
    def test_evaluate(self, sample_data, model_trainer):
        """Test latency-aware evaluation."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = LatencyAwareObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            target_latency_ms=100.0,
            latency_weight=0.3,
            accuracy_weight=0.7
        )
        
        params = {'n_estimators': 10}
        value = objective.evaluate(params)
        
        assert isinstance(value, float)
        assert objective.evaluation_count == 1
        
        metrics = objective.results_history[0].metrics
        assert 'f1' in metrics
        assert 'per_sample_latency_ms' in metrics
        assert 'train_time_ms' in metrics
    
    def test_latency_penalty(self, sample_data, model_trainer):
        """Test penalty for exceeding target latency."""
        X_train, y_train, X_val, y_val = sample_data
        
        objective = LatencyAwareObjective(
            model_trainer=model_trainer,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            target_latency_ms=0.001,  # Very low target to trigger penalty
            latency_weight=0.3,
            accuracy_weight=0.7
        )
        
        params = {'n_estimators': 100}  # Larger model = slower
        value = objective.evaluate(params)
        
        # Should have penalty applied
        assert isinstance(value, float)


class TestEnsembleObjective:
    """Test suite for EnsembleObjective."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        X, y = make_classification(
            n_samples=100,
            n_features=10,
            random_state=42
        )
        return X, y
    
    @pytest.fixture
    def ensemble_predictor(self):
        """Create mock ensemble predictor."""
        def predictor(X, params):
            # Mock predictions based on threshold
            threshold = params.get('thresholds', {}).get('ensemble', 0.5)
            weights = params.get('weights', {})
            
            # Generate mock predictions
            n_samples = len(X)
            scores = np.random.random(n_samples)
            predictions = [
                {
                    'is_anomaly': score > threshold,
                    'anomaly_score': score,
                    'confidence': abs(score - 0.5) * 2
                }
                for score in scores
            ]
            return predictions
        
        return predictor
    
    def test_evaluate(self, sample_data, ensemble_predictor):
        """Test ensemble evaluation."""
        X_val, y_val = sample_data
        
        objective = EnsembleObjective(
            ensemble_predictor=ensemble_predictor,
            X_val=X_val,
            y_val=y_val,
            target_fpr=0.01,
            target_recall=0.9
        )
        
        params = {
            'weights': {
                'isolation_forest': 0.3,
                'random_forest': 0.4,
                'autoencoder': 0.3
            },
            'thresholds': {
                'isolation_forest': 0.6,
                'random_forest': 0.5,
                'autoencoder': 0.7,
                'ensemble': 0.85
            }
        }
        
        value = objective.evaluate(params)
        
        assert isinstance(value, float)
        assert 0 <= value <= 1.5  # Can exceed 1 due to F1 bonus
        
        metrics = objective.results_history[0].metrics
        assert 'fpr' in metrics
        assert 'recall' in metrics
        assert 'f1' in metrics
    
    def test_target_meeting(self, sample_data, ensemble_predictor):
        """Test tracking of target meeting."""
        X_val, y_val = sample_data
        
        objective = EnsembleObjective(
            ensemble_predictor=ensemble_predictor,
            X_val=X_val,
            y_val=y_val,
            target_fpr=0.01,
            target_recall=0.9
        )
        
        params = {
            'weights': {'isolation_forest': 0.3, 'random_forest': 0.4, 'autoencoder': 0.3},
            'thresholds': {'ensemble': 0.5}
        }
        
        objective.evaluate(params)
        
        metadata = objective.results_history[0].metadata
        assert 'meets_fpr_target' in metadata
        assert 'meets_recall_target' in metadata


class TestMultiObjectiveOptimizer:
    """Test suite for MultiObjectiveOptimizer."""
    
    def test_evaluate_single_objective(self):
        """Test evaluation with single objective."""
        mock_obj = Mock()
        mock_obj.evaluate.return_value = 0.8
        
        optimizer = MultiObjectiveOptimizer(
            objectives=[(mock_obj, 1.0)],
            maximize=True
        )
        
        params = {'x': 1.0}
        value = optimizer.evaluate(params)
        
        assert value == 0.8
        assert mock_obj.evaluate.called
    
    def test_evaluate_multiple_objectives(self):
        """Test evaluation with multiple objectives."""
        mock_obj1 = Mock()
        mock_obj1.evaluate.return_value = 0.8
        
        mock_obj2 = Mock()
        mock_obj2.evaluate.return_value = 0.6
        
        optimizer = MultiObjectiveOptimizer(
            objectives=[(mock_obj1, 0.7), (mock_obj2, 0.3)],
            maximize=True
        )
        
        params = {'x': 1.0}
        value = optimizer.evaluate(params)
        
        # Weighted average: 0.8*0.7 + 0.6*0.3 = 0.56 + 0.18 = 0.74
        expected = 0.74
        assert abs(value - expected) < 0.01
    
    def test_evaluate_minimize(self):
        """Test minimization mode."""
        mock_obj = Mock()
        mock_obj.evaluate.return_value = 0.8
        
        optimizer = MultiObjectiveOptimizer(
            objectives=[(mock_obj, 1.0)],
            maximize=False
        )
        
        params = {'x': 1.0}
        value = optimizer.evaluate(params)
        
        # Should be negated for minimization
        assert value == -0.8
    
    @pytest.mark.asyncio
    async def test_evaluate_async(self):
        """Test async evaluation."""
        async def async_evaluate(params):
            await asyncio.sleep(0.001)
            return 0.8
        
        mock_obj = Mock()
        mock_obj.evaluate_async = async_evaluate
        
        optimizer = MultiObjectiveOptimizer(
            objectives=[(mock_obj, 1.0)],
            maximize=True
        )
        
        params = {'x': 1.0}
        value = await optimizer.evaluate_async(params)
        
        assert value == 0.8


class TestCreateDefaultObjective:
    """Test suite for create_default_objective factory function."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        X, y = make_classification(n_samples=100, n_features=10, random_state=42)
        return X[:70], y[:70], X[70:], y[70:]
    
    def test_create_isolation_forest_objective(self, sample_data):
        """Test creating objective for isolation forest."""
        X_train, y_train, X_val, y_val = sample_data
        
        def trainer(params):
            return Mock()
        
        obj = create_default_objective(
            'isolation_forest',
            trainer,
            X_train, y_train, X_val, y_val
        )
        
        assert isinstance(obj, DetectionAccuracyObjective)
        assert obj.use_cross_validation is False
    
    def test_create_random_forest_objective(self, sample_data):
        """Test creating objective for random forest."""
        X_train, y_train, X_val, y_val = sample_data
        
        def trainer(params, X, y):
            return Mock()
        
        obj = create_default_objective(
            'random_forest',
            trainer,
            X_train, y_train, X_val, y_val
        )
        
        assert isinstance(obj, FalsePositiveObjective)
        assert obj.target_fpr == 0.01
    
    def test_create_ensemble_objective(self, sample_data):
        """Test creating objective for ensemble."""
        X_train, y_train, X_val, y_val = sample_data
        
        def predictor(X, params):
            return []
        
        obj = create_default_objective(
            'ensemble',
            predictor,
            X_train, y_train, X_val, y_val
        )
        
        assert isinstance(obj, EnsembleObjective)
    
    def test_create_unknown_model_type(self, sample_data):
        """Test creating objective for unknown model type."""
        X_train, y_train, X_val, y_val = sample_data
        
        def trainer(params, X, y):
            return Mock()
        
        obj = create_default_objective(
            'unknown_model',
            trainer,
            X_train, y_train, X_val, y_val
        )
        
        assert isinstance(obj, DetectionAccuracyObjective)


class TestObjectiveResult:
    """Test suite for ObjectiveResult dataclass."""
    
    def test_to_dict(self):
        """Test serialization."""
        result = ObjectiveResult(
            value=0.85,
            metrics={'f1': 0.9, 'precision': 0.85},
            metadata={'params': {'x': 1.0}},
            timestamp=__import__('datetime').datetime.now()
        )
        
        data = result.to_dict()
        
        assert data['value'] == 0.85
        assert data['metrics'] == {'f1': 0.9, 'precision': 0.85}
        assert 'timestamp' in data
