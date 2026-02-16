"""
Aggregation Pre-computation Module

Implements background aggregation and materialized views for
frequently queried metrics.

Features:
- Background pre-computation of common aggregations
- Materialized views for fast queries
- Incremental aggregation updates
- Aggregation scheduling and management
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Callable, Any, Set, Tuple

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
import heapq

from .storage_engine import TimeSeriesStorage, DataPoint, ChunkMetadata
from .downsampling import AggregationFunction, AggregationType

logger = logging.getLogger(__name__)


class AggregationView:
    """
    A materialized view of pre-computed aggregations.
    
    Stores aggregated data at a specific time resolution for fast queries.
    """
    
    def __init__(
        self,
        metric_name: str,
        interval: timedelta,
        aggregations: List[AggregationType],
        tags: Optional[Dict[str, str]] = None
    ):
        """
        Initialize aggregation view.
        
        Args:
            metric_name: Source metric name
            interval: Aggregation interval
            aggregations: List of aggregation functions to compute
            tags: Optional filter tags
        """
        self.metric_name = metric_name
        self.interval = interval
        self.aggregations = aggregations
        self.tags = tags or {}
        
        self._data: Dict[datetime, Dict[AggregationType, Any]] = {}
        self._last_updated: Optional[datetime] = None
        self._lock = threading.RLock()
        
        # View metadata
        self.view_name = f"{metric_name}_{self._interval_to_str(interval)}"
    
    def _interval_to_str(self, interval: timedelta) -> str:
        """Convert interval to string representation."""
        total_seconds = interval.total_seconds()
        if total_seconds >= 86400:
            return f"{int(total_seconds // 86400)}d"
        elif total_seconds >= 3600:
            return f"{int(total_seconds // 3600)}h"
        elif total_seconds >= 60:
            return f"{int(total_seconds // 60)}m"
        else:
            return f"{int(total_seconds)}s"
    
    def update(self, points: List[DataPoint]) -> int:
        """
        Update view with new data points.
        
        Args:
            points: List of data points to aggregate
            
        Returns:
            Number of aggregation buckets updated
        """
        with self._lock:
            # Group by time bucket
            buckets: Dict[datetime, List[float]] = defaultdict(list)
            
            for point in points:
                # Apply tags filter if specified
                if self.tags:
                    if not all(point.tags.get(k) == v for k, v in self.tags.items()):
                        continue
                
                # Calculate bucket time
                bucket_time = self._get_bucket_time(point.timestamp)
                buckets[bucket_time].append(point.value)
            
            # Compute aggregations for each bucket
            updated_count = 0
            for bucket_time, values in buckets.items():
                if not values:
                    continue
                
                bucket_data = {}
                for agg_type in self.aggregations:
                    func = AggregationFunction.get_function(agg_type)
                    bucket_data[agg_type] = func(values)
                
                self._data[bucket_time] = bucket_data
                updated_count += 1
            
            self._last_updated = datetime.now()
            
            return updated_count
    
    def _get_bucket_time(self, timestamp: datetime) -> datetime:
        """Get bucket time for a timestamp."""
        if self.interval >= timedelta(days=1):
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.interval >= timedelta(hours=1):
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif self.interval >= timedelta(minutes=1):
            return timestamp.replace(second=0, microsecond=0)
        else:
            # Round to nearest interval
            seconds = int(timestamp.timestamp())
            bucket_seconds = (seconds // int(self.interval.total_seconds())) * int(self.interval.total_seconds())
            return datetime.fromtimestamp(bucket_seconds)
    
    def query(
        self,
        start_time: datetime,
        end_time: datetime,
        aggregation: Optional[AggregationType] = None
    ) -> List[DataPoint]:
        """
        Query aggregated data.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            aggregation: Specific aggregation to return (default: first)
            
        Returns:
            List of aggregated data points
        """
        with self._lock:
            if aggregation is None:
                aggregation = self.aggregations[0]
            
            results = []
            for bucket_time in sorted(self._data.keys()):
                if start_time <= bucket_time < end_time:
                    bucket_data = self._data[bucket_time]
                    if aggregation in bucket_data:
                        results.append(DataPoint(
                            timestamp=bucket_time,
                            value=bucket_data[aggregation],
                            tags={
                                "_view": self.view_name,
                                "_aggregation": aggregation.value,
                                "_interval": str(self.interval)
                            }
                        ))
            
            return results
    
    def get_range(self) -> Optional[Tuple[datetime, datetime]]:
        """Get time range of data in view."""
        with self._lock:
            if not self._data:
                return None
            times = sorted(self._data.keys())
            return (times[0], times[-1] + self.interval)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get view statistics."""
        with self._lock:
            return {
                "view_name": self.view_name,
                "metric_name": self.metric_name,
                "interval": str(self.interval),
                "aggregations": [a.value for a in self.aggregations],
                "buckets_count": len(self._data),
                "last_updated": self._last_updated.isoformat() if self._last_updated else None
            }
    
    def clear(self) -> None:
        """Clear all data from view."""
        with self._lock:
            self._data.clear()
            self._last_updated = None


