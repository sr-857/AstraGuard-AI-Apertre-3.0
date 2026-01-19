"""Dynamic policy updates from operator feedback success rates."""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from models.feedback import FeedbackEvent, FeedbackLabel
from core.input_validation import PolicyDecision, ValidationError
from core.timeout_handler import with_timeout
from .error_handling import (
    handle_memory_operation_error,
    handle_policy_update_error,
    MemoryOperationError
)


class FeedbackPolicyUpdater:
    """Aggregates pinned feedback → tunes thresholds/playbooks."""

    SUCCESS_RATE_HIGH = 0.7
    SUCCESS_RATE_LOW = 0.3
    THRESHOLD_ADJUSTMENT = 0.2

    def __init__(self, memory: Optional[object] = None) -> None:
        """Initialize with adaptive memory backend."""
        self.memory = memory

    @with_timeout(seconds=30.0, operation_name="policy_update_from_feedback")
    def update_from_feedback(self) -> Dict[str, int]:
        """Main entrypoint: Query pinned feedback → update policies."""
        if not self.memory:
            return {"updated": 0, "boosted": 0, "suppressed": 0}

        patterns = self._get_feedback_patterns()
        stats: Dict[str, int] = {"updated": 0, "boosted": 0, "suppressed": 0}

        for pattern, events in patterns.items():
            success_rate = self._compute_success_rate(events)

            anomaly_type, action = pattern
            phase = self._get_dominant_phase(events)

            self._update_policy(anomaly_type, action, success_rate, phase, stats)

        return stats

    def _get_feedback_patterns(
        self,
    ) -> Dict[Tuple[str, str], List[FeedbackEvent]]:
        """Query pinned memory for feedback patterns."""
        patterns: Dict[Tuple[str, str], List[FeedbackEvent]] = defaultdict(list)

        # Query all pinned feedback events from memory
        pinned_events: List[FeedbackEvent] = []
        if self.memory is not None and hasattr(self.memory, "query_feedback_events"):
            try:
                result = self.memory.query_feedback_events()
                # Handle Mock objects or non-iterable returns
                if isinstance(result, (list, tuple)):
                    pinned_events = result
                else:
                    pinned_events = []
            except Exception as e:
                raise handle_memory_operation_error(
                    e, "Failed to query feedback events from memory",
                    context={"operation": "query_feedback_events", "memory_available": True}
                )
        else:
            raise MemoryOperationError(
                "Memory backend not available or missing query_feedback_events method",
                memory_type="adaptive_memory",
                missing_method="query_feedback_events",
                context={"memory_available": self.memory is not None, "has_method": hasattr(self.memory, "query_feedback_events") if self.memory else False}
            )

        for event in pinned_events:
            pattern = (event.anomaly_type, event.recovery_action)
            patterns[pattern].append(event)

        return patterns

    def _compute_success_rate(self, events: List[FeedbackEvent]) -> float:
        """Empirical success: correct / total."""
        if not events:
            return 0.0

        correct = sum(1 for e in events if e.label == FeedbackLabel.CORRECT)
        return correct / len(events)

    def _get_dominant_phase(self, events: List[FeedbackEvent]) -> str:
        """Most common mission phase for pattern."""
        phase_counts: Dict[str, int] = defaultdict(int)
        for e in events:
            phase_counts[e.mission_phase] += 1
        if not phase_counts:
            return "NOMINAL_OPS"
        max_phase: str = max(phase_counts, key=lambda x: phase_counts[x])
        return max_phase

    def _update_policy(
        self,
        anomaly_type: str,
        action: str,
        rate: float,
        phase: str,
        stats: Dict[str, int],
    ) -> None:
        """Apply success rate → threshold + preference updates."""
        if not self.memory:
            return

        try:
            # Threshold tuning (anomaly_detector integration)
            if rate > self.SUCCESS_RATE_HIGH:
                # Less sensitive for proven patterns
                self._adjust_threshold(anomaly_type, phase, self.THRESHOLD_ADJUSTMENT)
                stats["boosted"] += 1

            elif rate < self.SUCCESS_RATE_LOW:
                # More sensitive for failure-prone
                self._adjust_threshold(anomaly_type, phase, -self.THRESHOLD_ADJUSTMENT)
                if hasattr(self.memory, "suppress_action") and self.memory is not None:
                    self.memory.suppress_action(action, phase)
                stats["suppressed"] += 1

            # Playbook preference (always update)
            preference_weight = min(rate, 1.0)  # 0-1 normalized
            if hasattr(self.memory, "set_action_preference") and self.memory is not None:
                self.memory.set_action_preference(action, preference_weight, phase)

            stats["updated"] += 1
        except Exception as e:
            raise handle_policy_update_error(
                e, f"Failed to update policy for anomaly type '{anomaly_type}' and action '{action}'",
                context={
                    "anomaly_type": anomaly_type,
                    "action": action,
                    "success_rate": rate,
                    "phase": phase,
                    "operation": "update_policy"
                }
            )

    def _adjust_threshold(self, anomaly_type: str, phase: str, delta: float) -> None:
        """Safe bounded threshold adjustment."""
        if not self.memory or not hasattr(self.memory, "get_threshold"):
            return

        try:
            current: float = self.memory.get_threshold(anomaly_type, phase)
            new_threshold = max(0.1, min(2.0, current * (1 + delta)))  # Safe 0.1-2.0
            if hasattr(self.memory, "set_threshold"):
                self.memory.set_threshold(anomaly_type, phase, new_threshold)
        except Exception as e:
            raise handle_memory_operation_error(
                e, f"Failed to adjust threshold for anomaly type '{anomaly_type}' in phase '{phase}'",
                context={
                    "anomaly_type": anomaly_type,
                    "phase": phase,
                    "delta": delta,
                    "operation": "adjust_threshold"
                }
            )


@with_timeout(seconds=35.0, operation_name="policy_processing")
def process_policy_updates(memory: Optional[object]) -> Dict[str, int]:
    """Public API - call after #53 pinning."""
    updater = FeedbackPolicyUpdater(memory)
    return updater.update_from_feedback()
