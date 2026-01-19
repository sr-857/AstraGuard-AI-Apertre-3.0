"""
Redis Cache Implementation

Redis-backed cache adapter for production environments.
Wraps existing backend.storage infrastructure for consistency.
"""

import json
import logging
import time
from typing import Any, Optional

from backend.cache.interface import Cache, CacheStats

logger = logging.getLogger(__name__)

# Key prefix to namespace cache entries
CACHE_KEY_PREFIX = "astra:cache:"


class RedisCache(Cache):
    """Redis-backed cache implementation.
    
    Uses existing backend.storage.RedisAdapter infrastructure for
    consistency with other Redis usage in the project.
    
    Features:
    - JSON serialization for complex types
    - TTL via Redis EXPIRE
    - Stats via local counters (Redis INFO for size)
    - Graceful fallback on connection errors
    
    Example:
        from backend.storage import RedisAdapter
        
        storage = await RedisAdapter.from_url("redis://localhost:6379")
        cache = RedisCache(storage=storage, default_ttl=60)
        await cache.set("key", {"data": "value"})
    """
    
    def __init__(
        self,
        storage=None,
        redis_url: str = "redis://localhost:6379",
        default_ttl: Optional[int] = 60,
        metrics_sink=None,
        key_prefix: str = CACHE_KEY_PREFIX
    ):
        """Initialize Redis cache.
        
        Args:
            storage: Optional pre-configured Storage instance
            redis_url: Redis connection URL (used if storage not provided)
            default_ttl: Default TTL in seconds
            metrics_sink: Optional MetricsSink for cache metrics
            key_prefix: Prefix for cache keys (default: "astra:cache:")
        """
        self._storage = storage
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._metrics_sink = metrics_sink
        self._key_prefix = key_prefix
        
        # Local statistics (Redis operations are tracked here)
        self._hits = 0
        self._misses = 0
        self._evictions = 0  # Not directly tracked for Redis
        
        self._connected = storage is not None
        
        logger.debug(
            f"RedisCache initialized: url={redis_url}, "
            f"default_ttl={default_ttl}, prefix={key_prefix}"
        )
    
    async def connect(self) -> bool:
        """Establish connection to Redis if not already connected.
        
        Returns:
            True if connected successfully
        """
        if self._connected and self._storage is not None:
            return True
        
        try:
            from backend.storage import RedisAdapter
            self._storage = await RedisAdapter.from_url(self._redis_url)
            self._connected = True
            logger.info(f"RedisCache connected to {self._redis_url}")
            return True
        except Exception as e:
            logger.error(f"RedisCache connection failed: {e}")
            self._connected = False
            return False
    
    def _make_key(self, key: str) -> str:
        """Create namespaced cache key."""
        return f"{self._key_prefix}{key}"
    
    def _serialize(self, value: Any) -> str:
        """Serialize value for Redis storage."""
        return json.dumps(value)
    
    def _deserialize(self, data: str) -> Any:
        """Deserialize value from Redis storage."""
        return json.loads(data)
    
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value by key from Redis.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if not self._connected:
            if not await self.connect():
                self._misses += 1
                return None
        
        start_time = time.time()
        redis_key = self._make_key(key)
        
        try:
            data = await self._storage.get(redis_key)
            
            if data is None:
                self._misses += 1
                self._emit_miss(key, start_time)
                return None
            
            value = self._deserialize(data)
            self._hits += 1
            self._emit_hit(key, start_time)
            return value
            
        except json.JSONDecodeError as e:
            logger.warning(f"Cache deserialization error for {key}: {e}")
            self._misses += 1
            return None
        except Exception as e:
            logger.error(f"RedisCache get error for {key}: {e}")
            self._misses += 1
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Store value in Redis with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: TTL in seconds (None uses default_ttl)
            
        Returns:
            True if successful
        """
        if not self._connected:
            if not await self.connect():
                return False
        
        effective_ttl = ttl if ttl is not None else self._default_ttl
        redis_key = self._make_key(key)
        
        try:
            data = self._serialize(value)
            success = await self._storage.set(redis_key, data, ttl=effective_ttl)
            
            if success:
                logger.debug(f"RedisCache set: {key} (ttl={effective_ttl})")
            
            return success
            
        except (TypeError, ValueError) as e:
            logger.error(f"Cache serialization error for {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"RedisCache set error for {key}: {e}")
            return False
    
    async def invalidate(self, key: str) -> bool:
        """Invalidate a single cache entry.
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            True if key existed and was removed
        """
        if not self._connected:
            if not await self.connect():
                return False
        
        redis_key = self._make_key(key)
        
        try:
            result = await self._storage.delete(redis_key)
            if result:
                logger.debug(f"RedisCache invalidated: {key}")
            return result
        except Exception as e:
            logger.error(f"RedisCache invalidate error for {key}: {e}")
            return False
    
    async def clear(self) -> int:
        """Clear all cache entries with this prefix.
        
        Returns:
            Number of entries cleared
        """
        if not self._connected:
            if not await self.connect():
                return 0
        
        try:
            # Find all keys with our prefix
            pattern = f"{self._key_prefix}*"
            keys = await self._storage.keys(pattern)
            
            if not keys:
                return 0
            
            # Delete all found keys
            count = 0
            for key in keys:
                if await self._storage.delete(key):
                    count += 1
            
            logger.info(f"RedisCache cleared: {count} entries removed")
            return count
            
        except Exception as e:
            logger.error(f"RedisCache clear error: {e}")
            return 0
    
    def stats(self) -> CacheStats:
        """Get cache statistics.
        
        Note: size is not available without Redis INFO call.
        
        Returns:
            CacheStats with current metrics
        """
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            size=0,  # Would require additional Redis call
        )
    
    async def get_size(self) -> int:
        """Get approximate number of cache entries.
        
        Performs a SCAN to count keys with our prefix.
        
        Returns:
            Number of entries
        """
        if not self._connected:
            return 0
        
        try:
            keys = await self._storage.keys(f"{self._key_prefix}*")
            return len(keys)
        except Exception:
            return 0
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    # -------------------------------------------------------------------------
    # Metrics Emission Helpers
    # -------------------------------------------------------------------------
    
    def _emit_hit(self, key: str, start_time: float) -> None:
        """Emit cache hit metrics."""
        if self._metrics_sink is None:
            return
        
        latency_ms = (time.time() - start_time) * 1000
        self._metrics_sink.emit_counter(
            "cache_hits_total",
            tags={"cache": "redis"}
        )
        self._metrics_sink.emit_histogram(
            "cache_latency_ms",
            latency_ms,
            tags={"cache": "redis", "result": "hit"}
        )
    
    def _emit_miss(self, key: str, start_time: float) -> None:
        """Emit cache miss metrics."""
        if self._metrics_sink is None:
            return
        
        latency_ms = (time.time() - start_time) * 1000
        self._metrics_sink.emit_counter(
            "cache_misses_total",
            tags={"cache": "redis"}
        )
        self._metrics_sink.emit_histogram(
            "cache_latency_ms",
            latency_ms,
            tags={"cache": "redis", "result": "miss"}
        )
