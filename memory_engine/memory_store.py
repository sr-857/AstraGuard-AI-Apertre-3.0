"""
Adaptive Memory Store with Temporal Weighting

Self-updating memory that prioritizes recent and recurring events.
"""

try:
    import numpy as np
except ImportError:
    np = None

import math
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Union, Any, TYPE_CHECKING
import pickle
import os
import logging
import fasteners

if TYPE_CHECKING:
    import numpy as np

# Import timeout and resource monitoring decorators
from core.timeout_handler import with_timeout
from core.resource_monitor import monitor_operation_resources


logger = logging.getLogger(__name__)

# Security: Base directory for memory store persistence
# All storage paths must be contained within this directory to prevent traversal attacks
MEMORY_STORE_BASE_DIR = os.path.abspath("memory_engine")

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


class MemoryEvent:
    """Represents a stored memory event."""

    def __init__(self, embedding: Union[List[float], "np.ndarray"], metadata: Dict, timestamp: datetime):
        self.embedding = embedding
        self.metadata = metadata
        self.timestamp = timestamp
        self.base_importance = metadata.get("severity", 0.5)
        self.recurrence_count = 1
        self.is_critical = metadata.get("critical", False)

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
        self.memory: List[MemoryEvent] = []
        self.storage_path = "memory_engine/memory_store.pkl"
        self._lock = threading.RLock()  # Reentrant lock for thread safety

    def write(
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
        if not embedding:
            raise ValueError("Embedding cannot be empty")
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")
        if timestamp is None:
            timestamp = datetime.now()

        with self._lock:
            # Check for similar existing events (recurrence)
            similar = self._find_similar(embedding, threshold=DEFAULT_SIMILARITY_THRESHOLD)

            if similar:
                # Boost recurrence count for existing event
                similar.recurrence_count += 1
                similar.metadata["last_seen"] = timestamp
            else:
                # Add new event
                event = MemoryEvent(embedding, metadata, timestamp)
                self.memory.append(event)

            # Auto-prune if capacity exceeded
            if len(self.memory) > self.max_capacity:
                self.prune(keep_critical=True)

    @with_timeout(seconds=30.0)
    @monitor_operation_resources()
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
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
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
            weighted_score = similarity * (
                SIMILARITY_WEIGHT + TEMPORAL_WEIGHT * temporal_weight + RECURRENCE_WEIGHT * recurrence_boost
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

    @with_timeout(seconds=60.0)
    @monitor_operation_resources()
    def save(self) -> None:
        """Persist memory to disk with path validation."""
        with self._lock:
            try:
                # Security: Validate storage path is within base directory (prevents path traversal)
                resolved_path = os.path.abspath(self.storage_path)
                if not resolved_path.startswith(MEMORY_STORE_BASE_DIR):
                    logger.error(
                        f"⚠️  Storage path traversal attempt blocked: {self.storage_path}"
                    )
                    raise ValueError(
                        f"Storage path must be within {MEMORY_STORE_BASE_DIR}"
                    )

                os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
                with open(resolved_path, "wb") as f:
                    pickle.dump(self.memory, f)
                logger.debug(f"Memory store saved to {resolved_path}")
            except Exception as e:
                logger.error(f"Failed to save memory store: {e}", exc_info=True)
                raise

    @with_timeout(seconds=60.0)
    @monitor_operation_resources()
    def load(self) -> bool:
        """Load memory from disk with validation, error handling, and file locking."""
        with self._lock:
            try:
                # Security: Validate storage path is within base directory (prevents path traversal)
                resolved_path = os.path.abspath(self.storage_path)
                if not resolved_path.startswith(MEMORY_STORE_BASE_DIR):
                    logger.error(
                        f"⚠️  Storage path traversal attempt blocked: {self.storage_path}"
                    )
                    raise ValueError(
                        f"Storage path must be within {MEMORY_STORE_BASE_DIR}"
                    )

                if os.path.exists(resolved_path):
                    # Use inter-process file lock to prevent concurrent access corruption
                    lock_path = resolved_path + ".lock"
                    with fasteners.InterProcessLock(lock_path):
                        with open(resolved_path, "rb") as f:
                            self.memory = pickle.load(f)  # nosec B301 - trusted internal persistence format
                    logger.debug(f"Memory store loaded from {resolved_path}")
                    return True
                return False
            except (pickle.UnpicklingError, EOFError, ValueError) as e:
                logger.error(f"Failed to load memory store: {e}", exc_info=True)
                return False
            except Exception as e:
                logger.error(f"Unexpected error loading memory store: {e}", exc_info=True)
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
            "avg_age_hours": np.mean(ages) if np is not None else sum(ages) / len(ages) if ages else 0,
            "max_recurrence": max(e.recurrence_count for e in self.memory),
        }

    # Private helper methods

    def _temporal_weight(self, event: MemoryEvent) -> float:
        """Calculate temporal weight using exponential decay."""
        age_hours = event.age_seconds() / 3600
        return math.exp(-self.decay_lambda * age_hours) if np is None else np.exp(-self.decay_lambda * age_hours)

    def _cosine_similarity(self, a: Union[List[float], "np.ndarray"], b: Union[List[float], "np.ndarray"]) -> float:
        """Calculate cosine similarity between vectors."""
        if np is not None:
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)
        else:
            # Manual calculation for lists
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot_product / (norm_a * norm_b + 1e-10)

    def _find_similar(
        self, embedding: Union[List[float], "np.ndarray"], threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> Optional[MemoryEvent]:
        """Find similar event in memory."""
        for event in self.memory:
            if self._cosine_similarity(embedding, event.embedding) > threshold:
                return event
        return None