class AggregationManager:
    """
    Manages aggregation views and background pre-computation.
    
    Coordinates multiple views and schedules incremental updates.
    """
    
    def __init__(self, storage: TimeSeriesStorage):
        """
        Initialize aggregation manager.
        
        Args:
            storage: TimeSeriesStorage instance
        """
        self.storage = storage
        self._views: Dict[str, AggregationView] = {}
        self._update_schedule: Dict[str, timedelta] = {}
        self._last_update: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._running = False
        self._update_thread: Optional[threading.Thread] = None
        
        # Stats
        self._updates_completed = 0
        self._points_processed = 0
        
        logger.info("AggregationManager initialized")
    
    def create_view(
        self,
        metric_name: str,
        interval: timedelta,
        aggregations: Optional[List[AggregationType]] = None,
        tags: Optional[Dict[str, str]] = None,
        auto_update: bool = True
    ) -> AggregationView:
        """
        Create a new aggregation view.
        
        Args:
            metric_name: Source metric name
            interval: Aggregation interval
            aggregations: List of aggregation functions
            tags: Optional filter tags
            auto_update: Whether to auto-update view
            
        Returns:
            Created AggregationView
        """
        if aggregations is None:
            aggregations = [
                AggregationType.MEAN,
                AggregationType.MIN,
                AggregationType.MAX,
                AggregationType.COUNT
            ]
        
        view = AggregationView(metric_name, interval, aggregations, tags)
        
        with self._lock:
            self._views[view.view_name] = view
            
            if auto_update:
                # Schedule updates based on interval
                self._update_schedule[view.view_name] = interval
                self._last_update[view.view_name] = datetime.min
        
        logger.info(f"Created aggregation view: {view.view_name}")
        
        # Initial population
        self._populate_view(view)
        
        return view
    
    def _populate_view(self, view: AggregationView) -> int:
        """
        Populate view with historical data.
        
        Args:
            view: AggregationView to populate
            
        Returns:
            Number of points processed
        """
        # Get time range for metric
        time_range = self.storage._index.get_time_range(view.metric_name)
        if not time_range:
            return 0
        
        # Query all data
        points = self.storage.query(
            view.metric_name,
            time_range[0],
            time_range[1]
        )
        
        if not points:
            return 0
        
        # Update view
        updated = view.update(points)
        
        logger.info(
            f"Populated view {view.view_name}: "
            f"{len(points)} points -> {updated} buckets"
        )
        
        return len(points)
    
    def get_view(self, view_name: str) -> Optional[AggregationView]:
        """Get an existing view by name."""
        with self._lock:
            return self._views.get(view_name)
    
    def list_views(self) -> List[str]:
        """List all view names."""
        with self._lock:
            return list(self._views.keys())
    
    def delete_view(self, view_name: str) -> bool:
        """
        Delete a view.
        
        Args:
            view_name: Name of view to delete
            
        Returns:
            True if view was deleted
        """
        with self._lock:
            if view_name in self._views:
                del self._views[view_name]
                if view_name in self._update_schedule:
                    del self._update_schedule[view_name]
                if view_name in self._last_update:
                    del self._last_update[view_name]
                logger.info(f"Deleted view: {view_name}")
                return True
            return False
    
    def update_view(self, view_name: str, incremental: bool = True) -> int:
        """
        Update a single view.
        
        Args:
            view_name: Name of view to update
            incremental: If True, only update since last update
            
        Returns:
            Number of points processed
        """
        view = self.get_view(view_name)
        if not view:
            logger.warning(f"View not found: {view_name}")
            return 0
        
        # Determine time range to update
        if incremental and view._last_updated:
            start_time = view._last_updated
        else:
            time_range = self.storage._index.get_time_range(view.metric_name)
            if not time_range:
                return 0
            start_time = time_range[0]
        
        end_time = datetime.now()
        
        # Query new data
        points = self.storage.query(
            view.metric_name,
            start_time,
            end_time
        )
        
        if not points:
            return 0
        
        # Update view
        updated = view.update(points)
        
        with self._lock:
            self._last_update[view_name] = datetime.now()
            self._updates_completed += 1
            self._points_processed += len(points)
        
        logger.debug(
            f"Updated view {view_name}: "
            f"{len(points)} points -> {updated} buckets"
        )
        
        return len(points)
    
    def update_all_views(self, incremental: bool = True) -> Dict[str, int]:
        """
        Update all views.
        
        Args:
            incremental: If True, only update since last update
            
        Returns:
            Dictionary of view_name -> points_processed
        """
        results = {}
        
        with self._lock:
            view_names = list(self._views.keys())
        
        for view_name in view_names:
            try:
                processed = self.update_view(view_name, incremental)
                results[view_name] = processed
            except Exception as e:
                logger.error(f"Failed to update view {view_name}: {e}")
                results[view_name] = -1
        
        return results
    
    def start_auto_update(self, interval_seconds: float = 60.0) -> None:
        """
        Start automatic background updates.
        
        Args:
            interval_seconds: Update check interval
        """
        if self._running:
            logger.warning("Auto-update already running")
            return
        
        self._running = True
        
        def update_loop():
            while self._running:
                try:
                    self._run_scheduled_updates()
                except Exception as e:
                    logger.error(f"Error in update loop: {e}")
                
                time.sleep(interval_seconds)
        
        self._update_thread = threading.Thread(target=update_loop, daemon=True)
        self._update_thread.start()
        
        logger.info(f"Started auto-update with interval {interval_seconds}s")
    
    def stop_auto_update(self) -> None:
        """Stop automatic background updates."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=5.0)
            self._update_thread = None
        logger.info("Stopped auto-update")
    
    def _run_scheduled_updates(self) -> None:
        """Run updates for views that are due."""
        now = datetime.now()
        
        with self._lock:
            due_views = []
            for view_name, schedule in self._update_schedule.items():
                last_update = self._last_update.get(view_name, datetime.min)
                if now - last_update >= schedule:
                    due_views.append(view_name)
        
        for view_name in due_views:
            try:
                self.update_view(view_name, incremental=True)
            except Exception as e:
                logger.error(f"Scheduled update failed for {view_name}: {e}")
    
    def query_view(
        self,
        view_name: str,
        start_time: datetime,
        end_time: datetime,
        aggregation: Optional[AggregationType] = None
    ) -> List[DataPoint]:
        """
        Query a view.
        
        Args:
            view_name: Name of view to query
            start_time: Start of time range
            end_time: End of time range
            aggregation: Specific aggregation to return
            
        Returns:
            List of aggregated data points
        """
        view = self.get_view(view_name)
        if not view:
            raise ValueError(f"View not found: {view_name}")
        
        return view.query(start_time, end_time, aggregation)
    
    def get_view_stats(self) -> Dict[str, Any]:
        """Get statistics for all views."""
        with self._lock:
            view_stats = {
                name: view.get_stats()
                for name, view in self._views.items()
            }
            
            return {
                "views_count": len(self._views),
                "views": view_stats,
                "updates_completed": self._updates_completed,
                "points_processed": self._points_processed
            }
    
    def get_aggregated_metric(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        aggregation: AggregationType,
        interval: Optional[timedelta] = None
    ) -> List[DataPoint]:
        """
        Get aggregated metric data, using view if available.
        
        Args:
            metric_name: Metric name
            start_time: Start time
            end_time: End time
            aggregation: Aggregation function
            interval: Optional interval (uses view if matches)
            
        Returns:
            List of aggregated data points
        """
        # Try to find matching view
        if interval:
            view_name = f"{metric_name}_{self._interval_to_str(interval)}"
            view = self.get_view(view_name)
            if view and aggregation in view.aggregations:
                return view.query(start_time, end_time, aggregation)
        
        # Fall back to on-the-fly aggregation
        points = self.storage.query(metric_name, start_time, end_time)
        
        if not points:
            return []
        
        # Group by interval if specified
        if interval:
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
            func = AggregationFunction.get_function(aggregation)
            results = []
            
            for bucket_time, values in sorted(buckets.items()):
                results.append(DataPoint(
                    timestamp=bucket_time,
                    value=func(values),
                    tags={
                        "_aggregation": aggregation.value,
                        "_interval": str(interval),
                        "_source_count": str(len(values))
                    }
                ))
            
            return results
        else:
            # Single aggregation of all points
            func = AggregationFunction.get_function(aggregation)
            return [DataPoint(
                timestamp=start_time,
                value=func([p.value for p in points]),
                tags={
                    "_aggregation": aggregation.value,
                    "_source_count": str(len(points))
                }
            )]
    
    def _interval_to_str(self, interval: timedelta) -> str:
        """Convert interval to string representation."""
        total_seconds = interval.total_seconds()
        if total_seconds >= 86400:
            return f"{int(total_seconds // 86400)}d"
        elif total_seconds >= 3600:
            return f"{int(total_seconds // 3600)}h"
        elif total_seconds >= 60:
            return f"{int(total_seconds // 60)}m"
        else:
            return f"{int(total_seconds)}s"


class IncrementalAggregator:
    """
    Incremental aggregation for streaming data.
    
    Maintains running aggregates that can be updated efficiently
    as new data arrives.
    """
    
    def __init__(self, window_size: timedelta = timedelta(hours=1)):
        """
        Initialize incremental aggregator.
        
        Args:
            window_size: Time window for aggregation
        """
        self.window_size = window_size
        self._windows: Dict[datetime, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def add_point(self, point: DataPoint) -> None:
        """
        Add a data point to incremental aggregation.
        
        Args:
            point: Data point to add
        """
        with self._lock:
            # Determine window
            window_time = self._get_window_time(point.timestamp)
            
            if window_time not in self._windows:
                self._windows[window_time] = {
                    "count": 0,
                    "sum": 0.0,
                    "sum_sq": 0.0,
                    "min": float('inf'),
                    "max": float('-inf'),
                    "values": []  # Keep for percentile calculation
                }
            
            window = self._windows[window_time]
            value = point.value
            
            window["count"] += 1
            window["sum"] += value
            window["sum_sq"] += value * value
            window["min"] = min(window["min"], value)
            window["max"] = max(window["max"], value)
            window["values"].append(value)
            
            # Limit stored values to prevent memory growth
            if len(window["values"]) > 10000:
                # Switch to approximate percentiles
                window["values"] = []
    
    def _get_window_time(self, timestamp: datetime) -> datetime:
        """Get window start time for timestamp."""
        window_seconds = int(self.window_size.total_seconds())
        seconds = int(timestamp.timestamp())
        window_start = (seconds // window_seconds) * window_seconds
        return datetime.fromtimestamp(window_start)
    
    def get_aggregate(
        self,
        window_time: datetime,
        aggregation: AggregationType
    ) -> Optional[float]:
        """
        Get aggregate for a specific window.
        
        Args:
            window_time: Window start time
            aggregation: Aggregation function
            
        Returns:
            Aggregated value or None if window not found
        """
        with self._lock:
            window = self._windows.get(window_time)
            if not window:
                return None
            
            if aggregation == AggregationType.COUNT:
                return window["count"]
            elif aggregation == AggregationType.SUM:
                return window["sum"]
            elif aggregation == AggregationType.MEAN:
                return window["sum"] / window["count"] if window["count"] > 0 else 0
            elif aggregation == AggregationType.MIN:
                return window["min"] if window["min"] != float('inf') else 0
            elif aggregation == AggregationType.MAX:
                return window["max"] if window["max"] != float('-inf') else 0
            elif aggregation in (AggregationType.P95, AggregationType.P99):
                if window["values"]:
                    sorted_vals = sorted(window["values"])
                    if aggregation == AggregationType.P95:
                        idx = int(len(sorted_vals) * 0.95)
                    else:
                        idx = int(len(sorted_vals) * 0.99)
                    return sorted_vals[min(idx, len(sorted_vals) - 1)]
                return None
            
            return None
    
    def get_all_windows(self) -> List[datetime]:
        """Get all window start times."""
        with self._lock:
            return sorted(self._windows.keys())
    
    def prune_old_windows(self, max_age: timedelta) -> int:
        """
        Remove windows older than max_age.
        
        Args:
            max_age: Maximum age to keep
            
        Returns:
            Number of windows removed
        """
        with self._lock:
            cutoff = datetime.now() - max_age
            to_remove = [
                wt for wt in self._windows.keys()
                if wt < cutoff
            ]
            
            for wt in to_remove:
                del self._windows[wt]
            
            return len(to_remove)
