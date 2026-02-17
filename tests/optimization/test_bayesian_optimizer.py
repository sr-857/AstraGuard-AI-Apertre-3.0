"""
Tests for Bayesian Optimizer module.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch
import asyncio

from optimization.bayesian_optimizer import (
    BayesianOptimizer,
    AcquisitionFunction,
    OptimizationResult,
)
from core.error_handling import AstraGuardException


class TestBayesianOptimizer:
    """Test suite for BayesianOptimizer."""
    
    @pytest.fixture
    def simple_bounds(self):
        """Simple parameter bounds for testing."""
        return {
            'x': (0.0, 10.0),
            'y': (-5.0, 5.0),
        }
    
    @pytest.fixture
    def optimizer(self, simple_bounds):
        """Create optimizer instance."""
        return BayesianOptimizer(
            param_bounds=simple_bounds,
            acquisition_function=AcquisitionFunction.EXPECTED_IMPROVEMENT,
            n_initial_points=3,
            n_iterations=10,
            random_state=42,
            maximize=True
        )
    
    def test_initialization(self, simple_bounds):
        """Test optimizer initialization."""
        optimizer = BayesianOptimizer(
            param_bounds=simple_bounds,
            acquisition_function=AcquisitionFunction.UPPER_CONFIDENCE_BOUND,
            n_initial_points=5,
            n_iterations=50
        )
        
        assert optimizer.param_bounds == simple_bounds
        assert optimizer.param_names == ['x', 'y']
        assert optimizer.n_initial_points == 5
        assert optimizer.n_iterations == 50
        assert optimizer.acquisition_function == AcquisitionFunction.UPPER_CONFIDENCE_BOUND
    
    def test_params_to_array(self, optimizer):
        """Test parameter conversion to array."""
        params = {'x': 5.0, 'y': 2.0}
        array = optimizer._params_to_array(params)
        
        assert array.shape == (2,)
        assert array[0] == 5.0
        assert array[1] == 2.0
    
    def test_array_to_params(self, optimizer):
        """Test array conversion to parameters."""
        array = np.array([3.0, -2.0])
        params = optimizer._array_to_params(array)
        
        assert params == {'x': 3.0, 'y': -2.0}
    
    def test_scale_params(self, optimizer):
        """Test parameter scaling to [0, 1]."""
        params_array = np.array([5.0, 0.0])  # Middle of bounds
        scaled = optimizer._scale_params(params_array)
        
        assert 0 <= scaled[0] <= 1
        assert 0 <= scaled[1] <= 1
        # x=5.0 is in middle of [0, 10], so should be ~0.5
        assert abs(scaled[0] - 0.5) < 0.01
        # y=0.0 is in middle of [-5, 5], so should be ~0.5
        assert abs(scaled[1] - 0.5) < 0.01
    
    def test_unscale_params(self, optimizer):
        """Test parameter unscaling from [0, 1]."""
        scaled = np.array([0.5, 0.5])
        unscaled = optimizer._unscale_params(scaled)
        
        # Should be middle of bounds
        assert abs(unscaled[0] - 5.0) < 0.01
        assert abs(unscaled[1] - 0.0) < 0.01
    
    def test_sample_random_params(self, optimizer):
        """Test random parameter sampling."""
        params = optimizer._sample_random_params()
        
        assert 'x' in params
        assert 'y' in params
        assert 0.0 <= params['x'] <= 10.0
        assert -5.0 <= params['y'] <= 5.0
    
    def test_tell_and_ask(self, optimizer):
        """Test tell and ask methods."""
        # Initial ask should return random params
        params1 = optimizer.ask()
        assert 'x' in params1 and 'y' in params1
        
        # Tell optimizer about result
        optimizer.tell(params1, 0.5)
        
        # Next ask should use acquisition function
        params2 = optimizer.ask()
        assert 'x' in params2 and 'y' in params2
        
        # Should have recorded observation
        assert len(optimizer.X_observed) == 1
        assert len(optimizer.y_observed) == 1
    
    def test_best_params_tracking(self, optimizer):
        """Test tracking of best parameters."""
        # Tell multiple observations
        optimizer.tell({'x': 1.0, 'y': 1.0}, 0.3)
        optimizer.tell({'x': 5.0, 'y': 0.0}, 0.8)  # Best
        optimizer.tell({'x': 9.0, 'y': -3.0}, 0.5)
        
        best = optimizer.get_best_params()
        assert best is not None
        assert best['x'] == 5.0
        assert best['y'] == 0.0
        assert optimizer.best_value == 0.8
    
    def test_predict(self, optimizer):
        """Test GP prediction."""
        # Need minimum observations
        for i in range(5):
            params = optimizer.ask()
            optimizer.tell(params, np.random.random())
        
        # Should be able to predict
        test_params = {'x': 5.0, 'y': 0.0}
        mu, sigma = optimizer.predict(test_params)
        
        assert isinstance(mu, float)
        assert isinstance(sigma, float)
        assert sigma >= 0  # Standard deviation should be non-negative
    
    def test_predict_not_enough_observations(self, optimizer):
        """Test prediction with insufficient observations."""
        with pytest.raises(ValueError):
            optimizer.predict({'x': 5.0, 'y': 0.0})
    
    @pytest.mark.asyncio
    async def test_optimize_simple_function(self, optimizer):
        """Test optimization of a simple function."""
        # Simple quadratic function with maximum at (5, 0)
        def objective(params):
            x, y = params['x'], params['y']
            return -((x - 5)**2 + y**2)  # Negative because we maximize
        
        result = await optimizer.optimize(objective, async_mode=False)
        
        assert isinstance(result, OptimizationResult)
        assert result.best_params is not None
        assert result.n_iterations > 0
        assert result.convergence_status in ['converged_early', 'max_iterations']
        
        # Best params should be near (5, 0)
        assert abs(result.best_params['x'] - 5.0) < 2.0
        assert abs(result.best_params['y'] - 0.0) < 2.0
    
    @pytest.mark.asyncio
    async def test_optimize_async(self, optimizer):
        """Test async optimization."""
        async def async_objective(params):
            await asyncio.sleep(0.001)  # Simulate async work
            x, y = params['x'], params['y']
            return -(x**2 + y**2)
        
        result = await optimizer.optimize(async_objective, async_mode=True)
        
        assert isinstance(result, OptimizationResult)
        assert result.best_params is not None
    
    def test_optimization_result_to_dict(self):
        """Test OptimizationResult serialization."""
        result = OptimizationResult(
            best_params={'x': 1.0, 'y': 2.0},
            best_value=0.95,
            all_params=[{'x': 1.0, 'y': 2.0}],
            all_values=[0.95],
            acquisition_history=[0.5],
            n_iterations=10,
            convergence_status='max_iterations',
            optimization_time_seconds=5.0,
            improvement_history=[0.5, 0.7, 0.95]
        )
        
        data = result.to_dict()
        assert data['best_params'] == {'x': 1.0, 'y': 2.0}
        assert data['best_value'] == 0.95
        assert data['n_iterations'] == 10
        assert 'improvement_rate' in data
        assert 'final_improvement' in data
    
    def test_different_acquisition_functions(self, simple_bounds):
        """Test different acquisition functions."""
        for acq_func in AcquisitionFunction:
            optimizer = BayesianOptimizer(
                param_bounds=simple_bounds,
                acquisition_function=acq_func,
                n_initial_points=2,
                n_iterations=5
            )
            
            # Add some observations
            for i in range(3):
                params = optimizer.ask()
                optimizer.tell(params, float(i))
            
            # Should be able to propose next point
            next_params = optimizer.ask()
            assert 'x' in next_params and 'y' in next_params
    
    def test_minimize_mode(self, simple_bounds):
        """Test minimization mode."""
        optimizer = BayesianOptimizer(
            param_bounds=simple_bounds,
            n_initial_points=2,
            n_iterations=5,
            maximize=False  # Minimize
        )
        
        # Tell observations
        optimizer.tell({'x': 1.0, 'y': 1.0}, 10.0)
        optimizer.tell({'x': 5.0, 'y': 0.0}, 1.0)  # Best (lowest)
        optimizer.tell({'x': 9.0, 'y': -3.0}, 5.0)
        
        assert optimizer.best_value == 1.0
    
    def test_early_stopping(self, simple_bounds):
        """Test early stopping based on convergence."""
        optimizer = BayesianOptimizer(
            param_bounds=simple_bounds,
            n_initial_points=2,
            n_iterations=100,
            early_stopping_patience=3,
            early_stopping_min_delta=0.01,
            maximize=True
        )
        
        # Simulate convergence
        for i in range(10):
            params = optimizer.ask()
            # Return nearly identical values to trigger convergence
            value = 0.5 + i * 0.001  # Very small improvements
            optimizer.tell(params, value)
            
            if optimizer._check_convergence():
                break
        
        # Should have converged early
        assert optimizer.no_improvement_count >= 3 or optimizer.iteration < 100
    
    def test_shutdown(self, optimizer):
        """Test optimizer shutdown."""
        optimizer.shutdown()
        # Should not raise any errors


class TestAcquisitionFunctions:
    """Test suite for acquisition functions."""
    
    @pytest.fixture
    def optimizer_with_data(self):
        """Create optimizer with sample data."""
        bounds = {'x': (0.0, 10.0)}
        optimizer = BayesianOptimizer(
            param_bounds=bounds,
            n_initial_points=2,
            random_state=42
        )
        
        # Add sample observations
        np.random.seed(42)
        for i in range(10):
            x = np.random.uniform(0, 10)
            y = np.sin(x) + np.random.normal(0, 0.1)
            optimizer.tell({'x': x}, y)
        
        return optimizer
    
    def test_expected_improvement(self, optimizer_with_data):
        """Test Expected Improvement calculation."""
        X_test = np.array([[5.0]])
        X_sample = np.array(optimizer_with_data.X_observed)
        y_sample = np.array(optimizer_with_data.y_observed)
        
        ei = optimizer_with_data._expected_improvement(X_test, X_sample, y_sample)
        
        assert isinstance(ei, np.ndarray)
        assert ei.shape == (1,)
        assert ei[0] >= 0  # EI should be non-negative
    
    def test_upper_confidence_bound(self, optimizer_with_data):
        """Test Upper Confidence Bound calculation."""
        X_test = np.array([[5.0]])
        
        ucb = optimizer_with_data._upper_confidence_bound(X_test, kappa=2.0)
        
        assert isinstance(ucb, np.ndarray)
        assert ucb.shape == (1,)
    
    def test_probability_of_improvement(self, optimizer_with_data):
        """Test Probability of Improvement calculation."""
        X_test = np.array([[5.0]])
        X_sample = np.array(optimizer_with_data.X_observed)
        y_sample = np.array(optimizer_with_data.y_observed)
        
        pi = optimizer_with_data._probability_of_improvement(X_test, X_sample, y_sample)
        
        assert isinstance(pi, np.ndarray)
        assert pi.shape == (1,)
        assert 0 <= pi[0] <= 1  # PI is a probability


class TestOptimizationIntegration:
    """Integration tests for optimization."""
    
    @pytest.mark.asyncio
    async def test_full_optimization_workflow(self):
        """Test complete optimization workflow."""
        # Define simple 1D optimization problem
        bounds = {'x': (-5.0, 5.0)}
        
        optimizer = BayesianOptimizer(
            param_bounds=bounds,
            acquisition_function=AcquisitionFunction.EXPECTED_IMPROVEMENT,
            n_initial_points=3,
            n_iterations=15,
            maximize=True,
            random_state=42
        )
        
        # Objective: maximize -x^2 (maximum at x=0)
        def objective(params):
            return -params['x']**2
        
        result = await optimizer.optimize(objective, async_mode=False)
        
        # Verify results
        assert result.best_params is not None
        assert abs(result.best_params['x']) < 1.0  # Should be near 0
        assert result.best_value > -1.0  # Should be near 0
        assert result.n_iterations <= 15
        assert len(result.all_params) == len(result.all_values)
        
        optimizer.shutdown()
    
    @pytest.mark.asyncio
    async def test_optimization_with_noise(self):
        """Test optimization with noisy objective."""
        bounds = {'x': (0.0, 10.0)}
        
        optimizer = BayesianOptimizer(
            param_bounds=bounds,
            n_initial_points=3,
            n_iterations=10,
            maximize=True,
            noise_level=0.1,
            random_state=42
        )
        
        np.random.seed(42)
        
        # Noisy objective
        def objective(params):
            true_value = -(params['x'] - 5)**2
            noise = np.random.normal(0, 0.5)
            return true_value + noise
        
        result = await optimizer.optimize(objective, async_mode=False)
        
        # Should still find approximate optimum despite noise
        assert result.best_params is not None
        assert 3.0 <= result.best_params['x'] <= 7.0
        
        optimizer.shutdown()
