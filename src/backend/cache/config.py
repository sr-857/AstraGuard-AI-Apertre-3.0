"""
Cache Configuration

Environment-based configuration for the caching layer.
Provides factory functions to create appropriate cache instances.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Global default cache instance
_default_cache = None


class CacheConfig:
    """Cache configuration from environment variables.
    
    Environment Variables:
        CACHE_ENABLED: Enable/disable caching (default: false)
        CACHE_BACKEND: "memory" or "redis" (default: memory)
        CACHE_MAXSIZE: Max entries for in-memory cache (default: 1024)
        CACHE_TTL_SECONDS: Default TTL in seconds (default: 60)
        CACHE_REDIS_URL: Redis URL for redis backend (default: redis://localhost:6379)
        CACHE_KEY_PREFIX: Key prefix for cache entries (default: astra:cache:)
    """
    
    def __init__(self):
        self.enabled = os.getenv("CACHE_ENABLED", "false").lower() in ("true", "1", "yes")
        self.backend = os.getenv("CACHE_BACKEND", "memory").lower()
        self.maxsize = int(os.getenv("CACHE_MAXSIZE", "1024"))
        self.ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "60"))
        self.redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
        self.key_prefix = os.getenv("CACHE_KEY_PREFIX", "astra:cache:")
    
    def __repr__(self) -> str:
        return (
            f"CacheConfig(enabled={self.enabled}, backend={self.backend}, "
            f"maxsize={self.maxsize}, ttl={self.ttl_seconds})"
        )


def get_cache_config() -> CacheConfig:
    """Get cache configuration from environment.
    
    Returns:
        CacheConfig instance with current settings
    """
    return CacheConfig()


def create_cache(config: Optional[CacheConfig] = None, metrics_sink=None):
    """Create cache instance based on configuration.
    
    Args:
        config: Optional CacheConfig. Uses get_cache_config() if None.
        metrics_sink: Optional MetricsSink for cache metrics.
    
    Returns:
        Cache instance or None if caching is disabled
    """
    if config is None:
        config = get_cache_config()
    
    if not config.enabled:
        logger.info("Caching is disabled (CACHE_ENABLED=false)")
        return None
    
    if config.backend == "redis":
        try:
            from backend.cache.redis_cache import RedisCache
            cache = RedisCache(
                redis_url=config.redis_url,
                default_ttl=config.ttl_seconds,
                metrics_sink=metrics_sink,
                key_prefix=config.key_prefix,
            )
            logger.info(f"Created RedisCache: {config.redis_url}")
            return cache
        except ImportError as e:
            logger.warning(f"Redis cache unavailable, falling back to memory: {e}")
    
    # Default: in-memory cache
    from backend.cache.in_memory import InMemoryLRUCache
    cache = InMemoryLRUCache(
        maxsize=config.maxsize,
        default_ttl=config.ttl_seconds,
        metrics_sink=metrics_sink,
    )
    logger.info(f"Created InMemoryLRUCache: maxsize={config.maxsize}")
    return cache


def get_default_cache():
    """Get or create the default cache instance.
    
    The default cache is a singleton created from environment config.
    Used by @cached decorator when no explicit cache is provided.
    
    Returns:
        Cache instance or None if disabled
    """
    global _default_cache
    
    if _default_cache is None:
        _default_cache = create_cache()
    
    return _default_cache


def set_default_cache(cache) -> None:
    """Set the default cache instance.
    
    Useful for testing or custom initialization.
    
    Args:
        cache: Cache instance to use as default
    """
    global _default_cache
    _default_cache = cache
    logger.debug(f"Default cache set to: {type(cache).__name__ if cache else None}")


def reset_default_cache() -> None:
    """Reset the default cache instance.
    
    Forces re-creation on next get_default_cache() call.
    """
    global _default_cache
    _default_cache = None
