"""
Adaptive Memory Store with Temporal Weighting

Self-updating memory that prioritizes recent and recurring events.
"""

import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pickle
import os
import logging

from core.timeout_handler import with_timeout

logger = logging.getLogger(__name__)

# Security: Base directory for memory store persistence
# All storage paths must be contained within this directory to prevent traversal attacks
MEMORY_STORE_BASE_DIR = os.path.abspath("memory_engine")


class MemoryEvent:
    """Represents a stored memory event."""

    def __init__(self, embedding: np.ndarray, metadata: Dict, timestamp: datetime):
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

    def __init__(self, decay_lambda: float = 0.1, max_capacity: int = 10000):
        """
        Initialize adaptive memory store.

        Args:
            decay_lambda: Decay rate for temporal weighting (default: 0.1)
            max_capacity: Maximum number of events to store
        """
        self.decay_lambda = decay_lambda
        self.max_capacity = max_capacity
        self.memory: List[MemoryEvent] = []
        self.storage_path = "memory_engine/memory_store.pkl"

    @with_timeout(seconds=3.0, operation_name="memory_write")
    def write(
        self,
        embedding: np.ndarray,
        metadata: Dict,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Store event with timestamp and importance.

        Args:
            embedding: Vector representation of event
            metadata: Event metadata (severity, type, etc.)
            timestamp: Event timestamp (defaults to now)
        """
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

        # Auto-prune if capacity exceeded
        if len(self.memory) > self.max_capacity:
            self.prune(keep_critical=True)

    @with_timeout(seconds=5.0, operation_name="memory_retrieve")
    def retrieve(
        self, query_embedding: np.ndarray, top_k: int = 5
    ) -> List[Tuple[float, Dict, datetime]]:
        """
        Retrieve similar events with temporal weighting.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return

        Returns:
            List of (weighted_score, metadata, timestamp) tuples
        """
        if not self.memory:
            return []

        scores = []
        for event in self.memory:
            # Calculate similarity
            similarity = self._cosine_similarity(query_embedding, event.embedding)

            # Apply temporal weighting
            temporal_weight = self._temporal_weight(event)

            # Apply recurrence boost
            recurrence_boost = 1 + 0.3 * np.log(1 + event.recurrence_count)

            # Combined weighted score
            weighted_score = similarity * (
                0.5 + 0.3 * temporal_weight + 0.2 * recurrence_boost
            )

            scores.append((weighted_score, event.metadata, event.timestamp))

        # Sort by weighted score and return top_k
        scores.sort(reverse=True, key=lambda x: x[0])
        return scores[:top_k]

    def prune(self, max_age_hours: int = 24, keep_critical: bool = True) -> int:
        """
        Safe decay mechanism - remove old events.

        Args:
            max_age_hours: Maximum age before pruning
            keep_critical: Keep critical events regardless of age

        Returns:
            Number of events pruned
        """
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

    def replay(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Replay events from memory within time range.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of event metadata in chronological order
        """
        events = [
            event.metadata
            for event in self.memory
            if start_time <= event.timestamp <= end_time
        ]

        # Sort chronologically
        events.sort(key=lambda x: x.get("timestamp", 0))
        return events

    def save(self) -> None:
        """Persist memory to disk with path validation."""
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

    def load(self) -> bool:
        """Load memory from disk with validation and error handling."""
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
            "avg_age_hours": np.mean(ages),
            "max_recurrence": max(e.recurrence_count for e in self.memory),
        }

    # Private helper methods

    def _temporal_weight(self, event: MemoryEvent) -> float:
        """Calculate temporal weight using exponential decay."""
        age_hours = event.age_seconds() / 3600
        return np.exp(-self.decay_lambda * age_hours)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between vectors."""
        # Handle dimension mismatch gracefully
        if a.shape != b.shape:
            # Log warning only once per mismatch pattern to avoid spam
            # logger.warning(f"Embedding dimension mismatch: {a.shape} vs {b.shape}")
            return 0.0
            
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)

    def _find_similar(
        self, embedding: np.ndarray, threshold: float = 0.85
    ) -> Optional[MemoryEvent]:
        """Find similar event in memory."""
        for event in self.memory:
            if self._cosine_similarity(embedding, event.embedding) > threshold:
                return event
        return None
