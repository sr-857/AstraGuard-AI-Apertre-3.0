"""
Objective Functions for Bayesian Optimization

Defines various objective functions for optimizing threat detection models,
including false positive rate minimization, accuracy maximization, and
multi-objective optimization.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime
import logging
import asyncio

from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import (
    precision_score, recall_score, f1_score, 
    roc_auc_score, confusion_matrix,
    make_scorer
)

from core.error_handling import (
    AstraGuardException,
    safe_execute,
    ErrorContext,
    ErrorSeverity
)

logger = logging.getLogger(__name__)


@dataclass
class ObjectiveResult:
    """Result of objective function evaluation."""
    value: float
    metrics: Dict[str, float]
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'value': float(self.value),
            'metrics': {k: float(v) for k, v in self.metrics.items()},
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class ObjectiveFunction(ABC):
    """Abstract base class for objective functions."""
    
    @abstractmethod
    def evaluate(self, params: Dict[str, Any]) -> float:
        """
        Evaluate objective function for given parameters.
        
        Args:
            params: Hyperparameter dictionary
            
        Returns:
            Objective value (to be minimized or maximized)
        """
        pass
    
    @abstractmethod
    async def evaluate_async(self, params: Dict[str, Any]) -> float:
        """Async version of evaluate."""
        pass


class FalsePositiveObjective(ObjectiveFunction):
    """
    Objective function to minimize false positive rate.
    
    Target: <1% false positive rate while maintaining reasonable detection rate.
    """
    
    def __init__(
        self,
        model_trainer: Callable,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        target_fpr: float = 0.01,
        min_recall: float = 0.8,
        penalty_weight: float = 10.0
    ):
        self.model_trainer = model_trainer
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.target_fpr = target_fpr
        self.min_recall = min_recall
        self.penalty_weight = penalty_weight
        
        self.evaluation_count = 0
        self.results_history: List[ObjectiveResult] = []
    
    def evaluate(self, params: Dict[str, Any]) -> float:
        """
        Evaluate false positive rate for given parameters.
        
        Returns:
            Objective value (lower is better)
            = FPR + penalty for recall < min_recall + penalty for FPR > target
        """
        try:
            self.evaluation_count += 1
            
            # Train model with given parameters
            model = self.model_trainer(params, self.X_train, self.y_train)
            
            # Predict on validation set
            y_pred = model.predict(self.X_val)
            y_prob = model.predict_proba(self.X_val)[:, 1] if hasattr(model, 'predict_proba') else y_pred
            
            # Calculate metrics
            cm = confusion_matrix(self.y_val, y_pred)
            tn, fp, fn, tp = cm.ravel()
            
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            f1 = f1_score(self.y_val, y_pred, zero_division=0)
            
            # Calculate objective value
            # Primary: minimize FPR
            objective = fpr
            
            # Penalty for low recall
            if recall < self.min_recall:
                recall_penalty = self.penalty_weight * (self.min_recall - recall)
                objective += recall_penalty
            
            # Penalty for exceeding target FPR
            if fpr > self.target_fpr:
                fpr_penalty = self.penalty_weight * (fpr - self.target_fpr)
                objective += fpr_penalty
            
            # Store result
            result = ObjectiveResult(
                value=objective,
                metrics={
                    'fpr': fpr,
                    'recall': recall,
                    'precision': precision,
                    'f1': f1,
                    'false_positives': int(fp),
                    'true_negatives': int(tn),
                },
                metadata={
                    'params': params,
                    'evaluation_count': self.evaluation_count,
                    'meets_target': fpr <= self.target_fpr and recall >= self.min_recall
                },
                timestamp=datetime.now()
            )
            self.results_history.append(result)
            
            logger.debug(
                f"Eval {self.evaluation_count}: FPR={fpr:.4f}, "
                f"Recall={recall:.4f}, Objective={objective:.4f}"
            )
            
            return objective
            
        except Exception as e:
            logger.error(f"Objective evaluation failed: {e}")
            # Return high penalty value on failure
            return 1.0
    
    async def evaluate_async(self, params: Dict[str, Any]) -> float:
        """Async wrapper for evaluate."""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.evaluate, params)
    
    def get_best_result(self) -> Optional[ObjectiveResult]:
        """Get best result found so far."""
        if not self.results_history:
            return None
        return min(self.results_history, key=lambda r: r.value)
    
    def get_results_meeting_target(self) -> List[ObjectiveResult]:
        """Get all results that meet the target FPR and recall."""
        return [r for r in self.results_history if r.metadata.get('meets_target', False)]


class DetectionAccuracyObjective(ObjectiveFunction):
    """
    Objective function to maximize detection accuracy (F1 score).
    
    Balances precision and recall for optimal threat detection.
    """
    
    def __init__(
        self,
        model_trainer: Callable,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        cv_folds: int = 5,
        use_cross_validation: bool = True
    ):
        self.model_trainer = model_trainer
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.cv_folds = cv_folds
        self.use_cross_validation = use_cross_validation
        
        self.evaluation_count = 0
        self.results_history: List[ObjectiveResult] = []
    
    def evaluate(self, params: Dict[str, Any]) -> float:
        """
        Evaluate detection accuracy for given parameters.
        
        Returns:
            Objective value (higher is better, we maximize F1)
        """
        try:
            self.evaluation_count += 1
            
            if self.use_cross_validation:
                # Use cross-validation for more robust evaluation
                model = self.model_trainer(params)
                
                # Create stratified k-fold
                cv = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=42)
                
                # Custom scorer for F1
                scorer = make_scorer(f1_score, zero_division=0)
                
                # Perform cross-validation
                scores = cross_val_score(
                    model, self.X_train, self.y_train,
                    cv=cv, scoring=scorer, n_jobs=-1
                )
                
                f1_mean = np.mean(scores)
                f1_std = np.std(scores)
                
                # Objective is mean F1 minus penalty for high variance
                objective = f1_mean - 0.1 * f1_std
                
                metrics = {
                    'f1_mean': f1_mean,
                    'f1_std': f1_std,
                    'f1_min': np.min(scores),
                    'f1_max': np.max(scores),
                }
                
            else:
                # Single train/validation split
                model = self.model_trainer(params, self.X_train, self.y_train)
                
                y_pred = model.predict(self.X_val)
                
                precision = precision_score(self.y_val, y_pred, zero_division=0)
                recall = recall_score(self.y_val, y_pred, zero_division=0)
                f1 = f1_score(self.y_val, y_pred, zero_division=0)
                
                # Try to get AUC if probabilities available
                try:
                    y_prob = model.predict_proba(self.X_val)[:, 1]
                    auc = roc_auc_score(self.y_val, y_prob)
                except:
                    auc = 0.5
                
                objective = f1
                
                metrics = {
                    'f1': f1,
                    'precision': precision,
                    'recall': recall,
                    'auc': auc,
                }
            
            # Store result
            result = ObjectiveResult(
                value=objective,
                metrics=metrics,
                metadata={
                    'params': params,
                    'evaluation_count': self.evaluation_count,
                    'used_cv': self.use_cross_validation
                },
                timestamp=datetime.now()
            )
            self.results_history.append(result)
            
            logger.debug(
                f"Eval {self.evaluation_count}: F1={metrics.get('f1_mean', metrics.get('f1', 0)):.4f}, "
                f"Objective={objective:.4f}"
            )
            
            return objective
            
        except Exception as e:
            logger.error(f"Objective evaluation failed: {e}")
            return 0.0  # Return 0 on failure (we're maximizing)
    
    async def evaluate_async(self, params: Dict[str, Any]) -> float:
        """Async wrapper for evaluate."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.evaluate, params)
    
    def get_best_result(self) -> Optional[ObjectiveResult]:
        """Get best result found so far."""
        if not self.results_history:
            return None
        return max(self.results_history, key=lambda r: r.value)


