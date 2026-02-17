"""
Adaptive Memory Store with Temporal Weighting (Async + WAL + MsgPack)

Self-updating the memory that prioritizes recent and recurring events.
Optimized for high-throughput I/O using async WAL and MsgPack serialization.
"""

try:
    import numpy as np
except ImportError:
    np = None

import math
import threading
import tempfile
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Union, Any, TYPE_CHECKING
import pickle
import os
import logging
import fasteners
import aiofiles
import msgpack
import collections

if TYPE_CHECKING:
    import numpy as np

# Import timeout and resource monitoring decorators
from core.timeout_handler import with_timeout
from core.resource_monitor import monitor_operation_resources
from core.io_utils import measure_io, record_batch_size

logger = logging.getLogger(__name__)

# Security: Base directory for memory store persistence
MEMORY_STORE_BASE_DIR = os.path.realpath(os.path.abspath("memory_engine"))
SYSTEM_TEMP_DIR = os.path.realpath(tempfile.gettempdir())

# Constants for memory store configuration
DEFAULT_DECAY_LAMBDA = 0.1
DEFAULT_MAX_CAPACITY = 10000
DEFAULT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_MAX_AGE_HOURS = 24
DEFAULT_TOP_K = 5

# Weighting constants
SIMILARITY_WEIGHT = 0.5
TEMPORAL_WEIGHT = 0.3
RECURRENCE_WEIGHT = 0.2
RECURRENCE_BOOST_FACTOR = 0.3
EPSILON = 1e-10

# I/O Configuration
BATCH_SIZE = 100
WAL_FILENAME_SUFFIX = ".wal"
SNAPSHOT_FILENAME = "memory_store.msgpack"


