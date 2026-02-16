"""
Tests for Memory Leak Detection (Issue #677)
"""

import pytest
import time
from src.core.memory_leak_detector import (
    MemoryLeakDetector,
    MemorySample,
    LeakReport,
    get_memory_leak_detector
)


class TestMemorySample:
    """Test MemorySample dataclass"""
    
    def test_creation(self):
        """Test sample creation"""
        from datetime import datetime
        now = datetime.now()
        sample = MemorySample(timestamp=now, memory_mb=100.5)
        assert sample.timestamp == now
        assert sample.memory_mb == 100.5
    
    def test_to_dict(self):
        """Test sample serialization"""
        from datetime import datetime
        sample = MemorySample(timestamp=datetime.now(), memory_mb=100.5)
        data = sample.to_dict()
        assert "timestamp" in data
        assert data["memory_mb"] == 100.5


class TestMemoryLeakDetector:
    """Test MemoryLeakDetector class"""
    
    @pytest.fixture
    def detector(self):
        """Create a memory leak detector for testing"""
        return MemoryLeakDetector(
            sample_interval_seconds=1.0,
            max_samples=10,
            leak_threshold_mb_per_hour=5.0
        )
    
    def test_initialization(self, detector):
        """Test detector initialization"""
        assert detector.sample_interval == 1.0
        assert detector.max_samples == 10
        assert detector.leak_threshold == 5.0
    
    def test_sample_memory(self, detector):
        """Test memory sampling"""
        sample = detector.sample_memory()
        assert sample.memory_mb > 0
        assert len(detector._samples) == 1
    
    def test_multiple_samples(self, detector):
        """Test taking multiple samples"""
        for _ in range(5):
            detector.sample_memory()
            time.sleep(0.01)
        
        assert len(detector._samples) == 5
    
    def test_max_samples_limit(self, detector):
        """Test that samples are limited to max_samples"""
        for _ in range(15):
            detector.sample_memory()
        
        assert len(detector._samples) == 10  # max_samples
    
    def test_detect_leak_insufficient_data(self, detector):
        """Test leak detection with insufficient data"""
        detector.sample_memory()
        report = detector.detect_leak()
        assert report.is_leaking is False
        assert report.samples_analyzed == 1
    
    def test_detect_leak_no_leak(self, detector):
        """Test leak detection when no leak exists"""
        # Take samples with stable memory
        for _ in range(5):
            detector.sample_memory()
            time.sleep(0.01)
        
        report = detector.detect_leak()
        # Growth rate should be low for stable memory
        assert report.samples_analyzed == 5
    
    def test_get_samples(self, detector):
        """Test getting samples"""
        detector.sample_memory()
        detector.sample_memory()
        
        samples = detector.get_samples()
        assert len(samples) == 2
        assert all("timestamp" in s for s in samples)
        assert all("memory_mb" in s for s in samples)
    
    def test_get_samples_with_count(self, detector):
        """Test getting limited number of samples"""
        for _ in range(5):
            detector.sample_memory()
        
        samples = detector.get_samples(count=3)
        assert len(samples) == 3
    
    def test_get_statistics(self, detector):
        """Test getting statistics"""
        detector.sample_memory()
        time.sleep(0.01)
        detector.sample_memory()
        
        stats = detector.get_statistics()
        assert stats["total_samples"] == 2
        assert stats["current_memory_mb"] > 0
        assert stats["min_memory_mb"] > 0
        assert stats["max_memory_mb"] > 0
        assert stats["avg_memory_mb"] > 0
    
    def test_reset(self, detector):
        """Test resetting detector"""
        detector.sample_memory()
        detector.sample_memory()
        assert len(detector._samples) > 0
        
        detector.reset()
        assert len(detector._samples) == 0


class TestMemoryLeakDetectorSingleton:
    """Test singleton pattern"""
    
    def test_singleton(self):
        """Test that get_memory_leak_detector returns singleton"""
        detector1 = get_memory_leak_detector()
        detector2 = get_memory_leak_detector()
        assert detector1 is detector2
