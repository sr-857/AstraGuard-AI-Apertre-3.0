"""
Migration Monitoring System.

Provides real-time monitoring of migration progress, performance impact,
and data integrity during zero-downtime migrations.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Set
from collections import deque
import aiosqlite

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of migration metrics."""
    PERFORMANCE = "performance"
    INTEGRITY = "integrity"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    LATENCY = "latency"


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: datetime
    metric_type: MetricType
    value: float
    unit: str
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MigrationMetrics:
    """Aggregated migration metrics."""
    migration_version: str
    start_time: datetime
    end_time: Optional[datetime] = None
    performance_impact_percent: float = 0.0
    data_integrity_score: float = 100.0
    throughput_ops_per_sec: float = 0.0
    error_rate_percent: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    total_operations: int = 0
    failed_operations: int = 0
    consistency_violations: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "migration_version": self.migration_version,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "performance_impact_percent": self.performance_impact_percent,
            "data_integrity_score": self.data_integrity_score,
            "throughput_ops_per_sec": self.throughput_ops_per_sec,
            "error_rate_percent": self.error_rate_percent,
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "total_operations": self.total_operations,
            "failed_operations": self.failed_operations,
            "consistency_violations": self.consistency_violations,
        }


class MigrationMonitor:
    """
    Monitors migration progress and health in real-time.
    
    Tracks performance impact, data integrity, and operational metrics
    to ensure migration stays within acceptable thresholds.
    """
    
    # Performance threshold (5% as per requirements)
    PERFORMANCE_THRESHOLD = 5.0
    
    # Data integrity threshold (must maintain 100%)
    INTEGRITY_THRESHOLD = 100.0
    
    # Error rate threshold (1%)
    ERROR_RATE_THRESHOLD = 1.0
    
    def __init__(
        self,
        migration_version: str,
        metrics_window_size: int = 1000,
        alert_callbacks: Optional[List[Callable]] = None,
    ):
        """
        Initialize migration monitor.
        
        Args:
            migration_version: Version being monitored
            metrics_window_size: Size of rolling metrics window
            alert_callbacks: List of alert callback functions
        """
        self.migration_version = migration_version
        self.metrics_window_size = metrics_window_size
        self.alert_callbacks = alert_callbacks or []
        
        self._metrics: deque = deque(maxlen=metrics_window_size)
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._baseline_performance: Optional[Dict[str, float]] = None
        self._monitoring = False
        self._alert_thresholds: Dict[MetricType, float] = {
            MetricType.PERFORMANCE: self.PERFORMANCE_THRESHOLD,
            MetricType.INTEGRITY: self.INTEGRITY_THRESHOLD,
            MetricType.ERROR_RATE: self.ERROR_RATE_THRESHOLD,
        }
        self._violation_count: Dict[MetricType, int] = {
            metric: 0 for metric in MetricType
        }
    
    def start_monitoring(self) -> None:
        """Start monitoring."""
        self._start_time = datetime.now()
        self._monitoring = True
        logger.info(f"Started monitoring migration {self.migration_version}")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self._end_time = datetime.now()
        self._monitoring = False
        logger.info(f"Stopped monitoring migration {self.migration_version}")
    
    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        unit: str = "",
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Record a metric point.
        
        Args:
            metric_type: Type of metric
            value: Metric value
            unit: Unit of measurement
            labels: Additional labels
        """
        if not self._monitoring:
            return
        
        point = MetricPoint(
            timestamp=datetime.now(),
            metric_type=metric_type,
            value=value,
            unit=unit,
            labels=labels or {},
        )
        
        self._metrics.append(point)
        
        # Check thresholds and alert if exceeded
        self._check_thresholds(metric_type, value)
    
    def _check_thresholds(self, metric_type: MetricType, value: float) -> None:
        """Check if metric exceeds thresholds."""
        threshold = self._alert_thresholds.get(metric_type)
        if threshold is None:
            return
        
        exceeded = False
        
        if metric_type == MetricType.PERFORMANCE:
            exceeded = value > threshold
        elif metric_type == MetricType.INTEGRITY:
            exceeded = value < threshold  # Integrity should stay at 100%
        elif metric_type == MetricType.ERROR_RATE:
            exceeded = value > threshold
        
        if exceeded:
            self._violation_count[metric_type] += 1
            self._trigger_alert(metric_type, value, threshold)
    
    def _trigger_alert(
        self,
        metric_type: MetricType,
        value: float,
        threshold: float,
    ) -> None:
        """Trigger alert callbacks."""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "migration_version": self.migration_version,
            "metric_type": metric_type.value,
            "value": value,
            "threshold": threshold,
            "message": f"{metric_type.value} threshold exceeded: {value:.2f} (threshold: {threshold:.2f})",
        }
        
        logger.warning(alert["message"])
        
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def record_operation(
        self,
        duration_ms: float,
        success: bool,
        consistency_verified: bool = True,
    ) -> None:
        """
        Record an operation for metrics.
        
        Args:
            duration_ms: Operation duration in milliseconds
            success: Whether operation succeeded
            consistency_verified: Whether consistency was verified
        """
        self.record_metric(MetricType.LATENCY, duration_ms, "ms")
        
        if not success:
            self.record_metric(MetricType.ERROR_RATE, 1.0, "count")
        
        if not consistency_verified:
            self.record_metric(MetricType.INTEGRITY, 0.0, "violation")
    
    def set_baseline(self, baseline: Dict[str, float]) -> None:
        """
        Set baseline performance metrics.
        
        Args:
            baseline: Baseline metrics dictionary
        """
        self._baseline_performance = baseline
        logger.info(f"Baseline performance set: {baseline}")
    
    def get_current_metrics(self) -> MigrationMetrics:
        """
        Get current aggregated metrics.
        
        Returns:
            Current migration metrics
        """
        if not self._metrics:
            return MigrationMetrics(
                migration_version=self.migration_version,
                start_time=self._start_time or datetime.now(),
            )
        
        # Calculate metrics from recorded points
        latency_values = [
            m.value for m in self._metrics 
            if m.metric_type == MetricType.LATENCY
        ]
        
        error_count = sum(
            1 for m in self._metrics 
            if m.metric_type == MetricType.ERROR_RATE
        )
        
        integrity_violations = sum(
            1 for m in self._metrics 
            if m.metric_type == MetricType.INTEGRITY and m.value == 0.0
        )
        
        total_ops = len(latency_values)
        
        # Calculate percentiles
        if latency_values:
            sorted_latencies = sorted(latency_values)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p99_idx = int(len(sorted_latencies) * 0.99)
            
            avg_latency = sum(latency_values) / len(latency_values)
            p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]
            p99_latency = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)]
        else:
            avg_latency = p95_latency = p99_latency = 0.0
        
        # Calculate throughput
        duration_seconds = (
            (datetime.now() - self._start_time).total_seconds() 
            if self._start_time else 1.0
        )
        throughput = total_ops / duration_seconds if duration_seconds > 0 else 0.0
        
        # Calculate performance impact
        performance_impact = 0.0
        if self._baseline_performance and "query_time_ms" in self._baseline_performance:
            baseline = self._baseline_performance["query_time_ms"]
            if baseline > 0 and avg_latency > 0:
                performance_impact = ((avg_latency - baseline) / baseline) * 100
        
        # Calculate data integrity score
        total_integrity_checks = total_ops
        integrity_score = (
            ((total_integrity_checks - integrity_violations) / total_integrity_checks * 100)
            if total_integrity_checks > 0 else 100.0
        )
        
        return MigrationMetrics(
            migration_version=self.migration_version,
            start_time=self._start_time or datetime.now(),
            end_time=self._end_time,
            performance_impact_percent=performance_impact,
            data_integrity_score=integrity_score,
            throughput_ops_per_sec=throughput,
            error_rate_percent=(error_count / total_ops * 100) if total_ops > 0 else 0.0,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            total_operations=total_ops,
            failed_operations=error_count,
            consistency_violations=integrity_violations,
        )
    
    def is_healthy(self) -> bool:
        """
        Check if migration is healthy.
        
        Returns:
            True if all metrics are within thresholds
        """
        metrics = self.get_current_metrics()
        
        return (
            metrics.performance_impact_percent <= self.PERFORMANCE_THRESHOLD and
            metrics.data_integrity_score >= self.INTEGRITY_THRESHOLD and
            metrics.error_rate_percent <= self.ERROR_RATE_THRESHOLD
        )
    
    def get_violations(self) -> Dict[MetricType, int]:
        """
        Get count of threshold violations.
        
        Returns:
            Dictionary of violation counts by metric type
        """
        return self._violation_count.copy()
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive monitoring report.
        
        Returns:
            Report dictionary
        """
        metrics = self.get_current_metrics()
        
        return {
            "migration_version": self.migration_version,
            "monitoring_period": {
                "start": self._start_time.isoformat() if self._start_time else None,
                "end": self._end_time.isoformat() if self._end_time else None,
                "duration_seconds": (
                    (self._end_time - self._start_time).total_seconds()
                    if self._end_time and self._start_time
                    else (datetime.now() - self._start_time).total_seconds()
                    if self._start_time
                    else 0
                ),
            },
            "metrics": metrics.to_dict(),
            "health_status": "healthy" if self.is_healthy() else "unhealthy",
            "violations": {
                metric.value: count 
                for metric, count in self._violation_count.items()
            },
            "thresholds": {
                metric.value: threshold 
                for metric, threshold in self._alert_thresholds.items()
            },
        }
    
    async def export_metrics(self, db_path: str) -> None:
        """
        Export metrics to database for persistence.
        
        Args:
            db_path: Path to SQLite database
        """
        report = self.generate_report()
        
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS migration_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_version TEXT,
                    timestamp TEXT,
                    metrics_json TEXT
                )
            """)
            
            await db.execute(
                "INSERT INTO migration_metrics (migration_version, timestamp, metrics_json) VALUES (?, ?, ?)",
                (
                    self.migration_version,
                    datetime.now().isoformat(),
                    json.dumps(report),
                )
            )
            await db.commit()
        
        logger.info(f"Exported metrics for migration {self.migration_version}")


class MigrationDashboard:
    """
    Real-time dashboard for migration monitoring.
    
    Provides live updates of migration progress and health.
    """
    
    def __init__(self):
        """Initialize dashboard."""
        self._monitors: Dict[str, MigrationMonitor] = {}
        self._update_callbacks: List[Callable] = []
    
    def register_monitor(self, monitor: MigrationMonitor) -> None:
        """Register a monitor with the dashboard."""
        self._monitors[monitor.migration_version] = monitor
        logger.info(f"Registered monitor for {monitor.migration_version}")
    
    def unregister_monitor(self, version: str) -> None:
        """Unregister a monitor."""
        if version in self._monitors:
            del self._monitors[version]
    
    def on_update(self, callback: Callable) -> None:
        """Register update callback."""
        self._update_callbacks.append(callback)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all monitored migrations.
        
        Returns:
            Summary dictionary
        """
        return {
            "active_migrations": len(self._monitors),
            "migrations": {
                version: {
                    "healthy": monitor.is_healthy(),
                    "metrics": monitor.get_current_metrics().to_dict(),
                }
                for version, monitor in self._monitors.items()
            },
            "timestamp": datetime.now().isoformat(),
        }
    
    def get_unhealthy_migrations(self) -> List[str]:
        """
        Get list of unhealthy migrations.
        
        Returns:
            List of migration versions
        """
        return [
            version for version, monitor in self._monitors.items()
            if not monitor.is_healthy()
        ]
