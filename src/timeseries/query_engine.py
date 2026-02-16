"""
Query Engine for Time-Series Data

Provides optimized query execution with:
- Time-range index for O(log n) lookups
- Pre-aggregated rollups for common queries
- Query result caching
- Parallel query execution
- Query optimization and planning

Target: <100ms query latency for typical queries
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import heapq

from .storage_engine import TimeSeriesStorage, DataPoint, ChunkMetadata

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result of a time-series query."""
    points: List[DataPoint]
    query_time_ms: float
    chunks_scanned: int
    points_scanned: int
    cache_hit: bool = False
    aggregated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "points": [p.to_dict() for p in self.points],
            "query_time_ms": self.query_time_ms,
            "chunks_scanned": self.chunks_scanned,
            "points_scanned": self.points_scanned,
            "cache_hit": self.cache_hit,
            "aggregated": self.aggregated
        }


@dataclass
class QueryPlan:
    """Query execution plan."""
    metric_name: str
    start_time: datetime
    end_time: datetime
    aggregation: Optional[str] = None
    group_by: Optional[timedelta] = None
    tags_filter: Optional[Dict[str, str]] = None
    use_rollup: bool = False
    rollup_interval: Optional[timedelta] = None
    chunks_to_scan: List[ChunkMetadata] = field(default_factory=list)
    estimated_points: int = 0
    estimated_cost: float = 0.0  # Estimated execution cost


class QueryCache:
    """
    LRU cache for query results.
    
    Caches results of expensive queries to improve performance.
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: float = 300):
        """
        Initialize query cache.
        
        Args:
            max_size: Maximum number of cached queries
            ttl_seconds: Time-to-live for cached entries
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[QueryResult, float]] = {}
        self._access_order: List[str] = []
        self._lock = threading.RLock()
    
    def _make_key(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        aggregation: Optional[str],
        tags_filter: Optional[Dict[str, str]]
    ) -> str:
        """Create cache key from query parameters."""
        tags_str = ""
        if tags_filter:
            tags_str = ",".join(f"{k}={v}" for k, v in sorted(tags_filter.items()))
        
        return f"{metric_name}:{start_time.isoformat()}:{end_time.isoformat()}:{aggregation}:{tags_str}"
    
    def get(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        aggregation: Optional[str] = None,
        tags_filter: Optional[Dict[str, str]] = None
    ) -> Optional[QueryResult]:
        """Get cached query result if available and not expired."""
        key = self._make_key(metric_name, start_time, end_time, aggregation, tags_filter)
        
        with self._lock:
            if key not in self._cache:
                return None
            
            result, timestamp = self._cache[key]
            now = time.time()
            
            # Check expiration
            if now - timestamp > self.ttl_seconds:
                del self._cache[key]
                self._access_order.remove(key)
                return None
            
            # Update LRU order
            self._access_order.remove(key)
            self._access_order.append(key)
            
            # Mark as cache hit
            result.cache_hit = True
            
            return result
        
        return None
    
    def put(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        result: QueryResult,
        aggregation: Optional[str] = None,
        tags_filter: Optional[Dict[str, str]] = None
    ) -> None:
        """Store query result in cache."""
        key = self._make_key(metric_name, start_time, end_time, aggregation, tags_filter)
        
        with self._lock:
            # Evict if necessary
            if len(self._cache) >= self.max_size and key not in self._cache:
                oldest = self._access_order.pop(0)
                del self._cache[oldest]
            
            # Store result
            self._cache[key] = (result, time.time())
            
            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
    
    def invalidate(self, metric_name: str) -> int:
        """Invalidate all cached entries for a metric."""
        with self._lock:
            keys_to_remove = [
                k for k in self._cache.keys()
                if k.startswith(f"{metric_name}:")
            ]
            
            for key in keys_to_remove:
                del self._cache[key]
                self._access_order.remove(key)
            
            return len(keys_to_remove)
    
    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            now = time.time()
            expired = sum(
                1 for _, timestamp in self._cache.values()
                if now - timestamp > self.ttl_seconds
            )
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "expired_entries": expired,
                "hit_rate": 0.0  # Would need to track hits/misses
            }


