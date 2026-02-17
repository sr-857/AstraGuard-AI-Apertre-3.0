"""
Tests for Resource Limit Enforcement (Issue #675)
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from src.core.resource_limits import (
    ResourceLimiter,
    ResourceQuota,
    ResourceLimitExceeded,
    ResourceType,
    get_resource_limiter
)


class TestResourceQuota:
    """Test ResourceQuota dataclass"""
    
    def test_default_values(self):
        """Test default quota values"""
        quota = ResourceQuota()
        assert quota.max_cpu_percent == 80.0
        assert quota.max_memory_mb == 1024.0
        assert quota.max_connections == 100
    
    def test_custom_values(self):
        """Test custom quota values"""
        quota = ResourceQuota(
            max_cpu_percent=90.0,
            max_memory_mb=2048.0,
            max_connections=200
        )
        assert quota.max_cpu_percent == 90.0
        assert quota.max_memory_mb == 2048.0
        assert quota.max_connections == 200
    
    def test_to_dict(self):
        """Test quota serialization"""
        quota = ResourceQuota(max_cpu_percent=75.0)
        data = quota.to_dict()
        assert data["max_cpu_percent"] == 75.0
        assert "max_memory_mb" in data
        assert "max_connections" in data


class TestResourceLimiter:
    """Test ResourceLimiter class"""
    
    @pytest.fixture
    def limiter(self):
        """Create a resource limiter for testing"""
        quota = ResourceQuota(
            max_cpu_percent=50.0,  # Low threshold for testing
            max_memory_mb=100.0,   # Low threshold for testing
            max_connections=5
        )
        return ResourceLimiter(quota)
    
    def test_initialization(self, limiter):
        """Test limiter initialization"""
        assert limiter.quota.max_cpu_percent == 50.0
        assert limiter.quota.max_memory_mb == 100.0
        assert limiter.quota.max_connections == 5
        assert limiter._active_connections == 0
    
    @patch('psutil.cpu_percent')
    def test_check_cpu_limit_within_bounds(self, mock_cpu, limiter):
        """Test CPU check when within limits"""
        mock_cpu.return_value = 30.0
        assert limiter.check_cpu_limit() is True
    
    @patch('psutil.cpu_percent')
    def test_check_cpu_limit_exceeded(self, mock_cpu, limiter):
        """Test CPU check when limit exceeded"""
        mock_cpu.return_value = 60.0  # Exceeds 50% limit
        
        with pytest.raises(ResourceLimitExceeded) as exc_info:
            limiter.check_cpu_limit()
        
        assert exc_info.value.resource_type == ResourceType.CPU
        assert exc_info.value.current == 60.0
        assert exc_info.value.limit == 50.0
    
    def test_check_memory_limit_within_bounds(self, limiter):
        """Test memory check when within limits"""
        # This test uses actual process memory, which should be reasonable
        # We set a high limit to ensure it passes
        limiter.quota.max_memory_mb = 10000.0
        assert limiter.check_memory_limit() is True
    
    def test_connection_limit_enforcement(self, limiter):
        """Test connection limit enforcement"""
        # Acquire connections up to limit
        for i in range(5):
            limiter.acquire_connection()
            assert limiter._active_connections == i + 1
        
        # Next acquisition should fail
        with pytest.raises(ResourceLimitExceeded) as exc_info:
            limiter.acquire_connection()
        
        assert exc_info.value.resource_type == ResourceType.CONNECTIONS
        assert exc_info.value.current == 5
        assert exc_info.value.limit == 5
    
    def test_connection_release(self, limiter):
        """Test connection release"""
        limiter.acquire_connection()
        limiter.acquire_connection()
        assert limiter._active_connections == 2
        
        limiter.release_connection()
        assert limiter._active_connections == 1
        
        limiter.release_connection()
        assert limiter._active_connections == 0
    
    def test_connection_acquire_release_cycle(self, limiter):
        """Test full acquire/release cycle"""
        # Fill to capacity
        for _ in range(5):
            limiter.acquire_connection()
        
        # Release one
        limiter.release_connection()
        assert limiter._active_connections == 4
        
        # Should be able to acquire again
        limiter.acquire_connection()
        assert limiter._active_connections == 5
    
    @patch('psutil.cpu_percent')
    def test_check_all_limits(self, mock_cpu, limiter):
        """Test checking all limits at once"""
        mock_cpu.return_value = 30.0
        limiter.quota.max_memory_mb = 10000.0  # High limit
        
        assert limiter.check_all_limits() is True
    
    @patch('psutil.cpu_percent')
    def test_get_current_usage(self, mock_cpu, limiter):
        """Test getting current resource usage"""
        mock_cpu.return_value = 25.0
        limiter.acquire_connection()
        limiter.acquire_connection()
        
        usage = limiter.get_current_usage()
        
        assert "timestamp" in usage
        assert usage["cpu"]["current_percent"] == 25.0
        assert usage["cpu"]["limit_percent"] == 50.0
        assert usage["cpu"]["usage_ratio"] == 0.5
        assert usage["connections"]["current"] == 2
        assert usage["connections"]["limit"] == 5
        assert usage["connections"]["usage_ratio"] == 0.4
    
    def test_update_quota(self, limiter):
        """Test updating quota configuration"""
        new_quota = ResourceQuota(
            max_cpu_percent=70.0,
            max_memory_mb=2048.0,
            max_connections=10
        )
        
        limiter.update_quota(new_quota)
        
        assert limiter.quota.max_cpu_percent == 70.0
        assert limiter.quota.max_memory_mb == 2048.0
        assert limiter.quota.max_connections == 10


class TestResourceLimiterSingleton:
    """Test singleton pattern for resource limiter"""
    
    def test_get_resource_limiter_singleton(self):
        """Test that get_resource_limiter returns singleton"""
        limiter1 = get_resource_limiter()
        limiter2 = get_resource_limiter()
        
        assert limiter1 is limiter2
    
    def test_singleton_state_persistence(self):
        """Test that singleton maintains state"""
        limiter = get_resource_limiter()
        limiter.acquire_connection()
        
        # Get instance again
        limiter2 = get_resource_limiter()
        assert limiter2._active_connections >= 1  # May have other connections


class TestResourceLimitExceeded:
    """Test ResourceLimitExceeded exception"""
    
    def test_exception_message(self):
        """Test exception message formatting"""
        exc = ResourceLimitExceeded(ResourceType.CPU, 95.0, 80.0)
        
        assert "cpu" in str(exc).lower()
        assert "95.00" in str(exc)
        assert "80.00" in str(exc)
    
    def test_exception_attributes(self):
        """Test exception attributes"""
        exc = ResourceLimitExceeded(ResourceType.MEMORY, 2048.0, 1024.0)
        
        assert exc.resource_type == ResourceType.MEMORY
        assert exc.current == 2048.0
        assert exc.limit == 1024.0
