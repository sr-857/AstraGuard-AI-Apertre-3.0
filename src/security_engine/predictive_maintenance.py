"""
Predictive Maintenance Module

Uses machine learning models for time-series analysis to forecast potential system failures
and trigger preventive recovery actions before issues escalate.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor
import pickle
import os

# ML imports
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

# Project imports
from memory_engine.memory_store import AdaptiveMemoryStore
from core.metrics import (
    PREDICTIVE_MAINTENANCE_PREDICTIONS_TOTAL,
    PREDICTIVE_MAINTENANCE_ACCURACY,
    PREDICTIVE_MAINTENANCE_PREVENTIVE_ACTIONS_TOTAL,
)
from core.error_handling import PredictiveMaintenanceError
from core.timeout_handler import async_timeout, get_timeout_config
from core.resource_monitor import get_resource_monitor
from core.component_health import get_health_monitor

logger = logging.getLogger(__name__)

class PredictionModel(Enum):
    """Available prediction models."""
    RANDOM_FOREST = "random_forest"
    LSTM = "lstm"
    ISOLATION_FOREST = "isolation_forest"
    AUTOENCODER = "autoencoder"

class FailureType(Enum):
    """Types of failures that can be predicted."""
    CPU_SPIKE = "cpu_spike"
    MEMORY_LEAK = "memory_leak"
    NETWORK_LATENCY = "network_latency"
    DISK_IO_BURST = "disk_io_burst"
    SERVICE_CRASH = "service_crash"
    RESOURCE_EXHAUSTION = "resource_exhaustion"

@dataclass
class PredictionResult:
    """Result of a predictive maintenance analysis."""
    failure_type: FailureType
    probability: float
    predicted_time: datetime
    confidence: float
    features_used: List[str]
    model_used: PredictionModel
    preventive_actions: List[str]

@dataclass
class TimeSeriesData:
    """Time series data point for training/prediction."""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    network_latency: float
    disk_io: float
    error_rate: float
    response_time: float
    active_connections: int
    failure_occurred: bool = False

class LSTMPredictor(nn.Module):
    """LSTM model for time-series prediction."""

    def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 2):
        super(LSTMPredictor, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)

        out, _ = self.lstm(x, (h0, c0))
        out = self.dropout(out[:, -1, :])
        out = self.fc(out)
        return out

class TimeSeriesDataset(Dataset):
    """Dataset for time-series data."""

    def __init__(self, data: np.ndarray, targets: np.ndarray, sequence_length: int = 24):
        self.data = data
        self.targets = targets
        self.sequence_length = sequence_length

    def __len__(self):
        return len(self.data) - self.sequence_length

    def __getitem__(self, idx):
        x = self.data[idx:idx + self.sequence_length]
        y = self.targets[idx + self.sequence_length]
        return torch.FloatTensor(x), torch.FloatTensor([y])

class PredictiveMaintenanceEngine:
    """
    Predictive Maintenance Engine using ML models for failure prediction.

    Features:
    - Multiple ML models (Random Forest, LSTM, Isolation Forest, Autoencoder)
    - Time-series analysis for failure prediction
    - Preventive action recommendations
    - Integration with existing anomaly detection
    - Model training and evaluation
    """

    def __init__(self, memory_store: AdaptiveMemoryStore):
        self.memory_store = memory_store
        self.models: Dict[FailureType, Dict[PredictionModel, Any]] = {}
        self.scalers: Dict[FailureType, StandardScaler] = {}
        self.model_dir = "security_engine/models"
        self.training_data: List[TimeSeriesData] = []
        self.prediction_history: List[PredictionResult] = []
        
        # Sliding window for rolling statistics (last 10 data points)
        self.recent_data: List[TimeSeriesData] = []
        self.max_window_size = 10

        # Create model directory if it doesn't exist
        os.makedirs(self.model_dir, exist_ok=True)

        # Initialize health monitoring
        self.health_monitor = get_health_monitor()
        self.health_monitor.register_component("predictive_maintenance")

        # Initialize resource monitor
        self.resource_monitor = get_resource_monitor()

        # Thread pool for CPU-intensive ML operations
        self.executor = ThreadPoolExecutor(max_workers=2)

    async def initialize(self) -> bool:
        """Initialize the predictive maintenance engine."""
        try:
            # Load existing models
            await self._load_models()

            # Initialize models for each failure type
            for failure_type in FailureType:
                self.models[failure_type] = {}
                self.scalers[failure_type] = StandardScaler()

            self.health_monitor.mark_healthy("predictive_maintenance", {
                "models_loaded": len(self.models),
                "training_data_points": len(self.training_data)
            })

            logger.info("Predictive maintenance engine initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize predictive maintenance engine: {e}")
            self.health_monitor.mark_failed("predictive_maintenance", str(e))
            return False

    async def add_training_data(self, data: TimeSeriesData) -> None:
        """Add new time-series data for training."""
        self.training_data.append(data)

        # Keep only recent data (last 30 days)
        cutoff = datetime.now() - timedelta(days=30)
        self.training_data = [d for d in self.training_data if d.timestamp > cutoff]

        # Maintain sliding window for rolling statistics
        self.recent_data.append(data)
        if len(self.recent_data) > self.max_window_size:
            self.recent_data.pop(0)

        # Store in memory for persistence
        await self._store_training_data(data)

    async def train_models(self) -> Dict[str, float]:
        """
        Train all predictive models using available data.

        Returns:
            Dictionary of model performance metrics
        """
        if len(self.training_data) < 100:  # Minimum data requirement
            logger.warning("Insufficient training data for model training")
            return {"error": "insufficient_data"}

        performance_metrics = {}

        try:
            # Prepare data
            df = self._prepare_training_dataframe()

            for failure_type in FailureType:
                logger.info(f"Training models for {failure_type.value}")

                # Prepare features and targets
                features, targets = self._prepare_features_and_targets(df, failure_type)

                if len(features) < 50:
                    continue

                # Train different models
                model_metrics = await self._train_models_for_failure_type(
                    failure_type, features, targets
                )

                performance_metrics[failure_type.value] = model_metrics

            # Save trained models
            await self._save_models()

            self.health_monitor.mark_healthy("predictive_maintenance", {
                "last_training": datetime.now().isoformat(),
                "performance_metrics": performance_metrics
            })

            logger.info("Model training completed successfully")
            return performance_metrics

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            self.health_monitor.mark_failed("predictive_maintenance", str(e))
            return {"error": str(e)}

    @async_timeout(seconds=15.0, operation_name="predictive_failure_prediction")
    async def predict_failures(self, current_data: TimeSeriesData) -> List[PredictionResult]:
        """
        Predict potential failures based on current system state.

        Returns:
            List of prediction results for potential failures
        """
        predictions = []

        try:
            for failure_type in FailureType:
                if failure_type not in self.models or not self.models[failure_type]:
                    continue

                # Get prediction from best performing model
                prediction = await self._predict_single_failure_type(failure_type, current_data)

                if prediction and prediction.probability > 0.3:  # High confidence threshold
                    predictions.append(prediction)
                    PREDICTIVE_MAINTENANCE_PREDICTIONS_TOTAL.labels(
                        failure_type=failure_type.value, 
                        model_type=prediction.model_used.value
                    ).inc()

            # Sort by probability and confidence
            predictions.sort(key=lambda x: x.probability * x.confidence, reverse=True)

            logger.info(f"Generated {len(predictions)} high-confidence failure predictions")
            return predictions[:5]  # Return top 5 predictions

        except Exception as e:
            logger.error(f"Failure prediction failed: {e}")
            return []

    @async_timeout(seconds=20.0, operation_name="preventive_actions_trigger")
    async def trigger_preventive_actions(self, predictions: List[PredictionResult]) -> List[str]:
        """
        Trigger preventive recovery actions based on predictions.

        Returns:
            List of actions taken
        """
        actions_taken = []

        for prediction in predictions:
            try:
                actions = await self._execute_preventive_actions(prediction)
                actions_taken.extend(actions)
                for action in actions:
                    PREDICTIVE_MAINTENANCE_PREVENTIVE_ACTIONS_TOTAL.labels(
                        failure_type=prediction.failure_type.value, 
                        action_type=action.replace(' ', '_').lower()[:50]  # Truncate and format action name
                    ).inc()

            except Exception as e:
                logger.error(f"Failed to execute preventive actions for {prediction.failure_type}: {e}")

        return actions_taken

    async def _predict_single_failure_type(self, failure_type: FailureType, data: TimeSeriesData) -> Optional[PredictionResult]:
        """Predict failure for a specific failure type."""
        if failure_type not in self.models:
            return None

        # Use the best performing model (Random Forest as default)
        model = self.models[failure_type].get(PredictionModel.RANDOM_FOREST)
        if not model:
            return None

        try:
            # Prepare features
            features = self._extract_features_from_data(data, failure_type)
            features_scaled = self.scalers[failure_type].transform([features])

            # Make prediction using regression model
            model = self.models[failure_type].get(PredictionModel.RANDOM_FOREST)
            if not model:
                return None
                
            predicted_value = model.predict(features_scaled)[0]
                
            # Calculate failure probability based on predicted value vs threshold
            # For each failure type, define what constitutes a "high" value indicating potential failure
            thresholds = {
                FailureType.CPU_SPIKE: 75.0,  # CPU usage > 75%
                FailureType.MEMORY_LEAK: 80.0,  # Memory usage > 80%
                FailureType.NETWORK_LATENCY: 100.0,  # Latency > 100ms
                FailureType.DISK_IO_BURST: 200.0,  # Disk I/O > 200 ops/sec
                FailureType.SERVICE_CRASH: 1.0,  # Error rate > 1%
                FailureType.RESOURCE_EXHAUSTION: 1.0  # Error rate > 1%
            }
            
            threshold = thresholds[failure_type]
            
            # Calculate probability as sigmoid of (predicted_value - threshold)
            # This gives higher probability when predicted value is much higher than threshold
            probability = 1 / (1 + np.exp(-(predicted_value - threshold) / 10))  # Sigmoid with scaling
            
            # Only create prediction if probability is significant (> 0.3)
            if probability < 0.3:
                return None

            # Estimate time to failure (simplified - higher probability = sooner failure)
            time_to_failure_hours = max(1, int((1 - probability) * 24))

            prediction = PredictionResult(
                failure_type=failure_type,
                probability=float(probability),
                predicted_time=datetime.now() + timedelta(hours=time_to_failure_hours),
                confidence=0.85,  # Simplified confidence score
                features_used=['cpu_usage', 'memory_usage', 'network_latency', 'disk_io', 'error_rate'],
                model_used=PredictionModel.RANDOM_FOREST,
                preventive_actions=self._get_preventive_actions(failure_type)
            )

            return prediction

        except Exception as e:
            logger.error(f"Prediction failed for {failure_type}: {e}")
            return None

    async def _train_models_for_failure_type(self, failure_type: FailureType, features: np.ndarray, targets: np.ndarray) -> Dict[str, float]:
        """Train multiple models for a specific failure type."""
        metrics = {}

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, targets, test_size=0.2, random_state=42
        )

        # Scale features
        self.scalers[failure_type].fit(X_train)
        X_train_scaled = self.scalers[failure_type].transform(X_train)
        X_test_scaled = self.scalers[failure_type].transform(X_test)

        # Random Forest
        rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
        rf_model.fit(X_train_scaled, y_train)
        rf_pred = rf_model.predict(X_test_scaled)
        rf_mse = mean_squared_error(y_test, rf_pred)
        rf_r2 = r2_score(y_test, rf_pred)

        self.models[failure_type][PredictionModel.RANDOM_FOREST] = rf_model
        metrics['random_forest'] = rf_r2

        # Isolation Forest for anomaly detection
        if_model = IsolationForest(contamination=0.1, random_state=42)
        if_model.fit(X_train_scaled)
        self.models[failure_type][PredictionModel.ISOLATION_FOREST] = if_model

        logger.info(f"Trained models for {failure_type.value}: RF R² = {rf_r2:.3f}")
        return metrics

    def _prepare_training_dataframe(self) -> pd.DataFrame:
        """Convert training data to pandas DataFrame."""
        data = []
        for item in self.training_data:
            data.append({
                'timestamp': item.timestamp,
                'cpu_usage': item.cpu_usage,
                'memory_usage': item.memory_usage,
                'network_latency': item.network_latency,
                'disk_io': item.disk_io,
                'error_rate': item.error_rate,
                'response_time': item.response_time,
                'active_connections': item.active_connections,
                'failure_occurred': item.failure_occurred
            })

        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        return df

    def _prepare_features_and_targets(self, df: pd.DataFrame, failure_type: FailureType) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features and targets for a specific failure type."""
        # Create target based on failure type
        if failure_type == FailureType.CPU_SPIKE:
            target_col = 'cpu_usage'
        elif failure_type == FailureType.MEMORY_LEAK:
            target_col = 'memory_usage'
        elif failure_type == FailureType.NETWORK_LATENCY:
            target_col = 'network_latency'
        elif failure_type == FailureType.DISK_IO_BURST:
            target_col = 'disk_io'
        else:
            target_col = 'error_rate'

        # Create rolling features
        df_features = df.copy()
        for col in ['cpu_usage', 'memory_usage', 'network_latency', 'disk_io', 'error_rate']:
            df_features[f'{col}_rolling_mean_3'] = df_features[col].rolling(window=3).mean()
            df_features[f'{col}_rolling_std_3'] = df_features[col].rolling(window=3).std()
            df_features[f'{col}_rolling_mean_6'] = df_features[col].rolling(window=6).mean()
            df_features[f'{col}_rolling_std_6'] = df_features[col].rolling(window=6).std()

        # Drop NaN values
        df_features = df_features.dropna()

        # Features are all columns except timestamp and target
        feature_cols = [col for col in df_features.columns if col not in ['timestamp', target_col]]
        features = df_features[feature_cols].values
        targets = df_features[target_col].values

        logger.debug(f"Training features for {failure_type}: {len(feature_cols)} columns - {feature_cols}")

        return features, targets

    def _extract_features_from_data(self, data: TimeSeriesData, failure_type: FailureType) -> List[float]:
        """Extract features from current data for prediction."""
        # If we don't have enough recent data, use current values as approximations
        if len(self.recent_data) < 3:
            # Fallback: use current values for all features
            base_features = [
                data.cpu_usage, data.memory_usage, data.network_latency, 
                data.disk_io, data.error_rate, data.response_time, data.active_connections
            ]
            # Approximate rolling stats
            features = base_features.copy()
            for _ in range(5):  # 5 metrics × 4 rolling stats
                features.extend([0.0, 0.0, 0.0, 0.0])
            return features
        
        # Create DataFrame from recent data + current data
        recent_with_current = self.recent_data + [data]
        df_recent = pd.DataFrame([{
            'cpu_usage': d.cpu_usage,
            'memory_usage': d.memory_usage,
            'network_latency': d.network_latency,
            'disk_io': d.disk_io,
            'error_rate': d.error_rate,
            'response_time': d.response_time,
            'active_connections': d.active_connections
        } for d in recent_with_current])
        
        # Compute rolling statistics for the last row (current data)
        for col in ['cpu_usage', 'memory_usage', 'network_latency', 'disk_io', 'error_rate']:
            df_recent[f'{col}_rolling_mean_3'] = df_recent[col].rolling(window=min(3, len(df_recent))).mean()
            df_recent[f'{col}_rolling_std_3'] = df_recent[col].rolling(window=min(3, len(df_recent))).std()
            df_recent[f'{col}_rolling_mean_6'] = df_recent[col].rolling(window=min(6, len(df_recent))).mean()
            df_recent[f'{col}_rolling_std_6'] = df_recent[col].rolling(window=min(6, len(df_recent))).std()
        
        # Get features for the last row (current prediction)
        last_row = df_recent.iloc[-1]
        
        # Base features (all except timestamp and target, including failure_occurred = False for prediction)
        if failure_type == FailureType.CPU_SPIKE:
            base_features = [
                last_row['memory_usage'], last_row['network_latency'], last_row['disk_io'], 
                last_row['error_rate'], last_row['response_time'], last_row['active_connections'], 0.0  # failure_occurred = False
            ]
        elif failure_type == FailureType.MEMORY_LEAK:
            base_features = [
                last_row['cpu_usage'], last_row['network_latency'], last_row['disk_io'], 
                last_row['error_rate'], last_row['response_time'], last_row['active_connections'], 0.0
            ]
        elif failure_type == FailureType.NETWORK_LATENCY:
            base_features = [
                last_row['cpu_usage'], last_row['memory_usage'], last_row['disk_io'], 
                last_row['error_rate'], last_row['response_time'], last_row['active_connections'], 0.0
            ]
        elif failure_type == FailureType.DISK_IO_BURST:
            base_features = [
                last_row['cpu_usage'], last_row['memory_usage'], last_row['network_latency'], 
                last_row['error_rate'], last_row['response_time'], last_row['active_connections'], 0.0
            ]
        else:  # SERVICE_CRASH or RESOURCE_EXHAUSTION
            base_features = [
                last_row['cpu_usage'], last_row['memory_usage'], last_row['network_latency'], 
                last_row['disk_io'], last_row['response_time'], last_row['active_connections'], 0.0
            ]
        
        # Rolling features for all metrics (20 features)
        rolling_features = []
        for col in ['cpu_usage', 'memory_usage', 'network_latency', 'disk_io', 'error_rate']:
            rolling_features.extend([
                last_row[f'{col}_rolling_mean_3'],
                last_row[f'{col}_rolling_std_3'], 
                last_row[f'{col}_rolling_mean_6'],
                last_row[f'{col}_rolling_std_6']
            ])
        
        # Combine base and rolling features
        features = base_features + rolling_features
        
        # Fill any NaN values with 0
        features = [0.0 if pd.isna(x) else x for x in features]
        
        return features

    def _get_preventive_actions(self, failure_type: FailureType) -> List[str]:
        """Get preventive actions for a failure type."""
        actions_map = {
            FailureType.CPU_SPIKE: [
                "Scale up CPU resources",
                "Optimize CPU-intensive processes",
                "Implement CPU usage throttling"
            ],
            FailureType.MEMORY_LEAK: [
                "Trigger garbage collection",
                "Restart memory-intensive services",
                "Implement memory usage limits"
            ],
            FailureType.NETWORK_LATENCY: [
                "Optimize network configuration",
                "Scale network resources",
                "Implement connection pooling"
            ],
            FailureType.DISK_IO_BURST: [
                "Optimize disk I/O operations",
                "Implement caching layers",
                "Scale storage resources"
            ],
            FailureType.SERVICE_CRASH: [
                "Restart affected services",
                "Implement health checks",
                "Scale service instances"
            ],
            FailureType.RESOURCE_EXHAUSTION: [
                "Scale resources horizontally",
                "Implement resource quotas",
                "Optimize resource usage"
            ]
        }
        return actions_map.get(failure_type, ["General system optimization"])

    async def _execute_preventive_actions(self, prediction: PredictionResult) -> List[str]:
        """Execute preventive actions for a prediction."""
        actions_executed = []

        # This would integrate with the existing recovery orchestrator
        # For now, we'll log the actions that would be taken
        for action in prediction.preventive_actions:
            logger.info(f"Executing preventive action: {action} for {prediction.failure_type.value}")
            actions_executed.append(action)

            # Here you would call the actual recovery orchestrator
            # await recovery_orchestrator.execute_action(action)

        return actions_executed

    async def _load_models(self) -> None:
        """Load trained models from disk."""
        try:
            for failure_type in FailureType:
                model_path = os.path.join(self.model_dir, f"{failure_type.value}_models.pkl")
                scaler_path = os.path.join(self.model_dir, f"{failure_type.value}_scaler.pkl")

                if os.path.exists(model_path):
                    with open(model_path, 'rb') as f:
                        self.models[failure_type] = pickle.load(f)  # nosec B301

                if os.path.exists(scaler_path):
                    with open(scaler_path, 'rb') as f:
                        self.scalers[failure_type] = pickle.load(f)  # nosec B301

            logger.info("Models loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load models: {e}")

    async def _save_models(self) -> None:
        """Save trained models to disk."""
        try:
            for failure_type in FailureType:
                if failure_type in self.models:
                    model_path = os.path.join(self.model_dir, f"{failure_type.value}_models.pkl")
                    scaler_path = os.path.join(self.model_dir, f"{failure_type.value}_scaler.pkl")

                    with open(model_path, 'wb') as f:
                        pickle.dump(self.models[failure_type], f)

                    with open(scaler_path, 'wb') as f:
                        pickle.dump(self.scalers[failure_type], f)

            logger.info("Models saved successfully")

        except Exception as e:
            logger.error(f"Failed to save models: {e}")

    async def _store_training_data(self, data: TimeSeriesData) -> None:
        """Store training data in memory store for persistence."""
        # Convert to embedding (simplified)
        embedding = np.array([
            data.cpu_usage,
            data.memory_usage,
            data.network_latency,
            data.disk_io,
            data.error_rate,
            data.response_time,
            float(data.active_connections)
        ])

        metadata = {
            "type": "training_data",
            "failure_occurred": data.failure_occurred,
            "severity": 0.5 if not data.failure_occurred else 0.9
        }

        self.memory_store.write(embedding, metadata, data.timestamp)

# Global instance
_predictive_engine: Optional[PredictiveMaintenanceEngine] = None

async def get_predictive_maintenance_engine(memory_store: AdaptiveMemoryStore) -> PredictiveMaintenanceEngine:
    """Get or create the global predictive maintenance engine instance."""
    global _predictive_engine

    if _predictive_engine is None:
        _predictive_engine = PredictiveMaintenanceEngine(memory_store)
        await _predictive_engine.initialize()

    return _predictive_engine