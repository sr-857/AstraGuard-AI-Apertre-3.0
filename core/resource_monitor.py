"""
Resource monitoring utilities for AstraGuard-AI.

Monitors system resources (CPU, memory, disk) to detect exhaustion
before it causes failures. Integrates with health monitoring system.

Features:
- Real-time CPU and memory usage tracking
- Configurable warning/critical thresholds
- Resource usage history for diagnostics
- Integration with health monitor
- Automatic alerts when thresholds exceeded
- Non-blocking CPU monitoring
"""

import psutil
import logging
import os
import threading
import functools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, TypeVar
from datetime import datetime, timedelta
from enum import Enum

# Import centralized secrets management
from core.secrets import get_secret

T = TypeVar('T')

logger = logging.getLogger(__name__)


def monitor_operation_resources(operation_name: Optional[str] = None):
    """
    Decorator to monitor CPU and memory usage during operation execution.

    Logs resource usage before and after the operation, and warns if usage
    exceeds thresholds during the operation.

    Args:
        operation_name: Optional name for the operation (defaults to function name)

    Returns:
        Decorated function that monitors resource usage

    Example:
        @monitor_operation_resources()
        def heavy_computation():
            # Resource usage will be monitored
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            op_name = operation_name or func.__name__
            monitor = get_resource_monitor()

            # Get initial metrics
            initial_metrics = monitor.get_current_metrics()

            logger.debug(
                f"Starting operation '{op_name}' - "
                f"CPU: {initial_metrics.cpu_percent:.1f}%, "
                f"Memory: {initial_metrics.memory_percent:.1f}% "
                f"({initial_metrics.process_memory_mb:.1f}MB)"
            )

            try:
                # Execute the function
                result = func(*args, **kwargs)

                # Get final metrics
                final_metrics = monitor.get_current_metrics()

                # Calculate resource usage during operation
                cpu_used = final_metrics.cpu_percent - initial_metrics.cpu_percent
                memory_used = final_metrics.process_memory_mb - initial_metrics.process_memory_mb

                logger.debug(
                    f"Completed operation '{op_name}' - "
                    f"CPU delta: {cpu_used:+.1f}%, "
                    f"Memory delta: {memory_used:+.1f}MB"
                )

                # Check for excessive resource usage
                if cpu_used > 50.0:  # More than 50% CPU increase
                    logger.warning(
                        f"High CPU usage in '{op_name}': +{cpu_used:.1f}% "
                        f"(final: {final_metrics.cpu_percent:.1f}%)"
                    )

                if memory_used > 100.0:  # More than 100MB memory increase
                    logger.warning(
                        f"High memory usage in '{op_name}': +{memory_used:.1f}MB "
                        f"(final: {final_metrics.process_memory_mb:.1f}MB)"
                    )

                return result

            except Exception as e:
                # Log resource usage even on failure
                final_metrics = monitor.get_current_metrics()
                cpu_used = final_metrics.cpu_percent - initial_metrics.cpu_percent
                memory_used = final_metrics.process_memory_mb - initial_metrics.process_memory_mb

                logger.error(
                    f"Operation '{op_name}' failed after using "
                    f"CPU: +{cpu_used:.1f}%, Memory: +{memory_used:.1f}MB - {e}"
                )
                raise

        return wrapper

    return decorator


class ResourceStatus(str, Enum):
    """Resource health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ResourceMetrics:
    """
    Snapshot of system resource metrics.
    
    Attributes:
        cpu_percent: CPU utilization percentage (0-100)
        memory_percent: Memory utilization percentage (0-100)
        memory_available_mb: Available memory in megabytes
        disk_usage_percent: Disk usage percentage (0-100)
        process_memory_mb: Memory used by current process
        timestamp: When metrics were collected
    """
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    process_memory_mb: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'cpu_percent': round(self.cpu_percent, 2),
            'memory_percent': round(self.memory_percent, 2),
            'memory_available_mb': round(self.memory_available_mb, 2),
            'disk_usage_percent': round(self.disk_usage_percent, 2),
            'process_memory_mb': round(self.process_memory_mb, 2),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ResourceThresholds:
    """
    Configurable thresholds for resource monitoring.
    
    Attributes:
        cpu_warning: CPU % to trigger warning (default: 70%)
        cpu_critical: CPU % to trigger critical alert (default: 90%)
        memory_warning: Memory % for warning (default: 75%)
        memory_critical: Memory % for critical alert (default: 90%)
        disk_warning: Disk % for warning (default: 80%)
        disk_critical: Disk % for critical alert (default: 95%)
    """
    cpu_warning: float = 70.0
    cpu_critical: float = 90.0
    memory_warning: float = 75.0
    memory_critical: float = 90.0
    disk_warning: float = 80.0
    disk_critical: float = 95.0


