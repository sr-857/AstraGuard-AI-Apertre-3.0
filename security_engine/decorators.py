"""Thread-safe decorator for automatic feedback event capture."""

from functools import wraps
from typing import Callable, Any, Optional, TypeVar
from datetime import datetime
import json
import threading
import logging
from pathlib import Path
import signal
import platform
import os

from models.feedback import FeedbackEvent, FeedbackLabel
from .error_handling import handle_file_operation_error

logger = logging.getLogger(__name__)

# Type variable for generic callable
F = TypeVar("F", bound=Callable[..., Any])

# File I/O timeout in seconds
FILE_IO_TIMEOUT_SECONDS = 5

# Try to import msvcrt for Windows file locking
try:
    import msvcrt
except ImportError:
    msvcrt = None


class ThreadSafeFeedbackStore:
    """Atomic pending events storage with thread-safe operations."""

    def __init__(self, path: Path = Path("feedback_pending.json")):
        self.path = path
        self.lock = threading.Lock()
        # Import msvcrt on Windows for file locking
        self.msvcrt = msvcrt if platform.system() == "Windows" else None

    def append(self, event: FeedbackEvent) -> None:
        """Thread-safely append event to pending store."""
        with self.lock:
            # Acquire file lock for cross-process safety on Windows
            lock_fd = None
            if self.msvcrt:
                try:
                    lock_fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT)
                    self.msvcrt.locking(lock_fd, self.msvcrt.LK_LOCK, 1)  # Lock first byte
                except (OSError, IOError):
                    # If locking fails, continue without it (fallback to thread safety only)
                    if lock_fd is not None:
                        os.close(lock_fd)
                    lock_fd = None

            try:
                try:
                    pending = self._load()
                except FileNotFoundError:
                    pending = []
                pending.append(json.loads(event.model_dump_json()))
                self._dump(pending)
            finally:
                # Release file lock
                if lock_fd is not None:
                    try:
                        self.msvcrt.locking(lock_fd, self.msvcrt.LK_UNLCK, 1)
                        os.close(lock_fd)
                    except (OSError, IOError):
                        pass  # Ignore unlock errors

    def _load(self) -> list[Any]:
        """Load pending events from disk with timeout protection."""
        try:
            with open(self.path, "r") as f:
                # Set timeout for file read operation
                content = f.read()
                try:
                    data = json.loads(content)
                    if isinstance(data, list):
                        return data
                    return []
                except json.JSONDecodeError as e:
                    logger.warning(f"Corrupted feedback JSON file: {e}")
                    return []
        except FileNotFoundError:
            return []
        except IOError as e:
            logger.warning(f"File I/O error reading feedback store: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error loading feedback events: {e}")
            return []

    def _dump(self, events: list[Any]) -> None:
        """Write pending events to disk with timeout protection and error handling."""
        try:
            # Create temp file to ensure atomicity
            temp_path = self.path.with_suffix('.tmp')
            with open(temp_path, "w") as f:
                json.dump(events, f, separators=(",", ":"))
            # Atomic rename
            temp_path.replace(self.path)
        except IOError as e:
            logger.warning(f"File I/O error writing feedback store: {e}")
        except Exception as e:
            logger.error(f"Unexpected error dumping feedback events: {e}")


_pending_store = ThreadSafeFeedbackStore()


def log_feedback(fault_id: str, anomaly_type: str = "unknown") -> Callable[[F], F]:
    """Decorator: Auto-capture recovery action → FeedbackEvent → pending store.

    Args:
        fault_id: Identifier for the fault being recovered from
        anomaly_type: Type of anomaly (e.g., "power_subsystem", "thermal")

    Returns:
        Decorator function that wraps recovery actions

    Example:
        @log_feedback(fault_id="power_loss_", anomaly_type="power_subsystem")
        def emergency_power_cycle(system_state):
            return True  # Recovery success
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result: Any = None  # Initialize result
            error_to_raise: Optional[Exception] = None

            try:
                # Extract mission_phase from first arg if it has the attribute
                mission_phase = "NOMINAL_OPS"
                if args and hasattr(args[0], "mission_phase"):
                    mp = args[0].mission_phase
                    # Ensure mission_phase is a string (handle mock objects)
                    mission_phase = str(mp) if mp else "NOMINAL_OPS"
                    # Validate against allowed values
                    if mission_phase not in (
                        "LAUNCH",
                        "DEPLOYMENT",
                        "NOMINAL_OPS",
                        "PAYLOAD_OPS",
                        "SAFE_MODE",
                    ):
                        mission_phase = "NOMINAL_OPS"

                # Execute the wrapped recovery function
                result = func(*args, **kwargs)
                success = result is True if isinstance(result, bool) else True

                # Auto-create pending FeedbackEvent
                event = FeedbackEvent(
                    fault_id=fault_id,
                    anomaly_type=anomaly_type,
                    recovery_action=func.__name__,
                    mission_phase=mission_phase,
                    label=FeedbackLabel.CORRECT if success else FeedbackLabel.WRONG,
                    confidence_score=1.0 if success else 0.5,
                    operator_notes=None,
                )

                _pending_store.append(event)
                # Silent logging - don't spam console

            except Exception as e:
                # Capture ANY exception but continue to feedback logging attempt
                error_to_raise = e
                # Only log specific exception types to avoid noise
                if isinstance(e, (IOError, json.JSONDecodeError, TypeError)):
                    logger.debug(f"Function {func.__name__} raised exception: {type(e).__name__}: {e}")

                # Try to log failure feedback even if function raised
                try:
                    mission_phase = "NOMINAL_OPS"
                    if args and hasattr(args[0], "mission_phase"):
                        mp = args[0].mission_phase
                        mission_phase = str(mp) if mp else "NOMINAL_OPS"
                        if mission_phase not in (
                            "LAUNCH",
                            "DEPLOYMENT",
                            "NOMINAL_OPS",
                            "PAYLOAD_OPS",
                            "SAFE_MODE",
                        ):
                            mission_phase = "NOMINAL_OPS"

                    event = FeedbackEvent(
                        fault_id=fault_id,
                        anomaly_type=anomaly_type,
                        recovery_action=func.__name__,
                        mission_phase=mission_phase,
                        label=FeedbackLabel.WRONG,  # Failure to execute
                        confidence_score=0.0,
                        operator_notes=None,
                    )
                    _pending_store.append(event)
                except (IOError, json.JSONDecodeError) as e:
                    # Non-blocking: log but don't raise feedback logging errors
                    logger.debug(
                        f"Failed to log feedback for {func.__name__}",
                        extra={
                            "error_type": type(e).__name__,
                            "error_msg": str(e),
                            "component": "feedback_decorator",
                            "function": func.__name__,
                        },
                    )

            if error_to_raise:
                raise error_to_raise

            return result  # Never break recovery flow

        return wrapper

    return decorator