def msgpack_default(obj):
    """Default handler for msgpack serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if np is not None and isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


class MemoryEvent:
    """Represents a stored memory event."""

    def __init__(self, embedding: Union[List[float], "np.ndarray"], metadata: Dict, timestamp: datetime, recurrence_count: int = 1):
        self.embedding = embedding
        self.metadata = metadata
        self.timestamp = timestamp
        self.base_importance = metadata.get("severity", 0.5)
        self.recurrence_count = recurrence_count
        self.is_critical = metadata.get("critical", False)

    def age_seconds(self) -> float:
        """Calculate age in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        embedding_list = self.embedding
        if np is not None and isinstance(self.embedding, np.ndarray):
            embedding_list = self.embedding.tolist()

        return {
            "embedding": embedding_list,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "recurrence_count": self.recurrence_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEvent":
        """Deserialize from dictionary."""
        timestamp = datetime.fromisoformat(data["timestamp"])
        embedding = data["embedding"]
        if np is not None:
            embedding = np.array(embedding)

        return cls(
            embedding=embedding,
            metadata=data["metadata"],
            timestamp=timestamp,
            recurrence_count=data.get("recurrence_count", 1)
        )


class WriteBatcher:
    """Async write batcher for WAL."""

    def __init__(self, filepath: str, batch_size: int = BATCH_SIZE):
        self.filepath = filepath
        self.batch_size = batch_size
        self.batch: List[bytes] = []
        self._lock = asyncio.Lock()

    async def add(self, data: bytes):
        """Add item to batch and flush if full."""
        async with self._lock:
            self.batch.append(data)
            current_size = len(self.batch)

        if current_size >= self.batch_size:
            await self.flush()

    @measure_io(operation_type="wal_flush", storage_type="disk")
    async def flush(self):
        """Flush batch to disk."""
        async with self._lock:
            if not self.batch:
                return

            data_to_write = b"".join(self.batch)
            count = len(self.batch)
            self.batch.clear()

        # Write to disk (append mode)
        async with aiofiles.open(self.filepath, "ab") as f:
            await f.write(data_to_write)
            await f.flush() # Ensure it hits disk (OS buffer)
            # os.fsync(f.fileno()) # Optional: strictly durable but slower. "Async File Write" implies OS buffer is OK.

        record_batch_size(count, "wal_write", "disk")


class AdaptiveMemoryStore:
    """
    Self-updating memory with temporal weighting and decay.
    Powered by Async I/O, Write-Ahead Logging (WAL), and MsgPack.
    """

    def __init__(self, decay_lambda: float = DEFAULT_DECAY_LAMBDA, max_capacity: int = DEFAULT_MAX_CAPACITY):
        if decay_lambda < 0:
            raise ValueError("decay_lambda must be non-negative")
        if max_capacity <= 0:
            raise ValueError("max_capacity must be positive")

        self.decay_lambda = decay_lambda
        self.max_capacity = max_capacity
        self.memory: List[MemoryEvent] = []

        # Persistence paths
        self.storage_path = os.path.join(MEMORY_STORE_BASE_DIR, SNAPSHOT_FILENAME)
        self.wal_path = self.storage_path + WAL_FILENAME_SUFFIX
        self.legacy_path = os.path.join(MEMORY_STORE_BASE_DIR, "memory_store.pkl")

        self._lock = threading.RLock()  # For in-memory thread safety
        self.batcher = WriteBatcher(self.wal_path, batch_size=BATCH_SIZE)

    async def write(
        self,
        embedding: Union[List[float], "np.ndarray"],
        metadata: Dict,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Store event with timestamp and importance.
        Updates in-memory state and appends to WAL asynchronously.
        """
        if embedding is None or (hasattr(embedding, 'size') and embedding.size == 0):
            raise ValueError("Embedding cannot be empty")
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")
        if timestamp is None:
            timestamp = datetime.now()

        # Perform CPU-bound similarity search under lock
        event_to_persist = None

        with self._lock:
            # Check for similar existing events (recurrence)
            similar = self._find_similar(embedding, threshold=0.85)

            if similar:
                # Update existing event
                similar.recurrence_count += 1
                similar.metadata["last_seen"] = timestamp
                event_to_persist = similar
            else:
                # Add new event
                event = MemoryEvent(embedding, metadata, timestamp)
                self.memory.append(event)
                event_to_persist = event

            # Auto-prune if capacity exceeded
            if len(self.memory) > self.max_capacity:
                self.prune(keep_critical=True)

        # Asynchronously write to WAL
        if event_to_persist:
            try:
                # Serialize to MsgPack
                event_dict = event_to_persist.to_dict()
                # Determine operation type (Update vs Insert)
                # For WAL, we just append the latest state of the event.
                # Or simplistic: Just append the event. Replay will re-insert/update.
                packed = msgpack.packb(event_dict, default=msgpack_default, use_bin_type=True)
                await self.batcher.add(packed)
            except Exception as e:
                logger.error(f"Failed to write to WAL: {e}")

    @with_timeout(seconds=5.0, operation_name="memory_retrieve")
    def retrieve(
        self, query_embedding: Union[List[float], "np.ndarray"], top_k: int = DEFAULT_TOP_K
    ) -> List[Tuple[float, Dict, datetime]]:
        """Retrieve similar events (Thread-safe, CPU-bound)."""
        if query_embedding is None or (hasattr(query_embedding, 'size') and query_embedding.size == 0):
            raise ValueError("Query embedding cannot be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        with self._lock:
            if not self.memory:
                return []

            scores = []
            for event in self.memory:
                similarity = self._cosine_similarity(query_embedding, event.embedding)
                temporal_weight = self._temporal_weight(event)
                recurrence_boost = 1 + RECURRENCE_BOOST_FACTOR * (
                    np.log(1 + event.recurrence_count) if np is not None else math.log(1 + event.recurrence_count)
                )

                weighted_score = (
                    SIMILARITY_WEIGHT * similarity +
                    TEMPORAL_WEIGHT * temporal_weight +
                    RECURRENCE_WEIGHT * recurrence_boost
                )

                scores.append((weighted_score, event.metadata, event.timestamp))

            scores.sort(reverse=True, key=lambda x: x[0])
            return scores[:top_k]

    @with_timeout(seconds=60.0)
    @monitor_operation_resources()
    def prune(self, max_age_hours: int = DEFAULT_MAX_AGE_HOURS, keep_critical: bool = True) -> int:
        """Safe decay mechanism."""
        if max_age_hours < 0:
            raise ValueError("max_age_hours must be non-negative")
        if max_age_hours == 0:
            return 0

        with self._lock:
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            initial_count = len(self.memory)

            if keep_critical:
                self.memory = [
                    event for event in self.memory
                    if event.is_critical or event.timestamp > cutoff
                ]
            else:
                self.memory = [event for event in self.memory if event.timestamp > cutoff]

            return initial_count - len(self.memory)

    @measure_io(operation_type="snapshot_save", storage_type="disk")
    async def save(self) -> None:
        """
        Async Checkpoint: Flush WAL and save full snapshot to disk (MsgPack).
        Triggers WAL truncation.
        """
        # First flush any pending WAL writes
        await self.batcher.flush()

        # Offload sync I/O and serialization to thread pool to avoid blocking loop
        # and to allow using blocking locks (fasteners)
        await asyncio.to_thread(self._save_sync)

    def _save_sync(self) -> None:
        """Synchronous implementation of save with locking."""
        # Serialize memory to bytes (CPU bound)
        with self._lock:
            try:
                # Convert all events to dicts
                data_list = [event.to_dict() for event in self.memory]
                packed_data = msgpack.packb(data_list, default=msgpack_default, use_bin_type=True)
            except Exception as e:
                logger.error(f"Failed to serialize memory: {e}")
                return

        # Write to disk sync with lock
        try:
            # Validate path security
            self._validate_path(self.storage_path)

            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

            # Use inter-process lock
            lock_path = self.storage_path + ".lock"
            with fasteners.InterProcessLock(lock_path):
                # Write to temporary file first then rename (atomic)
                temp_path = self.storage_path + ".tmp"
                with open(temp_path, "wb") as f:
                    f.write(packed_data)
                    f.flush()
                    os.fsync(f.fileno())

                # Atomic rename
                os.rename(temp_path, self.storage_path)

            # Truncate WAL
            if os.path.exists(self.wal_path):
                try:
                    os.remove(self.wal_path)
                except OSError:
                    pass

            logger.debug(f"Memory store saved to {self.storage_path}")

        except Exception as e:
            logger.error(f"Failed to save memory store: {e}", exc_info=True)
            raise

    @measure_io(operation_type="snapshot_load", storage_type="disk")
    def load(self) -> bool:
        """
        Load memory from disk (Snapshot + WAL).
        Handles migration from legacy Pickle format.
        """
        with self._lock:
            # 1. Migration: Check for legacy pickle file
            if not os.path.exists(self.storage_path) and os.path.exists(self.legacy_path):
                logger.info("Migrating from legacy pickle storage...")
                if self._load_legacy_pickle():
                    logger.info("Legacy data loaded. It will be saved as MsgPack on exit.")
                    return True

            # 2. Load Snapshot (MsgPack)
            loaded = False
            lock_path = self.storage_path + ".lock"

            # Try loading snapshot with lock
            if os.path.exists(self.storage_path):
                try:
                    self._validate_path(self.storage_path)

                    with fasteners.InterProcessLock(lock_path):
                        with open(self.storage_path, "rb") as f:
                            packed_data = f.read()

                    data_list = msgpack.unpackb(packed_data)
                    self.memory = [MemoryEvent.from_dict(d) for d in data_list]
                    loaded = True
                    logger.info(f"Loaded {len(self.memory)} events from snapshot")
                except Exception as e:
                    logger.error(f"Failed to load snapshot: {e}")
                    # CRITICAL: If snapshot is corrupted, clear memory to avoid undefined state
                    self.memory = []
                    # Don't return False yet, try WAL

            # 3. Replay WAL (Crash Recovery)
            if os.path.exists(self.wal_path):
                try:
                    self._replay_wal()
                    loaded = True
                except Exception as e:
                    logger.error(f"Failed to replay WAL: {e}")

            return loaded

    def _replay_wal(self):
        """Replay events from WAL."""
        count = 0
        try:
            with open(self.wal_path, "rb") as f:
                unpacker = msgpack.Unpacker(f)
                for obj in unpacker:
                    event = MemoryEvent.from_dict(obj)
                    # We assume WAL contains full events.
                    # We append or replace?
                    # Since we don't have unique IDs, we just append.
                    # This might cause duplicates if snapshot + WAL overlap.
                    # But typically WAL is cleared after snapshot.
                    # If crash happened, snapshot is old, WAL has new events.
                    self.memory.append(event)
                    count += 1
            logger.info(f"Replayed {count} events from WAL")
        except Exception as e:
            logger.warning(f"WAL replay partial/failed: {e}")

    def _load_legacy_pickle(self) -> bool:
        """Load from legacy pickle file."""
        try:
            self._validate_path(self.legacy_path)
            with open(self.legacy_path, "rb") as f:
                self.memory = pickle.load(f)
            return True
        except Exception as e:
            logger.error(f"Failed to load legacy pickle: {e}")
            return False

    def _validate_path(self, path: str):
        """Security check for path traversal."""
        resolved_path = os.path.realpath(os.path.abspath(path))
        # Bandit B108: Check for insecure usage of tmp directory
        # We explicitly allow system temp dir for temporary operations,
        # but ensure we are using the resolved system temp dir path.
        is_safe = (
            resolved_path.startswith(MEMORY_STORE_BASE_DIR) or
            resolved_path.startswith(SYSTEM_TEMP_DIR)
        )
        if not is_safe:
            raise ValueError(f"Path traversal detected: {path}")

    # Helper methods (copied from original)
    def get_stats(self) -> Dict:
        if not self.memory:
            return {
                "total_events": 0,
                "critical_events": 0,
                "avg_age_hours": 0,
                "max_recurrence": 0,
            }
        ages = [event.age_seconds() / 3600 for event in self.memory]
        return {
            "total_events": len(self.memory),
            "critical_events": sum(1 for e in self.memory if e.is_critical),
            "avg_age_hours": np.mean(ages) if np is not None else sum(ages) / len(ages),
            "max_recurrence": max(e.recurrence_count for e in self.memory),
        }

    def _temporal_weight(self, event: MemoryEvent) -> float:
        age_hours = event.age_seconds() / 3600
        return math.exp(-self.decay_lambda * age_hours) if np is None else np.exp(-self.decay_lambda * age_hours)

    def _cosine_similarity(self, a: Union[List[float], "np.ndarray"], b: Union[List[float], "np.ndarray"]) -> float:
        if len(a) != len(b):
            # Fail gracefully or log
            return 0.0
        if np is not None:
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return np.dot(a, b) / (norm_a * norm_b + EPSILON)
        else:
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            dot_product = sum(x * y for x, y in zip(a, b))
            return dot_product / (norm_a * norm_b + EPSILON)

    def _find_similar(
        self, embedding: Union[List[float], "np.ndarray"], threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> Optional[MemoryEvent]:
        for event in self.memory:
            if self._cosine_similarity(embedding, event.embedding) > threshold:
                return event
        return None

    @with_timeout(seconds=30.0)
    @monitor_operation_resources()
    def replay(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Replay events from memory within time range."""
        if start_time > end_time:
            raise ValueError("start_time must be before or equal to end_time")
        with self._lock:
            filtered_events = [
                event for event in self.memory
                if start_time <= event.timestamp <= end_time
            ]
            filtered_events.sort(key=lambda event: event.timestamp)
            return [event.metadata for event in filtered_events]