class LatencyAwareObjective(ObjectiveFunction):
    """
    Objective function that balances accuracy with inference latency.
    
    Important for real-time threat detection requirements.
    """
    
    def __init__(
        self,
        model_trainer: Callable,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        target_latency_ms: float = 100.0,
        latency_weight: float = 0.3,
        accuracy_weight: float = 0.7
    ):
        self.model_trainer = model_trainer
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.target_latency_ms = target_latency_ms
        self.latency_weight = latency_weight
        self.accuracy_weight = accuracy_weight
        
        self.evaluation_count = 0
        self.results_history: List[ObjectiveResult] = []
    
    def evaluate(self, params: Dict[str, Any]) -> float:
        """
        Evaluate accuracy-latency trade-off.
        
        Returns:
            Objective value (higher is better)
        """
        try:
            self.evaluation_count += 1
            
            import time
            
            # Train model
            start_time = time.time()
            model = self.model_trainer(params, self.X_train, self.y_train)
            train_time = (time.time() - start_time) * 1000  # ms
            
            # Measure inference latency
            start_time = time.time()
            y_pred = model.predict(self.X_val)
            inference_time = (time.time() - start_time) * 1000  # ms
            
            # Calculate per-sample latency
            per_sample_latency = inference_time / len(self.X_val)
            
            # Calculate accuracy
            f1 = f1_score(self.y_val, y_pred, zero_division=0)
            
            # Normalize latency (lower is better, so we invert)
            # Use exponential decay for latency penalty
            latency_score = np.exp(-per_sample_latency / self.target_latency_ms)
            
            # Combined objective
            objective = (
                self.accuracy_weight * f1 +
                self.latency_weight * latency_score
            )
            
            # Penalty for exceeding target latency
            if per_sample_latency > self.target_latency_ms:
                latency_penalty = 0.5 * (per_sample_latency - self.target_latency_ms) / self.target_latency_ms
                objective -= latency_penalty
            
            # Store result
            result = ObjectiveResult(
                value=objective,
                metrics={
                    'f1': f1,
                    'train_time_ms': train_time,
                    'inference_time_ms': inference_time,
                    'per_sample_latency_ms': per_sample_latency,
                    'latency_score': latency_score,
                },
                metadata={
                    'params': params,
                    'evaluation_count': self.evaluation_count,
                    'meets_latency_target': per_sample_latency <= self.target_latency_ms
                },
                timestamp=datetime.now()
            )
            self.results_history.append(result)
            
            logger.debug(
                f"Eval {self.evaluation_count}: F1={f1:.4f}, "
                f"Latency={per_sample_latency:.2f}ms, Objective={objective:.4f}"
            )
            
            return objective
            
        except Exception as e:
            logger.error(f"Objective evaluation failed: {e}")
            return 0.0
    
    async def evaluate_async(self, params: Dict[str, Any]) -> float:
        """Async wrapper for evaluate."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.evaluate, params)


class EnsembleObjective(ObjectiveFunction):
    """
    Objective function for optimizing ensemble weights and thresholds.
    
    Optimizes the combination of multiple models for best overall performance.
    """
    
    def __init__(
        self,
        ensemble_predictor: Callable,
        X_val: np.ndarray,
        y_val: np.ndarray,
        target_fpr: float = 0.01,
        target_recall: float = 0.9,
        fpr_weight: float = 0.5,
        recall_weight: float = 0.5
    ):
        self.ensemble_predictor = ensemble_predictor
        self.X_val = X_val
        self.y_val = y_val
        self.target_fpr = target_fpr
        self.target_recall = target_recall
        self.fpr_weight = fpr_weight
        self.recall_weight = recall_weight
        
        self.evaluation_count = 0
        self.results_history: List[ObjectiveResult] = []
    
    def evaluate(self, params: Dict[str, Any]) -> float:
        """
        Evaluate ensemble configuration.
        
        Args:
            params: Dictionary with 'weights' and 'thresholds' keys
            
        Returns:
            Objective value (higher is better)
        """
        try:
            self.evaluation_count += 1
            
            # Get predictions from ensemble
            predictions = self.ensemble_predictor(self.X_val, params)
            
            # Extract predictions and probabilities
            y_pred = np.array([p['is_anomaly'] for p in predictions])
            y_prob = np.array([p['anomaly_score'] for p in predictions])
            
            # Calculate metrics
            cm = confusion_matrix(self.y_val, y_pred)
            tn, fp, fn, tp = cm.ravel()
            
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            f1 = f1_score(self.y_val, y_pred, zero_division=0)
            
            # Calculate objective
            # Reward for meeting targets
            fpr_score = 1.0 - max(0, (fpr - self.target_fpr) / self.target_fpr)
            recall_score = min(1.0, recall / self.target_recall)
            
            objective = (
                self.fpr_weight * fpr_score +
                self.recall_weight * recall_score +
                0.1 * f1  # Small bonus for F1
            )
            
            # Store result
            result = ObjectiveResult(
                value=objective,
                metrics={
                    'fpr': fpr,
                    'recall': recall,
                    'precision': precision,
                    'f1': f1,
                    'fpr_score': fpr_score,
                    'recall_score': recall_score,
                    'false_positives': int(fp),
                    'true_positives': int(tp),
                },
                metadata={
                    'params': params,
                    'evaluation_count': self.evaluation_count,
                    'meets_fpr_target': fpr <= self.target_fpr,
                    'meets_recall_target': recall >= self.target_recall
                },
                timestamp=datetime.now()
            )
            self.results_history.append(result)
            
            logger.debug(
                f"Eval {self.evaluation_count}: FPR={fpr:.4f}, "
                f"Recall={recall:.4f}, Objective={objective:.4f}"
            )
            
            return objective
            
        except Exception as e:
            logger.error(f"Ensemble objective evaluation failed: {e}")
            return 0.0
    
    async def evaluate_async(self, params: Dict[str, Any]) -> float:
        """Async wrapper for evaluate."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.evaluate, params)


