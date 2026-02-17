"""
Model Ensemble for Advanced Threat Detection

Implements ensemble methods combining multiple ML models to achieve
<1% false positive rate while maintaining high detection accuracy.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging
import pickle
import os
import asyncio
from collections import deque

from sklearn.ensemble import IsolationForest, RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

# Deep learning imports with fallback
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch not available - Autoencoder model will be disabled")

from core.error_handling import (
    AstraGuardException, 
    safe_execute,
    ErrorContext,
    ErrorSeverity
)
from core.timeout_handler import async_timeout
from core.circuit_breaker import CircuitBreaker, register_circuit_breaker
from core.metrics import (
    THREAT_DETECTION_PREDICTIONS_TOTAL,
    THREAT_DETECTION_FALSE_POSITIVES,
    THREAT_DETECTION_LATENCY,
)

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Types of ML models in the ensemble."""
    ISOLATION_FOREST = "isolation_forest"
    RANDOM_FOREST = "random_forest"
    AUTOENCODER = "autoencoder"
    ENSEMBLE = "ensemble"


@dataclass
class ModelPrediction:
    """Prediction result from a single model."""
    model_type: ModelType
    is_anomaly: bool
    anomaly_score: float
    confidence: float
    raw_scores: Optional[Dict[str, float]] = None


@dataclass
class EnsemblePrediction:
    """Final prediction from the ensemble."""
    is_anomaly: bool
    anomaly_score: float
    confidence: float
    model_predictions: List[ModelPrediction]
    voting_weights: Dict[str, float]
    threshold_used: float
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'is_anomaly': self.is_anomaly,
            'anomaly_score': self.anomaly_score,
            'confidence': self.confidence,
            'model_predictions': [
                {
                    'model_type': p.model_type.value,
                    'is_anomaly': p.is_anomaly,
                    'anomaly_score': p.anomaly_score,
                    'confidence': p.confidence
                }
                for p in self.model_predictions
            ],
            'threshold_used': self.threshold_used,
            'timestamp': self.timestamp.isoformat()
        }


class AutoencoderModel(nn.Module):
    """Autoencoder for anomaly detection."""
    
    def __init__(self, input_dim: int, encoding_dim: int = 8):
        super(AutoencoderModel, self).__init__()
        
        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, encoding_dim)
        )
        
        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(encoding_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, input_dim)
        )
    
    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded
    
    def get_reconstruction_error(self, x):
        """Calculate reconstruction error for anomaly scoring."""
        with torch.no_grad():
            reconstructed = self.forward(x)
            error = torch.mean((x - reconstructed) ** 2, dim=1)
        return error


