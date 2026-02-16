"""
Database Chaos Actions for Chaos Testing

Provides database-level chaos injection:
- Primary database failure simulation
- Replica failover testing
- Connection pool exhaustion
- Query latency injection
"""

import asyncio
import logging
import random
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Global state for database chaos
_db_chaos_state = {
    "primary_failed": False,
    "replica_failed": False,
    "connection_delay_ms": 0,
    "query_delay_ms": 0,
    "failure_duration": 0,
    "failure_start_time": None,
}


async def simulate_db_failure(
    db_type: str = "primary",
    duration_seconds: int = 30,
) -> bool:
    """
    Simulate database failure for chaos testing.
    
    Args:
        db_type: Type of database to fail (primary, replica)
        duration_seconds: How long to simulate failure
        
    Returns:
        True if failure simulation started
    """
    global _db_chaos_state
    
    logger.info(f"Simulating {db_type} database failure for {duration_seconds}s")
    
    if db_type == "primary":
        _db_chaos_state["primary_failed"] = True
    elif db_type == "replica":
        _db_chaos_state["replica_failed"] = True
    
    _db_chaos_state["failure_duration"] = duration_seconds
    _db_chaos_state["failure_start_time"] = datetime.utcnow()
    
    # Schedule auto-recovery
    asyncio.create_task(_auto_restore_db(db_type, duration_seconds))
    
    return True


async def restore_db(db_type: str = "primary") -> bool:
    """
    Restore a failed database.
    
    Args:
        db_type: Type of database to restore (primary, replica)
        
    Returns:
        True if database restored
    """
    global _db_chaos_state
    
    logger.info(f"Restoring {db_type} database")
    
    if db_type == "primary":
        _db_chaos_state["primary_failed"] = False
    elif db_type == "replica":
        _db_chaos_state["replica_failed"] = False
    
    _db_chaos_state["failure_start_time"] = None
    _db_chaos_state["failure_duration"] = 0
    
    return True


async def inject_connection_delay(
    delay_ms: int = 1000,
    duration_seconds: int = 30,
) -> bool:
    """
    Inject delay in database connections.
    
    Args:
        delay_ms: Connection delay in milliseconds
        duration_seconds: How long to inject delay
        
    Returns:
        True if delay injection started
    """
    global _db_chaos_state
    
    logger.info(f"Injecting connection delay: {delay_ms}ms for {duration_seconds}s")
    
    _db_chaos_state["connection_delay_ms"] = delay_ms
    
    # Schedule auto-stop
    asyncio.create_task(_auto_stop_connection_delay(duration_seconds))
    
    return True


async def inject_query_delay(
    delay_ms: int = 500,
    duration_seconds: int = 30,
) -> bool:
    """
    Inject delay in database queries.
    
    Args:
        delay_ms: Query delay in milliseconds
        duration_seconds: How long to inject delay
        
    Returns:
        True if delay injection started
    """
    global _db_chaos_state
    
    logger.info(f"Injecting query delay: {delay_ms}ms for {duration_seconds}s")
    
    _db_chaos_state["query_delay_ms"] = delay_ms
    
    # Schedule auto-stop
    asyncio.create_task(_auto_stop_query_delay(duration_seconds))
    
    return True


async def _auto_restore_db(db_type: str, delay_seconds: int):
    """Automatically restore database after delay."""
    await asyncio.sleep(delay_seconds)
    
    is_failed = (
        _db_chaos_state["primary_failed"] if db_type == "primary"
        else _db_chaos_state["replica_failed"]
    )
    
    if is_failed:
        logger.info(f"Auto-restoring {db_type} database after {delay_seconds}s")
        await restore_db(db_type)


async def _auto_stop_connection_delay(delay_seconds: int):
    """Automatically stop connection delay after delay."""
    await asyncio.sleep(delay_seconds)
    if _db_chaos_state["connection_delay_ms"] > 0:
        logger.info(f"Auto-stopping connection delay after {delay_seconds}s")
        _db_chaos_state["connection_delay_ms"] = 0


async def _auto_stop_query_delay(delay_seconds: int):
    """Automatically stop query delay after delay."""
    await asyncio.sleep(delay_seconds)
    if _db_chaos_state["query_delay_ms"] > 0:
        logger.info(f"Auto-stopping query delay after {delay_seconds}s")
        _db_chaos_state["query_delay_ms"] = 0


def is_db_available(db_type: str = "primary") -> bool:
    """
    Check if database is available.
    
    Args:
        db_type: Type of database to check (primary, replica)
        
    Returns:
        True if database is available
    """
    if db_type == "primary":
        return not _db_chaos_state["primary_failed"]
    elif db_type == "replica":
        return not _db_chaos_state["replica_failed"]
    return True


def get_active_db() -> str:
    """
    Get currently active database (for failover testing).
    
    Returns:
        Database type that should be used (primary, replica)
    """
    if _db_chaos_state["primary_failed"] and not _db_chaos_state["replica_failed"]:
        return "replica"
    return "primary"


async def simulate_db_connection():
    """
    Simulate database connection with chaos effects.
    
    Call this when establishing database connections.
    """
    delay_ms = _db_chaos_state["connection_delay_ms"]
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)
    
    # Simulate connection failure if primary is down
    if _db_chaos_state["primary_failed"]:
        raise ConnectionError("Chaos: Primary database connection failed")


async def simulate_db_query():
    """
    Simulate database query with chaos effects.
    
    Call this when executing database queries.
    """
    delay_ms = _db_chaos_state["query_delay_ms"]
    if delay_ms > 0:
        # Add some randomness to query delay
        actual_delay = delay_ms + random.randint(-100, 100)
        await asyncio.sleep(max(0, actual_delay) / 1000.0)


def get_db_chaos_status() -> Dict[str, Any]:
    """
    Get current database chaos status.
    
    Returns:
        Dictionary with database chaos status
    """
    elapsed = 0
    if _db_chaos_state["failure_start_time"]:
        elapsed = (datetime.utcnow() - _db_chaos_state["failure_start_time"]).total_seconds()
    
    remaining = max(0, _db_chaos_state["failure_duration"] - elapsed)
    
    return {
        "primary_failed": _db_chaos_state["primary_failed"],
        "replica_failed": _db_chaos_state["replica_failed"],
        "connection_delay_ms": _db_chaos_state["connection_delay_ms"],
        "query_delay_ms": _db_chaos_state["query_delay_ms"],
        "failure_elapsed_seconds": elapsed,
        "failure_remaining_seconds": remaining,
        "active_db": get_active_db(),
    }