class MultiObjectiveOptimizer:
    """
    Multi-objective optimizer combining multiple objective functions.
    
    Uses weighted combination or Pareto frontier approach.
    """
    
    def __init__(
        self,
        objectives: List[Tuple[ObjectiveFunction, float]],
        maximize: bool = True
    ):
        """
        Initialize multi-objective optimizer.
        
        Args:
            objectives: List of (objective_function, weight) tuples
            maximize: Whether to maximize (True) or minimize (False)
        """
        self.objectives = objectives
        self.maximize = maximize
        self.evaluation_count = 0
    
    def evaluate(self, params: Dict[str, Any]) -> float:
        """
        Evaluate combined objective.
        
        Returns:
            Weighted combination of all objectives
        """
        self.evaluation_count += 1
        
        total_value = 0.0
        total_weight = 0.0
        
        for objective, weight in self.objectives:
            value = objective.evaluate(params)
            total_value += weight * value
            total_weight += weight
        
        if total_weight > 0:
            combined = total_value / total_weight
        else:
            combined = 0.0
        
        # Invert if minimizing
        if not self.maximize:
            combined = -combined
        
        return combined
    
    async def evaluate_async(self, params: Dict[str, Any]) -> float:
        """Async wrapper for evaluate."""
        # Evaluate all objectives concurrently
        tasks = [
            obj.evaluate_async(params) 
            for obj, _ in self.objectives
        ]
        values = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_values = []
        valid_weights = []
        
        for (obj, weight), value in zip(self.objectives, values):
            if not isinstance(value, Exception):
                valid_values.append(weight * value)
                valid_weights.append(weight)
        
        if sum(valid_weights) > 0:
            combined = sum(valid_values) / sum(valid_weights)
        else:
            combined = 0.0
        
        if not self.maximize:
            combined = -combined
        
        return combined
    
    def get_objective_results(self) -> List[List[ObjectiveResult]]:
        """Get results from all individual objectives."""
        return [
            obj.results_history 
            for obj, _ in self.objectives
        ]


