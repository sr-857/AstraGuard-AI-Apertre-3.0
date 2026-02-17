"""
Tests for optimization service module.
"""

import pytest
import numpy as np
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from sklearn.datasets import make_classification
from sklearn.ensemble import IsolationForest, RandomForestClassifier

from optimization.optimization_service import (
    OptimizationService,
    OptimizationConfig,
    OptimizationTarget,
    OptimizationJob,
    get_optimization_service,
    run_bayesian_optimization,
)
from optimization.bayesian_optimizer import AcquisitionFunction


class TestOptimizationConfig:
    """Test suite for OptimizationConfig."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = OptimizationConfig(
            target=OptimizationTarget.RANDOM_FOREST
        )
        
        assert config.target == OptimizationTarget.RANDOM_FOREST
        assert config.n_iterations == 50
        assert config.n_initial_points == 5
        assert config.acquisition_function == AcquisitionFunction.EXPECTED_IMPROVEMENT
        assert config.target_fpr == 0.01
        assert config.min_recall == 0.8
    
    def test_to_dict(self):
        """Test serialization."""
        config = OptimizationConfig(
            target=OptimizationTarget.ISOLATION_FOREST,
            n_iterations=30,
            target_fpr=0.005
        )
        
        data = config.to_dict()
        
        assert data['target'] == 'isolation_forest'
        assert data['n_iterations'] == 30
        assert data['target_fpr'] == 0.005
        assert data['acquisition_function'] == 'ei'


class TestOptimizationJob:
    """Test suite for OptimizationJob."""
    
    def test_job_creation(self):
        """Test job creation."""
        from datetime import datetime
        
        config = OptimizationConfig(target=OptimizationTarget.ENSEMBLE_WEIGHTS)
        
        job = OptimizationJob(
            job_id='test_job_001',
            config=config,
            status='pending',
            created_at=datetime.now(),
            progress=0.0
        )
        
        assert job.job_id == 'test_job_001'
        assert job.status == 'pending'
        assert job.progress == 0.0
    
    def test_to_dict(self):
        """Test serialization."""
        from datetime import datetime
        
        config = OptimizationConfig(target=OptimizationTarget.THRESHOLDS)
        
        job = OptimizationJob(
            job_id='test_job_002',
            config=config,
            status='completed',
            created_at=datetime.now(),
            completed_at=datetime.now(),
            progress=1.0
        )
        
        data = job.to_dict()
        
        assert data['job_id'] == 'test_job_002'
        assert data['status'] == 'completed'
        assert data['progress'] == 1.0
        assert data['config']['target'] == 'thresholds'


class TestOptimizationService:
    """Test suite for OptimizationService."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test results."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def service(self, temp_dir):
        """Create optimization service."""
        return OptimizationService(
            results_dir=temp_dir,
            max_concurrent_jobs=2,
            auto_optimize=False
        )
    
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
    
    def test_initialization(self, temp_dir):
        """Test service initialization."""
        service = OptimizationService(
            results_dir=temp_dir,
            max_concurrent_jobs=3,
            auto_optimize=True,
            optimization_interval_hours=12
        )
        
        assert service.max_concurrent_jobs == 3
        assert service.auto_optimize is True
        assert service.optimization_interval_hours == 12
        assert Path(temp_dir).exists()
    
    def test_submit_job(self, service):
        """Test job submission."""
        config = OptimizationConfig(target=OptimizationTarget.RANDOM_FOREST)
        
        job_id = service.submit_job(config)
        
        assert job_id.startswith('opt_')
        assert job_id in service.jobs
        assert service.jobs[job_id].status == 'pending'
    
    def test_get_job_status(self, service):
        """Test getting job status."""
        config = OptimizationConfig(target=OptimizationTarget.ISOLATION_FOREST)
        job_id = service.submit_job(config)
        
        status = service.get_job_status(job_id)
        
        assert status is not None
        assert status['job_id'] == job_id
        assert status['status'] == 'pending'
    
    def test_get_job_status_not_found(self, service):
        """Test getting status for non-existent job."""
        status = service.get_job_status('non_existent_job')
        assert status is None
    
    def test_get_all_jobs(self, service):
        """Test getting all jobs."""
        # Submit multiple jobs
        for target in [OptimizationTarget.RANDOM_FOREST, OptimizationTarget.ISOLATION_FOREST]:
            config = OptimizationConfig(target=target)
            service.submit_job(config)
        
        all_jobs = service.get_all_jobs()
        
        assert len(all_jobs) == 2
        assert all(isinstance(job, dict) for job in all_jobs)
    
    def test_get_best_params_empty(self, service):
        """Test getting best params when none exist."""
        params = service.get_best_params(OptimizationTarget.RANDOM_FOREST)
        assert params is None
    
    def test_save_and_load_best_params(self, service, temp_dir):
        """Test saving and loading best parameters."""
        # Set best params
        service.best_params[OptimizationTarget.RANDOM_FOREST] = {
            'n_estimators': 100,
            'max_depth': 10
        }
        
        # Save
        service._save_best_params()
        
        # Create new service to load
        new_service = OptimizationService(results_dir=temp_dir)
        
        params = new_service.get_best_params(OptimizationTarget.RANDOM_FOREST)
        assert params is not None
        assert params['n_estimators'] == 100
    
    @pytest.mark.asyncio
    async def test_optimize_isolation_forest(self, service, sample_data):
        """Test Isolation Forest optimization."""
        X_train, y_train, X_val, y_val = sample_data
        
        # Run optimization with few iterations for speed
        result = await service.optimize_isolation_forest(
            X_train, None, X_val, None,  # Unsupervised
            n_iterations=5,
            n_initial_points=2
        )
        
        assert result is not None
        assert result.best_params is not None
        assert 'n_estimators' in result.best_params
        assert result.n_iterations <= 5
        
        # Check that best params were saved
        saved_params = service.get_best_params(OptimizationTarget.ISOLATION_FOREST)
        assert saved_params is not None
    
    @pytest.mark.asyncio
    async def test_optimize_random_forest(self, service, sample_data):
        """Test Random Forest optimization."""
        X_train, y_train, X_val, y_val = sample_data
        
        result = await service.optimize_random_forest(
            X_train, y_train, X_val, y_val,
            n_iterations=5,
            n_initial_points=2
        )
        
        assert result is not None
        assert result.best_params is not None
        assert 'n_estimators' in result.best_params
        
        # Check that best params were saved
        saved_params = service.get_best_params(OptimizationTarget.RANDOM_FOREST)
        assert saved_params is not None
    
    @pytest.mark.asyncio
    async def test_optimize_ensemble_weights(self, service, sample_data):
        """Test ensemble weights optimization."""
        X_val, y_val = sample_data[2], sample_data[3]
        
        # Mock ensemble predictor
        def mock_predictor(X, params):
            threshold = params.get('ensemble_threshold', 0.5)
            return [
                {
                    'is_anomaly': np.random.random() > threshold,
                    'anomaly_score': np.random.random(),
                    'confidence': 0.8
                }
                for _ in range(len(X))
            ]
        
        result = await service.optimize_ensemble_weights(
            mock_predictor, X_val, y_val,
            n_iterations=5,
            n_initial_points=2
        )
        
        assert result is not None
        assert result.best_params is not None
        
        # Check that weights and thresholds were saved
        weights = service.get_best_params(OptimizationTarget.ENSEMBLE_WEIGHTS)
        thresholds = service.get_best_params(OptimizationTarget.THRESHOLDS)
        assert weights is not None or thresholds is not None
    
    def test_apply_best_params_no_params(self, service):
        """Test applying best params when none exist."""
        mock_model = Mock()
        
        result = service.apply_best_params(
            OptimizationTarget.RANDOM_FOREST,
            mock_model
        )
        
        assert result is False
    
    def test_should_optimize_empty_history(self, service):
        """Test should_optimize with empty history."""
        assert service._should_optimize() is True
    
    def test_should_optimize_recent_optimization(self, service):
        """Test should_optimize after recent optimization."""
        from datetime import datetime, timedelta
        
        # Add recent optimization
        service.optimization_history.append({
            'target': 'random_forest',
            'timestamp': datetime.now().isoformat(),
            'result': {}
        })
        
        # Should not optimize again immediately
        assert service._should_optimize() is False
    
    def test_should_optimize_old_optimization(self, service):
        """Test should_optimize after old optimization."""
        from datetime import datetime, timedelta
        
        # Add old optimization
        old_time = datetime.now() - timedelta(hours=25)
        service.optimization_history.append({
            'target': 'random_forest',
            'timestamp': old_time.isoformat(),
            'result': {}
        })
        
        # Should optimize again after interval
        assert service._should_optimize() is True


