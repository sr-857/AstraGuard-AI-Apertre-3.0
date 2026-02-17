"""
Bayesian Optimizer using Gaussian Processes

Implements Bayesian optimization with acquisition functions for
automated hyperparameter tuning of ML models.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel
from sklearn.preprocessing import StandardScaler
from scipy.optimize import minimize
from scipy.stats import norm

from core.error_handling import (
    AstraGuardException,
    safe_execute,
    ErrorContext,
    ErrorSeverity
)

logger = logging.getLogger(__name__)


class AcquisitionFunction(Enum):
    """Acquisition functions for Bayesian optimization."""
    EXPECTED_IMPROVEMENT = "ei"
    UPPER_CONFIDENCE_BOUND = "ucb"
    PROBABILITY_OF_IMPROVEMENT = "pi"
    GREEDY = "greedy"


@dataclass
class OptimizationResult:
    """Result of Bayesian optimization."""
    best_params: Dict[str, Any]
    best_value: float
    all_params: List[Dict[str, Any]]
    all_values: List[float]
    acquisition_history: List[float]
    n_iterations: int
    convergence_status: str
    optimization_time_seconds: float
    improvement_history: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'best_params': self.best_params,
            'best_value': float(self.best_value),
            'n_iterations': self.n_iterations,
            'convergence_status': self.convergence_status,
            'optimization_time_seconds': self.optimization_time_seconds,
            'improvement_rate': self._calculate_improvement_rate(),
            'final_improvement': self._get_final_improvement()
        }
    
    def _calculate_improvement_rate(self) -> float:
        """Calculate rate of improvement over iterations."""
        if len(self.improvement_history) < 2:
            return 0.0
        improvements = np.diff(self.improvement_history)
        return float(np.mean(improvements)) if len(improvements) > 0 else 0.0
    
    def _get_final_improvement(self) -> float:
        """Get improvement from first to best value."""
        if len(self.all_values) == 0:
            return 0.0
        first_value = self.all_values[0]
        if first_value == 0:
            return 0.0
        return float((self.best_value - first_value) / abs(first_value)) * 100


class BayesianOptimizer:
    """
    Bayesian optimizer using Gaussian Process regression.
    
    Features:
    - Multiple acquisition functions (EI, UCB, PI)
    - Async support for non-blocking optimization
    - Early stopping based on convergence
    - Automatic hyperparameter scaling
    - Parallel evaluation support
    """
    
    def __init__(
        self,
        param_bounds: Dict[str, Tuple[float, float]],
        acquisition_function: AcquisitionFunction = AcquisitionFunction.EXPECTED_IMPROVEMENT,
        n_initial_points: int = 5,
        n_iterations: int = 50,
        xi: float = 0.01,  # Exploration parameter for EI
        kappa: float = 2.576,  # Exploration parameter for UCB
        noise_level: float = 1e-5,
        random_state: Optional[int] = 42,
        early_stopping_patience: int = 10,
        early_stopping_min_delta: float = 1e-4,
        maximize: bool = True
    ):
        self.param_bounds = param_bounds
        self.param_names = list(param_bounds.keys())
        self.acquisition_function = acquisition_function
        self.n_initial_points = n_initial_points
        self.n_iterations = n_iterations
        self.xi = xi
        self.kappa = kappa
        self.noise_level = noise_level
        self.random_state = random_state
        self.early_stopping_patience = early_stopping_patience
        self.early_stopping_min_delta = early_stopping_min_delta
        self.maximize = maximize
        
        # Initialize Gaussian Process
        self._init_gp()
        
        # Data storage
        self.X_observed: List[np.ndarray] = []
        self.y_observed: List[float] = []
        self.param_history: List[Dict[str, Any]] = []
        self.acquisition_history: List[float] = []
        
        # Scaler for parameters
        self.scaler = StandardScaler()
        self.scaler_fitted = False
        
        # State
        self.best_value = float('-inf') if maximize else float('inf')
        self.best_params: Optional[Dict[str, Any]] = None
        self.iteration = 0
        self.no_improvement_count = 0
        self.last_best_value = None
        
        # Thread pool for parallel execution
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info(f"BayesianOptimizer initialized with {acquisition_function.value} acquisition")
    
    def _init_gp(self):
        """Initialize Gaussian Process with Matern kernel."""
        # Matern kernel with automatic relevance determination
        kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(
            length_scale=1.0,
            length_scale_bounds=(1e-2, 1e2),
            nu=2.5
        ) + WhiteKernel(noise_level=self.noise_level)
        
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=10,
            random_state=self.random_state,
            normalize_y=True,
            alpha=self.noise_level
        )
    
    def _params_to_array(self, params: Dict[str, Any]) -> np.ndarray:
        """Convert parameter dictionary to array."""
        return np.array([params[name] for name in self.param_names])
    
    def _array_to_params(self, array: np.ndarray) -> Dict[str, Any]:
        """Convert array to parameter dictionary."""
        return {name: float(array[i]) for i, name in enumerate(self.param_names)}
    
    def _scale_params(self, params_array: np.ndarray) -> np.ndarray:
        """Scale parameters to [0, 1] range."""
        bounds_array = np.array([
            [self.param_bounds[name][0], self.param_bounds[name][1]]
            for name in self.param_names
        ])
        
        # Min-max scaling
        scaled = (params_array - bounds_array[:, 0]) / (bounds_array[:, 1] - bounds_array[:, 0])
        return np.clip(scaled, 0, 1)
    
    def _unscale_params(self, scaled_array: np.ndarray) -> np.ndarray:
        """Unscale parameters from [0, 1] to original range."""
        bounds_array = np.array([
            [self.param_bounds[name][0], self.param_bounds[name][1]]
            for name in self.param_names
        ])
        
        return scaled_array * (bounds_array[:, 1] - bounds_array[:, 0]) + bounds_array[:, 0]
    
    def _sample_random_params(self) -> Dict[str, Any]:
        """Sample random parameters within bounds."""
        params = {}
        for name, (low, high) in self.param_bounds.items():
            if isinstance(low, int) and isinstance(high, int):
                params[name] = np.random.randint(low, high + 1)
            else:
                params[name] = np.random.uniform(low, high)
        return params
    
    def _expected_improvement(
        self,
        X: np.ndarray,
        X_sample: np.ndarray,
        y_sample: np.ndarray
    ) -> np.ndarray:
        """
        Expected Improvement acquisition function.
        
        EI(x) = E[max(f(x) - f(x+), 0)]
        """
        mu, sigma = self.gp.predict(X, return_std=True)
        
        if not self.maximize:
            mu = -mu
        
        # Current best
        y_best = np.max(y_sample) if self.maximize else np.min(y_sample)
        
        with np.errstate(divide='warn'):
            imp = mu - y_best - self.xi
            Z = imp / sigma
            ei = imp * norm.cdf(Z) + sigma * norm.pdf(Z)
            ei[sigma == 0.0] = 0.0
        
        return ei
    
    def _upper_confidence_bound(
        self,
        X: np.ndarray,
        kappa: Optional[float] = None
    ) -> np.ndarray:
        """
        Upper Confidence Bound acquisition function.
        
        UCB(x) = mu(x) + kappa * sigma(x)
        """
        if kappa is None:
            kappa = self.kappa
        
        mu, sigma = self.gp.predict(X, return_std=True)
        
        if not self.maximize:
            mu = -mu
        
        return mu + kappa * sigma
    
    def _probability_of_improvement(
        self,
        X: np.ndarray,
        X_sample: np.ndarray,
        y_sample: np.ndarray
    ) -> np.ndarray:
        """
        Probability of Improvement acquisition function.
        """
        mu, sigma = self.gp.predict(X, return_std=True)
        
        if not self.maximize:
            mu = -mu
        
        y_best = np.max(y_sample) if self.maximize else np.min(y_sample)
        
        with np.errstate(divide='warn'):
            imp = mu - y_best - self.xi
            Z = imp / sigma
            pi = norm.cdf(Z)
            pi[sigma == 0.0] = 0.0
        
        return pi
    
    def _acquisition_function_values(self, X: np.ndarray) -> np.ndarray:
        """Compute acquisition function values."""
        X_sample = np.array(self.X_observed)
        y_sample = np.array(self.y_observed)
        
        if self.acquisition_function == AcquisitionFunction.EXPECTED_IMPROVEMENT:
            return -self._expected_improvement(X, X_sample, y_sample)
        elif self.acquisition_function == AcquisitionFunction.UPPER_CONFIDENCE_BOUND:
            return -self._upper_confidence_bound(X)
        elif self.acquisition_function == AcquisitionFunction.PROBABILITY_OF_IMPROVEMENT:
            return -self._probability_of_improvement(X, X_sample, y_sample)
        else:  # GREEDY
            mu, _ = self.gp.predict(X, return_std=True)
            return -mu if self.maximize else mu
    
    def _propose_next_point(self) -> Dict[str, Any]:
        """Propose next point to evaluate using acquisition function optimization."""
        # Start from best observed point
        if len(self.X_observed) > 0:
            best_idx = np.argmax(self.y_observed) if self.maximize else np.argmin(self.y_observed)
            x0 = self.X_observed[best_idx]
        else:
            x0 = np.random.uniform(0, 1, len(self.param_names))
        
        # Define bounds for optimization
        bounds = [(0, 1) for _ in self.param_names]
        
        # Optimize acquisition function
        result = minimize(
            fun=lambda x: self._acquisition_function_values(x.reshape(1, -1))[0],
            x0=x0,
            bounds=bounds,
            method='L-BFGS-B'
        )
        
        # Unscale and convert to params
        unscaled = self._unscale_params(result.x)
        return self._array_to_params(unscaled)
    
    def _check_convergence(self) -> bool:
        """Check if optimization has converged."""
        if len(self.y_observed) < self.n_initial_points + 5:
            return False
        
        # Check for improvement
        current_best = max(self.y_observed) if self.maximize else min(self.y_observed)
        
        if self.last_best_value is not None:
            improvement = abs(current_best - self.last_best_value)
            
            if improvement < self.early_stopping_min_delta:
                self.no_improvement_count += 1
            else:
                self.no_improvement_count = 0
        
        self.last_best_value = current_best
        
        # Early stopping
        if self.no_improvement_count >= self.early_stopping_patience:
            logger.info(f"Early stopping triggered after {len(self.y_observed)} iterations")
            return True
        
        # Max iterations
        if self.iteration >= self.n_iterations:
            return True
        
        return False
    
    def tell(self, params: Dict[str, Any], value: float) -> None:
        """
        Tell the optimizer about a new observation.
        
        Args:
            params: Parameter dictionary
            value: Objective function value
        """
        # Convert to array and scale
        params_array = self._params_to_array(params)
        scaled = self._scale_params(params_array)
        
        self.X_observed.append(scaled)
        self.y_observed.append(value)
        self.param_history.append(params.copy())
        
        # Update best
        is_better = (value > self.best_value) if self.maximize else (value < self.best_value)
        if is_better or self.best_params is None:
            self.best_value = value
            self.best_params = params.copy()
            logger.debug(f"New best value: {value:.4f} with params {params}")
        
        # Fit GP if we have enough points
        if len(self.X_observed) >= self.n_initial_points:
            X_array = np.array(self.X_observed)
            y_array = np.array(self.y_observed)
            self.gp.fit(X_array, y_array)
    
    def ask(self) -> Dict[str, Any]:
        """
        Ask the optimizer for the next point to evaluate.
        
        Returns:
            Dictionary of parameters to evaluate
        """
        # Initial random sampling
        if len(self.X_observed) < self.n_initial_points:
            return self._sample_random_params()
        
        # Use acquisition function to propose next point
        return self._propose_next_point()
    
    async def optimize(
        self,
        objective_func: Callable[[Dict[str, Any]], float],
        async_mode: bool = True
    ) -> OptimizationResult:
        """
        Run Bayesian optimization.
        
        Args:
            objective_func: Function to minimize/maximize
            async_mode: Whether to run asynchronously
            
        Returns:
            OptimizationResult with best parameters found
        """
        start_time = datetime.now()
        self.iteration = 0
        
        logger.info(f"Starting Bayesian optimization with max {self.n_iterations} iterations")
        
        try:
            while not self._check_convergence():
                # Get next parameters
                params = self.ask()
                
                # Evaluate objective function
                if async_mode and asyncio.iscoroutinefunction(objective_func):
                    value = await objective_func(params)
                else:
                    value = objective_func(params)
                
                # Tell optimizer about result
                self.tell(params, value)
                
                # Track acquisition value
                if len(self.X_observed) > self.n_initial_points:
                    X_last = np.array([self.X_observed[-1]])
                    acq_val = -self._acquisition_function_values(X_last)[0]
                    self.acquisition_history.append(float(acq_val))
                
                self.iteration += 1
                
                # Log progress
                if self.iteration % 10 == 0:
                    logger.info(f"Iteration {self.iteration}: best value = {self.best_value:.4f}")
            
            # Prepare result
            optimization_time = (datetime.now() - start_time).total_seconds()
            
            result = OptimizationResult(
                best_params=self.best_params or {},
                best_value=self.best_value,
                all_params=self.param_history,
                all_values=self.y_observed.copy(),
                acquisition_history=self.acquisition_history,
                n_iterations=self.iteration,
                convergence_status=(
                    "converged_early" 
                    if self.no_improvement_count >= self.early_stopping_patience 
                    else "max_iterations"
                ),
                optimization_time_seconds=optimization_time,
                improvement_history=self.y_observed.copy()
            )
            
            logger.info(
                f"Optimization completed in {optimization_time:.2f}s. "
                f"Best value: {self.best_value:.4f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            raise AstraGuardException(
                f"Bayesian optimization failed: {e}",
                component="bayesian_optimizer",
                context={"iteration": self.iteration}
            )
    
    def get_best_params(self) -> Optional[Dict[str, Any]]:
        """Get best parameters found so far."""
        return self.best_params
    
    def get_observation_count(self) -> int:
        """Get number of observations made."""
        return len(self.X_observed)
    
    def predict(self, params: Dict[str, Any]) -> Tuple[float, float]:
        """
        Predict objective value and uncertainty for given parameters.
        
        Returns:
            Tuple of (mean, standard_deviation)
        """
        if len(self.X_observed) < self.n_initial_points:
            raise ValueError("Not enough observations to make predictions")
        
        params_array = self._params_to_array(params)
        scaled = self._scale_params(params_array)
        
        mu, sigma = self.gp.predict(scaled.reshape(1, -1), return_std=True)
        return float(mu[0]), float(sigma[0])
    
    def shutdown(self):
        """Clean up resources."""
        self._executor.shutdown(wait=True)
