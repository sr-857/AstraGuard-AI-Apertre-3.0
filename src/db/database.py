"""
Database integration layer for connection pooling.

This module provides a simplified interface for database operations using the connection pool.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite

from src.db.pool_config import PoolConfig
from src.db.pool_manager import AsyncConnectionPool
from src.db.pool_metrics import PoolStats

logger = logging.getLogger(__name__)

# Global pool instance
_pool: Optional[AsyncConnectionPool] = None
_config: Optional[PoolConfig] = None


async def init_pool(config: Optional[PoolConfig] = None) -> None:
    """
    Initialize the global connection pool.
    Called during application startup.
    
    Args:
        config: Optional pool configuration. If None, loads from file.
    """
    global _pool, _config
    
    if _pool is not None:
        logger.warning("Pool already initialized")
        return
    
    # Load configuration
    if config is None:
        config = PoolConfig.from_file()
    
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Invalid pool configuration: {e}. Using defaults.")
        config = PoolConfig()
    
    _config = config
    
    # Initialize pool if enabled
    if config.enable_pool:
        _pool = AsyncConnectionPool(config)
        await _pool.initialize()
        logger.info("Connection pool initialized successfully")
    else:
        logger.info("Connection pooling disabled, using direct connections")


async def close_pool() -> None:
    """
    Close the global connection pool.
    Called during application shutdown.
    """
    global _pool
    
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Connection pool closed")


@asynccontextmanager
async def get_connection():
    """
    Get a database connection from the pool or create a direct connection.
    
    Usage:
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT ...")
    
    Yields:
        aiosqlite.Connection
    """
    if _pool is not None and _config and _config.enable_pool:
        # Use pooled connection
        async with _pool.acquire() as conn:
            yield conn
    else:
        # Fallback to direct connection
        if _config:
            db_path = _config.db_path
        else:
            db_path = "data/contact_submissions.db"
        
        conn = await aiosqlite.connect(db_path)
        try:
            yield conn
        finally:
            await conn.close()


async def get_pool_stats() -> Optional[PoolStats]:
    """
    Get current pool statistics.
    Used by health check endpoints.
    
    Returns:
        PoolStats if pooling is enabled, None otherwise
    """
    if _pool is not None:
        return await _pool.get_stats()
    return None


def is_pool_enabled() -> bool:
    """
    Check if connection pooling is enabled.
    
    Returns:
        True if pooling is enabled
    """
    return _pool is not None