class TestGetOptimizationService:
    """Test suite for get_optimization_service."""
    
    def test_singleton(self):
        """Test that service is a singleton."""
        service1 = get_optimization_service()
        service2 = get_optimization_service()
        
        assert service1 is service2
    
    def test_different_results_dir(self):
        """Test that same instance is returned regardless of args."""
        service1 = get_optimization_service(results_dir='dir1')
        service2 = get_optimization_service(results_dir='dir2')
        
        # Should still be same instance (first one wins)
        assert service1 is service2


class TestRunBayesianOptimization:
    """Test suite for run_bayesian_optimization convenience function."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data."""
        X, y = make_classification(
            n_samples=100,
            n_features=10,
            random_state=42
        )
        return X[:70], y[:70], X[70:], y[70:]
    
    @pytest.mark.asyncio
    async def test_run_isolation_forest(self, sample_data):
        """Test running isolation forest optimization."""
        X_train, y_train, X_val, y_val = sample_data
        
        result = await run_bayesian_optimization(
            'isolation_forest',
            X_train, y_train, X_val, y_val,
            n_iterations=3
        )
        
        assert isinstance(result, dict)
        assert 'best_params' in result
        assert 'best_value' in result
        assert 'n_iterations' in result
    
    @pytest.mark.asyncio
    async def test_run_random_forest(self, sample_data):
        """Test running random forest optimization."""
        X_train, y_train, X_val, y_val = sample_data
        
        result = await run_bayesian_optimization(
            'random_forest',
            X_train, y_train, X_val, y_val,
            n_iterations=3
        )
        
        assert isinstance(result, dict)
        assert 'best_params' in result
    
    @pytest.mark.asyncio
    async def test_run_unknown_model(self, sample_data):
        """Test running optimization for unknown model type."""
        X_train, y_train, X_val, y_val = sample_data
        
        with pytest.raises(ValueError):
            await run_bayesian_optimization(
                'unknown_model',
                X_train, y_train, X_val, y_val
            )


class TestOptimizationServiceIntegration:
    """Integration tests for OptimizationService."""
    
    @pytest.mark.asyncio
    async def test_full_service_lifecycle(self):
        """Test full service lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = OptimizationService(
                results_dir=temp_dir,
                max_concurrent_jobs=1,
                auto_optimize=False
            )
            
            # Create sample data
            X, y = make_classification(n_samples=100, n_features=10, random_state=42)
            
            # Optimize isolation forest
            result = await service.optimize_isolation_forest(
                X, None, X, None,
                n_iterations=3,
                n_initial_points=2
            )
            
            assert result is not None
            
            # Check best params
            best_params = service.get_best_params(OptimizationTarget.ISOLATION_FOREST)
            assert best_params is not None
            
            # Check history
            assert len(service.optimization_history) > 0
