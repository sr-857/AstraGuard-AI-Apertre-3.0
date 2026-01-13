"""
Cache Decorators

Function-level caching decorators for easy integration with existing code.
"""

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)


def cached(
    cache=None,
    key_fn: Optional[Callable[..., str]] = None,
    ttl: Optional[int] = None,
    prefix: str = "fn"
):
    """Decorator to cache function results.
    
    Works with both sync and async functions. Cache key is generated from
    function arguments using key_fn, or defaults to string representation.
    
    Args:
        cache: Cache instance to use. If None, uses default from config.
        key_fn: Callable to generate cache key from function args.
                Signature: key_fn(*args, **kwargs) -> str
                If None, uses repr of args.
        ttl: TTL in seconds for cached result. None uses cache default.
        prefix: Key prefix for this function (default: "fn")
    
    Example:
        @cached(key_fn=lambda user_id: f"user:{user_id}", ttl=300)
        async def get_user(user_id: str) -> dict:
            return await db.fetch_user(user_id)
        
        # Or with explicit cache:
        @cached(cache=my_cache, ttl=60)
        def compute_expensive(x: int) -> int:
            return heavy_computation(x)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Get cache instance
            active_cache = cache
            if active_cache is None:
                active_cache = _get_default_cache()
            
            if active_cache is None:
                # Cache disabled, call function directly
                return await func(*args, **kwargs)
            
            # Generate cache key
            cache_key = _generate_key(prefix, func, key_fn, args, kwargs)
            
            # Try to get from cache
            try:
                result = await active_cache.get(cache_key)
                if result is not None:
                    logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                    return result
            except Exception as e:
                logger.warning(f"Cache get error in {func.__name__}: {e}")
            
            # Cache miss - call function
            result = await func(*args, **kwargs)
            
            # Store in cache
            try:
                await active_cache.set(cache_key, result, ttl)
                logger.debug(f"Cached result for {func.__name__}: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache set error in {func.__name__}: {e}")
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Get cache instance
            active_cache = cache
            if active_cache is None:
                active_cache = _get_default_cache()
            
            if active_cache is None:
                # Cache disabled, call function directly
                return func(*args, **kwargs)
            
            # Generate cache key
            cache_key = _generate_key(prefix, func, key_fn, args, kwargs)
            
            # For sync functions with async cache, we need to run in event loop
            loop = _get_or_create_event_loop()
            
            # Try to get from cache
            try:
                result = loop.run_until_complete(active_cache.get(cache_key))
                if result is not None:
                    logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                    return result
            except Exception as e:
                logger.warning(f"Cache get error in {func.__name__}: {e}")
            
            # Cache miss - call function
            result = func(*args, **kwargs)
            
            # Store in cache
            try:
                loop.run_until_complete(active_cache.set(cache_key, result, ttl))
                logger.debug(f"Cached result for {func.__name__}: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache set error in {func.__name__}: {e}")
            
            return result
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def cache_invalidate(
    cache=None,
    key_fn: Optional[Callable[..., str]] = None,
    prefix: str = "fn"
):
    """Decorator to invalidate cache after function execution.
    
    Useful for write operations that should clear related cache entries.
    
    Args:
        cache: Cache instance to use
        key_fn: Callable to generate cache key to invalidate
        prefix: Key prefix (default: "fn")
    
    Example:
        @cache_invalidate(key_fn=lambda user_id, data: f"user:{user_id}")
        async def update_user(user_id: str, data: dict) -> bool:
            await db.update_user(user_id, data)
            return True
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Call the function first
            result = await func(*args, **kwargs)
            
            # Then invalidate cache
            active_cache = cache
            if active_cache is None:
                active_cache = _get_default_cache()
            
            if active_cache is not None:
                cache_key = _generate_key(prefix, func, key_fn, args, kwargs)
                try:
                    await active_cache.invalidate(cache_key)
                    logger.debug(f"Cache invalidated for {func.__name__}: {cache_key}")
                except Exception as e:
                    logger.warning(f"Cache invalidate error: {e}")
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            
            active_cache = cache
            if active_cache is None:
                active_cache = _get_default_cache()
            
            if active_cache is not None:
                cache_key = _generate_key(prefix, func, key_fn, args, kwargs)
                loop = _get_or_create_event_loop()
                try:
                    loop.run_until_complete(active_cache.invalidate(cache_key))
                    logger.debug(f"Cache invalidated for {func.__name__}: {cache_key}")
                except Exception as e:
                    logger.warning(f"Cache invalidate error: {e}")
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _generate_key(
    prefix: str,
    func: Callable,
    key_fn: Optional[Callable],
    args: tuple,
    kwargs: dict
) -> str:
    """Generate cache key from function and arguments."""
    if key_fn is not None:
        try:
            custom_key = key_fn(*args, **kwargs)
            return f"{prefix}:{func.__name__}:{custom_key}"
        except Exception as e:
            logger.warning(f"key_fn error, using default key: {e}")
    
    # Default: use repr of args
    args_key = ":".join(repr(a) for a in args)
    kwargs_key = ":".join(f"{k}={repr(v)}" for k, v in sorted(kwargs.items()))
    
    if kwargs_key:
        return f"{prefix}:{func.__name__}:{args_key}:{kwargs_key}"
    return f"{prefix}:{func.__name__}:{args_key}"


def _get_default_cache():
    """Get default cache from config."""
    try:
        from backend.cache.config import get_default_cache
        return get_default_cache()
    except ImportError:
        return None


def _get_or_create_event_loop():
    """Get current event loop or create new one for sync context."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create new one
        return asyncio.new_event_loop()
