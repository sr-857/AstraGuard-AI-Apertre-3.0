"""
Tests for health check implementations.

Tests cover:
- HealthCheck protocol compliance
- Check execution with timeout handling
- Error recovery
- Individual check implementations (Redis, Downstream, Disk, Component)
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from backend.health.checks import (
    HealthCheck,
    HealthCheckResult,
    HealthCheckStatus,
    BaseHealthCheck,
    RedisHealthCheck,
    DownstreamServiceCheck,
    DiskSpaceCheck,
    ComponentHealthCheck,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_health_monitor():
    """Create mock health monitor for component checks."""
    from unittest.mock import Mock
    from core.component_health import HealthStatus
    
    component = Mock()
    component.status = HealthStatus.HEALTHY
    component.last_error = None
    component.error_count = 0
    component.warning_count = 0
    component.fallback_active = False
    
    monitor = Mock()
    monitor.get_component_health = Mock(return_value=component)
    return monitor


# ============================================================================
# HEALTH CHECK RESULT TESTS
# ============================================================================


def test_health_check_result_creation():
    """Test HealthCheckResult can be created with defaults."""
    result = HealthCheckResult(
        name="test",
        status=HealthCheckStatus.HEALTHY
    )
    
    assert result.name == "test"
    assert result.status == HealthCheckStatus.HEALTHY
    assert result.message == ""
    assert result.latency_ms == 0.0
    assert isinstance(result.timestamp, datetime)
    assert result.metadata == {}


def test_health_check_result_to_dict():
    """Test HealthCheckResult serialization."""
    result = HealthCheckResult(
        name="redis",
        status=HealthCheckStatus.DEGRADED,
        message="High latency",
        latency_ms=150.5,
        metadata={"host": "localhost"}
    )
    
    d = result.to_dict()
    
    assert d["name"] == "redis"
    assert d["status"] == "degraded"
    assert d["message"] == "High latency"
    assert d["latency_ms"] == 150.5
    assert "timestamp" in d
    assert d["metadata"]["host"] == "localhost"


def test_health_check_status_values():
    """Test HealthCheckStatus enum values."""
    assert HealthCheckStatus.HEALTHY.value == "healthy"
    assert HealthCheckStatus.DEGRADED.value == "degraded"
    assert HealthCheckStatus.UNHEALTHY.value == "unhealthy"
    assert HealthCheckStatus.UNKNOWN.value == "unknown"


# ============================================================================
# REDIS HEALTH CHECK TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_redis_health_check_healthy(mock_redis_client):
    """Test Redis check returns healthy when ping succeeds."""
    check = RedisHealthCheck(redis_client=mock_redis_client)
    
    result = await check.check()
    
    assert result.status == HealthCheckStatus.HEALTHY
    assert result.name == "redis"
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_redis_health_check_unhealthy(mock_redis_client):
    """Test Redis check returns unhealthy when ping fails."""
    mock_redis_client.ping = AsyncMock(side_effect=ConnectionError("Connection refused"))
    check = RedisHealthCheck(redis_client=mock_redis_client)
    
    result = await check.check()
    
    assert result.status == HealthCheckStatus.UNHEALTHY
    assert "Connection refused" in result.message


@pytest.mark.asyncio
async def test_redis_health_check_timeout():
    """Test Redis check handles timeout."""
    async def slow_ping():
        await asyncio.sleep(10)  # Very slow
        return True
    
    mock_client = AsyncMock()
    mock_client.ping = slow_ping
    
    check = RedisHealthCheck(redis_client=mock_client, timeout_seconds=0.1)
    result = await check.check()
    
    assert result.status == HealthCheckStatus.UNHEALTHY
    assert "timed out" in result.message.lower()


# ============================================================================
# DISK SPACE CHECK TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_disk_space_check_healthy():
    """Test disk space check returns healthy with normal usage."""
    with patch("shutil.disk_usage") as mock_disk:
        # 50% usage
        mock_disk.return_value = (100 * 1024**3, 50 * 1024**3, 50 * 1024**3)
        
        check = DiskSpaceCheck(path="/")
        result = await check.check()
        
        assert result.status == HealthCheckStatus.HEALTHY
        assert "50" in result.message


@pytest.mark.asyncio
async def test_disk_space_check_warning():
    """Test disk space check returns degraded with high usage."""
    with patch("shutil.disk_usage") as mock_disk:
        # 85% usage
        mock_disk.return_value = (100 * 1024**3, 85 * 1024**3, 15 * 1024**3)
        
        check = DiskSpaceCheck(path="/", warning_threshold_percent=80.0)
        result = await check.check()
        
        assert result.status == HealthCheckStatus.DEGRADED
        assert "warning" in result.message.lower()


@pytest.mark.asyncio
async def test_disk_space_check_critical():
    """Test disk space check returns unhealthy with critical usage."""
    with patch("shutil.disk_usage") as mock_disk:
        # 97% usage
        mock_disk.return_value = (100 * 1024**3, 97 * 1024**3, 3 * 1024**3)
        
        check = DiskSpaceCheck(path="/", critical_threshold_percent=95.0)
        result = await check.check()
        
        assert result.status == HealthCheckStatus.UNHEALTHY
        assert "critical" in result.message.lower()


@pytest.mark.asyncio
async def test_disk_space_check_metadata():
    """Test disk space check includes proper metadata."""
    with patch("shutil.disk_usage") as mock_disk:
        mock_disk.return_value = (100 * 1024**3, 50 * 1024**3, 50 * 1024**3)
        
        check = DiskSpaceCheck(path="/data")
        result = await check.check()
        
        assert result.metadata["path"] == "/data"
        assert "total_gb" in result.metadata
        assert "used_gb" in result.metadata
        assert "free_gb" in result.metadata
        assert "usage_percent" in result.metadata


# ============================================================================
# COMPONENT HEALTH CHECK TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_component_health_check_healthy(mock_health_monitor):
    """Test component check returns correct status for healthy component."""
    check = ComponentHealthCheck(
        component_name="anomaly_detector",
        health_monitor=mock_health_monitor
    )
    
    result = await check.check()
    
    assert result.status == HealthCheckStatus.HEALTHY
    assert result.name == "anomaly_detector"


@pytest.mark.asyncio
async def test_component_health_check_failed(mock_health_monitor):
    """Test component check returns unhealthy for failed component."""
    from core.component_health import HealthStatus
    
    mock_health_monitor.get_component_health.return_value.status = HealthStatus.FAILED
    mock_health_monitor.get_component_health.return_value.last_error = "Connection lost"
    
    check = ComponentHealthCheck(
        component_name="redis",
        health_monitor=mock_health_monitor
    )
    
    result = await check.check()
    
    assert result.status == HealthCheckStatus.UNHEALTHY
    assert "Connection lost" in result.message


@pytest.mark.asyncio
async def test_component_health_check_metadata(mock_health_monitor):
    """Test component check includes metadata."""
    mock_health_monitor.get_component_health.return_value.error_count = 5
    mock_health_monitor.get_component_health.return_value.warning_count = 2
    mock_health_monitor.get_component_health.return_value.fallback_active = True
    
    check = ComponentHealthCheck(
        component_name="memory_store",
        health_monitor=mock_health_monitor
    )
    
    result = await check.check()
    
    assert result.metadata["error_count"] == 5
    assert result.metadata["warning_count"] == 2
    assert result.metadata["fallback_active"] is True


# ============================================================================
# HEALTH CHECK PROTOCOL TESTS
# ============================================================================


def test_health_check_protocol_compliance():
    """Test that check classes implement HealthCheck protocol."""
    mock_redis = AsyncMock()
    mock_monitor = Mock()
    
    redis_check = RedisHealthCheck(redis_client=mock_redis)
    disk_check = DiskSpaceCheck()
    component_check = ComponentHealthCheck("test", mock_monitor)
    
    # All should have name property and check method
    for check in [redis_check, disk_check, component_check]:
        assert hasattr(check, "name")
        assert hasattr(check, "check")
        assert callable(check.check)


# ============================================================================
# BASE HEALTH CHECK TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_base_health_check_timeout_handling():
    """Test BaseHealthCheck handles timeouts properly."""
    
    class SlowCheck(BaseHealthCheck):
        async def _perform_check(self):
            await asyncio.sleep(10)
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.HEALTHY
            )
    
    check = SlowCheck(name="slow", timeout_seconds=0.1)
    result = await check.check()
    
    assert result.status == HealthCheckStatus.UNHEALTHY
    assert "timed out" in result.message.lower()
    assert result.latency_ms >= 100  # At least 100ms (0.1s timeout)


@pytest.mark.asyncio
async def test_base_health_check_error_handling():
    """Test BaseHealthCheck handles errors properly."""
    
    class FailingCheck(BaseHealthCheck):
        async def _perform_check(self):
            raise ValueError("Something went wrong")
    
    check = FailingCheck(name="failing")
    result = await check.check()
    
    assert result.status == HealthCheckStatus.UNHEALTHY
    assert "Something went wrong" in result.message


@pytest.mark.asyncio
async def test_base_health_check_latency_tracking():
    """Test BaseHealthCheck tracks latency correctly."""
    
    class FastCheck(BaseHealthCheck):
        async def _perform_check(self):
            await asyncio.sleep(0.05)  # 50ms
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.HEALTHY
            )
    
    check = FastCheck(name="fast")
    result = await check.check()
    
    assert result.latency_ms >= 50  # At least 50ms
    assert result.latency_ms < 200  # But not too long
