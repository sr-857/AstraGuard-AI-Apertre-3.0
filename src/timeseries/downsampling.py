"""
Downsampling Module for Time-Series Data

Implements automatic downsampling strategies based on data age:
- Raw data: 0-7 days (full resolution)
- 1-minute aggregates: 7-30 days
- 1-hour aggregates: 30-90 days
- 1-day aggregates: 90+ days

This reduces storage costs while maintaining query performance for historical data.
"""

import logging
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import heapq

from .storage_engine import TimeSeriesStorage, DataPoint, ChunkMetadata

logger = logging.getLogger(__name__)


class AggregationType(str, Enum):
    """Types of aggregation functions."""
    MEAN = "mean"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    COUNT = "count"
    P95 = "p95"
    P99 = "p99"
    FIRST = "first"
    LAST = "last"


@dataclass
class DownsamplingPolicy:
    """
    Policy for downsampling data based on age.
    
    Defines retention periods and aggregation intervals.
    """
    name: str
    raw_retention_days: int = 7
    minute_aggregation_days: int = 30
    hour_aggregation_days: int = 90
    day_aggregation_days: int = 365
    aggregations: List[AggregationType] = None
    
    def __post_init__(self):
        if self.aggregations is None:
            self.aggregations = [
                AggregationType.MEAN,
                AggregationType.MIN,
                AggregationType.MAX,
                AggregationType.P95,
                AggregationType.COUNT
            ]
    
    def get_target_resolution(self, data_age_days: int) -> Optional[timedelta]:
        """
        Get target time resolution based on data age.
        
        Returns:
            Time delta for aggregation, or None if data should be deleted
        """
        if data_age_days <= self.raw_retention_days:
            return None  # Keep raw data
        
        if data_age_days <= self.minute_aggregation_days:
            return timedelta(minutes=1)
        
        if data_age_days <= self.hour_aggregation_days:
            return timedelta(hours=1)
        
        if data_age_days <= self.day_aggregation_days:
            return timedelta(days=1)
        
        return None  # Data should be deleted
    
    def should_downsample(self, data_age_days: int, current_resolution: timedelta) -> bool:
        """
        Check if data should be downsampled.
        
        Args:
            data_age_days: Age of data in days
            current_resolution: Current time resolution of data
            
        Returns:
            True if downsampling is needed
        """
        target = self.get_target_resolution(data_age_days)
        if target is None:
            return False  # Keep as-is or delete
        
        return current_resolution < target


class AggregationFunction:
    """Aggregation functions for downsampling."""
    
    @staticmethod
    def mean(values: List[float]) -> float:
        """Calculate mean."""
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    @staticmethod
    def min(values: List[float]) -> float:
        """Calculate minimum."""
        if not values:
            return 0.0
        return min(values)
    
    @staticmethod
    def max(values: List[float]) -> float:
        """Calculate maximum."""
        if not values:
            return 0.0
        return max(values)
    
    @staticmethod
    def sum(values: List[float]) -> float:
        """Calculate sum."""
        return sum(values)
    
    @staticmethod
    def count(values: List[float]) -> int:
        """Calculate count."""
        return len(values)
    
    @staticmethod
    def p95(values: List[float]) -> float:
        """Calculate 95th percentile."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * 0.95)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]
    
    @staticmethod
    def p99(values: List[float]) -> float:
        """Calculate 99th percentile."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * 0.99)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]
    
    @staticmethod
    def first(values: List[float]) -> float:
        """Get first value."""
        return values[0] if values else 0.0
    
    @staticmethod
    def last(values: List[float]) -> float:
        """Get last value."""
        return values[-1] if values else 0.0
    
    @classmethod
    def get_function(cls, agg_type: AggregationType) -> Callable[[List[float]], Any]:
        """Get aggregation function by type."""
        functions = {
            AggregationType.MEAN: cls.mean,
            AggregationType.MIN: cls.min,
            AggregationType.MAX: cls.max,
            AggregationType.SUM: cls.sum,
            AggregationType.COUNT: cls.count,
            AggregationType.P95: cls.p95,
            AggregationType.P99: cls.p99,
            AggregationType.FIRST: cls.first,
            AggregationType.LAST: cls.last,
        }
        return functions.get(agg_type, cls.mean)


