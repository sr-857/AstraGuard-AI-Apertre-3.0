"""
Core connection pool manager for SQLite database operations.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

import aiosqlite

from src.db.exceptions import PoolClosedError, PoolExhaustedError, ConnectionError as PoolConnectionError
from src.db.pool_config import PoolConfig
from src.db.pool_metrics import PoolMetrics, PoolStats

logger = logging.getLogger(__name__)


@dataclass(frozen=False, eq=False)
class PooledConnection:
    """
    Wrapper for a pooled database connection.
    
    Attributes:
        connection: The underlying aiosqlite.Connection
        created_at: Timestamp when connection was created
        last_used: Timestamp of last use
        use_count: Number of times connection has been used
        is_valid: Whether connection is still valid
    """
    
    connection: aiosqlite.Connection
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    is_valid: bool = True
    
    def __hash__(self):
        """Make hashable based on connection object id."""
        return hash(id(self.connection))
    
    def __eq__(self, other):
        """Equality based on connection object identity."""
        if not isinstance(other, PooledConnection):
            return False
        return id(self.connection) == id(other.connection)
    
    def mark_used(self) -> None:
        """Update last_used timestamp and increment use_count."""
        self.last_used = datetime.now()
        self.use_count += 1
    
    def is_idle_expired(self, idle_timeout: float) -> bool:
        """
        Check if connection has exceeded idle timeout.
        
        Args:
            idle_timeout: Maximum idle time in seconds
            
        Returns:
            True if connection has been idle too long
        """
        idle_time = (datetime.now() - self.last_used).total_seconds()
        return idle_time > idle_timeout
    
    async def validate(self) -> bool:
        """
        Validate connection is still usable.
        Executes a simple query to verify connection health.
        
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            cursor = await self.connection.execute("SELECT 1")
            await cursor.close()
            return True
        except Exception as e:
            logger.warning(f"Connection validation failed: {e}")
            self.is_valid = False
            return False


