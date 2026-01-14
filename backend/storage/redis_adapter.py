"""
Redis adapter implementing the Storage interface.

Wraps Redis operations with proper serialization, connection handling,
retries, and health checks. This adapter contains no business logic—
only storage concerns.
"""

import redis.asyncio as aioredis
import json
import logging
import asyncio
from typing import Optional, Any, List, Dict
from datetime import datetime

from backend.storage.interface import Storage

logger = logging.getLogger(__name__)


class RedisAdapter:
    """
    Redis-backed storage implementation.
    
    Provides a clean abstraction over Redis with JSON serialization,
    connection management, and proper error handling.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        timeout: float = 5.0,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ):
        """
        Initialize Redis adapter.
        
        Args:
            redis_url: Redis connection URL
            timeout: Default timeout for operations in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.redis_url = redis_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.redis: Optional[aioredis.Redis] = None
        self.connected = False

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "RedisAdapter":
        """
        Create adapter from configuration dictionary.
        
        Args:
            config: Configuration dict with keys like redis_url, timeout, etc.
            
        Returns:
            Configured RedisAdapter instance
        """
        return cls(
            redis_url=config.get("redis_url", "redis://localhost:6379"),
            timeout=config.get("timeout", 5.0),
            max_retries=config.get("max_retries", 3),
            retry_delay=config.get("retry_delay", 0.5)
        )

    async def connect(self) -> bool:
        """
        Establish connection to Redis.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            self.connected = True
            logger.info(f"Connected to Redis: {self.redis_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            try:
                await self.redis.close()
                self.connected = False
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """
        Execute operation with retry logic.
        
        Args:
            operation: Async callable to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result of operation
            
        Raises:
            Exception: If all retries exhausted
        """
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await asyncio.wait_for(
                    operation(*args, **kwargs),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    f"Operation timeout (attempt {attempt + 1}/{self.max_retries})"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Operation failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        raise last_error

    def _serialize(self, value: Any) -> str:
        """
        Serialize value to JSON string.
        
        Args:
            value: Value to serialize
            
        Returns:
            JSON string representation
        """
        if isinstance(value, str):
            return value
        return json.dumps(value)

    def _deserialize(self, value: Optional[str]) -> Optional[Any]:
        """
        Deserialize JSON string to Python object.
        
        Args:
            value: JSON string or None
            
        Returns:
            Deserialized object or None
        """
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # If not valid JSON, return as-is (plain string)
            return value

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value by key.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The stored value (deserialized from JSON) or None if not found
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return None

        try:
            value = await self._execute_with_retry(self.redis.get, key)
            return self._deserialize(value)
        except Exception as e:
            logger.error(f"Failed to get key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        *,
        expire: Optional[int] = None
    ) -> bool:
        """
        Store a value with optional expiration.
        
        Args:
            key: The key to store under
            value: The value to store (will be serialized to JSON)
            expire: Optional TTL in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        try:
            serialized = self._serialize(value)
            await self._execute_with_retry(
                self.redis.set,
                key,
                serialized,
                ex=expire
            )
            logger.debug(f"Set key {key}" + (f" with TTL {expire}s" if expire else ""))
            return True
        except Exception as e:
            logger.error(f"Failed to set key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete a key.
        
        Args:
            key: The key to delete
            
        Returns:
            True if key was deleted, False if key didn't exist
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        try:
            result = await self._execute_with_retry(self.redis.delete, key)
            deleted = result > 0
            if deleted:
                logger.debug(f"Deleted key {key}")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete key {key}: {e}")
            return False

    async def scan_keys(self, pattern: str) -> List[str]:
        """
        Scan for keys matching a pattern using non-blocking SCAN.
        
        Args:
            pattern: Glob-style pattern (e.g., "prefix:*")
            
        Returns:
            List of matching keys
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return []

        try:
            keys = []
            cursor = 0
            
            while True:
                cursor, batch_keys = await self._execute_with_retry(
                    self.redis.scan,
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                keys.extend(batch_keys)
                if cursor == 0:
                    break
            
            logger.debug(f"Scanned {len(keys)} keys matching {pattern}")
            return keys
        except Exception as e:
            logger.error(f"Failed to scan keys with pattern {pattern}: {e}")
            return []

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration on an existing key.
        
        Args:
            key: The key to set expiration on
            seconds: TTL in seconds
            
        Returns:
            True if expiration was set, False if key doesn't exist
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        try:
            result = await self._execute_with_retry(
                self.redis.expire,
                key,
                seconds
            )
            success = bool(result)
            if success:
                logger.debug(f"Set expiration on {key} to {seconds}s")
            return success
        except Exception as e:
            logger.error(f"Failed to set expiration on {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists.
        
        Args:
            key: The key to check
            
        Returns:
            True if key exists, False otherwise
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        try:
            result = await self._execute_with_retry(self.redis.exists, key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to check existence of {key}: {e}")
            return False

    async def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        if not self.connected:
            return False

        try:
            await self._execute_with_retry(self.redis.ping)
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self.connected = False
            return False
