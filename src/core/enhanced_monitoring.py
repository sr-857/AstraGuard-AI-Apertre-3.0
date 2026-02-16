"""
System Monitoring Enhancements for AstraGuard

Extends resource_monitor.py with additional monitoring capabilities:
- Resource utilization tracking and trends
- Temperature monitoring (CPU/GPU)
- Disk space monitoring per partition
- Automated cleanup functionality
"""

import logging
import psutil
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import deque
import os
import glob

logger = logging.getLogger(__name__)


@dataclass
class UtilizationTrend:
    """Resource utilization trend data"""
    resource_type: str
    avg_utilization: float
    min_utilization: float
    max_utilization: float
    trend_direction: str  # "increasing", "decreasing", "stable"
    samples_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "avg_utilization": round(self.avg_utilization, 2),
            "min_utilization": round(self.min_utilization, 2),
            "max_utilization": round(self.max_utilization, 2),
            "trend_direction": self.trend_direction,
            "samples_count": self.samples_count
        }


class EnhancedResourceMonitor:
    """
    Enhanced resource monitoring with trends, temperature, and disk space.
    
    Addresses issues #682-#685:
    - #682: Resource utilization tracking
    - #683: Temperature monitoring
    - #684: Disk space monitoring
    - #685: Automated cleanup
    """
    
    def __init__(self, history_size: int = 100):
        """Initialize enhanced monitor."""
        self._cpu_history: deque = deque(maxlen=history_size)
        self._memory_history: deque = deque(maxlen=history_size)
        self._lock = threading.Lock()
        
        logger.info("EnhancedResourceMonitor initialized")
    
    # Issue #682: Resource Utilization Tracking
    def get_utilization_trends(self, window_minutes: int = 60) -> Dict[str, UtilizationTrend]:
        """
        Get resource utilization trends over time window.
        
        Args:
            window_minutes: Time window for trend analysis
            
        Returns:
            Dictionary of trends by resource type
        """
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        
        with self._lock:
            # Filter samples within window
            cpu_samples = [s for s in self._cpu_history if s["timestamp"] >= cutoff]
            mem_samples = [s for s in self._memory_history if s["timestamp"] >= cutoff]
            
            trends = {}
            
            # CPU trend
            if cpu_samples:
                cpu_values = [s["value"] for s in cpu_samples]
                trends["cpu"] = self._calculate_trend("cpu", cpu_values)
            
            # Memory trend
            if mem_samples:
                mem_values = [s["value"] for s in mem_samples]
                trends["memory"] = self._calculate_trend("memory", mem_values)
            
            return trends
    
    def _calculate_trend(self, resource_type: str, values: List[float]) -> UtilizationTrend:
        """Calculate trend from values."""
        if not values:
            return UtilizationTrend(resource_type, 0, 0, 0, "stable", 0)
        
        avg = sum(values) / len(values)
        min_val = min(values)
        max_val = max(values)
        
        # Simple trend detection: compare first half to second half
        mid = len(values) // 2
        if mid > 0:
            first_half_avg = sum(values[:mid]) / mid
            second_half_avg = sum(values[mid:]) / (len(values) - mid)
            
            if second_half_avg > first_half_avg * 1.1:
                direction = "increasing"
            elif second_half_avg < first_half_avg * 0.9:
                direction = "decreasing"
            else:
                direction = "stable"
        else:
            direction = "stable"
        
        return UtilizationTrend(resource_type, avg, min_val, max_val, direction, len(values))
    
    def track_utilization(self):
        """Track current utilization (call periodically)."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
        
        with self._lock:
            self._cpu_history.append({
                "timestamp": datetime.now(),
                "value": cpu_percent
            })
            self._memory_history.append({
                "timestamp": datetime.now(),
                "value": memory_percent
            })
    
    # Issue #683: Temperature Monitoring
    def get_temperature_metrics(self) -> Dict[str, Any]:
        """
        Get CPU/GPU temperature metrics.
        
        Returns:
            Temperature data by sensor
        """
        temps = {}
        
        try:
            # Try to get temperature sensors
            if hasattr(psutil, "sensors_temperatures"):
                sensors = psutil.sensors_temperatures()
                
                for name, entries in sensors.items():
                    temps[name] = []
                    for entry in entries:
                        temps[name].append({
                            "label": entry.label or "unknown",
                            "current": entry.current,
                            "high": entry.high if entry.high else None,
                            "critical": entry.critical if entry.critical else None
                        })
            else:
                logger.warning("Temperature sensors not available on this platform")
                
        except Exception as e:
            logger.error(f"Error reading temperature sensors: {e}")
        
        return {
            "temperatures": temps,
            "timestamp": datetime.now().isoformat(),
            "available": len(temps) > 0
        }
    
    # Issue #684: Disk Space Monitoring
    def get_disk_space_by_partition(self) -> List[Dict[str, Any]]:
        """
        Get disk space usage by partition.
        
        Returns:
            List of partition usage data
        """
        partitions = []
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partitions.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent_used": usage.percent
                })
            except PermissionError:
                # Skip partitions we can't access
                continue
        
        return partitions
    
    # Issue #685: Automated Cleanup
    def run_automated_cleanup(
        self,
        temp_dirs: Optional[List[str]] = None,
        log_retention_days: int = 7,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Run automated cleanup of temp files and old logs.
        
        Args:
            temp_dirs: Directories to clean (default: system temp)
            log_retention_days: Keep logs newer than this
            dry_run: If True, don't actually delete files
            
        Returns:
            Cleanup results
        """
        results = {
            "files_deleted": 0,
            "space_freed_mb": 0,
            "errors": []
        }
        
        # Default temp directories
        if temp_dirs is None:
            temp_dirs = [
                os.path.join(os.path.expanduser("~"), "tmp"),
                "/tmp" if os.path.exists("/tmp") else None,
                os.environ.get("TEMP"),
                os.environ.get("TMP")
            ]
            temp_dirs = [d for d in temp_dirs if d and os.path.exists(d)]
        
        cutoff_time = datetime.now() - timedelta(days=log_retention_days)
        
        for temp_dir in temp_dirs:
            try:
                # Clean old log files
                log_pattern = os.path.join(temp_dir, "*.log")
                for log_file in glob.glob(log_pattern):
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                        if mtime < cutoff_time:
                            size = os.path.getsize(log_file)
                            if not dry_run:
                                os.remove(log_file)
                            results["files_deleted"] += 1
                            results["space_freed_mb"] += size / (1024 * 1024)
                    except Exception as e:
                        results["errors"].append(f"Error deleting {log_file}: {e}")
                        
            except Exception as e:
                results["errors"].append(f"Error cleaning {temp_dir}: {e}")
        
        results["space_freed_mb"] = round(results["space_freed_mb"], 2)
        logger.info(
            f"Cleanup completed: {results['files_deleted']} files, "
            f"{results['space_freed_mb']}MB freed"
        )
        
        return results


# Global singleton
_enhanced_monitor: Optional[EnhancedResourceMonitor] = None
_monitor_lock = threading.Lock()


def get_enhanced_monitor() -> EnhancedResourceMonitor:
    """Get global enhanced monitor singleton."""
    global _enhanced_monitor
    if _enhanced_monitor is None:
        with _monitor_lock:
            if _enhanced_monitor is None:
                _enhanced_monitor = EnhancedResourceMonitor()
    return _enhanced_monitor
