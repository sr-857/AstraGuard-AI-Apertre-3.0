"""
Adaptive Memory Store with Temporal Weighting

Self-updating the memory that prioritizes recent and recurring events.
"""

try:
    import numpy as np
except ImportError:
    np = None

import json
import threading
import tempfile
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Union, Any, TYPE_CHECKING
import os
import logging
import fasteners
from prometheus_client import Gauge, Histogram
import os
import logging
import fasteners

if TYPE_CHECKING:
    import numpy as np

# Import timeout and resource monitoring decorators
from core.timeout_handler import with_timeout
from core.resource_monitor import monitor_operation_resources

from core.timeout_handler import with_timeout

logger = logging.getLogger(__name__)

# Security: Base directory for memory store persistence
# All storage paths must be contained within this directory to prevent traversal attacks
MEMORY_STORE_BASE_DIR = os.path.realpath(os.path.abspath("memory_engine"))

# Get system temp directory for testing (platform-independent)
SYSTEM_TEMP_DIR = os.path.realpath(tempfile.gettempdir())

# Constants for memory store configuration
DEFAULT_DECAY_LAMBDA = 0.1
DEFAULT_MAX_CAPACITY = 10000
DEFAULT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_MAX_AGE_HOURS = 24
DEFAULT_TOP_K = 5

# Weighting constants for scoring
SIMILARITY_WEIGHT = 0.5
TEMPORAL_WEIGHT = 0.3
RECURRENCE_WEIGHT = 0.2
RECURRENCE_BOOST_FACTOR = 0.3

# Numerical stability constant
EPSILON = 1e-10


# Metrics
MEMORY_STORE_SIZE = Gauge("memory_store_events_total", "Total events in memory store")
MEMORY_STORE_OP_LATENCY = Histogram("memory_store_op_latency_seconds", "Latency of memory store operations", ["operation"])

