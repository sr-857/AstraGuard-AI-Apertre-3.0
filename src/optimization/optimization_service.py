"""
Optimization Service for AstraGuard-AI

Provides background optimization capabilities for ML models with
Bayesian optimization, continuous learning, and API integration.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import asyncio
import json
import pickle
import os
from pathlib import Path

from .bayesian_optimizer import BayesianOptimizer, AcquisitionFunction, OptimizationResult
from .hyperparameter_spaces import (
    IsolationForestSpace,
    RandomForestSpace,
    AutoencoderSpace,
    EnsembleWeightSpace,
    DetectionThresholdSpace,
    get_combined_space,
    parse_combined_params
)
from .objective_functions import (
    FalsePositiveObjective,
    DetectionAccuracyObjective,
    EnsembleObjective,
    MultiObjectiveOptimizer,
    create_default_objective,
    ObjectiveResult
)

from core.error_handling import (
    AstraGuardException,
    safe_execute,
    ErrorContext,
    ErrorSeverity
)
from core.metrics import (
    OPTIMIZATION_ITERATIONS_TOTAL,
    OPTIMIZATION_BEST_VALUE,
    OPTIMIZATION_TIME_SECONDS,
)

logger = logging.getLogger(__name__)


class OptimizationTarget(Enum):
    """Targets for optimization."""
    ISOLATION_FOREST = "isolation_forest"
    RANDOM_FOREST = "random_forest"
    AUTOENCODER = "autoencoder"
    ENSEMBLE_WEIGHTS = "ensemble_weights"
    THRESHOLDS = "thresholds"
    COMBINED = "combined"


@dataclass
class OptimizationConfig:
    """Configuration for optimization run."""
    target: OptimizationTarget
    n_iterations: int = 50
    n_initial_points: int = 5
    acquisition_function: AcquisitionFunction = AcquisitionFunction.EXPECTED_IMPROVEMENT
    early_stopping_patience: int = 10
    target_fpr: float = 0.01
    min_recall: float = 0.8
    async_mode: bool = True
    save_results: bool = True
    use_cross_validation: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'target': self.target.value,
            'n_iterations': self.n_iterations,
            'n_initial_points': self.n_initial_points,
            'acquisition_function': self.acquisition_function.value,
            'early_stopping_patience': self.early_stopping_patience,
            'target_fpr': self.target_fpr,
            'min_recall': self.min_recall,
            'async_mode': self.async_mode,
            'save_results': self.save_results,
            'use_cross_validation': self.use_cross_validation,
        }


@dataclass
class OptimizationJob:
    """Represents an optimization job."""
    job_id: str
    config: OptimizationConfig
    status: str  # 'pending', 'running', 'completed', 'failed'
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[OptimizationResult] = None
    error: Optional[str] = None
    progress: float = 0.0  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'job_id': self.job_id,
            'config': self.config.to_dict(),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result.to_dict() if self.result else None,
            'error': self.error,
            'progress': self.progress,
        }


class OptimizationService:
    """
    Service for managing Bayesian optimization of ML models.
    
    Features:
    - Queue-based optimization jobs
    - Background optimization execution
    - Results persistence
    - Integration with model ensemble
    - Continuous learning from feedback
    """
    
    def __init__(
        self,
        results_dir: str = "optimization_results",
        max_concurrent_jobs: int = 2,
        auto_optimize: bool = False,
        optimization_interval_hours: int = 24
    ):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.max_concurrent_jobs = max_concurrent_jobs
        self.auto_optimize = auto_optimize
        self.optimization_interval_hours = optimization_interval_hours
        
        # Job management
        self.jobs: Dict[str, OptimizationJob] = {}
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self.running_jobs: set = set()
        self._shutdown_event: Optional[asyncio.Event] = None
        
        # Optimization state
        self.best_params: Dict[OptimizationTarget, Dict[str, Any]] = {}
        self.optimization_history: List[Dict[str, Any]] = []
        
        # Load previous results
        self._load_saved_results()
        
        logger.info(f"OptimizationService initialized with results_dir={results_dir}")
    
    def _load_saved_results(self):
        """Load previously saved optimization results."""
        try:
            best_params_file = self.results_dir / "best_params.json"
            if best_params_file.exists():
                with open(best_params_file, 'r') as f:
                    data = json.load(f)
                    for target_str, params in data.items():
                        try:
                            target = OptimizationTarget(target_str)
                            self.best_params[target] = params
                        except ValueError:
                            continue
                logger.info(f"Loaded best params for {len(self.best_params)} targets")
        except Exception as e:
            logger.warning(f"Failed to load saved results: {e}")
    
    def _save_best_params(self):
        """Save best parameters to disk."""
        try:
            best_params_file = self.results_dir / "best_params.json"
            data = {
                target.value: params 
                for target, params in self.best_params.items()
            }
            with open(best_params_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save best params: {e}")
    
    async def start(self):
        """Start the optimization service."""
        self._shutdown_event = asyncio.Event()
        
        # Start background workers
        workers = [
            asyncio.create_task(self._optimization_worker())
            for _ in range(self.max_concurrent_jobs)
        ]
        
        # Start auto-optimization if enabled
        if self.auto_optimize:
            asyncio.create_task(self._auto_optimization_loop())
        
        logger.info("OptimizationService started")
        
        # Wait for shutdown
        await self._shutdown_event.wait()
        
        # Cancel workers
        for worker in workers:
            worker.cancel()
        
        logger.info("OptimizationService stopped")
    
    async def stop(self):
        """Stop the optimization service."""
        if self._shutdown_event:
            self._shutdown_event.set()
    
    async def _optimization_worker(self):
        """Worker that processes optimization jobs."""
        while True:
            try:
                job = await self.job_queue.get()
                
                if job.job_id in self.running_jobs:
                    continue
                
                self.running_jobs.add(job.job_id)
                job.status = 'running'
                job.started_at = datetime.now()
                
                try:
                    logger.info(f"Starting optimization job {job.job_id}")
                    result = await self._run_optimization(job)
                    job.result = result
                    job.status = 'completed'
                    job.progress = 1.0
                    
                    # Store best params
                    if result and result.best_params:
                        self.best_params[job.config.target] = result.best_params
                        self._save_best_params()
                    
                    logger.info(f"Optimization job {job.job_id} completed")
                    
                except Exception as e:
                    job.status = 'failed'
                    job.error = str(e)
                    logger.error(f"Optimization job {job.job_id} failed: {e}")
                
                finally:
                    job.completed_at = datetime.now()
                    self.running_jobs.discard(job.job_id)
                    self.job_queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Optimization worker error: {e}")
    
    async def _run_optimization(self, job: OptimizationJob) -> OptimizationResult:
        """Run optimization for a job."""
        # This is a placeholder - actual implementation would integrate
        # with the model training pipeline
        raise NotImplementedError(
            "Optimization must be run with specific data and models. "
            "Use optimize_isolation_forest, optimize_random_forest, etc."
        )
    
    async def _auto_optimization_loop(self):
        """Background loop for automatic optimization."""
        while True:
            try:
                await asyncio.sleep(self.optimization_interval_hours * 3600)
                
                # Check if optimization is needed based on feedback
                if self._should_optimize():
                    logger.info("Triggering automatic optimization")
                    # Trigger optimization for all targets
                    for target in OptimizationTarget:
                        if target != OptimizationTarget.COMBINED:
                            # Create and queue optimization job
                            pass  # Implementation depends on data availability
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-optimization loop error: {e}")
    
    def _should_optimize(self) -> bool:
        """Determine if optimization should be triggered."""
        # Check time since last optimization
        if not self.optimization_history:
            return True
        
        last_optimization = self.optimization_history[-1].get('timestamp')
        if last_optimization:
            last_time = datetime.fromisoformat(last_optimization)
            hours_since = (datetime.now() - last_time).total_seconds() / 3600
            return hours_since >= self.optimization_interval_hours
        
        return True
    
    def submit_job(self, config: OptimizationConfig) -> str:
        """
        Submit an optimization job.
        
        Args:
            config: Optimization configuration
            
        Returns:
            Job ID
        """
        job_id = f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.jobs)}"
        
        job = OptimizationJob(
            job_id=job_id,
            config=config,
            status='pending',
            created_at=datetime.now()
        )
        
        self.jobs[job_id] = job
        asyncio.create_task(self.job_queue.put(job))
        
        logger.info(f"Submitted optimization job {job_id}")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an optimization job."""
        job = self.jobs.get(job_id)
        if job:
            return job.to_dict()
        return None
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Get all optimization jobs."""
        return [job.to_dict() for job in self.jobs.values()]
    
    def get_best_params(self, target: OptimizationTarget) -> Optional[Dict[str, Any]]:
        """Get best parameters for a target."""
        return self.best_params.get(target)
    
    async def optimize_isolation_forest(
        self,
        X_train: np.ndarray,
        y_train: Optional[np.ndarray],
        X_val: np.ndarray,
        y_val: np.ndarray,
        n_iterations: int = 30,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize Isolation Forest hyperparameters.
        
        Args:
            X_train: Training features
            y_train: Training labels (optional for unsupervised)
            X_val: Validation features
            y_val: Validation labels
            n_iterations: Number of optimization iterations
            **kwargs: Additional optimization parameters
            
        Returns:
            OptimizationResult with best parameters
        """
        from sklearn.ensemble import IsolationForest
        
        # Define parameter space
        param_space = IsolationForestSpace.get_space()
        
        # Define model trainer
        def train_model(params, X, y=None):
            model_params = IsolationForestSpace.convert_params(
                params, len(X), X.shape[1]
            )
            model = IsolationForest(**model_params)
            model.fit(X)
            return model
        
        # Create objective function
        if y_train is not None and y_val is not None:
            # Supervised evaluation
            objective = DetectionAccuracyObjective(
                train_model, X_train, y_train, X_val, y_val,
                use_cross_validation=False
            )
        else:
            # Unsupervised - use reconstruction error or other metric
            objective = DetectionAccuracyObjective(
                train_model, X_train, np.zeros(len(X_train)), 
                X_val, np.zeros(len(X_val)),
                use_cross_validation=False
            )
        
        # Create optimizer
        optimizer = BayesianOptimizer(
            param_bounds=param_space,
            acquisition_function=AcquisitionFunction.EXPECTED_IMPROVEMENT,
            n_iterations=n_iterations,
            maximize=True,
            **kwargs
        )
        
        # Run optimization
        result = await optimizer.optimize(objective.evaluate_async, async_mode=True)
        
        # Store result
        self.best_params[OptimizationTarget.ISOLATION_FOREST] = result.best_params
        self._save_best_params()
        
        # Record in history
        self.optimization_history.append({
            'target': OptimizationTarget.ISOLATION_FOREST.value,
            'timestamp': datetime.now().isoformat(),
            'result': result.to_dict()
        })
        
        return result
    
    async def optimize_random_forest(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        n_iterations: int = 30,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize Random Forest hyperparameters.
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            n_iterations: Number of optimization iterations
            **kwargs: Additional optimization parameters
            
        Returns:
            OptimizationResult with best parameters
        """
        from sklearn.ensemble import RandomForestClassifier
        
        # Define parameter space
        param_space = RandomForestSpace.get_space()
        
        # Define model trainer
        def train_model(params, X, y):
            model_params = RandomForestSpace.convert_params(params, X.shape[1])
            model = RandomForestClassifier(**model_params)
            model.fit(X, y)
            return model
        
        # Create objective function targeting low FPR
        objective = FalsePositiveObjective(
            train_model, X_train, y_train, X_val, y_val,
            target_fpr=0.01,
            min_recall=0.8
        )
        
        # Create optimizer (minimize FPR)
        optimizer = BayesianOptimizer(
            param_bounds=param_space,
            acquisition_function=AcquisitionFunction.EXPECTED_IMPROVEMENT,
            n_iterations=n_iterations,
            maximize=False,  # Minimize FPR
            **kwargs
        )
        
        # Run optimization
        result = await optimizer.optimize(objective.evaluate_async, async_mode=True)
        
        # Store result
        self.best_params[OptimizationTarget.RANDOM_FOREST] = result.best_params
        self._save_best_params()
        
        return result
    
    async def optimize_ensemble_weights(
        self,
        ensemble_predictor: Callable,
        X_val: np.ndarray,
        y_val: np.ndarray,
        n_iterations: int = 20,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize ensemble weights and thresholds.
        
        Args:
            ensemble_predictor: Function that takes X and params, returns predictions
            X_val: Validation features
            y_val: Validation labels
            n_iterations: Number of optimization iterations
            **kwargs: Additional optimization parameters
            
        Returns:
            OptimizationResult with best weights and thresholds
        """
        # Combine weight and threshold spaces
        weight_space = EnsembleWeightSpace.get_space()
        threshold_space = DetectionThresholdSpace.get_space()
        
        combined_space = {**weight_space, **threshold_space}
        
        # Create objective
        objective = EnsembleObjective(
            ensemble_predictor, X_val, y_val,
            target_fpr=0.01,
            target_recall=0.9
        )
        
        # Create optimizer
        optimizer = BayesianOptimizer(
            param_bounds=combined_space,
            acquisition_function=AcquisitionFunction.EXPECTED_IMPROVEMENT,
            n_iterations=n_iterations,
            maximize=True,
            **kwargs
        )
        
        # Run optimization
        result = await optimizer.optimize(objective.evaluate_async, async_mode=True)
        
        # Parse and store result
        parsed = parse_combined_params(result.best_params)
        self.best_params[OptimizationTarget.ENSEMBLE_WEIGHTS] = parsed['ensemble_weights']
        self.best_params[OptimizationTarget.THRESHOLDS] = parsed['thresholds']
        self._save_best_params()
        
        return result
    
    def apply_best_params(
        self,
        target: OptimizationTarget,
        model_or_ensemble: Any
    ) -> bool:
        """
        Apply best parameters to a model or ensemble.
        
        Args:
            target: Optimization target
            model_or_ensemble: Model instance to update
            
        Returns:
            True if parameters were applied successfully
        """
        best_params = self.best_params.get(target)
        if not best_params:
            logger.warning(f"No best params found for {target.value}")
            return False
        
        try:
            if target == OptimizationTarget.ISOLATION_FOREST:
                # Apply to Isolation Forest
                pass  # Model needs to be retrained with new params
            
            elif target == OptimizationTarget.RANDOM_FOREST:
                # Apply to Random Forest
                pass  # Model needs to be retrained with new params
            
            elif target == OptimizationTarget.ENSEMBLE_WEIGHTS:
                # Apply weights to ensemble
                if hasattr(model_or_ensemble, 'weights'):
                    from threat_detection.model_ensemble import ModelType
                    model_or_ensemble.weights = {
                        ModelType.ISOLATION_FOREST: best_params.get('isolation_forest', 0.3),
                        ModelType.RANDOM_FOREST: best_params.get('random_forest', 0.4),
                        ModelType.AUTOENCODER: best_params.get('autoencoder', 0.3),
                    }
            
            elif target == OptimizationTarget.THRESHOLDS:
                # Apply thresholds
                if hasattr(model_or_ensemble, 'thresholds'):
                    from threat_detection.model_ensemble import ModelType
                    model_or_ensemble.thresholds = {
                        ModelType.ISOLATION_FOREST: best_params.get('isolation_forest', 0.6),
                        ModelType.RANDOM_FOREST: best_params.get('random_forest', 0.5),
                        ModelType.AUTOENCODER: best_params.get('autoencoder', 0.7),
                    }
            
            logger.info(f"Applied best params for {target.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply best params: {e}")
            return False


# Global instance
_optimization_service: Optional[OptimizationService] = None


def get_optimization_service(
    results_dir: str = "optimization_results",
    **kwargs
) -> OptimizationService:
    """Get or create global optimization service instance."""
    global _optimization_service
    if _optimization_service is None:
        _optimization_service = OptimizationService(
            results_dir=results_dir,
            **kwargs
        )
    return _optimization_service


async def run_bayesian_optimization(
    model_type: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    n_iterations: int = 30,
    target_fpr: float = 0.01,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to run Bayesian optimization for a model.
    
    Args:
        model_type: Type of model to optimize
        X_train: Training features
        y_train: Training labels
        X_val: Validation features
        y_val: Validation labels
        n_iterations: Number of optimization iterations
        target_fpr: Target false positive rate
        **kwargs: Additional parameters
        
    Returns:
        Dictionary with optimization results
    """
    service = get_optimization_service()
    
    if model_type == 'isolation_forest':
        result = await service.optimize_isolation_forest(
            X_train, y_train, X_val, y_val, n_iterations, **kwargs
        )
    elif model_type == 'random_forest':
        result = await service.optimize_random_forest(
            X_train, y_train, X_val, y_val, n_iterations, **kwargs
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    return result.to_dict()
