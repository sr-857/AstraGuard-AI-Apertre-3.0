import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from src.core.component_health import SystemHealthMonitor, HealthStatus

@pytest.fixture
def health_monitor():
    monitor = SystemHealthMonitor()
    monitor.reset()
    return monitor

@pytest.mark.asyncio
async def test_active_health_check_success(health_monitor):
    """Verify that a successful callback marks component as HEALTHY."""
    callback = Mock(return_value=True)
    health_monitor.register_component("test_comp", check_callback=callback)
    
    status = await health_monitor.check_component_health("test_comp")
    
    assert status == HealthStatus.HEALTHY
    assert health_monitor.get_component_health("test_comp").status == HealthStatus.HEALTHY
    callback.assert_called_once()

@pytest.mark.asyncio
async def test_active_health_check_failure(health_monitor):
    """Verify that a failed callback marks component as FAILED."""
    callback = Mock(return_value=False)
    health_monitor.register_component("test_comp", check_callback=callback)
    
    status = await health_monitor.check_component_health("test_comp")
    
    assert status == HealthStatus.FAILED
    assert health_monitor.get_component_health("test_comp").status == HealthStatus.FAILED

@pytest.mark.asyncio
async def test_async_health_check(health_monitor):
    """Verify support for async callbacks."""
    async def async_check():
        await asyncio.sleep(0.01)
        return True
        
    health_monitor.register_component("async_comp", check_callback=async_check)
    
    status = await health_monitor.check_component_health("async_comp")
    assert status == HealthStatus.HEALTHY

@pytest.mark.asyncio
async def test_dependency_failure(health_monitor):
    """Verify that dependency failure degrades the dependent component."""
    # Register dependency and mark it failed
    health_monitor.register_component("db", is_critical=True)
    health_monitor.mark_failed("db", "Connection lost")
    
    # Register dependent component
    health_monitor.register_component("api", dependencies=["db"])
    
    status = await health_monitor.check_component_health("api")
    
    assert status == HealthStatus.DEGRADED
    assert health_monitor.get_component_health("api").status == HealthStatus.DEGRADED
    assert "Dependency db is unhealthy" in health_monitor.get_component_health("api").last_error

@pytest.mark.asyncio
async def test_critical_vs_non_critical(health_monitor):
    """Verify system status calculation for critical vs non-critical components."""
    # Non-critical failure -> DEGRADED
    health_monitor.register_component("cache", is_critical=False)
    health_monitor.mark_failed("cache", "Cache down")
    assert health_monitor.get_system_status()["overall_status"] == HealthStatus.DEGRADED.value
    
    # Critical failure -> FAILED
    health_monitor.register_component("db", is_critical=True)
    health_monitor.mark_failed("db", "DB down")
    assert health_monitor.get_system_status()["overall_status"] == HealthStatus.FAILED.value

@pytest.mark.asyncio
async def test_check_all(health_monitor):
    """Verify check_all runs checks for all components."""
    cb1 = Mock(return_value=True)
    cb2 = Mock(return_value=True)
    
    health_monitor.register_component("c1", check_callback=cb1)
    health_monitor.register_component("c2", check_callback=cb2)
    
    results = await health_monitor.check_all()
    
    assert len(results) == 2
    assert results["c1"] == HealthStatus.HEALTHY
    assert results["c2"] == HealthStatus.HEALTHY
    cb1.assert_called_once()
    cb2.assert_called_once()
