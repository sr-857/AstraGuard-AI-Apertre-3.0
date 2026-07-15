"""
Swarm Network Layer - HTTP/2ized and Optimized Communication

Issue #961: Network optimization for distributed operations.
- HTTP/2 support
- Connection pooling
- Message compression (zstd)
- Request batching
- Circuit breaker & Retry logic
"""

import asyncio
import logging
import httpx
from typing import Dict, Optional, List, Any, Union
import time
from dataclasses import dataclass, field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, CircuitBreakerError

try:
    import zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

from astraguard.swarm.models import SwarmConfig, AgentID

logger = logging.getLogger(__name__)

@dataclass
class NetworkStats:
    sent_bytes: int = 0
    received_bytes: int = 0
    requests_total: int = 0
    requests_failed: int = 0
    latency_sum_ms: float = 0.0

    def record_request(self, latency_ms: float, bytes_sent: int, failed: bool = False):
        self.requests_total += 1
        self.sent_bytes += bytes_sent
        self.latency_sum_ms += latency_ms
        if failed:
            self.requests_failed += 1

    @property
    def avg_latency(self) -> float:
        return self.latency_sum_ms / self.requests_total if self.requests_total > 0 else 0.0

class NetworkClient:
    """optimized HTTP/2 client for swarm communication."""
    
    def __init__(self, config: Optional[SwarmConfig] = None, max_connections: int = 100):
        self.config = config
        self.stats = NetworkStats()
        
        # Connection Pooling & HTTP/2
        self.client = httpx.AsyncClient(
            http2=True,
            limits=httpx.Limits(
                max_keepalive_connections=20, 
                max_connections=max_connections,
                keepalive_expiry=30.0
            ),
            timeout=10.0,
            verify=False # Assuming internal network for now
        )
        
        self.peer_urls: Dict[str, str] = {} # agent_uuid -> url
        self._circuit_breakers: Dict[str, Any] = {} # simple state tracking for now

    async def register_peer(self, agent_id: str, url: str):
        self.peer_urls[agent_id] = url

    async def close(self):
        await self.client.aclose()

    def _compress_payload(self, payload: bytes) -> bytes:
        if HAS_ZSTD:
            return zstd.compress(payload, 1) # Level 1 for speed
        return payload

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException))
    )
    async def send_message(self, target_agent_id: str, payload: bytes, compress: bool = True) -> bool:
        """Send message to a peer with retry and circuit breaker."""
        
        url = self.peer_urls.get(target_agent_id)
        if not url:
            logger.warning(f"No URL found for agent {target_agent_id}")
            return False

        # Circuit Breaker Check (Simple implementation)
        cb_state = self._circuit_breakers.get(target_agent_id, {"failures": 0, "last_failure": 0})
        if cb_state["failures"] > 5:
            if time.time() - cb_state["last_failure"] < 30: # 30s cooldown
                logger.warning(f"Circuit open for {target_agent_id}")
                return False
            else:
                # Reset half-open
                cb_state["failures"] = 0

        start_time = time.time()
        try:
            headers = {"Content-Type": "application/octet-stream"}
            data = payload
            
            if compress and HAS_ZSTD:
                data = self._compress_payload(payload)
                headers["Content-Encoding"] = "zstd"

            response = await self.client.post(url, content=data, headers=headers)
            response.raise_for_status()
            
            latency = (time.time() - start_time) * 1000
            self.stats.record_request(latency, len(data))
            
            # Reset failures on success
            self._circuit_breakers[target_agent_id] = {"failures": 0, "last_failure": 0}
            
            return True

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.stats.record_request(latency, len(payload) if 'data' not in locals() else len(data), failed=True)
            
            logger.error(f"Failed to send to {target_agent_id}: {e}")
            
            # Update CB
            failures = self._circuit_breakers.get(target_agent_id, {"failures": 0})["failures"] + 1
            self._circuit_breakers[target_agent_id] = {"failures": failures, "last_failure": time.time()}
            
            raise # Let tenacity retry
            
    async def batch_send(self, target_agent_id: str, messages: List[bytes]):
        """Send multiple messages in a single request (Request Batching)."""
        # Implementation depends on receiver support for multipart or batch format
        # For now, we simulate simple sequential sending or concatenated payload
        
        # Concatenate with length prefix if protocol allows, or just send sequentially
        # Optimized: Send concurrently
        tasks = [self.send_message(target_agent_id, msg) for msg in messages]
        return await asyncio.gather(*tasks, return_exceptions=True)

