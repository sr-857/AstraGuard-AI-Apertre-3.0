"""Operator feedback → high-priority memory pinning + resonance updates."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from models.feedback import FeedbackEvent, FeedbackLabel
from .error_handling import (
    handle_file_operation_error,
    handle_memory_operation_error,
    handle_policy_update_error,
    handle_feedback_validation_error,
    FeedbackValidationError
)

logger = logging.getLogger(__name__)


class FeedbackPinner:
    """Pins operator-validated events with label-aware weight boosting."""

    WEIGHT_MAP = {
        FeedbackLabel.CORRECT: 10.0,  # Max priority, never decay
        FeedbackLabel.INSUFFICIENT: 5.0,  # Medium + needs review
        FeedbackLabel.WRONG: 0.1,  # Suppress pattern matches
    }

    def __init__(
        self, memory: Optional[Any] = None, processed_path: Optional[Path] = None
    ):
        """
        Initialize feedback pinner.

        Args:
            memory: AdaptiveMemoryStore instance (optional for testing)
            processed_path: Path to feedback_processed.json (defaults to cwd)
        """
        self.memory = memory
        self.processed_path = processed_path or Path("feedback_processed.json")

    def pin_all_feedback(self) -> Dict[str, int]:
        """Process ALL pending feedback → pinned memory."""
        if not self.processed_path.exists():
            return {"pinned": 0, "correct": 0, "insufficient": 0, "wrong": 0}

        try:
            raw_events = json.loads(self.processed_path.read_text())
            if not isinstance(raw_events, list):
                raise FeedbackValidationError(
                    "format", "feedback data",
                    issues=[f"Expected list of feedback events, received {type(raw_events).__name__}"]
                )
        except json.JSONDecodeError as e:
            raise handle_feedback_validation_error(
                "JSON", f"Corrupted feedback file: {self.processed_path}",
                issues=[str(e)],
                context={"file_path": str(self.processed_path), "error_position": getattr(e, 'pos', 'unknown')}
            )
        except FeedbackValidationError:
            # Let FeedbackValidationError propagate without wrapping
            raise

        # Parse and validate all events
        try:
            events = [FeedbackEvent.model_validate(e) for e in raw_events]
        except Exception as e:
            raise handle_feedback_validation_error(
                "schema", "feedback event data", [str(e)],
                context={"validation_error": str(e), "total_events": len(raw_events)}
            )

        stats = {"pinned": 0, "correct": 0, "insufficient": 0, "wrong": 0}

        for event in events:
            try:
                weight = self.WEIGHT_MAP[event.label]

                # Pin as non-decaying, high-resonance event
                if self.memory is not None:
                    self.memory.pin_event(
                        event_id=event.fault_id,
                        content=event.model_dump(),
                        weight=weight,
                        mission_phase=event.mission_phase,
                        category=f"feedback_{event.anomaly_type}_{event.recovery_action}",
                    )

                    # Update resonance scoring for pattern matches
                    self._update_resonance(event, weight)

                stats["pinned"] += 1
                stats[event.label.value] += 1
            except Exception as e:
                raise handle_memory_operation_error(
                    e, f"Failed to pin feedback event: {event.fault_id}",
                    context={"event_id": event.fault_id, "label": event.label.value, "operation": "pin_event"}
                )

        # Atomic cleanup
        try:
            self.processed_path.unlink(missing_ok=True)
            Path("feedback_pending.json").unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup feedback files: {e}")

        # Trigger policy updates from pinned feedback (#54)
        try:
            from security_engine.policy_engine import process_policy_updates
            process_policy_updates(self.memory)
        except (ImportError, ModuleNotFoundError, AttributeError) as e:
            # Non-blocking: policy update errors don't block feedback pinning
            logger.debug(f"Policy update failed (non-blocking): {type(e).__name__}: {e}")
        except Exception as e:
            raise handle_policy_update_error(
                e, "Failed to process policy updates from feedback",
                context={"operation": "process_policy_updates", "memory_available": self.memory is not None}
            )

        return stats

    def _update_resonance(self, event: FeedbackEvent, weight: float) -> None:
        """Boost/suppress similar future patterns."""
        if self.memory is None:
            return

        try:
            pattern = f"{event.anomaly_type}:{event.recovery_action}"
            resonance_boost = weight * event.confidence_score

            if weight < 1.0:  # WRONG/INSUFFICIENT → suppress
                if hasattr(self.memory, "suppress_pattern"):
                    self.memory.suppress_pattern(pattern, mission_phase=event.mission_phase)
            else:  # CORRECT → prefer
                if hasattr(self.memory, "boost_pattern"):
                    self.memory.boost_pattern(pattern, resonance_boost, event.mission_phase)
        except Exception as e:
            raise handle_memory_operation_error(
                e, f"Failed to update resonance for pattern: {event.anomaly_type}:{event.recovery_action}",
                context={
                    "event_id": event.fault_id,
                    "pattern": f"{event.anomaly_type}:{event.recovery_action}",
                    "weight": weight,
                    "operation": "update_resonance"
                }
            )


# Global integration hook (called post-CLI #52)
def process_feedback_after_review(memory: Any) -> Dict[str, int]:
    """Public API for #52 CLI integration."""
    pinner = FeedbackPinner(memory)
    return pinner.pin_all_feedback()