class RollupManager:
    """
    Manages pre-aggregated rollups for fast queries.
    
    Maintains materialized views of common aggregations at different
    time granularities.
    """
    
    def __init__(self, storage: TimeSeriesStorage):
        self.storage = storage
        self._rollups: Dict[str, Dict[timedelta, List[DataPoint]]] = defaultdict(dict)
        self._lock = threading.RLock()
    
    def create_rollup(
        self,
        metric_name: str,
        interval: timedelta,
        aggregation: str = "mean"
    ) -> bool:
        """
        Create a pre-aggregated rollup for a metric.
        
        Args:
            metric_name: Name of the metric
            interval: Time interval for aggregation
            aggregation: Aggregation function (mean, min, max, etc.)
            
        Returns:
            True if rollup was created successfully
        """
        try:
            # Get all data for metric
            time_range = self.storage._index.get_time_range(metric_name)
            if not time_range:
                return False
            
            # Query all data
            points = self.storage.query(
                metric_name,
                time_range[0],
                time_range[1]
            )
            
            if not points:
                return False
            
            # Group by interval
            buckets: Dict[datetime, List[float]] = defaultdict(list)
            
            for point in points:
                if interval >= timedelta(days=1):
                    bucket_time = point.timestamp.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                elif interval >= timedelta(hours=1):
                    bucket_time = point.timestamp.replace(
                        minute=0, second=0, microsecond=0
                    )
                elif interval >= timedelta(minutes=1):
                    bucket_time = point.timestamp.replace(
                        second=0, microsecond=0
                    )
                else:
                    bucket_time = point.timestamp
                
                buckets[bucket_time].append(point.value)
            
            # Aggregate
            from .downsampling import AggregationFunction
            
            agg_func = AggregationFunction.get_function(
                aggregation if hasattr(aggregation, 'value') else aggregation
            )
            
            rollup_points = []
            for bucket_time, values in sorted(buckets.items()):
                agg_value = agg_func(values)
                
                rollup_points.append(DataPoint(
                    timestamp=bucket_time,
                    value=agg_value,
                    tags={
                        "_rollup": "true",
                        "_interval": str(interval),
                        "_aggregation": aggregation,
                        "_source_count": str(len(values))
                    }
                ))
            
            with self._lock:
                self._rollups[metric_name][interval] = rollup_points
            
            logger.info(
                f"Created rollup for {metric_name}: "
                f"{len(rollup_points)} points at {interval} interval"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create rollup for {metric_name}: {e}")
            return False
    
    def get_rollup(
        self,
        metric_name: str,
        interval: timedelta,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[List[DataPoint]]:
        """
        Get pre-aggregated rollup data.
        
        Args:
            metric_name: Name of the metric
            interval: Time interval
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of aggregated points or None if rollup doesn't exist
        """
        with self._lock:
            if metric_name not in self._rollups:
                return None
            
            if interval not in self._rollups[metric_name]:
                # Check if we have a larger interval that could work
                available = sorted(self._rollups[metric_name].keys())
                for avail_interval in available:
                    if avail_interval >= interval:
                        interval = avail_interval
                        break
                else:
                    return None
            
            points = self._rollups[metric_name][interval]
            
            # Filter by time range
            filtered = [
                p for p in points
                if start_time <= p.timestamp < end_time
            ]
            
            return filtered
    
    def has_rollup(self, metric_name: str, interval: timedelta) -> bool:
        """Check if a rollup exists for given metric and interval."""
        with self._lock:
            return (
                metric_name in self._rollups and
                interval in self._rollups[metric_name]
            )
    
    def list_rollups(self, metric_name: str) -> List[timedelta]:
        """List available rollup intervals for a metric."""
        with self._lock:
            return list(self._rollups.get(metric_name, {}).keys())


class QueryEngine:
    """
    Optimized query engine for time-series data.
    
    Provides fast query execution with caching, rollups, and parallel processing.
    """
    
    def __init__(
        self,
        storage: TimeSeriesStorage,
        cache_size: int = 100,
        cache_ttl_seconds: float = 300,
        max_workers: int = 4
    ):
        """
        Initialize query engine.
        
        Args:
            storage: TimeSeriesStorage instance
            cache_size: Size of query cache
            cache_ttl_seconds: Cache entry TTL
            max_workers: Maximum parallel workers for queries
        """
        self.storage = storage
        self.cache = QueryCache(cache_size, cache_ttl_seconds)
        self.rollup_manager = RollupManager(storage)
        self.max_workers = max_workers
        
        self._query_count = 0
        self._total_query_time_ms = 0.0
        self._lock = threading.RLock()
        
        logger.info(f"QueryEngine initialized with cache_size={cache_size}")
    
    def plan_query(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        aggregation: Optional[str] = None,
        group_by: Optional[timedelta] = None,
        tags_filter: Optional[Dict[str, str]] = None,
        use_rollup: bool = True
    ) -> QueryPlan:
        """
        Create an optimized query plan.
        
        Args:
            metric_name: Metric to query
            start_time: Start of time range
            end_time: End of time range
            aggregation: Optional aggregation function
            group_by: Optional grouping interval
            tags_filter: Optional tags filter
            use_rollup: Whether to use pre-aggregated rollups
            
        Returns:
            QueryPlan with execution strategy
        """
        plan = QueryPlan(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            aggregation=aggregation,
            group_by=group_by,
            tags_filter=tags_filter
        )
        
        # Check if rollup is available
        if use_rollup and aggregation and group_by:
            if self.rollup_manager.has_rollup(metric_name, group_by):
                plan.use_rollup = True
                plan.rollup_interval = group_by
        
        # Find chunks to scan
        if not plan.use_rollup:
            plan.chunks_to_scan = self.storage._index.find_chunks(
                metric_name, start_time, end_time
            )
            
            # Estimate points
            plan.estimated_points = sum(c.point_count for c in plan.chunks_to_scan)
            
            # Estimate cost (simplified)
            plan.estimated_cost = plan.estimated_points * 0.001  # 1ms per 1000 points
        
        return plan
    
    def execute_query(self, plan: QueryPlan) -> QueryResult:
        """
        Execute a query plan.
        
        Args:
            plan: QueryPlan to execute
            
        Returns:
            QueryResult with data and metadata
        """
        start_time = time.time()
        
        # Check cache first
        cached = self.cache.get(
            plan.metric_name,
            plan.start_time,
            plan.end_time,
            plan.aggregation,
            plan.tags_filter
        )
        
        if cached:
            return cached
        
        # Use rollup if available
        if plan.use_rollup and plan.rollup_interval:
            rollup_points = self.rollup_manager.get_rollup(
                plan.metric_name,
                plan.rollup_interval,
                plan.start_time,
                plan.end_time
            )
            
            if rollup_points is not None:
                query_time_ms = (time.time() - start_time) * 1000
                
                result = QueryResult(
                    points=rollup_points,
                    query_time_ms=query_time_ms,
                    chunks_scanned=0,
                    points_scanned=len(rollup_points),
                    cache_hit=False,
                    aggregated=True
                )
                
                # Cache result
                self.cache.put(
                    plan.metric_name,
                    plan.start_time,
                    plan.end_time,
                    result,
                    plan.aggregation,
                    plan.tags_filter
                )
                
                return result
        
        # Execute regular query
        points = self.storage.query(
            plan.metric_name,
            plan.start_time,
            plan.end_time,
            plan.tags_filter
        )
        
        # Apply aggregation if specified
        if plan.aggregation and plan.group_by:
            points = self._aggregate_points(points, plan.group_by, plan.aggregation)
        
        query_time_ms = (time.time() - start_time) * 1000
        
        # Update stats
        with self._lock:
            self._query_count += 1
            self._total_query_time_ms += query_time_ms
        
        result = QueryResult(
            points=points,
            query_time_ms=query_time_ms,
            chunks_scanned=len(plan.chunks_to_scan),
            points_scanned=plan.estimated_points,
            cache_hit=False,
            aggregated=plan.aggregation is not None
        )
        
        # Cache result
        self.cache.put(
            plan.metric_name,
            plan.start_time,
            plan.end_time,
            result,
            plan.aggregation,
            plan.tags_filter
        )
        
        return result
    
    def query(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        aggregation: Optional[str] = None,
        group_by: Optional[timedelta] = None,
        tags_filter: Optional[Dict[str, str]] = None,
        use_rollup: bool = True
    ) -> QueryResult:
        """
        Execute a query with automatic optimization.
        
        This is the main entry point for queries.
        
        Args:
            metric_name: Metric to query
            start_time: Start of time range
            end_time: End of time range
            aggregation: Optional aggregation function
            group_by: Optional grouping interval
            tags_filter: Optional tags filter
            use_rollup: Whether to use pre-aggregated rollups
            
        Returns:
            QueryResult with data and metadata
        """
        # Create optimized plan
        plan = self.plan_query(
            metric_name,
            start_time,
            end_time,
            aggregation,
            group_by,
            tags_filter,
            use_rollup
        )
        
        # Execute plan
        return self.execute_query(plan)
    
    def _aggregate_points(
        self,
        points: List[DataPoint],
        group_by: timedelta,
        aggregation: str
    ) -> List[DataPoint]:
        """
        Aggregate points by time interval.
        
        Args:
            points: List of data points
            group_by: Grouping interval
            aggregation: Aggregation function
            
        Returns:
            List of aggregated points
        """
        if not points:
            return []
        
        # Group by time bucket
        buckets: Dict[datetime, List[float]] = defaultdict(list)
        
        for point in points:
            if group_by >= timedelta(days=1):
                bucket_time = point.timestamp.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            elif group_by >= timedelta(hours=1):
                bucket_time = point.timestamp.replace(
                    minute=0, second=0, microsecond=0
                )
            elif group_by >= timedelta(minutes=1):
                bucket_time = point.timestamp.replace(
                    second=0, microsecond=0
                )
            else:
                bucket_time = point.timestamp
            
            buckets[bucket_time].append(point.value)
        
        # Apply aggregation
        from .downsampling import AggregationFunction
        
        agg_func = AggregationFunction.get_function(
            aggregation if hasattr(aggregation, 'value') else aggregation
        )
        
        aggregated = []
        for bucket_time, values in sorted(buckets.items()):
            agg_value = agg_func(values)
            
            aggregated.append(DataPoint(
                timestamp=bucket_time,
                value=agg_value,
                tags={
                    "_aggregated": "true",
                    "_interval": str(group_by),
                    "_aggregation": aggregation,
                    "_source_count": str(len(values))
                }
            ))
        
        return aggregated
    
    def parallel_query(
        self,
        queries: List[Tuple[str, datetime, datetime]]
    ) -> List[QueryResult]:
        """
        Execute multiple queries in parallel.
        
        Args:
            queries: List of (metric_name, start_time, end_time) tuples
            
        Returns:
            List of QueryResult objects
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self.query,
                    metric,
                    start,
                    end
                ): (metric, start, end)
                for metric, start, end in queries
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Query failed: {e}")
                    # Return empty result on error
                    metric, start, end = futures[future]
                    results.append(QueryResult(
                        points=[],
                        query_time_ms=0.0,
                        chunks_scanned=0,
                        points_scanned=0,
                        cache_hit=False
                    ))
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get query engine statistics."""
        with self._lock:
            avg_query_time = (
                self._total_query_time_ms / self._query_count
                if self._query_count > 0 else 0.0
            )
            
            return {
                "total_queries": self._query_count,
                "avg_query_time_ms": round(avg_query_time, 2),
                "cache_stats": self.cache.get_stats()
            }
    
    def create_rollup(
        self,
        metric_name: str,
        interval: timedelta,
        aggregation: str = "mean"
    ) -> bool:
        """
        Create a pre-aggregated rollup for faster queries.
        
        Args:
            metric_name: Name of the metric
            interval: Time interval for aggregation
            aggregation: Aggregation function
            
        Returns:
            True if rollup was created successfully
        """
        return self.rollup_manager.create_rollup(metric_name, interval, aggregation)