class MemoryEvent:
    """Represents a stored memory event."""

    def __init__(self, embedding: Union[List[float], "np.ndarray"], metadata: Dict, timestamp: Union[datetime, str]):
        # Handle numpy arrays -> list for storage
        if np is not None and isinstance(embedding, np.ndarray):
            self.embedding = embedding.tolist()
        else:
            self.embedding = embedding
            
        self.metadata = metadata
        
        # Handle timestamp parsing
        if isinstance(timestamp, str):
            self.timestamp = datetime.fromisoformat(timestamp)
        else:
            self.timestamp = timestamp
            
        self.base_importance = metadata.get("severity", 0.5)
        self.recurrence_count = 1
        self.is_critical = metadata.get("critical", False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "embedding": self.embedding,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "recurrence_count": self.recurrence_count,
            "is_critical": self.is_critical
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEvent":
        """Deserialize from dictionary."""
        event = cls(
            embedding=data["embedding"],
            metadata=data["metadata"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )
        event.recurrence_count = data.get("recurrence_count", 1)
        event.is_critical = data.get("is_critical", False)
        return event

    def age_seconds(self) -> float:
        """Calculate age in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()


class AdaptiveMemoryStore:
    """
    Self-updating memory with temporal weighting and decay.

    Features:
    - Temporal weighting: recent events weighted higher
    - Recurrence scoring: repeated patterns reinforced
    - Safe decay: critical events never deleted
    - Clean interfaces: write, retrieve, prune, replay
    """

    def __init__(self, decay_lambda: float = DEFAULT_DECAY_LAMBDA, max_capacity: int = DEFAULT_MAX_CAPACITY):
        """
        Initialize adaptive memory store.

        Args:
            decay_lambda: Decay rate for temporal weighting (default: 0.1)
            max_capacity: Maximum number of events to store

        Raises:
            ValueError: If decay_lambda is negative or max_capacity is not positive
        """
        if decay_lambda < 0:
            raise ValueError("decay_lambda must be non-negative")
        if max_capacity <= 0:
            raise ValueError("max_capacity must be positive")
        self.decay_lambda = decay_lambda
        self.max_capacity = max_capacity
        self.max_capacity = max_capacity
        self.memory: List[MemoryEvent] = []
        # JSON file extension
        self.storage_path = "memory_engine/memory_store.json"
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        
        # Initialize metrics
        MEMORY_STORE_SIZE.set(0)

    async def write(
        self,
        embedding: Union[List[float], "np.ndarray"],
        metadata: Dict,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Store event with timestamp and importance.

        Args:
            embedding: Vector representation of event
            metadata: Event metadata (severity, type, etc.)
            timestamp: Event timestamp (defaults to now)

        Raises:
            ValueError: If embedding is empty or metadata is not a dict
        """
        if embedding is None or len(embedding) == 0:
            raise ValueError("Embedding cannot be empty")
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")
        if timestamp is None:
            timestamp = datetime.now()

        # Check for similar existing events (recurrence)
        similar = self._find_similar(embedding, threshold=0.85)

        if similar:
            # Boost recurrence count for existing event
            similar.recurrence_count += 1
            similar.metadata["last_seen"] = timestamp
        else:
            # Add new event
            event = MemoryEvent(embedding, metadata, timestamp)
            self.memory.append(event)

        # Update size metric
        MEMORY_STORE_SIZE.set(len(self.memory))

        # Auto-prune if capacity exceeded
        if len(self.memory) > self.max_capacity:
            self.prune(keep_critical=True)

    @with_timeout(seconds=5.0, operation_name="memory_retrieve")
    def retrieve(
        self, query_embedding: Union[List[float], "np.ndarray"], top_k: int = DEFAULT_TOP_K
    ) -> List[Tuple[float, Dict, datetime]]:
        """
        Retrieve similar events with temporal weighting.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return

        Returns:
            List of (weighted_score, metadata, timestamp) tuples

        Raises:
            ValueError: If query_embedding is empty or top_k is invalid
        """
        # Handle numpy arrays - check None or empty explicitly
        if query_embedding is None or (hasattr(query_embedding, 'size') and query_embedding.size == 0):
            raise ValueError("Query embedding cannot be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        with self._lock:
            if not self.memory:
                return []

            scores = []
            for event in self.memory:
                # Calculate similarity
                similarity = self._cosine_similarity(query_embedding, event.embedding)

                # Apply temporal weighting
                temporal_weight = self._temporal_weight(event)

                # Apply recurrence boost
                recurrence_boost = 1 + RECURRENCE_BOOST_FACTOR * (np.log(1 + event.recurrence_count) if np is not None else math.log(1 + event.recurrence_count))

                # Combined weighted score
                weighted_score = (
                    SIMILARITY_WEIGHT * similarity +
                    TEMPORAL_WEIGHT * temporal_weight +
                    RECURRENCE_WEIGHT * recurrence_boost
                )

                scores.append((weighted_score, event.metadata, event.timestamp))

            # Sort by weighted score and return top_k
            scores.sort(reverse=True, key=lambda x: x[0])
            return scores[:top_k]

    @with_timeout(seconds=60.0)
    @monitor_operation_resources()
    def prune(self, max_age_hours: int = DEFAULT_MAX_AGE_HOURS, keep_critical: bool = True) -> int:
        """
        Safe decay mechanism - remove old events.

        Args:
            max_age_hours: Maximum age before pruning
            keep_critical: Keep critical events regardless of age

        Returns:
            Number of events pruned

        Raises:
            ValueError: If max_age_hours is negative
        """
        if max_age_hours < 0:
            raise ValueError("max_age_hours must be non-negative")
        if max_age_hours == 0:
            return 0
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            initial_count = len(self.memory)

            if keep_critical:
                # Keep critical events and recent events
                self.memory = [
                    event
                    for event in self.memory
                    if event.is_critical or event.timestamp > cutoff
                ]
            else:
                # Only keep recent events
                self.memory = [event for event in self.memory if event.timestamp > cutoff]

            pruned_count = initial_count - len(self.memory)
            MEMORY_STORE_SIZE.set(len(self.memory))
            return pruned_count

    @with_timeout(seconds=30.0)
    @monitor_operation_resources()
    def replay(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Replay events from memory within time range.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of event metadata in chronological order

        Raises:
            ValueError: If start_time is after end_time
        """
        if start_time > end_time:
            raise ValueError("start_time must be before or equal to end_time")
        with self._lock:
            # Filter events in time range and sort by timestamp
            filtered_events = [
                event
                for event in self.memory
                if start_time <= event.timestamp <= end_time
            ]

            # Sort chronologically by event timestamp
            filtered_events.sort(key=lambda event: event.timestamp)

            # Extract metadata
            return [event.metadata for event in filtered_events]

    async def save(self) -> None:
        """Persist memory to disk with path validation, JSON format, and async I/O."""
        # Use asyncio.to_thread to avoid blocking the event loop during file I/O
        with MEMORY_STORE_OP_LATENCY.labels(operation="save").time():
            await asyncio.to_thread(self._save_sync)

    def _save_sync(self) -> None:
        """Synchronous save method to be run in thread."""
        with self._lock:
            try:
                # Security: Validate storage path
                resolved_path = os.path.realpath(os.path.abspath(self.storage_path))
                is_safe = (
                    resolved_path.startswith(MEMORY_STORE_BASE_DIR) or
                    resolved_path.startswith("/tmp") or # nosec B108
                    resolved_path.startswith(SYSTEM_TEMP_DIR)
                )

                if not is_safe:
                    logger.error(f"⚠️ Storage path traversal attempt blocked: {self.storage_path}")
                    raise ValueError(f"Storage path must be within allowed directories")

                os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
                
                # Serialize data
                data_to_save = [e.to_dict() for e in self.memory]
                
                # Use inter-process file lock
                lock_path = resolved_path + ".lock"
                with fasteners.InterProcessLock(lock_path):
                    with open(resolved_path, "w") as f:
                        json.dump(data_to_save, f)
                        
                logger.debug(f"Memory store saved to {resolved_path}")
            except Exception as e:
                logger.error(f"Failed to save memory store: {e}", exc_info=True)
                raise

    @with_timeout(seconds=60.0)
    @monitor_operation_resources()
    @with_timeout(seconds=60.0)
    @monitor_operation_resources()
    async def load(self) -> bool:
        """Load memory from disk (async wrapper)."""
        with MEMORY_STORE_OP_LATENCY.labels(operation="load").time():
             return await asyncio.to_thread(self._load_sync)

    def _load_sync(self) -> bool:
        """Synchronous load method to be run in thread."""
        with self._lock:
            try:
                # Security: Validate storage path
                resolved_path = os.path.realpath(os.path.abspath(self.storage_path))
                is_safe = (
                    resolved_path.startswith(MEMORY_STORE_BASE_DIR) or
                    resolved_path.startswith("/tmp") or # nosec B108
                    resolved_path.startswith(SYSTEM_TEMP_DIR)
                )

                if not is_safe:
                    logger.error(f"⚠️ Storage path traversal attempt blocked: {self.storage_path}")
                    raise ValueError(f"Storage path must be within allowed directories")

                if os.path.exists(resolved_path):
                    lock_path = resolved_path + ".lock"
                    with fasteners.InterProcessLock(lock_path):
                        with open(resolved_path, "r") as f:
                            data = json.load(f)
                            self.memory = [MemoryEvent.from_dict(item) for item in data]
                            
                    logger.debug(f"Memory store loaded from {resolved_path}")
                    MEMORY_STORE_SIZE.set(len(self.memory))
                    return True
                return False
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to load memory store: {e}", exc_info=True)
                self.memory = []
                # Try to load legacy pickle if JSON fails? 
                # For now, just reset. Migration could be added if needed.
                return False
            except Exception as e:
                logger.error(f"Unexpected error loading memory store: {e}", exc_info=True)
                self.memory = []
                return False

    def get_stats(self) -> Dict:
        """Get memory statistics."""
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

    # Private helper methods

    def _temporal_weight(self, event: MemoryEvent) -> float:
        """Calculate temporal weight using exponential decay."""
        age_hours = event.age_seconds() / 3600
        return math.exp(-self.decay_lambda * age_hours) if np is None else np.exp(-self.decay_lambda * age_hours)

    def _cosine_similarity(self, a: Union[List[float], "np.ndarray"], b: Union[List[float], "np.ndarray"]) -> float:
        """Calculate cosine similarity between vectors."""
        if len(a) != len(b):
            raise ValueError("Embeddings must have the same length for cosine similarity")
        if np is not None:
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return np.dot(a, b) / (norm_a * norm_b + EPSILON)
        else:
            # Manual calculation for lists
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            dot_product = sum(x * y for x, y in zip(a, b))
            return dot_product / (norm_a * norm_b + EPSILON)

    def _find_similar(
        self, embedding: Union[List[float], "np.ndarray"], threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> Optional[MemoryEvent]:
        """Find similar event in memory."""
        for event in self.memory:
            if self._cosine_similarity(embedding, event.embedding) > threshold:
                return event
        return None
