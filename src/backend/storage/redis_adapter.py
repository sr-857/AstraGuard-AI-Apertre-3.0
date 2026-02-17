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

    @classmethod
    async def from_url(
        cls,
        url: str,
        max_retries: int = 5,
        retry_delay: float = 2.0
    ) -> "RedisAdapter":
        """
        Create adapter from URL with connection retries.

        Args:
            url: Redis connection URL
            max_retries: Number of connection attempts
            retry_delay: Delay between attempts in seconds

        Returns:
            Connected RedisAdapter instance

        Raises:
            RuntimeError: If connection fails after retries
        """
        adapter = cls(redis_url=url)

        for attempt in range(max_retries):
            if await adapter.connect():
                return adapter

            logger.warning(
                f"Redis connection failed (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay}s..."
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        raise RuntimeError(f"Failed to connect to Redis at {url} after {max_retries} attempts")

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

    # ========================================================================
    # Distributed Coordination Methods
    # ========================================================================

    async def set_nx(
        self,
        key: str,
        value: Any,
        *,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set key only if it doesn't exist (SET NX).
        
        Used for leader election and distributed locking.
        
        Args:
            key: The key to set
            value: The value to store
            expire: Optional TTL in seconds
            
        Returns:
            True if key was set, False if key already exists
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        try:
            serialized = self._serialize(value)
            result = await self._execute_with_retry(
                self.redis.set,
                key,
                serialized,
                nx=True,  # Only set if not exists
                ex=expire
            )
            success = bool(result)
            if success:
                logger.debug(f"Set key {key} with NX" + (f" and TTL {expire}s" if expire else ""))
            return success
        except Exception as e:
            logger.error(f"Failed to set key {key} with NX: {e}")
            return False

    async def eval_script(
        self,
        script: str,
        keys: List[str],
        args: List[Any]
    ) -> Any:
        """
        Execute Lua script atomically.
        
        Args:
            script: Lua script to execute
            keys: List of keys (available as KEYS in script)
            args: List of arguments (available as ARGV in script)
            
        Returns:
            Script result (deserialized if JSON)
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return None

        try:
            # Serialize arguments
            serialized_args = [self._serialize(arg) for arg in args]
            
            result = await self._execute_with_retry(
                self.redis.eval,
                script,
                len(keys),
                *keys,
                *serialized_args
            )
            
            logger.debug(f"Executed Lua script with {len(keys)} keys")
            return self._deserialize(result) if isinstance(result, str) else result
        except Exception as e:
            logger.error(f"Failed to execute Lua script: {e}")
            return None

    async def publish(self, channel: str, message: Any) -> int:
        """
        Publish message to pub/sub channel.
        
        Args:
            channel: Channel name
            message: Message to publish (will be serialized to JSON)
            
        Returns:
            Number of subscribers that received the message
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return 0

        try:
            serialized = self._serialize(message)
            subscribers = await self._execute_with_retry(
                self.redis.publish,
                channel,
                serialized
            )
            logger.debug(f"Published to {channel}, {subscribers} subscribers")
            return subscribers
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")
            return 0

    async def subscribe(self, channel: str):
        """
        Subscribe to pub/sub channel.
        
        Args:
            channel: Channel name to subscribe to
            
        Returns:
            PubSub object for receiving messages, or None on failure
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return None

        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")
            return pubsub
        except Exception as e:
            logger.error(f"Failed to subscribe to {channel}: {e}")
            return None

    async def pipeline_get(self, keys: List[str]) -> Dict[str, Any]:
        """
        Batch get multiple keys using pipeline.
        
        Args:
            keys: List of keys to retrieve
            
        Returns:
            Dict mapping keys to values (None for missing keys)
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return {}

        if not keys:
            return {}

        try:
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)
            
            values = await self._execute_with_retry(pipe.execute)
            
            result = {}
            for key, value in zip(keys, values):
                result[key] = self._deserialize(value)
            
            logger.debug(f"Pipeline get {len(keys)} keys")
            return result
        except Exception as e:
            logger.error(f"Failed to pipeline get keys: {e}")
            return {}

    async def pipeline_set(
        self,
        items: Dict[str, Any],
        *,
        expire: Optional[int] = None
    ) -> bool:
        """
        Batch set multiple keys using pipeline.
        
        Args:
            items: Dict mapping keys to values
            expire: Optional TTL in seconds (applied to all keys)
            
        Returns:
            True if all sets successful, False otherwise
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        if not items:
            return True

        try:
            pipe = self.redis.pipeline()
            for key, value in items.items():
                serialized = self._serialize(value)
                pipe.set(key, serialized, ex=expire)
            
            await self._execute_with_retry(pipe.execute)
            
            logger.debug(f"Pipeline set {len(items)} keys" + (f" with TTL {expire}s" if expire else ""))
            return True
        except Exception as e:
            logger.error(f"Failed to pipeline set keys: {e}")
            return False

    async def pipeline_delete(self, keys: List[str]) -> int:
        """
        Batch delete multiple keys using pipeline.
        
        Args:
            keys: List of keys to delete
            
        Returns:
            Number of keys deleted
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return 0

        if not keys:
            return 0

        try:
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.delete(key)
            
            results = await self._execute_with_retry(pipe.execute)
            deleted = sum(1 for r in results if r)
            
            logger.debug(f"Pipeline deleted {deleted}/{len(keys)} keys")
            return deleted
        except Exception as e:
            logger.error(f"Failed to pipeline delete keys: {e}")
            return 0

    # ========================================================================
    # Distributed Coordination Methods
    # ========================================================================

    async def set_nx(
        self,
        key: str,
        value: Any,
        *,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set key only if it doesn't exist (SET NX).
        
        Used for leader election and distributed locking.
        
        Args:
            key: The key to set
            value: The value to store
            expire: Optional TTL in seconds
            
        Returns:
            True if key was set, False if key already exists
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        try:
            serialized = self._serialize(value)
            result = await self._execute_with_retry(
                self.redis.set,
                key,
                serialized,
                nx=True,  # Only set if not exists
                ex=expire
            )
            success = bool(result)
            if success:
                logger.debug(f"Set key {key} with NX" + (f" and TTL {expire}s" if expire else ""))
            return success
        except Exception as e:
            logger.error(f"Failed to set key {key} with NX: {e}")
            return False

    async def eval_script(
        self,
        script: str,
        keys: List[str],
        args: List[Any]
    ) -> Any:
        """
        Execute Lua script atomically.
        
        Args:
            script: Lua script to execute
            keys: List of keys (available as KEYS in script)
            args: List of arguments (available as ARGV in script)
            
        Returns:
            Script result (deserialized if JSON)
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return None

        try:
            # Serialize arguments
            serialized_args = [self._serialize(arg) for arg in args]
            
            result = await self._execute_with_retry(
                self.redis.eval,
                script,
                len(keys),
                *keys,
                *serialized_args
            )
            
            logger.debug(f"Executed Lua script with {len(keys)} keys")
            return self._deserialize(result) if isinstance(result, str) else result
        except Exception as e:
            logger.error(f"Failed to execute Lua script: {e}")
            return None

    async def publish(self, channel: str, message: Any) -> int:
        """
        Publish message to pub/sub channel.
        
        Args:
            channel: Channel name
            message: Message to publish (will be serialized to JSON)
            
        Returns:
            Number of subscribers that received the message
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return 0

        try:
            serialized = self._serialize(message)
            subscribers = await self._execute_with_retry(
                self.redis.publish,
                channel,
                serialized
            )
            logger.debug(f"Published to {channel}, {subscribers} subscribers")
            return subscribers
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")
            return 0

    async def subscribe(self, channel: str):
        """
        Subscribe to pub/sub channel.
        
        Args:
            channel: Channel name to subscribe to
            
        Returns:
            PubSub object for receiving messages, or None on failure
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return None

        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")
            return pubsub
        except Exception as e:
            logger.error(f"Failed to subscribe to {channel}: {e}")
            return None

    async def pipeline_get(self, keys: List[str]) -> Dict[str, Any]:
        """
        Batch get multiple keys using pipeline.
        
        Args:
            keys: List of keys to retrieve
            
        Returns:
            Dict mapping keys to values (None for missing keys)
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return {}

        if not keys:
            return {}

        try:
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)
            
            values = await self._execute_with_retry(pipe.execute)
            
            result = {}
            for key, value in zip(keys, values):
                result[key] = self._deserialize(value)
            
            logger.debug(f"Pipeline get {len(keys)} keys")
            return result
        except Exception as e:
            logger.error(f"Failed to pipeline get keys: {e}")
            return {}

    async def pipeline_set(
        self,
        items: Dict[str, Any],
        *,
        expire: Optional[int] = None
    ) -> bool:
        """
        Batch set multiple keys using pipeline.
        
        Args:
            items: Dict mapping keys to values
            expire: Optional TTL in seconds (applied to all keys)
            
        Returns:
            True if all sets successful, False otherwise
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        if not items:
            return True

        try:
            pipe = self.redis.pipeline()
            for key, value in items.items():
                serialized = self._serialize(value)
                pipe.set(key, serialized, ex=expire)
            
            await self._execute_with_retry(pipe.execute)
            
            logger.debug(f"Pipeline set {len(items)} keys" + (f" with TTL {expire}s" if expire else ""))
            return True
        except Exception as e:
            logger.error(f"Failed to pipeline set keys: {e}")
            return False

    async def pipeline_delete(self, keys: List[str]) -> int:
        """
        Batch delete multiple keys using pipeline.
        
        Args:
            keys: List of keys to delete
            
        Returns:
            Number of keys deleted
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return 0

        if not keys:
            return 0

        try:
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.delete(key)
            
            results = await self._execute_with_retry(pipe.execute)
            deleted = sum(1 for r in results if r)
            
            logger.debug(f"Pipeline deleted {deleted}/{len(keys)} keys")
            return deleted
        except Exception as e:
            logger.error(f"Failed to pipeline delete keys: {e}")
            return 0

    # ========================================================================
    # Distributed Coordination Methods
    # ========================================================================

    async def set_nx(
        self,
        key: str,
        value: Any,
        *,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set key only if it doesn't exist (SET NX).
        
        Used for leader election and distributed locking.
        
        Args:
            key: The key to set
            value: The value to store
            expire: Optional TTL in seconds
            
        Returns:
            True if key was set, False if key already exists
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        try:
            serialized = self._serialize(value)
            result = await self._execute_with_retry(
                self.redis.set,
                key,
                serialized,
                nx=True,  # Only set if not exists
                ex=expire
            )
            success = bool(result)
            if success:
                logger.debug(f"Set key {key} with NX" + (f" and TTL {expire}s" if expire else ""))
            return success
        except Exception as e:
            logger.error(f"Failed to set key {key} with NX: {e}")
            return False

    async def eval_script(
        self,
        script: str,
        keys: List[str],
        args: List[Any]
    ) -> Any:
        """
        Execute Lua script atomically.
        
        Args:
            script: Lua script to execute
            keys: List of keys (available as KEYS in script)
            args: List of arguments (available as ARGV in script)
            
        Returns:
            Script result (deserialized if JSON)
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return None

        try:
            # Serialize arguments
            serialized_args = [self._serialize(arg) for arg in args]
            
            result = await self._execute_with_retry(
                self.redis.eval,
                script,
                len(keys),
                *keys,
                *serialized_args
            )
            
            logger.debug(f"Executed Lua script with {len(keys)} keys")
            return self._deserialize(result) if isinstance(result, str) else result
        except Exception as e:
            logger.error(f"Failed to execute Lua script: {e}")
            return None

    async def publish(self, channel: str, message: Any) -> int:
        """
        Publish message to pub/sub channel.
        
        Args:
            channel: Channel name
            message: Message to publish (will be serialized to JSON)
            
        Returns:
            Number of subscribers that received the message
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return 0

        try:
            serialized = self._serialize(message)
            subscribers = await self._execute_with_retry(
                self.redis.publish,
                channel,
                serialized
            )
            logger.debug(f"Published to {channel}, {subscribers} subscribers")
            return subscribers
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")
            return 0

    async def subscribe(self, channel: str):
        """
        Subscribe to pub/sub channel.
        
        Args:
            channel: Channel name to subscribe to
            
        Returns:
            PubSub object for receiving messages, or None on failure
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return None

        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")
            return pubsub
        except Exception as e:
            logger.error(f"Failed to subscribe to {channel}: {e}")
            return None

    async def pipeline_get(self, keys: List[str]) -> Dict[str, Any]:
        """
        Batch get multiple keys using pipeline.
        
        Args:
            keys: List of keys to retrieve
            
        Returns:
            Dict mapping keys to values (None for missing keys)
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return {}

        if not keys:
            return {}

        try:
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)
            
            values = await self._execute_with_retry(pipe.execute)
            
            result = {}
            for key, value in zip(keys, values):
                result[key] = self._deserialize(value)
            
            logger.debug(f"Pipeline get {len(keys)} keys")
            return result
        except Exception as e:
            logger.error(f"Failed to pipeline get keys: {e}")
            return {}

    async def pipeline_set(
        self,
        items: Dict[str, Any],
        *,
        expire: Optional[int] = None
    ) -> bool:
        """
        Batch set multiple keys using pipeline.
        
        Args:
            items: Dict mapping keys to values
            expire: Optional TTL in seconds (applied to all keys)
            
        Returns:
            True if all sets successful, False otherwise
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return False

        if not items:
            return True

        try:
            pipe = self.redis.pipeline()
            for key, value in items.items():
                serialized = self._serialize(value)
                pipe.set(key, serialized, ex=expire)
            
            await self._execute_with_retry(pipe.execute)
            
            logger.debug(f"Pipeline set {len(items)} keys" + (f" with TTL {expire}s" if expire else ""))
            return True
        except Exception as e:
            logger.error(f"Failed to pipeline set keys: {e}")
            return False

    async def pipeline_delete(self, keys: List[str]) -> int:
        """
        Batch delete multiple keys using pipeline.
        
        Args:
            keys: List of keys to delete
            
        Returns:
            Number of keys deleted
        """
        if not self.connected:
            logger.warning("Redis not connected")
            return 0

        if not keys:
            return 0

        try:
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.delete(key)
            
            results = await self._execute_with_retry(pipe.execute)
            deleted = sum(1 for r in results if r)
            
            logger.debug(f"Pipeline deleted {deleted}/{len(keys)} keys")
            return deleted
        except Exception as e:
            logger.error(f"Failed to pipeline delete keys: {e}")
            return 0
