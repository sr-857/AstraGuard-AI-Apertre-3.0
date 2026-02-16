"""
Network Chaos Actions for Chaos Testing

Provides network-level chaos injection:
- Latency injection
- Packet loss
- Bandwidth throttling
- DNS failures
"""

import asyncio
import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)

# Global state for network chaos
_network_chaos_active = False
_network_chaos_config = {
    "latency_ms": 0,
    "jitter_ms": 0,
    "packet_loss_rate": 0.0,
    "duration_seconds": 0,
}


async def inject_latency(
    duration_seconds: int = 30,
    latency_ms: int = 500,
    jitter_ms: int = 100,
) -> bool:
    """
    Inject network latency for chaos testing.
    
    Args:
        duration_seconds: How long to inject latency
        latency_ms: Base latency in milliseconds
        jitter_ms: Random jitter added to latency
        
    Returns:
        True if injection started successfully
    """
    global _network_chaos_active, _network_chaos_config
    
    logger.info(
        f"Injecting network latency: "
        f"duration={duration_seconds}s, latency={latency_ms}ms, jitter={jitter_ms}ms"
    )
    
    _network_chaos_active = True
    _network_chaos_config = {
        "latency_ms": latency_ms,
        "jitter_ms": jitter_ms,
        "packet_loss_rate": 0.0,
        "duration_seconds": duration_seconds,
    }
    
    # Schedule automatic stop
    asyncio.create_task(_auto_stop_network_chaos(duration_seconds))
    
    return True


async def inject_packet_loss(
    duration_seconds: int = 30,
    loss_rate: float = 0.1,
) -> bool:
    """
    Inject packet loss for chaos testing.
    
    Args:
        duration_seconds: How long to inject packet loss
        loss_rate: Probability of packet loss (0.0-1.0)
        
    Returns:
        True if injection started successfully
    """
    global _network_chaos_active, _network_chaos_config
    
    logger.info(f"Injecting packet loss: duration={duration_seconds}s, rate={loss_rate}")
    
    _network_chaos_active = True
    _network_chaos_config = {
        "latency_ms": 0,
        "jitter_ms": 0,
        "packet_loss_rate": loss_rate,
        "duration_seconds": duration_seconds,
    }
    
    asyncio.create_task(_auto_stop_network_chaos(duration_seconds))
    
    return True


async def remove_latency() -> bool:
    """
    Remove all network latency injection.
    
    Returns:
        True if removed successfully
    """
    global _network_chaos_active, _network_chaos_config
    
    logger.info("Removing network latency injection")
    
    _network_chaos_active = False
    _network_chaos_config = {
        "latency_ms": 0,
        "jitter_ms": 0,
        "packet_loss_rate": 0.0,
        "duration_seconds": 0,
    }
    
    return True


async def _auto_stop_network_chaos(delay_seconds: int):
    """Automatically stop network chaos after delay."""
    await asyncio.sleep(delay_seconds)
    if _network_chaos_active:
        logger.info(f"Auto-stopping network chaos after {delay_seconds}s")
        await remove_latency()


def get_current_latency() -> float:
    """
    Get current injected latency in seconds.
    
    Returns:
        Latency in seconds (0 if no chaos active)
    """
    if not _network_chaos_active:
        return 0.0
    
    base_latency = _network_chaos_config["latency_ms"] / 1000.0
    jitter = _network_chaos_config["jitter_ms"] / 1000.0
    
    # Add random jitter
    if jitter > 0:
        base_latency += random.uniform(-jitter, jitter)
    
    return max(0, base_latency)


def should_drop_packet() -> bool:
    """
    Check if current packet should be dropped.
    
    Returns:
        True if packet should be dropped
    """
    if not _network_chaos_active:
        return False
    
    return random.random() < _network_chaos_config["packet_loss_rate"]


async def simulate_network_delay():
    """
    Simulate network delay if chaos is active.
    
    Call this before network operations to inject latency.
    """
    delay = get_current_latency()
    if delay > 0:
        await asyncio.sleep(delay)


def get_network_chaos_status() -> dict:
    """
    Get current network chaos status.
    
    Returns:
        Dictionary with chaos status
    """
    return {
        "active": _network_chaos_active,
        "latency_ms": _network_chaos_config["latency_ms"],
        "jitter_ms": _network_chaos_config["jitter_ms"],
        "packet_loss_rate": _network_chaos_config["packet_loss_rate"],
    }


# Decorator for adding network chaos to async functions
def with_network_chaos(func):
    """
    Decorator to add network chaos simulation to async functions.
    
    Usage:
        @with_network_chaos
        async def make_request():
            # Function implementation
            pass
    """
    async def wrapper(*args, **kwargs):
        await simulate_network_delay()
        if should_drop_packet():
            raise ConnectionError("Chaos: Simulated packet loss")
        return await func(*args, **kwargs)
    return wrapper
