"""
Cache Interface and Types

Defines the abstract Cache protocol and associated types for the caching layer.
All cache implementations must conform to this interface.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring.
    
    Attributes:
        hits: Number of successful cache retrievals
        misses: Number of cache misses (key not found or expired)
        evictions: Number of entries evicted due to size limits
        size: Current number of entries in cache
    """
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    
    def hit_rate(self) -> float:
        """Calculate cache hit rate.
        
        Returns:
            Hit rate as float between 0.0 and 1.0
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    def to_dict(self) -> dict:
        """Convert stats to dictionary for serialization."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "hit_rate": self.hit_rate(),
        }


class Cache(ABC):
    """Abstract cache interface.
    
    Implementations must provide thread-safe operations for:
    - get/set with optional TTL
    - invalidation (single key or pattern)
    - clearing all entries
    - statistics reporting
    
    Implementations:
    - InMemoryLRUCache: Thread-safe LRU cache for local/staging
    - RedisCache: Redis-backed cache for production
    """
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value by key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        ...
    
    @abstractmethod
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Store value with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (must be serializable for Redis)
            ttl: Time to live in seconds (None uses default)
            
        Returns:
            True if successful, False otherwise
        """
        ...
    
    @abstractmethod
    async def invalidate(self, key: str) -> bool:
        """Invalidate a single cache entry.
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            True if key existed and was removed, False otherwise
        """
        ...
    
    @abstractmethod
    async def clear(self) -> int:
        """Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        ...
    
    @abstractmethod
    def stats(self) -> CacheStats:
        """Get cache statistics.
        
        Returns:
            CacheStats with hits, misses, evictions, size
        """
        ...
    
    async def get_or_set(
        self,
        key: str,
        factory,
        ttl: Optional[int] = None
    ) -> Any:
        """Get value from cache or compute and store it.
        
        Args:
            key: Cache key
            factory: Async callable to compute value if not cached
            ttl: Optional TTL override
            
        Returns:
            Cached or computed value
        """
        value = await self.get(key)
        if value is not None:
            return value
        
        # Compute value
        if callable(factory):
            import asyncio
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()
        else:
            value = factory
        
        await self.set(key, value, ttl)
        return value
