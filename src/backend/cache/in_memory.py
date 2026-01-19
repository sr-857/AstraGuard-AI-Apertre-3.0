"""
In-Memory LRU Cache Implementation

Thread-safe LRU cache with TTL support for local and staging environments.
Uses OrderedDict for O(1) LRU eviction and threading.Lock for safety.
"""

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional

from backend.cache.interface import Cache, CacheStats

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Internal cache entry with value and expiration."""
    value: Any
    expires_at: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class InMemoryLRUCache(Cache):
    """Thread-safe in-memory LRU cache with TTL support.
    
    Features:
    - O(1) get/set/invalidate operations
    - LRU eviction when maxsize is reached
    - Per-entry TTL with automatic expiration
    - Thread-safe via lock
    - Optional metrics emission via MetricsSink
    
    Example:
        cache = InMemoryLRUCache(maxsize=1024, default_ttl=60)
        await cache.set("key", "value")
        result = await cache.get("key")
    """
    
    def __init__(
        self,
        maxsize: int = 1024,
        default_ttl: Optional[int] = None,
        metrics_sink=None
    ):
        """Initialize LRU cache.
        
        Args:
            maxsize: Maximum number of entries (default: 1024)
            default_ttl: Default TTL in seconds (None = no expiration)
            metrics_sink: Optional MetricsSink for cache metrics
        """
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._metrics_sink = metrics_sink
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        logger.debug(
            f"InMemoryLRUCache initialized: maxsize={maxsize}, "
            f"default_ttl={default_ttl}"
        )
    
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value by key.
        
        Moves accessed entry to end of OrderedDict (most recently used).
        Returns None and increments miss count if key not found or expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        start_time = time.time()
        
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                self._emit_miss(key, start_time)
                return None
            
            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self._misses += 1
                self._emit_miss(key, start_time)
                logger.debug(f"Cache key expired: {key}")
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            self._emit_hit(key, start_time)
            
            return entry.value
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Store value with optional TTL.
        
        If cache is at maxsize, evicts least recently used entry.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None uses default_ttl)
            
        Returns:
            True (always succeeds for in-memory cache)
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = None
        if effective_ttl is not None:
            expires_at = time.time() + effective_ttl
        
        entry = CacheEntry(value=value, expires_at=expires_at)
        
        with self._lock:
            # If key exists, update and move to end
            if key in self._cache:
                self._cache[key] = entry
                self._cache.move_to_end(key)
                return True
            
            # Evict LRU if at capacity
            while len(self._cache) >= self._maxsize:
                evicted_key, _ = self._cache.popitem(last=False)
                self._evictions += 1
                self._emit_eviction(evicted_key)
                logger.debug(f"Cache evicted LRU key: {evicted_key}")
            
            self._cache[key] = entry
        
        return True
    
    async def invalidate(self, key: str) -> bool:
        """Invalidate a single cache entry.
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            True if key existed and was removed
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache invalidated key: {key}")
                return True
            return False
    
    async def clear(self) -> int:
        """Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")
            return count
    
    def stats(self) -> CacheStats:
        """Get cache statistics.
        
        Returns:
            CacheStats with current metrics
        """
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                size=len(self._cache),
            )
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0
    
    async def cleanup_expired(self) -> int:
        """Remove all expired entries.
        
        Call periodically to proactively clean up expired entries.
        
        Returns:
            Number of entries removed
        """
        removed = 0
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        
        if removed > 0:
            logger.debug(f"Cache cleanup: {removed} expired entries removed")
        
        return removed
    
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
            tags={"cache": "memory"}
        )
        self._metrics_sink.emit_histogram(
            "cache_latency_ms",
            latency_ms,
            tags={"cache": "memory", "result": "hit"}
        )
    
    def _emit_miss(self, key: str, start_time: float) -> None:
        """Emit cache miss metrics."""
        if self._metrics_sink is None:
            return
        
        latency_ms = (time.time() - start_time) * 1000
        self._metrics_sink.emit_counter(
            "cache_misses_total",
            tags={"cache": "memory"}
        )
        self._metrics_sink.emit_histogram(
            "cache_latency_ms",
            latency_ms,
            tags={"cache": "memory", "result": "miss"}
        )
    
    def _emit_eviction(self, key: str) -> None:
        """Emit cache eviction metrics."""
        if self._metrics_sink is None:
            return
        
        self._metrics_sink.emit_counter(
            "cache_evictions_total",
            tags={"cache": "memory"}
        )
