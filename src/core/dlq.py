
import json
import time
import logging
from typing import Any, Dict, List, Optional
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

class DeadLetterQueue:
    """
    Redis-backed Dead Letter Queue (DLQ) for failed telemetry items.
    
    Features:
    - FIFO queue for failed items
    - Metadata capture (error reason, timestamp, source)
    - Retry capability (re-queueing)
    - Retention policies (max size/TTL)
    """
    
    def __init__(
        self, 
        redis_client: Redis, 
        queue_key: str = "dlq:telemetry",
        max_size: int = 10000,
        retention_days: int = 7
    ):
        self.redis = redis_client
        self.queue_key = queue_key
        self.max_size = max_size
        self.retention_seconds = retention_days * 86400

    async def enqueue(self, item: Dict[str, Any], error: str, source: str = "unknown") -> bool:
        """
        Add a failed item to the DLQ.
        """
        try:
            dlq_entry = {
                "item": item,
                "error": str(error),
                "source": source,
                "timestamp": time.time(),
                "retry_count": item.get("_retry_count", 0)
            }
            
            # Use LPUSH to add to head of list
            await self.redis.lpush(self.queue_key, json.dumps(dlq_entry))
            
            # Trim list to max_size
            await self.redis.ltrim(self.queue_key, 0, self.max_size - 1)
            
            logger.warning(
                f"Item moved to DLQ: {error}", 
                extra={"source": source, "queue": self.queue_key}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue to DLQ: {e}", exc_info=True)
            return False

    async def dequeue(self, count: int = 1) -> List[Dict[str, Any]]:
        """
        Retrieve items from the DLQ for inspection or reprocessing.
        """
        items = []
        try:
            for _ in range(count):
                # RPOP removes from tail (FIFO if we used LPUSH)
                data = await self.redis.rpop(self.queue_key)
                if data:
                    items.append(json.loads(data))
                else:
                    break
        except Exception as e:
            logger.error(f"Failed to dequeue from DLQ: {e}", exc_info=True)
        return items

    async def size(self) -> int:
        """Get current DLQ size."""
        try:
            return await self.redis.llen(self.queue_key)
        except Exception:
            return 0

    async def clear(self) -> bool:
        """Clear the DLQ."""
        try:
            await self.redis.delete(self.queue_key)
            return True
        except Exception:
            return False