class ModelEnsemble:
    """
    Ensemble of ML models for threat detection.
    
    Combines Isolation Forest, Random Forest, and Autoencoder models
    with weighted voting to achieve high accuracy and low false positives.
    """
    
    # Target false positive rate: < 1%
    TARGET_FPR: float = 0.01
    # Minimum confidence threshold
    MIN_CONFIDENCE: float = 0.85
    
    def __init__(self, input_dim: int = 50, model_dir: str = "models/threat_detection"):
        self.input_dim = input_dim
        self.model_dir = model_dir
        self.models: Dict[ModelType, Any] = {}
        self.scalers: Dict[ModelType, StandardScaler] = {}
        self.weights: Dict[ModelType, float] = {
            ModelType.ISOLATION_FOREST: 0.3,
            ModelType.RANDOM_FOREST: 0.4,
            ModelType.AUTOENCODER: 0.3
        }
        
        # Adaptive thresholds for each model
        self.thresholds: Dict[ModelType, float] = {
            ModelType.ISOLATION_FOREST: 0.6,
            ModelType.RANDOM_FOREST: 0.5,
            ModelType.AUTOENCODER: 0.7
        }
        
        # Performance tracking for weight adjustment
        self.performance_history: deque = deque(maxlen=1000)
        self.false_positive_count: int = 0
        self.true_positive_count: int = 0
        self.total_predictions: int = 0
        
        # Circuit breaker for model inference
        self.inference_circuit = register_circuit_breaker(
            CircuitBreaker(
                name="ensemble_inference",
                failure_threshold=10,
                success_threshold=3,
                recovery_timeout=30,
                expected_exceptions=(Exception,)
            )
        )
        
        # Create model directory
        os.makedirs(model_dir, exist_ok=True)
        
        # Initialize autoencoder if torch available
        if TORCH_AVAILABLE:
            self.autoencoder = AutoencoderModel(input_dim)
            self.autoencoder_trained = False
        else:
            self.autoencoder = None
            self.autoencoder_trained = False
    
    async def initialize(self) -> bool:
        """Initialize all models."""
        try:
            # Initialize Isolation Forest
            self.models[ModelType.ISOLATION_FOREST] = IsolationForest(
                contamination=0.05,  # Expected anomaly rate
                n_estimators=200,
                max_samples='auto',
                random_state=42,
                n_jobs=-1
            )
            
            # Initialize Random Forest Classifier
            self.models[ModelType.RANDOM_FOREST] = RandomForestClassifier(
                n_estimators=200,
                max_depth=15,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1,
                class_weight='balanced'
            )
            
            # Initialize scalers
            for model_type in [ModelType.ISOLATION_FOREST, ModelType.RANDOM_FOREST, ModelType.AUTOENCODER]:
                self.scalers[model_type] = StandardScaler()
            
            logger.info("Model ensemble initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize model ensemble: {e}")
            return False
    
    @async_timeout(seconds=10.0, operation_name="ensemble_training")
    async def train(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Train all models in the ensemble.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Optional labels (1 for anomaly, 0 for normal)
            
        Returns:
            Training metrics
        """
        metrics = {}
        
        try:
            # Split data for validation
            if y is not None:
                X_train, X_val, y_train, y_val = train_test_split(
                    X, y, test_size=0.2, random_state=42, stratify=y
                )
            else:
                X_train, X_val = X, X
                y_train, y_val = None, None
            
            # Train Isolation Forest (unsupervised)
            await self._train_isolation_forest(X_train)
            metrics['isolation_forest'] = {'status': 'trained'}
            
            # Train Random Forest (supervised if labels available)
            if y_train is not None:
                rf_metrics = await self._train_random_forest(X_train, y_train, X_val, y_val)
                metrics['random_forest'] = rf_metrics
            else:
                metrics['random_forest'] = {'status': 'skipped_no_labels'}
            
            # Train Autoencoder (unsupervised)
            if TORCH_AVAILABLE and self.autoencoder:
                ae_metrics = await self._train_autoencoder(X_train, X_val)
                metrics['autoencoder'] = ae_metrics
            else:
                metrics['autoencoder'] = {'status': 'unavailable'}
            
            # Calibrate thresholds based on validation set
            if y_val is not None:
                await self._calibrate_thresholds(X_val, y_val)
            
            # Save models
            await self._save_models()
            
            logger.info(f"Ensemble training completed: {metrics}")
            return metrics
            
        except Exception as e:
            logger.error(f"Ensemble training failed: {e}")
            raise AstraGuardException(
                f"Model training failed: {e}",
                component="model_ensemble",
                context={"input_shape": X.shape}
            )
    
    async def _train_isolation_forest(self, X: np.ndarray):
        """Train Isolation Forest model."""
        # Fit scaler
        self.scalers[ModelType.ISOLATION_FOREST].fit(X)
        X_scaled = self.scalers[ModelType.ISOLATION_FOREST].transform(X)
        
        # Train model
        self.models[ModelType.ISOLATION_FOREST].fit(X_scaled)
        logger.info("Isolation Forest trained")
    
    async def _train_random_forest(self, X_train: np.ndarray, y_train: np.ndarray, 
                                   X_val: np.ndarray, y_val: np.ndarray) -> Dict[str, float]:
        """Train Random Forest classifier."""
        # Fit scaler
        self.scalers[ModelType.RANDOM_FOREST].fit(X_train)
        X_train_scaled = self.scalers[ModelType.RANDOM_FOREST].transform(X_train)
        X_val_scaled = self.scalers[ModelType.RANDOM_FOREST].transform(X_val)
        
        # Train model
        self.models[ModelType.RANDOM_FOREST].fit(X_train_scaled, y_train)
        
        # Validate
        y_pred = self.models[ModelType.RANDOM_FOREST].predict(X_val_scaled)
        
        metrics = {
            'precision': precision_score(y_val, y_pred, zero_division=0),
            'recall': recall_score(y_val, y_pred, zero_division=0),
            'f1': f1_score(y_val, y_pred, zero_division=0),
        }
        
        logger.info(f"Random Forest trained: {metrics}")
        return metrics
    
    async def _train_autoencoder(self, X_train: np.ndarray, X_val: np.ndarray) -> Dict[str, float]:
        """Train Autoencoder model."""
        if not TORCH_AVAILABLE or not self.autoencoder:
            return {'status': 'unavailable'}
        
        # Fit scaler
        self.scalers[ModelType.AUTOENCODER].fit(X_train)
        X_train_scaled = self.scalers[ModelType.AUTOENCODER].transform(X_train)
        X_val_scaled = self.scalers[ModelType.AUTOENCODER].transform(X_val)
        
        # Convert to tensors
        X_train_tensor = torch.FloatTensor(X_train_scaled)
        X_val_tensor = torch.FloatTensor(X_val_scaled)
        
        # Create data loader
        train_dataset = TensorDataset(X_train_tensor, X_train_tensor)
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        
        # Training setup
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.autoencoder.parameters(), lr=0.001)
        
        # Training loop
        self.autoencoder.train()
        num_epochs = 50
        
        for epoch in range(num_epochs):
            total_loss = 0
            for batch_x, _ in train_loader:
                optimizer.zero_grad()
                outputs = self.autoencoder(batch_x)
                loss = criterion(outputs, batch_x)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            
            if epoch % 10 == 0:
                logger.debug(f"Autoencoder epoch {epoch}, loss: {total_loss / len(train_loader):.4f}")
        
        # Calculate validation reconstruction error threshold
        self.autoencoder.eval()
        with torch.no_grad():
            val_reconstructed = self.autoencoder(X_val_tensor)
            val_errors = torch.mean((X_val_tensor - val_reconstructed) ** 2, dim=1).numpy()
            
            # Set threshold at 95th percentile of validation errors
            self.thresholds[ModelType.AUTOENCODER] = np.percentile(val_errors, 95)
        
        self.autoencoder_trained = True
        
        metrics = {
            'status': 'trained',
            'val_error_mean': float(np.mean(val_errors)),
            'val_error_std': float(np.std(val_errors)),
            'threshold': float(self.thresholds[ModelType.AUTOENCODER])
        }
        
        logger.info(f"Autoencoder trained: {metrics}")
        return metrics
    
    async def _calibrate_thresholds(self, X_val: np.ndarray, y_val: np.ndarray):
        """
        Calibrate thresholds to achieve target false positive rate.
        """
        # Get predictions from each model
        predictions = await self._get_all_predictions(X_val)
        
        for model_type in [ModelType.ISOLATION_FOREST, ModelType.RANDOM_FOREST]:
            if model_type not in predictions:
                continue
            
            scores = np.array([p.anomaly_score for p in predictions[model_type]])
            
            # Find threshold that achieves target FPR for normal samples
            normal_scores = scores[y_val == 0]
            if len(normal_scores) > 0:
                # Set threshold at (1 - TARGET_FPR) percentile
                new_threshold = np.percentile(normal_scores, (1 - self.TARGET_FPR) * 100)
                self.thresholds[model_type] = max(0.5, min(0.95, new_threshold))
                logger.info(f"Calibrated {model_type.value} threshold to {self.thresholds[model_type]:.3f}")
    
    async def _get_all_predictions(self, X: np.ndarray) -> Dict[ModelType, List[ModelPrediction]]:
        """Get predictions from all models."""
        predictions = {}
        
        for model_type in self.models.keys():
            preds = await self._predict_single_model(model_type, X)
            if preds:
                predictions[model_type] = preds
        
        return predictions
    
    async def _predict_single_model(self, model_type: ModelType, X: np.ndarray) -> List[ModelPrediction]:
        """Get predictions from a single model."""
        predictions = []
        
        try:
            if model_type == ModelType.ISOLATION_FOREST:
                model = self.models[model_type]
                scaler = self.scalers[model_type]
                X_scaled = scaler.transform(X)
                
                # Get anomaly scores (negative scores, higher = more anomalous)
                scores = -model.decision_function(X_scaled)
                labels = model.predict(X_scaled)
                
                for i in range(len(X)):
                    # Normalize score to [0, 1]
                    score = (scores[i] - scores.min()) / (scores.max() - scores.min() + 1e-10)
                    is_anomaly = labels[i] == -1 and score > self.thresholds[model_type]
                    
                    predictions.append(ModelPrediction(
                        model_type=model_type,
                        is_anomaly=is_anomaly,
                        anomaly_score=float(score),
                        confidence=float(score) if is_anomaly else 1.0 - float(score)
                    ))
            
            elif model_type == ModelType.RANDOM_FOREST:
                model = self.models[model_type]
                scaler = self.scalers[model_type]
                X_scaled = scaler.transform(X)
                
                # Get probability of anomaly (class 1)
                probs = model.predict_proba(X_scaled)[:, 1]
                preds = model.predict(X_scaled)
                
                for i in range(len(X)):
                    score = probs[i]
                    is_anomaly = score > self.thresholds[model_type]
                    
                    predictions.append(ModelPrediction(
                        model_type=model_type,
                        is_anomaly=is_anomaly,
                        anomaly_score=float(score),
                        confidence=float(max(score, 1.0 - score))
                    ))
            
            elif model_type == ModelType.AUTOENCODER:
                if not TORCH_AVAILABLE or not self.autoencoder_trained:
                    return []
                
                scaler = self.scalers[model_type]
                X_scaled = scaler.transform(X)
                X_tensor = torch.FloatTensor(X_scaled)
                
                self.autoencoder.eval()
                with torch.no_grad():
                    reconstructed = self.autoencoder(X_tensor)
                    errors = torch.mean((X_tensor - reconstructed) ** 2, dim=1).numpy()
                
                threshold = self.thresholds[model_type]
                
                for i in range(len(X)):
                    # Normalize error to score
                    score = min(1.0, errors[i] / (threshold * 2))
                    is_anomaly = errors[i] > threshold
                    
                    predictions.append(ModelPrediction(
                        model_type=model_type,
                        is_anomaly=is_anomaly,
                        anomaly_score=float(score),
                        confidence=float(min(1.0, errors[i] / threshold))
                    ))
        
        except Exception as e:
            logger.warning(f"Prediction failed for {model_type.value}: {e}")
        
        return predictions
    
    async def predict(self, X: np.ndarray) -> EnsemblePrediction:
        """
        Get ensemble prediction with weighted voting.
        
        Args:
            X: Feature matrix (n_samples, n_features) or single sample (n_features,)
            
        Returns:
            EnsemblePrediction with final decision and confidence
        """
        start_time = datetime.now()
        
        # Ensure 2D array
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        try:
            # Get predictions from all models through circuit breaker
            all_predictions = await self.inference_circuit.call(
                self._get_all_predictions,
                X
            )
            
            # Combine predictions with weighted voting
            final_predictions = []
            
            for i in range(len(X)):
                sample_predictions = []
                
                for model_type, preds in all_predictions.items():
                    if i < len(preds):
                        sample_predictions.append(preds[i])
                
                # Weighted voting
                weighted_score = 0.0
                total_weight = 0.0
                voting_weights = {}
                
                for pred in sample_predictions:
                    weight = self.weights.get(pred.model_type, 0.33)
                    weighted_score += pred.anomaly_score * weight
                    total_weight += weight
                    voting_weights[pred.model_type.value] = weight
                
                if total_weight > 0:
                    final_score = weighted_score / total_weight
                else:
                    final_score = 0.5
                
                # Dynamic threshold based on recent performance
                dynamic_threshold = self._calculate_dynamic_threshold()
                
                # Final decision with confidence check
                is_anomaly = final_score > dynamic_threshold and final_score > self.MIN_CONFIDENCE
                
                # Calculate confidence based on model agreement
                if sample_predictions:
                    agreement = sum(1 for p in sample_predictions if p.is_anomaly == is_anomaly) / len(sample_predictions)
                    confidence = agreement * (1.0 - abs(final_score - 0.5) * 2)  # Higher confidence near extremes
                else:
                    confidence = 0.5
                
                final_predictions.append(EnsemblePrediction(
                    is_anomaly=is_anomaly,
                    anomaly_score=float(final_score),
                    confidence=float(confidence),
                    model_predictions=sample_predictions,
                    voting_weights=voting_weights,
                    threshold_used=dynamic_threshold,
                    timestamp=datetime.now()
                ))
            
            # Track metrics
            self.total_predictions += len(X)
            THREAT_DETECTION_PREDICTIONS_TOTAL.inc()
            
            # Record latency
            latency = (datetime.now() - start_time).total_seconds()
            THREAT_DETECTION_LATENCY.observe(latency)
            
            # Return single prediction if only one sample, else return list
            if len(final_predictions) == 1:
                return final_predictions[0]
            return final_predictions[0]  # For now, return first; could return list
        
        except Exception as e:
            logger.error(f"Ensemble prediction failed: {e}")
            # Return conservative prediction (not anomaly) on failure
            return EnsemblePrediction(
                is_anomaly=False,
                anomaly_score=0.5,
                confidence=0.0,
                model_predictions=[],
                voting_weights={},
                threshold_used=0.5,
                timestamp=datetime.now()
            )
    
    def _calculate_dynamic_threshold(self) -> float:
        """Calculate dynamic threshold based on recent false positive rate."""
        if self.total_predictions == 0:
            return 0.6  # Default threshold
        
        current_fpr = self.false_positive_count / max(1, self.total_predictions)
        
        # Adjust threshold if FPR is too high
        if current_fpr > self.TARGET_FPR:
            # Increase threshold to reduce false positives
            return min(0.9, 0.6 + (current_fpr - self.TARGET_FPR))
        
        return 0.6
    
    def update_performance(self, predicted_anomaly: bool, actual_anomaly: bool):
        """
        Update performance tracking for adaptive learning.
        
        Args:
            predicted_anomaly: Whether anomaly was predicted
            actual_anomaly: Whether it was actually an anomaly
        """
        self.performance_history.append({
            'predicted': predicted_anomaly,
            'actual': actual_anomaly,
            'timestamp': datetime.now()
        })
        
        if predicted_anomaly and not actual_anomaly:
            self.false_positive_count += 1
            THREAT_DETECTION_FALSE_POSITIVES.inc()
        elif predicted_anomaly and actual_anomaly:
            self.true_positive_count += 1
        
        # Adjust weights periodically
        if len(self.performance_history) % 100 == 0:
            self._adjust_weights()
    
    def _adjust_weights(self):
        """Adjust model weights based on recent performance."""
        if len(self.performance_history) < 50:
            return
        
        recent = list(self.performance_history)[-100:]
        
        # Calculate accuracy for each model type (simplified)
        # In practice, you'd track per-model performance separately
        
        # If false positive rate is high, increase weight of conservative models
        fp_rate = sum(1 for r in recent if r['predicted'] and not r['actual']) / len(recent)
        
        if fp_rate > self.TARGET_FPR:
            # Increase weight for Random Forest (typically more conservative)
            self.weights[ModelType.RANDOM_FOREST] = min(0.6, self.weights[ModelType.RANDOM_FOREST] + 0.05)
            self.weights[ModelType.ISOLATION_FOREST] = max(0.2, self.weights[ModelType.ISOLATION_FOREST] - 0.025)
            self.weights[ModelType.AUTOENCODER] = max(0.2, self.weights[ModelType.AUTOENCODER] - 0.025)
            
            logger.info(f"Adjusted weights due to high FPR ({fp_rate:.3f}): {self.weights}")
    
    async def _save_models(self):
        """Save all models to disk."""
        try:
            for model_type, model in self.models.items():
                path = os.path.join(self.model_dir, f"{model_type.value}.pkl")
                with open(path, 'wb') as f:
                    pickle.dump(model, f)
            
            # Save scalers
            for model_type, scaler in self.scalers.items():
                path = os.path.join(self.model_dir, f"{model_type.value}_scaler.pkl")
                with open(path, 'wb') as f:
                    pickle.dump(scaler, f)
            
            # Save autoencoder if available
            if TORCH_AVAILABLE and self.autoencoder and self.autoencoder_trained:
                path = os.path.join(self.model_dir, "autoencoder.pt")
                torch.save(self.autoencoder.state_dict(), path)
            
            # Save thresholds and weights
            config = {
                'thresholds': {k.value: v for k, v in self.thresholds.items()},
                'weights': {k.value: v for k, v in self.weights.items()}
            }
            config_path = os.path.join(self.model_dir, "ensemble_config.pkl")
            with open(config_path, 'wb') as f:
                pickle.dump(config, f)
            
            logger.info("Models saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save models: {e}")
    
    async def load_models(self) -> bool:
        """Load all models from disk."""
        try:
            # Load ML models
            for model_type in [ModelType.ISOLATION_FOREST, ModelType.RANDOM_FOREST]:
                path = os.path.join(self.model_dir, f"{model_type.value}.pkl")
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        self.models[model_type] = pickle.load(f)
            
            # Load scalers
            for model_type in [ModelType.ISOLATION_FOREST, ModelType.RANDOM_FOREST, ModelType.AUTOENCODER]:
                path = os.path.join(self.model_dir, f"{model_type.value}_scaler.pkl")
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        self.scalers[model_type] = pickle.load(f)
            
            # Load autoencoder
            if TORCH_AVAILABLE and self.autoencoder:
                path = os.path.join(self.model_dir, "autoencoder.pt")
                if os.path.exists(path):
                    self.autoencoder.load_state_dict(torch.load(path))
                    self.autoencoder_trained = True
            
            # Load config
            config_path = os.path.join(self.model_dir, "ensemble_config.pkl")
            if os.path.exists(config_path):
                with open(config_path, 'rb') as f:
                    config = pickle.load(f)
                    self.thresholds = {ModelType(k): v for k, v in config['thresholds'].items()}
                    self.weights = {ModelType(k): v for k, v in config['weights'].items()}
            
            logger.info("Models loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            return False
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        if self.total_predictions == 0:
            return {'status': 'no_predictions_yet'}
        
        recent = list(self.performance_history)
        
        return {
            'total_predictions': self.total_predictions,
            'false_positives': self.false_positive_count,
            'true_positives': self.true_positive_count,
            'false_positive_rate': self.false_positive_count / self.total_predictions,
            'current_thresholds': {k.value: v for k, v in self.thresholds.items()},
            'current_weights': {k.value: v for k, v in self.weights.items()},
            'recent_history_size': len(recent)
        }


# Global instance
_ensemble: Optional[ModelEnsemble] = None


async def get_model_ensemble(input_dim: int = 50) -> ModelEnsemble:
    """Get or create global model ensemble instance."""
    global _ensemble
    if _ensemble is None:
        _ensemble = ModelEnsemble(input_dim=input_dim)
        await _ensemble.initialize()
    return _ensemble
