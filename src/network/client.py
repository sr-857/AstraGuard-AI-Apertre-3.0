"""
Core Network Client using httpx (HTTP/2) + Resilience.
Implements connection pooling, HTTP/2 multiplexing, and timeouts.
"""

import httpx
import logging
import time
from typing import Optional, Callable
from contextlib import asynccontextmanager

from .resilience import ResilientClientWrapper

logger = logging.getLogger(__name__)

# Singleton client instance
_client_instance: Optional[httpx.AsyncClient] = None

def get_network_client() -> ResilientClientWrapper:
    """
    Get or create the global pooled HTTP/2 client.
    Ensures optimal connection reuse across the application.
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = httpx.AsyncClient(
            http2=True,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20
            ),
            timeout=5.0
        )
        logger.info("Initialized global pooled HTTP/2 client")

    return ResilientClientWrapper(_client_instance)

@asynccontextmanager
async def resilient_client():
    """Context manager for client usage."""
    client = get_network_client()
    yield client

async def close_client():
    """Gracefully close the global client."""
    global _client_instance
    if _client_instance:
        await _client_instance.aclose()
        _client_instance = None
        logger.info("Closed global HTTP/2 client")

async def measure_network_call(func: Callable, *args, **kwargs):
    """
    Wrapper to measure network latency.
    Step 1.1 of optimization plan.
    """
    start = time.perf_counter()
    try:
        result = await func(*args, **kwargs)
        latency = (time.perf_counter() - start) * 1000
        logger.debug(f"Network latency: {latency:.2f} ms")
        return result, latency
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"Network call failed after {latency:.2f} ms: {e}")
        raise
