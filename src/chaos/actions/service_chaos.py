"""
Service Chaos Actions for Chaos Testing

Provides service-level chaos injection:
- Stop/start services
- Service restarts
- Health check failures
"""

import asyncio
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Global state for service chaos
_service_chaos_state = {
    "stopped_services": set(),
    "simulated_failures": set(),
}


async def stop_service(
    service_name: str,
    duration_seconds: Optional[int] = None,
) -> bool:
    """
    Stop a service for chaos testing.
    
    In production, this would use systemctl or docker.
    For testing, it simulates service unavailability.
    
    Args:
        service_name: Name of service to stop
        duration_seconds: Auto-restart after this duration (None = manual)
        
    Returns:
        True if service stopped successfully
    """
    logger.info(f"Stopping service: {service_name}")
    
    _service_chaos_state["stopped_services"].add(service_name)
    
    # Try to actually stop the service if possible
    try:
        if service_name == "redis":
            subprocess.run(
                ["redis-cli", "shutdown"],
                capture_output=True,
                timeout=5,
                check=False,
            )
    except Exception as e:
        logger.warning(f"Could not stop {service_name} via command: {e}")
    
    # Schedule auto-restart if duration specified
    if duration_seconds:
        asyncio.create_task(_auto_start_service(service_name, duration_seconds))
    
    logger.info(f"Service {service_name} marked as stopped")
    return True


async def start_service(service_name: str) -> bool:
    """
    Start a previously stopped service.
    
    Args:
        service_name: Name of service to start
        
    Returns:
        True if service started successfully
    """
    logger.info(f"Starting service: {service_name}")
    
    _service_chaos_state["stopped_services"].discard(service_name)
    
    # Try to actually start the service if possible
    try:
        if service_name == "redis":
            subprocess.run(
                ["redis-server", "--daemonize", "yes"],
                capture_output=True,
                timeout=5,
                check=False,
            )
    except Exception as e:
        logger.warning(f"Could not start {service_name} via command: {e}")
    
    logger.info(f"Service {service_name} marked as started")
    return True


async def restart_service(
    service_name: str,
    delay_seconds: int = 0,
) -> bool:
    """
    Restart a service for chaos testing.
    
    Args:
        service_name: Name of service to restart
        delay_seconds: Delay before restarting
        
    Returns:
        True if service restarted successfully
    """
    logger.info(f"Restarting service: {service_name} (delay: {delay_seconds}s)")
    
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    
    await stop_service(service_name)
    await asyncio.sleep(2)  # Brief pause between stop and start
    await start_service(service_name)
    
    logger.info(f"Service {service_name} restarted")
    return True


async def simulate_service_failure(
    service_name: str,
    failure_type: str = "unavailable",
    duration_seconds: int = 30,
) -> bool:
    """
    Simulate service failure without actually stopping it.
    
    Args:
        service_name: Name of service to simulate failure for
        failure_type: Type of failure (unavailable, slow, error)
        duration_seconds: Duration of simulated failure
        
    Returns:
        True if simulation started
    """
    logger.info(
        f"Simulating {failure_type} failure for {service_name} "
        f"for {duration_seconds}s"
    )
    
    failure_key = f"{service_name}:{failure_type}"
    _service_chaos_state["simulated_failures"].add(failure_key)
    
    # Schedule removal of simulation
    asyncio.create_task(
        _remove_simulated_failure(failure_key, duration_seconds)
    )
    
    return True


async def _auto_start_service(service_name: str, delay_seconds: int):
    """Automatically start service after delay."""
    await asyncio.sleep(delay_seconds)
    if service_name in _service_chaos_state["stopped_services"]:
        logger.info(f"Auto-starting service {service_name} after {delay_seconds}s")
        await start_service(service_name)


async def _remove_simulated_failure(failure_key: str, delay_seconds: int):
    """Remove simulated failure after delay."""
    await asyncio.sleep(delay_seconds)
    _service_chaos_state["simulated_failures"].discard(failure_key)
    logger.info(f"Removed simulated failure: {failure_key}")


def is_service_available(service_name: str) -> bool:
    """
    Check if a service is available (not stopped or simulated failure).
    
    Args:
        service_name: Name of service to check
        
    Returns:
        True if service is available
    """
    if service_name in _service_chaos_state["stopped_services"]:
        return False
    
    failure_key = f"{service_name}:unavailable"
    if failure_key in _service_chaos_state["simulated_failures"]:
        return False
    
    return True


def get_service_chaos_status() -> dict:
    """
    Get current service chaos status.
    
    Returns:
        Dictionary with service chaos status
    """
    return {
        "stopped_services": list(_service_chaos_state["stopped_services"]),
        "simulated_failures": list(_service_chaos_state["simulated_failures"]),
    }