class DownsamplingManager:
    """
    Manages automatic downsampling of time-series data.
    
    Runs background jobs to downsample data based on age and policies.
    """
    
    def __init__(
        self,
        storage: TimeSeriesStorage,
        policy: Optional[DownsamplingPolicy] = None
    ):
        """
        Initialize downsampling manager.
        
        Args:
            storage: TimeSeriesStorage instance
            policy: Downsampling policy (uses default if None)
        """
        self.storage = storage
        self.policy = policy or DownsamplingPolicy("default")
        self._lock = threading.RLock()
        self._downsampled_chunks: Dict[str, List[ChunkMetadata]] = defaultdict(list)
        self._stats = {
            "chunks_downsampled": 0,
            "points_reduced": 0,
            "bytes_saved": 0
        }
        
        logger.info(f"DownsamplingManager initialized with policy: {self.policy.name}")
    
    def downsample_chunk(
        self,
        metric_name: str,
        chunk_meta: ChunkMetadata,
        target_resolution: timedelta
    ) -> Optional[ChunkMetadata]:
        """
        Downsample a single chunk to target resolution.
        
        Args:
            metric_name: Name of the metric
            chunk_meta: Chunk metadata
            target_resolution: Target time resolution
            
        Returns:
            New chunk metadata if downsampling succeeded, None otherwise
        """
        try:
            # Load original data
            from .storage_engine import TimeSeriesChunk
            
            chunk = TimeSeriesChunk(
                metric_name,
                chunk_meta.start_time,
                self.storage.base_path
            )
            chunk._metadata = chunk_meta
            points = chunk.load()
            
            if not points:
                logger.warning(f"No points to downsample in chunk {chunk_meta.file_path}")
                return None
            
            # Group points by time buckets
            buckets: Dict[datetime, List[DataPoint]] = defaultdict(list)
            
            for point in points:
                # Round to target resolution
                if target_resolution >= timedelta(days=1):
                    bucket_time = point.timestamp.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                elif target_resolution >= timedelta(hours=1):
                    bucket_time = point.timestamp.replace(
                        minute=0, second=0, microsecond=0
                    )
                elif target_resolution >= timedelta(minutes=1):
                    bucket_time = point.timestamp.replace(
                        second=0, microsecond=0
                    )
                else:
                    bucket_time = point.timestamp
                
                buckets[bucket_time].append(point)
            
            # Aggregate each bucket
            downsampled_points = []
            for bucket_time, bucket_points in sorted(buckets.items()):
                values = [p.value for p in bucket_points]
                
                # Calculate aggregations
                aggregated_tags = {
                    "_downsampled": "true",
                    "_original_count": str(len(bucket_points)),
                    "_resolution": str(target_resolution)
                }
                
                # Add first tag set as representative
                if bucket_points:
                    aggregated_tags.update(bucket_points[0].tags)
                
                # Use mean as the primary value
                mean_value = AggregationFunction.mean(values)
                
                downsampled_points.append(DataPoint(
                    timestamp=bucket_time,
                    value=mean_value,
                    tags=aggregated_tags
                ))
            
            # Create new chunk with downsampled data
            new_chunk = TimeSeriesChunk(
                f"{metric_name}_downsampled",
                chunk_meta.start_time,
                self.storage.base_path / "downsampled"
            )
            
            for point in downsampled_points:
                new_chunk.add_point(point)
            
            # Finalize new chunk
            new_meta = new_chunk.finalize()
            
            # Update stats
            with self._lock:
                self._stats["chunks_downsampled"] += 1
                self._stats["points_reduced"] += (len(points) - len(downsampled_points))
                self._stats["bytes_saved"] += (
                    chunk_meta.compressed_size - new_meta.compressed_size
                )
                self._downsampled_chunks[metric_name].append(new_meta)
            
            logger.info(
                f"Downsampled chunk {metric_name}: "
                f"{len(points)} -> {len(downsampled_points)} points "
                f"({len(downsampled_points) / len(points) * 100:.1f}%)"
            )
            
            return new_meta
            
        except Exception as e:
            logger.error(f"Failed to downsample chunk {chunk_meta.file_path}: {e}")
            return None
    
    def process_metric(self, metric_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Process all chunks for a metric and downsample as needed.
        
        Args:
            metric_name: Name of the metric to process
            dry_run: If True, only report what would be done
            
        Returns:
            Statistics about processing
        """
        now = datetime.now()
        stats = {
            "metric": metric_name,
            "chunks_processed": 0,
            "chunks_downsampled": 0,
            "chunks_deleted": 0,
            "errors": 0
        }
        
        # Get all chunks for metric
        time_range = self.storage._index.get_time_range(metric_name)
        if not time_range:
            return stats
        
        chunks = self.storage._index.find_chunks(
            metric_name,
            time_range[0],
            time_range[1]
        )
        
        for chunk_meta in chunks:
            stats["chunks_processed"] += 1
            
            # Calculate age
            age_days = (now - chunk_meta.end_time).days
            
            # Check if should delete
            if age_days > self.policy.day_aggregation_days:
                if not dry_run:
                    # Delete old data
                    try:
                        import os
                        os.remove(chunk_meta.file_path)
                        meta_path = chunk_meta.file_path.replace('.tschunk', '.json')
                        if os.path.exists(meta_path):
                            os.remove(meta_path)
                        stats["chunks_deleted"] += 1
                        logger.info(f"Deleted old chunk: {chunk_meta.file_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete chunk: {e}")
                        stats["errors"] += 1
                else:
                    stats["chunks_deleted"] += 1
                continue
            
            # Check if should downsample
            target_resolution = self.policy.get_target_resolution(age_days)
            if target_resolution is None:
                continue  # Keep as-is
            
            # Check if already downsampled
            if chunk_meta.file_path.startswith(
                str(self.storage.base_path / "downsampled")
            ):
                continue  # Already downsampled
            
            if not dry_run:
                new_meta = self.downsample_chunk(
                    metric_name, chunk_meta, target_resolution
                )
                if new_meta:
                    stats["chunks_downsampled"] += 1
                else:
                    stats["errors"] += 1
            else:
                stats["chunks_downsampled"] += 1
        
        return stats
    
    def run_downsampling(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run downsampling for all metrics.
        
        Args:
            dry_run: If True, only report what would be done
            
        Returns:
            Overall statistics
        """
        all_stats = {
            "dry_run": dry_run,
            "metrics_processed": 0,
            "total_chunks_processed": 0,
            "total_chunks_downsampled": 0,
            "total_chunks_deleted": 0,
            "errors": 0,
            "details": []
        }
        
        metrics = self.storage._index.get_all_metrics()
        
        for metric_name in metrics:
            stats = self.process_metric(metric_name, dry_run)
            all_stats["metrics_processed"] += 1
            all_stats["total_chunks_processed"] += stats["chunks_processed"]
            all_stats["total_chunks_downsampled"] += stats["chunks_downsampled"]
            all_stats["total_chunks_deleted"] += stats["chunks_deleted"]
            all_stats["errors"] += stats["errors"]
            all_stats["details"].append(stats)
        
        logger.info(
            f"Downsampling complete: "
            f"{all_stats['total_chunks_downsampled']} chunks downsampled, "
            f"{all_stats['total_chunks_deleted']} chunks deleted"
        )
        
        return all_stats
    
    def get_stats(self) -> Dict[str, Any]:
        """Get downsampling statistics."""
        with self._lock:
            return dict(self._stats)
    
    def get_policy(self) -> DownsamplingPolicy:
        """Get current downsampling policy."""
        return self.policy
    
    def set_policy(self, policy: DownsamplingPolicy) -> None:
        """Set new downsampling policy."""
        self.policy = policy
        logger.info(f"Updated downsampling policy to: {policy.name}")


class RetentionEnforcer:
    """
    Enforces data retention policies by deleting expired data.
    """
    
    def __init__(
        self,
        storage: TimeSeriesStorage,
        retention_days: Dict[str, int]
    ):
        """
        Initialize retention enforcer.
        
        Args:
            storage: TimeSeriesStorage instance
            retention_days: Map of metric name pattern to retention days
        """
        self.storage = storage
        self.retention_days = retention_days
        self._lock = threading.RLock()
        self._deleted_count = 0
    
    def get_retention_for_metric(self, metric_name: str) -> int:
        """Get retention period for a metric."""
        # Check exact matches first
        if metric_name in self.retention_days:
            return self.retention_days[metric_name]
        
        # Check patterns
        for pattern, days in self.retention_days.items():
            if '*' in pattern:
                import fnmatch
                if fnmatch.fnmatch(metric_name, pattern):
                    return days
        
        # Default: 1 year
        return 365
    
    def enforce_retention(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Enforce retention policies by deleting expired data.
        
        Args:
            dry_run: If True, only report what would be deleted
            
        Returns:
            Statistics about enforcement
        """
        now = datetime.now()
        stats = {
            "dry_run": dry_run,
            "metrics_checked": 0,
            "chunks_deleted": 0,
            "bytes_freed": 0,
            "errors": 0
        }
        
        metrics = self.storage._index.get_all_metrics()
        
        for metric_name in metrics:
            stats["metrics_checked"] += 1
            retention_days = self.get_retention_for_metric(metric_name)
            cutoff_time = now - timedelta(days=retention_days)
            
            # Find expired chunks
            time_range = self.storage._index.get_time_range(metric_name)
            if not time_range:
                continue
            
            all_chunks = self.storage._index.find_chunks(
                metric_name,
                time_range[0],
                time_range[1]
            )
            
            for chunk_meta in all_chunks:
                if chunk_meta.end_time < cutoff_time:
                    if not dry_run:
                        try:
                            import os
                            file_size = os.path.getsize(chunk_meta.file_path)
                            os.remove(chunk_meta.file_path)
                            meta_path = chunk_meta.file_path.replace('.tschunk', '.json')
                            if os.path.exists(meta_path):
                                os.remove(meta_path)
                            
                            stats["chunks_deleted"] += 1
                            stats["bytes_freed"] += file_size
                            self._deleted_count += 1
                            
                            logger.info(f"Deleted expired chunk: {chunk_meta.file_path}")
                        except Exception as e:
                            logger.error(f"Failed to delete chunk: {e}")
                            stats["errors"] += 1
                    else:
                        stats["chunks_deleted"] += 1
        
        return stats
    
    def get_deleted_count(self) -> int:
        """Get total number of chunks deleted."""
        with self._lock:
            return self._deleted_count
