"""
Resilience Layer: Retries and Circuit Breakers
Provides fault tolerance for network operations.
"""

import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from pybreaker import CircuitBreaker, CircuitBreakerError
import httpx
import asyncio

logger = logging.getLogger(__name__)

# Circuit Breaker Configuration
# Fails open after 5 consecutive errors, resets after 30 seconds
circuit_breaker = CircuitBreaker(fail_max=5, reset_timeout=30)

# Exceptions to retry on (transient failures)
RETRY_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.PoolTimeout,
    httpx.TimeoutException,
    asyncio.TimeoutError
)

# Retry Policy: Exponential Backoff (1s -> 2s -> 4s -> ... -> 10s), Max 5 attempts
retry_policy = retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RETRY_EXCEPTIONS),
    reraise=True
)

class ResilientClientWrapper:
    """Wrapper that applies resilience patterns to HTTP methods."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @circuit_breaker
    @retry_policy
    async def request(self, method: str, url: str, **kwargs):
        """Execute request with circuit breaker and retry logic."""
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except CircuitBreakerError:
            logger.warning(f"Circuit open for {url}")
            raise
        except Exception as e:
            logger.warning(f"Request failed: {method} {url} - {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.warning(f"Response: {e.response.text}")
            raise

    async def get(self, url: str, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs):
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs):
        return await self.request("DELETE", url, **kwargs)
