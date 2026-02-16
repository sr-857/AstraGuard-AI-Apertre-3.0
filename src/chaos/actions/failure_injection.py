"""
Failure Injection Actions for Chaos Testing

Provides controlled failure injection for testing system resilience:
- Model loader failures
- Service failures
- Component failures
"""

import asyncio
import logging
import random
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Global state for failure injection
_failure_injection_active = False
_failure_injection_config = {
    "failure_rate": 0.0,
    "duration_seconds": 0,
    "start_time": None,
    "failure_type": "model_loader",
}


async def inject_model_loader_failure(
    duration_seconds: int = 30,
    failure_rate: float = 0.8,
) -> bool:
    """
    Inject model loader failures for chaos testing.
    
    Simulates high failure rate in model loading to trigger circuit breaker.
    
    Args:
        duration_seconds: How long to inject failures
        failure_rate: Probability of failure (0.0-1.0)
        
    Returns:
        True if injection started successfully
    """
    global _failure_injection_active, _failure_injection_config
    
    logger.info(
        f"Injecting model loader failures: "
        f"duration={duration_seconds}s, rate={failure_rate}"
    )
    
    _failure_injection_active = True
    _failure_injection_config = {
        "failure_rate": failure_rate,
        "duration_seconds": duration_seconds,
        "start_time": datetime.utcnow(),
        "failure_type": "model_loader",
    }
    
    # Schedule automatic stop
    asyncio.create_task(_auto_stop_failure_injection(duration_seconds))
    
    return True


async def stop_failure_injection() -> bool:
    """
    Stop all failure injection.
    
    Returns:
        True if stopped successfully
    """
    global _failure_injection_active, _failure_injection_config
    
    logger.info("Stopping failure injection")
    
    _failure_injection_active = False
    _failure_injection_config = {
        "failure_rate": 0.0,
        "duration_seconds": 0,
        "start_time": None,
        "failure_type": "none",
    }
    
    return True


async def _auto_stop_failure_injection(delay_seconds: int):
    """Automatically stop failure injection after delay."""
    await asyncio.sleep(delay_seconds)
    if _failure_injection_active:
        logger.info(f"Auto-stopping failure injection after {delay_seconds}s")
        await stop_failure_injection()


def should_fail() -> bool:
    """
    Check if current operation should fail based on injection config.
    
    Returns:
        True if operation should fail
    """
    if not _failure_injection_active:
        return False
    
    # Check if duration expired
    if _failure_injection_config["start_time"]:
        elapsed = (datetime.utcnow() - _failure_injection_config["start_time"]).total_seconds()
        if elapsed > _failure_injection_config["duration_seconds"]:
            return False
    
    # Random failure based on rate
    return random.random() < _failure_injection_config["failure_rate"]


def get_injection_status() -> dict:
    """
    Get current failure injection status.
    
    Returns:
        Dictionary with injection status
    """
    if not _failure_injection_active:
        return {
            "active": False,
            "failure_rate": 0.0,
            "remaining_seconds": 0,
        }
    
    elapsed = 0
    if _failure_injection_config["start_time"]:
        elapsed = (datetime.utcnow() - _failure_injection_config["start_time"]).total_seconds()
    
    remaining = max(0, _failure_injection_config["duration_seconds"] - elapsed)
    
    return {
        "active": True,
        "failure_type": _failure_injection_config["failure_type"],
        "failure_rate": _failure_injection_config["failure_rate"],
        "elapsed_seconds": elapsed,
        "remaining_seconds": remaining,
    }


# Decorator for making functions chaos-aware
def chaos_inject(failure_type: str = "model_loader"):
    """
    Decorator to add chaos injection to a function.
    
    Usage:
        @chaos_inject(failure_type="model_loader")
        async def load_model():
            # Function implementation
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if should_fail() and _failure_injection_config["failure_type"] == failure_type:
                logger.warning(f"Chaos injection: Failing {func.__name__}")
                raise RuntimeError(f"Chaos: Simulated {failure_type} failure")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
