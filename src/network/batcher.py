"""
Request Batching Layer
Reduces network round trips by aggregating small requests.
"""

import asyncio
import time
import logging
from typing import List, Any, Optional

from .serialization import serialize_payload
from .compression import compress_payload
from .client import get_network_client
from .metrics import track_network_request

logger = logging.getLogger(__name__)

class RequestBatcher:
    """
    Batches small requests into a single payload.
    Supports timeout-based flushing and size-based flushing.
    """

    def __init__(self, endpoint: str, batch_size: int = 20, max_wait_ms: int = 100):
        self.endpoint = endpoint
        self.batch: List[Any] = []
        self.batch_size = batch_size
        self.max_wait_ms = max_wait_ms
        self.last_flush_time = time.perf_counter()
        self.client = get_network_client()
        self._flush_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the background flush timer task."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self):
        """Stop the background flush task and flush remaining items."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()

    async def add(self, item: Any):
        """Add item to batch. Flushes if full."""
        async with self._lock:
            self.batch.append(item)
            if len(self.batch) >= self.batch_size:
                await self.flush()

    async def _periodic_flush(self):
        """Flush periodically based on max_wait_ms."""
        while True:
            await asyncio.sleep(self.max_wait_ms / 1000.0)
            async with self._lock:
                if self.batch and (time.perf_counter() - self.last_flush_time) * 1000 >= self.max_wait_ms:
                    await self.flush()

    @track_network_request(method="POST", endpoint="batch_flush")
    async def flush(self):
        """Serialize, compress, and send the batch."""
        if not self.batch:
            return

        try:
            # 1. Serialize (MsgPack)
            payload_bytes = serialize_payload({"telemetry": self.batch})

            # 2. Compress (Zstd)
            compressed_bytes = compress_payload(payload_bytes)

            # 3. Send (HTTP/2)
            headers = {
                "Content-Type": "application/msgpack",
                "Content-Encoding": "zstd",
                "X-Batch-Size": str(len(self.batch))
            }

            logger.debug(f"Flushing batch of {len(self.batch)} items ({len(compressed_bytes)} bytes compressed)")

            # Use the pooled client
            response = await self.client.post(
                self.endpoint,
                content=compressed_bytes,
                headers=headers
            )
            response.raise_for_status()

            # Clear batch
            self.batch.clear()
            self.last_flush_time = time.perf_counter()

        except Exception as e:
            logger.error(f"Failed to flush batch: {e}")
            # Depending on policy, we might retry or drop.
            # Here we keep retrying via the resilient client, but if that fails, data is lost (or kept in batch).
            # To be safe, we might clear or retry later.
            # For this implementation, we clear to avoid blocking indefinitely, but log error.
            # In production, maybe use a persistent queue.
            self.batch.clear() # Prevent infinite loop on bad payload
            raise
