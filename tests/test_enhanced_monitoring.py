"""Tests for Enhanced Monitoring (#682-#685)"""

import pytest
from src.core.enhanced_monitoring import (
    EnhancedResourceMonitor,
    get_enhanced_monitor
)


class TestEnhancedResourceMonitor:
    @pytest.fixture
    def monitor(self):
        return EnhancedResourceMonitor()
    
    def test_track_utilization(self, monitor):
        monitor.track_utilization()
        assert len(monitor._cpu_history) > 0
        assert len(monitor._memory_history) > 0
    
    def test_get_utilization_trends(self, monitor):
        # Track some data
        for _ in range(5):
            monitor.track_utilization()
        
        trends = monitor.get_utilization_trends(window_minutes=1)
        assert "cpu" in trends or "memory" in trends
    
    def test_get_temperature_metrics(self, monitor):
        temps = monitor.get_temperature_metrics()
        assert "temperatures" in temps
        assert "available" in temps
    
    def test_get_disk_space_by_partition(self, monitor):
        partitions = monitor.get_disk_space_by_partition()
        assert isinstance(partitions, list)
        if partitions:
            assert "mountpoint" in partitions[0]
            assert "percent_used" in partitions[0]
    
    def test_run_automated_cleanup_dry_run(self, monitor):
        results = monitor.run_automated_cleanup(dry_run=True)
        assert "files_deleted" in results
        assert "space_freed_mb" in results
    
    def test_singleton(self):
        m1 = get_enhanced_monitor()
        m2 = get_enhanced_monitor()
        assert m1 is m2
