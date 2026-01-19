"""
AstraGuard Rate Limiter - Distributed Rate Limiting with Redis

Implements token bucket algorithm for distributed rate limiting across
telemetry ingestion and API endpoints. Uses Redis for atomic operations
and shared state across multiple instances.
"""

import time
import os
from typing import Optional, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis

# Import centralized secrets management
from core.secrets import get_secret

# Prometheus metrics
try:
    from prometheus_client import Counter, Histogram
    rate_limit_hits = Counter(
        'astra_rate_limit_hits_total',
        'Total number of requests allowed by rate limiter',
        ['endpoint']
    )
    rate_limit_blocks = Counter(
        'astra_rate_limit_blocks_total',
        'Total number of requests blocked by rate limiter',
        ['endpoint']
    )
    rate_limit_latency = Histogram(
        'astra_rate_limit_check_duration_seconds',
        'Time spent checking rate limits',
        ['endpoint']
    )
except ImportError:
    # Fallback if prometheus not available
    rate_limit_hits = None
    rate_limit_blocks = None
    rate_limit_latency = None


class RateLimiter:
    """Distributed rate limiter using Redis token bucket algorithm."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        key_prefix: str,
        rate_per_second: float,
        burst_capacity: int
    ):
        """
        Initialize rate limiter.

        Args:
            redis_client: Redis client instance
            key_prefix: Key prefix for Redis storage (e.g., 'telemetry', 'api')
            rate_per_second: Tokens added per second (sustained rate)
            burst_capacity: Maximum tokens in bucket (burst capacity)
        """
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.rate_per_second = rate_per_second
        self.burst_capacity = burst_capacity

        # Lua script for atomic token bucket operations
        self._token_bucket_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local capacity = tonumber(ARGV[3])
        local requested = tonumber(ARGV[4])

        -- Get current bucket state
        local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
        local tokens = tonumber(bucket[1] or capacity)
        local last_update = tonumber(bucket[2] or now)

        -- Calculate tokens to add since last update
        local elapsed = now - last_update
        local new_tokens = elapsed * rate
        tokens = math.min(capacity, tokens + new_tokens)

        -- Check if request can be fulfilled
        if tokens >= requested then
            -- Consume tokens
            tokens = tokens - requested
            redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
            redis.call('EXPIRE', key, 86400)  -- Expire after 24 hours of inactivity
            return 1  -- Allowed
        else
            -- Update last_update even if denied (to prevent stale data)
            redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
            redis.call('EXPIRE', key, 86400)
            return 0  -- Denied
        end
        """

    async def is_allowed(self, identifier: str = "global", tokens: int = 1) -> bool:
        """
        Check if request is allowed under rate limit.

        Args:
            identifier: Unique identifier (e.g., satellite_id, mission_id)
            tokens: Number of tokens to consume (default: 1)

        Returns:
            True if allowed, False if rate limited
        """
        key = f"astra:rate_limit:{self.key_prefix}:{identifier}"
        now = time.time()

        try:
            result = await self.redis.eval(
                self._token_bucket_script,
                1,  # number of keys
                key,  # KEYS[1]
                now,  # ARGV[1] - current time
                self.rate_per_second,  # ARGV[2] - rate
                self.burst_capacity,  # ARGV[3] - capacity
                tokens  # ARGV[4] - requested tokens
            )
            return bool(result)
        except Exception as e:
            # On Redis errors, allow request to prevent blocking legitimate traffic
            print(f"Rate limiter error: {e}")
            return True

    def get_retry_after(self, identifier: str = "global") -> int:
        """
        Calculate retry-after time in seconds.

        Args:
            identifier: Unique identifier

        Returns:
            Seconds until next token becomes available
        """
        # Simplified calculation - in production might want more sophisticated logic
        return int(1.0 / self.rate_per_second) if self.rate_per_second > 0 else 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for automatic rate limiting."""

    def __init__(self, app, telemetry_limiter: RateLimiter, api_limiter: RateLimiter):
        super().__init__(app)
        self.telemetry_limiter = telemetry_limiter
        self.api_limiter = api_limiter

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting middleware."""
        # Determine which limiter to use based on path
        if request.url.path.startswith("/api/v1/telemetry"):
            limiter = self.telemetry_limiter
            endpoint = "telemetry"
        else:
            limiter = self.api_limiter
            endpoint = "api"

        # Check rate limit
        start_time = time.time()
        allowed = await limiter.is_allowed()

        if rate_limit_latency:
            rate_limit_latency.labels(endpoint=endpoint).observe(time.time() - start_time)

        if not allowed:
            # Rate limited - return 429
            if rate_limit_blocks:
                rate_limit_blocks.labels(endpoint=endpoint).inc()

            retry_after = limiter.get_retry_after()
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Try again in {retry_after} seconds.",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )

        # Allowed - proceed with request
        if rate_limit_hits:
            rate_limit_hits.labels(endpoint=endpoint).inc()

        response = await call_next(request)
        return response


def parse_rate_limit_config(rate_str: str) -> tuple[float, int]:
    """
    Parse rate limit configuration string.

    Supports formats like:
    - "1000/hour" -> (1000/3600, burst_capacity)
    - "100/minute" -> (100/60, burst_capacity)
    - "10/second" -> (10, burst_capacity)

    Args:
        rate_str: Rate limit string (e.g., "1000/hour")

    Returns:
        Tuple of (rate_per_second, burst_capacity)
    """
    if not rate_str:
        return 10.0, 100  # Default: 10/sec with burst of 100

    try:
        parts = rate_str.lower().split('/')
        if len(parts) != 2:
            raise ValueError("Invalid format")

        rate_num = float(parts[0])
        time_unit = parts[1]

        # Convert to per second
        if time_unit in ['hour', 'hours', 'h']:
            rate_per_second = rate_num / 3600
        elif time_unit in ['minute', 'minutes', 'min', 'm']:
            rate_per_second = rate_num / 60
        elif time_unit in ['second', 'seconds', 'sec', 's']:
            rate_per_second = rate_num
        else:
            raise ValueError(f"Unknown time unit: {time_unit}")

        # Burst capacity: allow 2x the rate for burst handling
        burst_capacity = max(10, int(rate_num * 2))

        return rate_per_second, burst_capacity

    except (ValueError, IndexError):
        print(f"Warning: Invalid rate limit config '{rate_str}', using defaults")
        return 10.0, 100


def get_rate_limit_config() -> Dict[str, tuple[float, int]]:
    """
    Get rate limit configurations from environment variables.

    Returns:
        Dict with 'telemetry' and 'api' rate configurations
    """
    telemetry_rate_str = get_secret("rate_limit_telemetry")
    api_rate_str = get_secret("rate_limit_api")

    return {
        "telemetry": parse_rate_limit_config(telemetry_rate_str),
        "api": parse_rate_limit_config(api_rate_str)
    }
