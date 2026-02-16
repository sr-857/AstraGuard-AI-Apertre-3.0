"""
Time-Series Database Optimization Layer for AstraGuard.

This module provides optimized storage and querying for time-series data
with the following features:
- 10x compression ratio via Gorilla compression and delta encoding
- <100ms query latency via indexing and pre-aggregation
- Automatic downsampling based on data age
- Configurable retention policies
- Hot/warm/cold data tiering
- Background aggregation pre-computation

Example:
    from src.timeseries import TimeSeriesStorage
    
    # Initialize storage
    storage = TimeSeriesStorage(base_path="data/timeseries")
    
    # Write data point
    storage.write(
        metric_name="latency",
        timestamp=datetime.now(),
        value=45.2,
        tags={"satellite": "SAT1", "type": "fault_detection"}
    )
    
    # Query data
    results = storage.query(
        metric_name="latency",
        start_time=datetime.now() - timedelta(hours=1),
        end_time=datetime.now()
    )
"""

from .storage_engine import TimeSeriesStorage, TimeSeriesChunk
from .compression import TimeSeriesCompressor, CompressionStats
from .downsampling import DownsamplingManager, DownsamplingPolicy
from .query_engine import QueryEngine, QueryResult
from .tiering import TieredStorageManager, StorageTier

from .aggregation import AggregationManager, AggregationView

__version__ = "1.0.0"
__all__ = [
    "TimeSeriesStorage",
    "TimeSeriesChunk",
    "TimeSeriesCompressor",
    "CompressionStats",
    "DownsamplingManager",
    "DownsamplingPolicy",
    "QueryEngine",
    "QueryResult",
    "TieredStorageManager",

    "StorageTier",
    "AggregationManager",
    "AggregationView",
]
