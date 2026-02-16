from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from datetime import datetime

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