class ResourceMonitor:
    """
    Monitor system resource utilization.
    
    Tracks CPU, memory, and disk usage with configurable thresholds.
    Maintains history for trend analysis and diagnostics.
    """
    
    def __init__(
        self,
        thresholds: Optional[ResourceThresholds] = None,
        history_size: int = 100,
        history_time_window_hours: int = 1,
        monitoring_enabled: bool = True
    ):
        """
        Initialize resource monitor.

        Args:
            thresholds: Custom threshold configuration (uses defaults if None)
            history_size: Number of metric snapshots to retain
            history_time_window_hours: Time window in hours to retain metrics
            monitoring_enabled: Whether monitoring is active
        """
        self.thresholds = thresholds or ResourceThresholds()
        self.history_size = history_size
        self.history_time_window_hours = history_time_window_hours
        self.monitoring_enabled = monitoring_enabled

        self._metrics_history: List[ResourceMetrics] = []
        self._process = psutil.Process()

        logger.info(
            f"ResourceMonitor initialized: "
            f"cpu_warning={self.thresholds.cpu_warning}%, "
            f"memory_warning={self.thresholds.memory_warning}%, "
            f"history_size={self.history_size}, "
            f"history_time_window={self.history_time_window_hours}h"
        )
    
    def get_current_metrics(self) -> ResourceMetrics:
        """
        Collect current resource metrics.

        Uses interval=0 for CPU to ensure non-blocking operation.

        Returns:
            ResourceMetrics snapshot of current system state
        """
        if not self.monitoring_enabled:
            return ResourceMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                process_memory_mb=0.0
            )

        try:
            # CPU usage (interval=0 for non-blocking return)
            # This returns usage since last call, which is ideal for periodic monitoring
            cpu_percent = psutil.cpu_percent(interval=0)
            # CPU usage (1 second interval for accuracy)
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent if memory.percent is not None else 0.0
            memory_available_mb = memory.available / (1024 * 1024) if memory.available is not None else 0.0

            # Disk usage - with fallback for CI environments
            try:
                disk = psutil.disk_usage('/')
                disk_usage_percent = disk.percent if disk.percent is not None else 0.0
            except (OSError, PermissionError):
                disk_usage_percent = 0.0

            # Process memory
            process_info = self._process.memory_info()
            process_memory_mb = process_info.rss / (1024 * 1024) if process_info.rss is not None else 0.0

            metrics = ResourceMetrics(
                cpu_percent=float(cpu_percent) if cpu_percent is not None else 0.0,
                memory_percent=float(memory_percent) if memory_percent is not None else 0.0,
                memory_available_mb=float(memory_available_mb) if memory_available_mb is not None else 0.0,
                disk_usage_percent=float(disk_usage_percent) if disk_usage_percent is not None else 0.0,
                process_memory_mb=float(process_memory_mb) if process_memory_mb is not None else 0.0,
                timestamp=datetime.now()
            )

            # Add to history
            self._add_to_history(metrics)

            return metrics

        except Exception as e:
            logger.error(f"Error collecting resource metrics: {e}")
            return ResourceMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                process_memory_mb=0.0
            )

    def get_current_metrics_no_history(self) -> ResourceMetrics:
        """
        Collect current resource metrics without adding to history.

        Used by operation monitoring decorator to avoid polluting history.

        Returns:
            ResourceMetrics snapshot of current system state
        """
        if not self.monitoring_enabled:
            return ResourceMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                process_memory_mb=0.0
            )

        try:
            # CPU usage (interval=0 for non-blocking return)
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_mb = memory.available / (1024 * 1024)

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent

            # Process memory
            process_info = self._process.memory_info()
            process_memory_mb = process_info.rss / (1024 * 1024)

            return ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                process_memory_mb=process_memory_mb,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error collecting resource metrics: {e}")
            return ResourceMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                process_memory_mb=0.0
            )
    
    def _add_to_history(self, metrics: ResourceMetrics):
        """Add metrics to history, maintaining size and time limits"""
        self._metrics_history.append(metrics)

        # Clean up old entries based on time window
        cutoff_time = datetime.now() - timedelta(hours=self.history_time_window_hours)
        self._metrics_history = [
            m for m in self._metrics_history
            if m.timestamp >= cutoff_time
        ]

        # Trim history if exceeded size (after time-based cleanup)
        if len(self._metrics_history) > self.history_size:
            self._metrics_history = self._metrics_history[-self.history_size:]
    
    def check_resource_health(self) -> Dict[str, str]:
        """
        Check if resources are within safe limits.
        
        Returns:
            Dictionary with status for each resource type:
            {
                'cpu': 'healthy' | 'warning' | 'critical',
                'memory': 'healthy' | 'warning' | 'critical',
                'disk': 'healthy' | 'warning' | 'critical',
                'overall': 'healthy' | 'warning' | 'critical'
            }
        """
        metrics = self.get_current_metrics()
        
        status = {
            'cpu': ResourceStatus.HEALTHY,
            'memory': ResourceStatus.HEALTHY,
            'disk': ResourceStatus.HEALTHY,
            'overall': ResourceStatus.HEALTHY
        }
        
        # Check CPU (handle None values)
        if metrics.cpu_percent is not None:
            if metrics.cpu_percent >= self.thresholds.cpu_critical:
                status['cpu'] = ResourceStatus.CRITICAL
                logger.warning(
                    f"CPU critical: {metrics.cpu_percent:.1f}% "
                    f"(threshold: {self.thresholds.cpu_critical}%)"
                )
            elif metrics.cpu_percent >= self.thresholds.cpu_warning:
                status['cpu'] = ResourceStatus.WARNING
                logger.info(
                    f"CPU warning: {metrics.cpu_percent:.1f}% "
                    f"(threshold: {self.thresholds.cpu_warning}%)"
                )
        
        # Check Memory (handle None values)
        if metrics.memory_percent is not None:
            if metrics.memory_percent >= self.thresholds.memory_critical:
                status['memory'] = ResourceStatus.CRITICAL
                logger.warning(
                    f"Memory critical: {metrics.memory_percent:.1f}% "
                    f"(threshold: {self.thresholds.memory_critical}%)"
                )
            elif metrics.memory_percent >= self.thresholds.memory_warning:
                status['memory'] = ResourceStatus.WARNING
                logger.info(
                    f"Memory warning: {metrics.memory_percent:.1f}% "
                    f"(threshold: {self.thresholds.memory_warning}%)"
                )
        
        # Check Disk (handle None values)
        if metrics.disk_usage_percent is not None:
            if metrics.disk_usage_percent >= self.thresholds.disk_critical:
                status['disk'] = ResourceStatus.CRITICAL
                logger.warning(
                    f"Disk critical: {metrics.disk_usage_percent:.1f}% "
                    f"(threshold: {self.thresholds.disk_critical}%)"
                )
            elif metrics.disk_usage_percent >= self.thresholds.disk_warning:
                status['disk'] = ResourceStatus.WARNING
        
        # Determine overall status (worst status wins)
        if any(s == ResourceStatus.CRITICAL for s in status.values()):
            status['overall'] = ResourceStatus.CRITICAL
        elif any(s == ResourceStatus.WARNING for s in status.values()):
            status['overall'] = ResourceStatus.WARNING
        
        return {k: v.value for k, v in status.items()}
    
    def is_resource_available(self, min_cpu_free: float = 10.0, min_memory_mb: float = 100.0) -> bool:
        """
        Check if sufficient resources are available for operations.
        
        Args:
            min_cpu_free: Minimum free CPU percentage required
            min_memory_mb: Minimum free memory in MB required
        
        Returns:
            True if resources are available, False otherwise
        """
        metrics = self.get_current_metrics()
        
        cpu_free = 100.0 - metrics.cpu_percent
        memory_available = metrics.memory_available_mb
        
        if cpu_free < min_cpu_free:
            logger.warning(
                f"Insufficient CPU: {cpu_free:.1f}% free (need {min_cpu_free}%)"
            )
            return False
        
        if memory_available < min_memory_mb:
            logger.warning(
                f"Insufficient memory: {memory_available:.1f}MB free (need {min_memory_mb}MB)"
            )
            return False
        
        return True
    
    def get_metrics_summary(self, duration_minutes: int = 5) -> Dict:
        """
        Get statistical summary of recent metrics.
        
        Args:
            duration_minutes: Look back window in minutes
        
        Returns:
            Dictionary with min/max/avg for each metric
        """
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        recent_metrics = [
            m for m in self._metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return {'error': 'No metrics available'}
        
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        
        return {
            'timeframe_minutes': duration_minutes,
            'samples': len(recent_metrics),
            'cpu': {
                'min': min(cpu_values),
                'max': max(cpu_values),
                'avg': sum(cpu_values) / len(cpu_values)
            },
            'memory': {
                'min': min(memory_values),
                'max': max(memory_values),
                'avg': sum(memory_values) / len(memory_values)
            },
            'current': self.get_current_metrics().to_dict()
        }
    
    def get_history(self, count: Optional[int] = None) -> List[Dict]:
        """
        Get recent metrics history.
        
        Args:
            count: Number of recent entries (None for all)
        
        Returns:
            List of metric dictionaries
        """
        history = self._metrics_history[-count:] if count else self._metrics_history
        return [m.to_dict() for m in history]


# Singleton instance and lock for thread safety
_resource_monitor: Optional[ResourceMonitor] = None
_resource_monitor_lock = threading.Lock()


def get_resource_monitor() -> ResourceMonitor:
    """
    Get global resource monitor singleton.

    Initializes with configuration from environment variables if not already created.
    Thread-safe using double-checked locking pattern.

    Returns:
        ResourceMonitor singleton instance
    """
    global _resource_monitor

    # First check without lock for performance
    if _resource_monitor is None:
        with _resource_monitor_lock:
            # Double-check pattern: check again inside lock
            if _resource_monitor is None:
                import os

                # Load configuration from environment, with fallback defaults
                # Convert to float if get_secret returns a value
                cpu_warning = get_secret('resource_cpu_warning')
                cpu_warning = float(cpu_warning) if cpu_warning else 70.0
                
                cpu_critical = get_secret('resource_cpu_critical')
                cpu_critical = float(cpu_critical) if cpu_critical else 90.0
                
                memory_warning = get_secret('resource_memory_warning')
                memory_warning = float(memory_warning) if memory_warning else 75.0
                
                memory_critical = get_secret('resource_memory_critical')
                memory_critical = float(memory_critical) if memory_critical else 90.0

                thresholds = ResourceThresholds(
                    cpu_warning=cpu_warning,
                    cpu_critical=cpu_critical,
                    memory_warning=memory_warning,
                    memory_critical=memory_critical,
                )

                monitoring_enabled = get_secret('resource_monitoring_enabled')

                _resource_monitor = ResourceMonitor(
                    thresholds=thresholds,
                    monitoring_enabled=monitoring_enabled
                )

    return _resource_monitor
