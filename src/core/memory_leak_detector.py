"""
Memory Leak Detection for AstraGuard

Tracks memory growth patterns to detect potential memory leaks.
Monitors process memory usage over time and alerts on sustained growth.
"""

import logging
import psutil
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class MemorySample:
    """Memory usage sample"""
    timestamp: datetime
    memory_mb: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "memory_mb": round(self.memory_mb, 2)
        }


@dataclass
class LeakReport:
    """Memory leak detection report"""
    is_leaking: bool
    growth_rate_mb_per_hour: float
    samples_analyzed: int
    current_memory_mb: float
    baseline_memory_mb: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_leaking": self.is_leaking,
            "growth_rate_mb_per_hour": round(self.growth_rate_mb_per_hour, 2),
            "samples_analyzed": self.samples_analyzed,
            "current_memory_mb": round(self.current_memory_mb, 2),
            "baseline_memory_mb": round(self.baseline_memory_mb, 2),
            "timestamp": self.timestamp.isoformat()
        }


class MemoryLeakDetector:
    """
    Detect potential memory leaks by tracking memory growth patterns.
    
    Features:
    - Track memory usage over time
    - Calculate growth rate
    - Alert on sustained memory growth
    - Configurable thresholds
    """
    
    def __init__(
        self,
        sample_interval_seconds: float = 60.0,
        max_samples: int = 60,
        leak_threshold_mb_per_hour: float = 10.0
    ):
        """
        Initialize memory leak detector.
        
        Args:
            sample_interval_seconds: How often to sample memory
            max_samples: Maximum number of samples to retain
            leak_threshold_mb_per_hour: Growth rate threshold for leak detection
        """
        self.sample_interval = sample_interval_seconds
        self.max_samples = max_samples
        self.leak_threshold = leak_threshold_mb_per_hour
        
        self._samples: deque = deque(maxlen=max_samples)
        self._process = psutil.Process()
        self._lock = threading.Lock()
        
        logger.info(
            f"MemoryLeakDetector initialized: "
            f"interval={sample_interval_seconds}s, "
            f"max_samples={max_samples}, "
            f"threshold={leak_threshold_mb_per_hour}MB/h"
        )
    
    def sample_memory(self) -> MemorySample:
        """
        Take a memory usage sample.
        
        Returns:
            MemorySample with current memory usage
        """
        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        
        sample = MemorySample(
            timestamp=datetime.now(),
            memory_mb=memory_mb
        )
        
        with self._lock:
            self._samples.append(sample)
        
        logger.debug(f"Memory sample: {memory_mb:.2f}MB")
        return sample
    
    def detect_leak(self) -> LeakReport:
        """
        Detect memory leaks based on growth rate.
        
        Returns:
            LeakReport with detection results
        """
        with self._lock:
            if len(self._samples) < 2:
                # Not enough data
                current_mem = self._samples[-1].memory_mb if self._samples else 0.0
                return LeakReport(
                    is_leaking=False,
                    growth_rate_mb_per_hour=0.0,
                    samples_analyzed=len(self._samples),
                    current_memory_mb=current_mem,
                    baseline_memory_mb=current_mem
                )
            
            # Calculate growth rate using linear regression
            samples_list = list(self._samples)
            growth_rate = self._calculate_growth_rate(samples_list)
            
            baseline_mb = samples_list[0].memory_mb
            current_mb = samples_list[-1].memory_mb
            
            is_leaking = growth_rate > self.leak_threshold
            
            if is_leaking:
                logger.warning(
                    f"Memory leak detected! Growth rate: {growth_rate:.2f}MB/h "
                    f"(threshold: {self.leak_threshold}MB/h)"
                )
            
            return LeakReport(
                is_leaking=is_leaking,
                growth_rate_mb_per_hour=growth_rate,
                samples_analyzed=len(samples_list),
                current_memory_mb=current_mb,
                baseline_memory_mb=baseline_mb
            )
    
    def _calculate_growth_rate(self, samples: List[MemorySample]) -> float:
        """
        Calculate memory growth rate in MB/hour using linear regression.
        
        Args:
            samples: List of memory samples
            
        Returns:
            Growth rate in MB/hour
        """
        if len(samples) < 2:
            return 0.0
        
        # Convert timestamps to hours since first sample
        first_time = samples[0].timestamp
        times = [(s.timestamp - first_time).total_seconds() / 3600.0 for s in samples]
        memories = [s.memory_mb for s in samples]
        
        # Simple linear regression: y = mx + b
        n = len(samples)
        sum_x = sum(times)
        sum_y = sum(memories)
        sum_xy = sum(t * m for t, m in zip(times, memories))
        sum_x2 = sum(t * t for t in times)
        
        # Calculate slope (growth rate)
        if n * sum_x2 - sum_x * sum_x == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        return slope
    
    def get_samples(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recent memory samples.
        
        Args:
            count: Number of recent samples (None for all)
            
        Returns:
            List of sample dictionaries
        """
        with self._lock:
            samples = list(self._samples)
            if count:
                samples = samples[-count:]
            return [s.to_dict() for s in samples]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get memory leak detection statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            if not self._samples:
                return {
                    "total_samples": 0,
                    "current_memory_mb": 0.0,
                    "min_memory_mb": 0.0,
                    "max_memory_mb": 0.0,
                    "avg_memory_mb": 0.0
                }
            
            samples_list = list(self._samples)
            memories = [s.memory_mb for s in samples_list]
            
            return {
                "total_samples": len(samples_list),
                "current_memory_mb": round(memories[-1], 2),
                "min_memory_mb": round(min(memories), 2),
                "max_memory_mb": round(max(memories), 2),
                "avg_memory_mb": round(sum(memories) / len(memories), 2),
                "sample_interval_seconds": self.sample_interval,
                "leak_threshold_mb_per_hour": self.leak_threshold
            }
    
    def reset(self):
        """Clear all samples."""
        with self._lock:
            self._samples.clear()
        logger.info("Memory leak detector reset")


# Global singleton instance
_memory_leak_detector: Optional[MemoryLeakDetector] = None
_detector_lock = threading.Lock()


def get_memory_leak_detector() -> MemoryLeakDetector:
    """
    Get global memory leak detector singleton.
    
    Returns:
        MemoryLeakDetector instance
    """
    global _memory_leak_detector
    
    if _memory_leak_detector is None:
        with _detector_lock:
            if _memory_leak_detector is None:
                _memory_leak_detector = MemoryLeakDetector()
    
    return _memory_leak_detector
