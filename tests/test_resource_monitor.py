"""
Tests for resource monitoring functionality.

Validates:
- Resource metrics collection
- Threshold detection and alerts
- Warning/critical state transitions
- Historical metrics tracking
"""

import pytest
import psutil
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from core.resource_monitor import (
    ResourceMonitor,
    ResourceMetrics,
    ResourceThresholds,
    ResourceStatus,
    get_resource_monitor,
)


class TestResourceMetrics:
    """Test resource metrics dataclass"""
    
    def test_metrics_creation(self):
        """Test creating resource metrics"""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_percent=60.0,
            memory_available_mb=1024.0,
            disk_usage_percent=70.0,
            process_memory_mb=100.0
        )
        
        assert metrics.cpu_percent == 50.0
        assert metrics.memory_percent == 60.0
        assert metrics.timestamp is not None
    
    def test_metrics_to_dict(self):
        """Test metrics serialization to dict"""
        metrics = ResourceMetrics(
            cpu_percent=50.5,
            memory_percent=60.7,
            memory_available_mb=1024.3,
            disk_usage_percent=70.2,
            process_memory_mb=100.1
        )
        
        data = metrics.to_dict()
        
        assert 'cpu_percent' in data
        assert 'memory_percent' in data
        assert 'timestamp' in data
        assert data['cpu_percent'] == 50.5
        assert isinstance(data['timestamp'], str)


class TestResourceThresholds:
    """Test threshold configuration"""
    
    def test_default_thresholds(self):
        """Test default threshold values"""
        thresholds = ResourceThresholds()
        
        assert thresholds.cpu_warning == 70.0
        assert thresholds.cpu_critical == 90.0
        assert thresholds.memory_warning == 75.0
        assert thresholds.memory_critical == 90.0
    
    def test_custom_thresholds(self):
        """Test custom threshold configuration"""
        thresholds = ResourceThresholds(
            cpu_warning=60.0,
            cpu_critical=80.0,
            memory_warning=65.0,
            memory_critical=85.0
        )
        
        assert thresholds.cpu_warning == 60.0
        assert thresholds.cpu_critical == 80.0


