"""
Cache Abstraction Layer for AstraGuard-AI

Provides a standardized cache interface with multiple implementations:
- InMemoryLRUCache: Thread-safe LRU cache for local/staging
- RedisCache: Optional Redis-backed cache for production

Example usage:
    from backend.cache import InMemoryLRUCache, cached
    
    cache = InMemoryLRUCache(maxsize=1024, default_ttl=60)
    
    @cached(cache=cache, key_fn=lambda x: f"user:{x}")
    async def get_user(user_id: str) -> dict:
        ...
"""

from backend.cache.interface import Cache, CacheStats
from backend.cache.in_memory import InMemoryLRUCache
from backend.cache.decorators import cached
from backend.cache.config import get_cache_config, create_cache

# Redis cache is optional; import if available
try:
    from backend.cache.redis_cache import RedisCache
except ImportError:
    RedisCache = None

__all__ = [
    # Interface
    "Cache",
    "CacheStats",
    # Implementations
    "InMemoryLRUCache",
    # Decorators
    "cached",
    # Configuration
    "get_cache_config",
    "create_cache",
]

if RedisCache is not None:
    __all__.append("RedisCache")
