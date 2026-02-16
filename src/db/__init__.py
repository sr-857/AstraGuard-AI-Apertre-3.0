"""
Database connection pooling module for AstraGuard AI.

This module provides connection pooling functionality for SQLite database operations,
improving performance and resource management under high traffic.
"""

from src.db.exceptions import (
    PoolError,
    PoolExhaustedError,
    PoolClosedError,
    ConnectionError as PoolConnectionError,
)
from src.db.pool_config import PoolConfig
from src.db.pool_metrics import PoolMetrics, PoolStats
from src.db.database import (
    init_pool,
    close_pool,
    get_connection,
    get_pool_stats,
    is_pool_enabled,
)

__all__ = [
    "PoolError",
    "PoolExhaustedError",
    "PoolClosedError",
    "PoolConnectionError",
    "PoolConfig",
    "PoolMetrics",
    "PoolStats",
    "init_pool",
    "close_pool",
    "get_connection",
    "get_pool_stats",
    "is_pool_enabled",
]