class TestResourceMonitor:
    """Test resource monitor"""
    
    def test_monitor_initialization(self):
        """Test monitor initialization"""
        monitor = ResourceMonitor()
        
        assert monitor.thresholds is not None
        assert monitor.monitoring_enabled is True
    
    def test_monitor_with_custom_thresholds(self):
        """Test monitor with custom thresholds"""
        thresholds = ResourceThresholds(cpu_warning=60.0)
        monitor = ResourceMonitor(thresholds=thresholds)
        
        assert monitor.thresholds.cpu_warning == 60.0
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_get_current_metrics(self, mock_disk, mock_memory, mock_cpu):
        """Test collecting current metrics"""
        # Mock psutil responses
        mock_cpu.return_value = 45.0
        mock_memory.return_value = Mock(
            percent=55.0,
            available=1024 * 1024 * 1024  # 1GB
        )
        mock_disk.return_value = Mock(percent=65.0)
        
        monitor = ResourceMonitor()
        metrics = monitor.get_current_metrics()
        
        assert metrics.cpu_percent == 45.0
        assert metrics.memory_percent == 55.0
        assert metrics.disk_usage_percent == 65.0
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_check_resource_health_healthy(self, mock_disk, mock_memory, mock_cpu):
        """Test resource health check - healthy state"""
        # Mock healthy values
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(
            percent=50.0,
            available=2048 * 1024 * 1024
        )
        mock_disk.return_value = Mock(percent=50.0)
        
        monitor = ResourceMonitor()
        status = monitor.check_resource_health()
        
        assert status['overall'] == ResourceStatus.HEALTHY.value
        assert status['cpu'] == ResourceStatus.HEALTHY.value
        assert status['memory'] == ResourceStatus.HEALTHY.value
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_check_resource_health_warning(self, mock_disk, mock_memory, mock_cpu):
        """Test resource health check - warning state"""
        # Mock warning-level CPU
        mock_cpu.return_value = 75.0  # Above 70% threshold
        mock_memory.return_value = Mock(
            percent=50.0,
            available=2048 * 1024 * 1024
        )
        mock_disk.return_value = Mock(percent=50.0)
        
        monitor = ResourceMonitor()
        status = monitor.check_resource_health()
        
        assert status['overall'] == ResourceStatus.WARNING.value
        assert status['cpu'] == ResourceStatus.WARNING.value
        assert status['memory'] == ResourceStatus.HEALTHY.value
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_check_resource_health_critical(self, mock_disk, mock_memory, mock_cpu):
        """Test resource health check - critical state"""
        # Mock critical-level memory
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(
            percent=95.0,  # Above 90% threshold
            available=100 * 1024 * 1024
        )
        mock_disk.return_value = Mock(percent=50.0)
        
        monitor = ResourceMonitor()
        status = monitor.check_resource_health()
        
        assert status['overall'] == ResourceStatus.CRITICAL.value
        assert status['memory'] == ResourceStatus.CRITICAL.value
        assert status['cpu'] == ResourceStatus.HEALTHY.value
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_is_resource_available(self, mock_disk, mock_memory, mock_cpu):
        """Test resource availability check"""
        mock_cpu.return_value = 70.0  # 30% free
        mock_memory.return_value = Mock(
            percent=60.0,
            available=500 * 1024 * 1024  # 500MB
        )
        mock_disk.return_value = Mock(percent=50.0)
        
        monitor = ResourceMonitor()
        
        # Should have enough resources
        assert monitor.is_resource_available(
            min_cpu_free=20.0,  # Need 20% free, have 30%
            min_memory_mb=100.0  # Need 100MB, have 500MB
        ) is True
        
        # Should not have enough CPU
        assert monitor.is_resource_available(
            min_cpu_free=40.0,  # Need 40% free, have 30%
            min_memory_mb=100.0
        ) is False
    
    def test_metrics_history(self):
        """Test metrics history tracking"""
        monitor = ResourceMonitor(history_size=3)
        
        # Add metrics to history
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory', return_value=Mock(percent=50.0, available=1024*1024*1024)), \
             patch('psutil.disk_usage', return_value=Mock(percent=50.0)):
            
            monitor.get_current_metrics()
            monitor.get_current_metrics()
            monitor.get_current_metrics()
            monitor.get_current_metrics()  # Exceeds size
        
        history = monitor.get_history()
        
        # Should only keep last 3
        assert len(history) == 3
    
    def test_get_metrics_summary(self):
        """Test metrics summary generation"""
        monitor = ResourceMonitor()
        
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory', return_value=Mock(percent=60.0, available=1024*1024*1024)), \
             patch('psutil.disk_usage', return_value=Mock(percent=50.0)):
            
            # Collect some metrics
            monitor.get_current_metrics()
            monitor.get_current_metrics()
        
        summary = monitor.get_metrics_summary(duration_minutes=5)
        
        assert 'cpu' in summary
        assert 'memory' in summary
        assert 'samples' in summary
        assert summary['samples'] >= 1
    
    def test_monitoring_disabled(self):
        """Test monitor with monitoring disabled"""
        monitor = ResourceMonitor(monitoring_enabled=False)
        
        metrics = monitor.get_current_metrics()
        
        # Should return zero values
        assert metrics.cpu_percent == 0.0
        assert metrics.memory_percent == 0.0


class TestResourceMonitorSingleton:
    """Test resource monitor singleton"""
    
    def test_get_resource_monitor_singleton(self):
        """Test that get_resource_monitor returns same instance"""
        monitor1 = get_resource_monitor()
        monitor2 = get_resource_monitor()
        
        assert monitor1 is monitor2
    
    def test_monitor_loads_from_environment(self):
        """Test that monitor loads config from environment"""
        import os
        
        # Set test environment variables
        os.environ['RESOURCE_CPU_WARNING'] = '65.0'
        os.environ['RESOURCE_MEMORY_WARNING'] = '70.0'
        
        # Reset singleton to force reload
        from core import resource_monitor as rm
        from core.secrets import init_secrets_manager, get_secrets_manager
        
        # Initialize secrets manager if not already done with a test master key
        try:
            init_secrets_manager(master_key="test_master_key_32_chars_minimum_")
        except (RuntimeError, ValueError):
            # Already initialized or key error - this is OK
            pass
        
        rm._resource_monitor = None
        try:
            get_secrets_manager().reload_cache()
        except (RuntimeError, AttributeError):
            # Secrets manager may not be initialized; skip reload
            pass
        
        monitor = get_resource_monitor()
        
        assert monitor.thresholds.cpu_warning == 65.0
        assert monitor.thresholds.memory_warning == 70.0
        
        # Cleanup
        del os.environ['RESOURCE_CPU_WARNING']
        del os.environ['RESOURCE_MEMORY_WARNING']
        rm._resource_monitor = None