class AsyncConnectionPool:
    """
    Manages a pool of aiosqlite database connections with configurable parameters.
    
    Attributes:
        config: PoolConfig instance with pool parameters
        _pool: Queue of available connections
        _active_connections: Set of currently in-use connections
        _lock: Asyncio lock for thread-safe operations
        _metrics: PoolMetrics instance for tracking statistics
        _closed: Boolean flag indicating if pool is closed
        _cleanup_task: Background task for idle connection cleanup
    """
    
    def __init__(self, config: PoolConfig):
        """
        Initialize the connection pool.
        
        Args:
            config: Pool configuration
        """
        self.config = config
        self._pool: asyncio.Queue[PooledConnection] = asyncio.Queue(maxsize=config.max_size)
        self._active_connections: Set[PooledConnection] = set()
        self._lock = asyncio.Lock()
        self._metrics = PoolMetrics()
        self._closed = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._total_connections = 0
    
    async def initialize(self) -> None:
        """
        Initialize the pool with minimum connections.
        Creates initial connections and starts background tasks.
        """
        logger.info(
            f"Initializing connection pool: max_size={self.config.max_size}, "
            f"min_size={self.config.min_size}, db_path={self.config.db_path}"
        )
        
        # Create minimum connections
        for _ in range(self.config.min_size):
            try:
                conn = await self._create_connection()
                await self._pool.put(conn)
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}", exc_info=True)
                raise
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"Connection pool initialized with {self.config.min_size} connections")
    
    async def _create_connection(self) -> PooledConnection:
        """
        Create a new aiosqlite connection.
        
        Returns:
            PooledConnection wrapper
            
        Raises:
            PoolConnectionError: If connection creation fails
        """
        try:
            # Ensure database directory exists
            db_path = Path(self.config.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            conn = await aiosqlite.connect(self.config.db_path)
            await self._metrics.record_connection_created()
            
            async with self._lock:
                self._total_connections += 1
            
            pooled_conn = PooledConnection(
                connection=conn,
                created_at=datetime.now(),
                last_used=datetime.now()
            )
            
            logger.debug(f"Created new connection (total: {self._total_connections})")
            return pooled_conn
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}", exc_info=True)
            raise PoolConnectionError(f"Failed to create connection: {e}") from e
    
    async def _validate_connection(self, pooled_conn: PooledConnection) -> bool:
        """
        Check connection health.
        
        Args:
            pooled_conn: Connection to validate
            
        Returns:
            True if connection is valid
        """
        return await pooled_conn.validate()
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.
        
        Yields:
            aiosqlite.Connection
            
        Raises:
            PoolExhaustedError: If no connection available within timeout
            PoolClosedError: If pool has been closed
        """
        if self._closed:
            raise PoolClosedError("Cannot acquire connection from closed pool")
        
        start_time = time.time()
        pooled_conn = None
        
        try:
            pooled_conn = await asyncio.wait_for(
                self._get_connection(),
                timeout=self.config.connection_timeout
            )
            
            wait_time = time.time() - start_time
            await self._metrics.record_acquisition(wait_time)
            
            pooled_conn.mark_used()
            
            async with self._lock:
                self._active_connections.add(pooled_conn)
            
            logger.debug(f"Connection acquired (wait time: {wait_time:.3f}s)")
            
            yield pooled_conn.connection
            
        except asyncio.TimeoutError:
            await self._metrics.record_timeout()
            stats = await self.get_stats()
            logger.warning(
                f"Pool exhausted: {stats.active_connections} active, "
                f"{stats.idle_connections} idle, {stats.max_size} max"
            )
            raise PoolExhaustedError(
                f"No connection available within {self.config.connection_timeout}s. "
                f"Pool stats: active={stats.active_connections}, "
                f"idle={stats.idle_connections}, max={stats.max_size}"
            )
        except Exception as e:
            await self._metrics.record_error()
            logger.error(f"Error acquiring connection: {e}", exc_info=True)
            raise
        finally:
            if pooled_conn:
                await self.release(pooled_conn)
    
    async def _get_connection(self) -> PooledConnection:
        """
        Get or create a connection.
        
        Returns:
            PooledConnection from pool or newly created
        """
        # Try to get from pool
        try:
            pooled_conn = self._pool.get_nowait()
            
            # Validate connection
            if await self._validate_connection(pooled_conn):
                return pooled_conn
            else:
                # Connection invalid, close and create new one
                logger.warning("Invalid connection found in pool, creating new one")
                try:
                    await pooled_conn.connection.close()
                except Exception:
                    pass
                
                async with self._lock:
                    self._total_connections -= 1
                
                return await self._create_connection_with_retry()
                
        except asyncio.QueueEmpty:
            # Pool empty, check if we can create new connection
            can_create = False
            async with self._lock:
                if self._total_connections < self.config.max_size:
                    can_create = True
                    # Reserve the slot immediately
                    self._total_connections += 1
            
            if can_create:
                try:
                    # Create connection outside the lock
                    conn = await aiosqlite.connect(self.config.db_path)
                    await self._metrics.record_connection_created()
                    
                    pooled_conn = PooledConnection(
                        connection=conn,
                        created_at=datetime.now(),
                        last_used=datetime.now()
                    )
                    
                    logger.debug(f"Created new connection (total: {self._total_connections})")
                    return pooled_conn
                except Exception as e:
                    # Failed to create, release the reserved slot
                    async with self._lock:
                        self._total_connections -= 1
                    logger.error(f"Failed to create connection: {e}", exc_info=True)
                    raise PoolConnectionError(f"Failed to create connection: {e}") from e
            
            # Pool full, wait for connection
            return await self._pool.get()
    
    async def _create_connection_with_retry(self) -> PooledConnection:
        """
        Create connection with retry logic.
        
        Returns:
            PooledConnection
            
        Raises:
            PoolConnectionError: If all retries fail
        """
        for attempt in range(self.config.max_retries):
            try:
                return await self._create_connection()
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    wait_time = self.config.retry_backoff * (2 ** attempt)
                    logger.warning(
                        f"Connection creation failed (attempt {attempt + 1}/{self.config.max_retries}), "
                        f"retrying in {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Connection creation failed after all retries")
                    raise PoolConnectionError("Failed to create connection after retries") from e
    
    async def release(self, pooled_conn: PooledConnection) -> None:
        """
        Return a connection to the pool.
        
        Args:
            pooled_conn: The connection to return
        """
        async with self._lock:
            if pooled_conn in self._active_connections:
                self._active_connections.remove(pooled_conn)
        
        await self._metrics.record_release()
        
        # Validate before returning to pool
        if await self._validate_connection(pooled_conn):
            try:
                self._pool.put_nowait(pooled_conn)
                logger.debug("Connection returned to pool")
            except asyncio.QueueFull:
                # Pool full, close connection
                logger.debug("Pool full, closing connection")
                try:
                    await pooled_conn.connection.close()
                except Exception:
                    pass
                
                async with self._lock:
                    self._total_connections -= 1
        else:
            # Connection invalid, close it
            logger.warning("Invalid connection not returned to pool")
            try:
                await pooled_conn.connection.close()
            except Exception:
                pass
            
            async with self._lock:
                self._total_connections -= 1
    
    async def _cleanup_loop(self) -> None:
        """Background task for cleaning up idle connections."""
        try:
            while not self._closed:
                await asyncio.sleep(60)  # Check every minute
                if not self._closed:  # Check again after sleep
                    await self._cleanup_idle_connections()
        except asyncio.CancelledError:
            logger.debug("Cleanup loop cancelled")
            # Don't re-raise, just exit cleanly
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}", exc_info=True)
    
    async def _cleanup_idle_connections(self) -> None:
        """Remove idle connections that exceed idle timeout."""
        connections_to_check = []
        
        # Get all connections from pool
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                connections_to_check.append(conn)
            except asyncio.QueueEmpty:
                break
        
        # Check each connection
        for pooled_conn in connections_to_check:
            if pooled_conn.is_idle_expired(self.config.idle_timeout):
                logger.debug("Closing idle connection")
                try:
                    await pooled_conn.connection.close()
                except Exception:
                    pass
                
                async with self._lock:
                    self._total_connections -= 1
            else:
                # Return to pool
                try:
                    self._pool.put_nowait(pooled_conn)
                except asyncio.QueueFull:
                    # Pool full, close connection
                    try:
                        await pooled_conn.connection.close()
                    except Exception:
                        pass
                    
                    async with self._lock:
                        self._total_connections -= 1
    
    async def close(self) -> None:
        """
        Close all connections and shut down the pool.
        Waits for active operations to complete.
        """
        logger.info("Closing connection pool")
        self._closed = True
        
        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await asyncio.wait_for(self._cleanup_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        # Wait for active operations
        await self._wait_for_active_operations()
        
        # Close all connections
        await self._close_all_connections()
        
        logger.info("Connection pool closed")
    
    async def _wait_for_active_operations(self, timeout: float = 10.0) -> None:
        """
        Wait for active operations to complete.
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        start_time = time.time()
        
        while self._active_connections:
            if time.time() - start_time > timeout:
                logger.warning(
                    f"Timeout waiting for active operations "
                    f"({len(self._active_connections)} still active)"
                )
                break
            
            await asyncio.sleep(0.1)
    
    async def _close_all_connections(self) -> None:
        """Close all pool connections."""
        # Close active connections
        for pooled_conn in list(self._active_connections):
            try:
                await pooled_conn.connection.close()
            except Exception as e:
                logger.warning(f"Error closing active connection: {e}")
        
        self._active_connections.clear()
        
        # Close idle connections
        while not self._pool.empty():
            try:
                pooled_conn = self._pool.get_nowait()
                await pooled_conn.connection.close()
            except Exception as e:
                logger.warning(f"Error closing idle connection: {e}")
        
        async with self._lock:
            self._total_connections = 0
    
    async def get_stats(self) -> PoolStats:
        """
        Get current pool statistics.
        
        Returns:
            PoolStats with current metrics
        """
        async with self._lock:
            active_count = len(self._active_connections)
            idle_count = self._pool.qsize()
            total_count = self._total_connections
        
        avg_wait_time = await self._metrics.get_average_wait_time()
        
        return PoolStats(
            active_connections=active_count,
            idle_connections=idle_count,
            total_connections=total_count,
            max_size=self.config.max_size,
            total_created=self._metrics.total_connections_created,
            total_timeouts=self._metrics.total_timeouts,
            average_wait_time=avg_wait_time,
            total_acquisitions=self._metrics.total_acquisitions,
            total_releases=self._metrics.total_releases,
            total_errors=self._metrics.total_errors,
        )