def create_default_objective(
    model_type: str,
    model_trainer: Callable,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    **kwargs
) -> ObjectiveFunction:
    """
    Factory function to create appropriate objective function.
    
    Args:
        model_type: Type of model ('isolation_forest', 'random_forest', 'ensemble')
        model_trainer: Function to train model with given params
        X_train: Training features
        y_train: Training labels
        X_val: Validation features
        y_val: Validation labels
        **kwargs: Additional arguments for objective function
        
    Returns:
        Configured objective function
    """
    if model_type == 'isolation_forest':
        # For unsupervised models, use accuracy objective
        return DetectionAccuracyObjective(
            model_trainer, X_train, y_train, X_val, y_val,
            use_cross_validation=False,
            **kwargs
        )
    
    elif model_type == 'random_forest':
        # For supervised models, prioritize low FPR
        return FalsePositiveObjective(
            model_trainer, X_train, y_train, X_val, y_val,
            target_fpr=0.01,
            min_recall=0.8,
            **kwargs
        )
    
    elif model_type == 'ensemble':
        # For ensemble, use ensemble-specific objective
        return EnsembleObjective(
            model_trainer, X_val, y_val,
            target_fpr=0.01,
            target_recall=0.9,
            **kwargs
        )
    
    else:
        # Default to accuracy objective
        return DetectionAccuracyObjective(
            model_trainer, X_train, y_train, X_val, y_val,
            **kwargs
        )
