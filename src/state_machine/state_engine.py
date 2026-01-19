from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import threading

# Import error handling
from core.error_handling import StateTransitionError
from core.component_health import get_health_monitor
from core.metrics import MISSION_PHASE
# Import input validation
from core.input_validation import MissionPhaseValidator, ValidationError, TelemetryData

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """Represents the operational state of the CubeSat system."""

    NORMAL = "NORMAL"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    FAULT_DETECTED = "FAULT_DETECTED"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    SAFE_MODE = "SAFE_MODE"


class MissionPhase(Enum):
    """
    Mission phases for CubeSat operations.

    Each phase has specific operational constraints and fault response policies:
    - LAUNCH: Rocket ascent and orbital insertion. Highly constrained.
    - DEPLOYMENT: Initial system startup and stabilization. Limited actions.
    - NOMINAL_OPS: Standard mission operations. Full capabilities.
    - PAYLOAD_OPS: Specialized payload mission operations. Custom constraints.
    - SAFE_MODE: Minimal power state for survival. Minimal automated actions.
    """

    LAUNCH = "LAUNCH"
    DEPLOYMENT = "DEPLOYMENT"
    NOMINAL_OPS = "NOMINAL_OPS"
    PAYLOAD_OPS = "PAYLOAD_OPS"
    SAFE_MODE = "SAFE_MODE"


class StateMachine:
    """
    Manages system state and mission phase transitions.

    Responsibilities:
    - Track current system state (NORMAL, ANOMALY_DETECTED, FAULT_DETECTED, etc.)
    - Track mission phase (LAUNCH, DEPLOYMENT, NOMINAL_OPS, PAYLOAD_OPS, SAFE_MODE)
    - Provide APIs for querying and updating both state and phase
    - Manage phase transitions based on mission events
    """

    # Valid phase transitions
    PHASE_TRANSITIONS = {
        MissionPhase.LAUNCH: [MissionPhase.DEPLOYMENT, MissionPhase.SAFE_MODE],
        MissionPhase.DEPLOYMENT: [MissionPhase.NOMINAL_OPS, MissionPhase.SAFE_MODE],
        MissionPhase.NOMINAL_OPS: [MissionPhase.PAYLOAD_OPS, MissionPhase.SAFE_MODE],
        MissionPhase.PAYLOAD_OPS: [MissionPhase.NOMINAL_OPS, MissionPhase.SAFE_MODE],
        MissionPhase.SAFE_MODE: [
            MissionPhase.NOMINAL_OPS,
            MissionPhase.DEPLOYMENT,
            MissionPhase.LAUNCH,
        ],
    }

    def __init__(self):
        self.current_state = SystemState.NORMAL
        self.current_phase = MissionPhase.NOMINAL_OPS
        self.phase_start_time = datetime.now()
        self.phase_history = [(MissionPhase.NOMINAL_OPS, datetime.now())]
        self.recovery_start_time = None
        self.recovery_duration = 5  # seconds (simulated)
        self.recovery_steps = 0
        
        # Thread-safe lock for phase transitions
        self._transition_lock = threading.RLock()
        self._is_transitioning = False

        # Register with health monitor (guarantee HEALTHY status)
        try:
            health_monitor = get_health_monitor()
            health_monitor.register_component(
                "state_machine",
                {
                    "initial_state": self.current_state.value,
                    "initial_phase": self.current_phase.value,
                },
            )
            # Ensure it's marked as HEALTHY (idempotent)
            health_monitor.mark_healthy("state_machine")
        except Exception as e:
            logger.warning(
                f"Failed to register state_machine with health monitor: {e}",
                extra={
                    "component": "state_machine",
                    "error_type": type(e).__name__,
                    "current_state": self.current_state.value,
                    "current_phase": self.current_phase.value,
                },
                exc_info=True,
            )

    def get_current_phase(self) -> MissionPhase:
        """Get the current mission phase."""
        return self.current_phase

    def get_current_state(self) -> SystemState:
        """Get the current system state."""
        return self.current_state

    def set_phase(self, phase: MissionPhase) -> Dict[str, Any]:
        """
        Update the mission phase with validation and error handling.

        Args:
            phase: Target MissionPhase

        Returns:
            Dict with previous_phase, new_phase, success, and message

        Raises:
            StateTransitionError: If phase transition fails after retry
        """
        # Acquire lock to prevent concurrent transitions
        with self._transition_lock:
            # Check if another transition is already in progress
            if self._is_transitioning:
                raise StateTransitionError(
                    "Phase transition already in progress. Please wait for the current transition to complete.",
                    component="state_machine",
                    context={
                        "current_phase": self.current_phase.value,
                        "target_phase": str(phase),
                        "status": "transition_in_progress"
                    }
                )
            
            # Mark transition as in progress
            self._is_transitioning = True
            
        health_monitor = get_health_monitor()
        previous_phase = self.current_phase  # Capture before any validation


        try:
            try:
                # Validate phase string and type
                if isinstance(phase, MissionPhase):
                    target_phase_str = phase.value
                elif isinstance(phase, str):
                    target_phase_str = phase
                else:
                     raise ValidationError(f"Invalid phase type: {type(phase)}")

                # Use central validator for phase name
                target_phase_str = MissionPhaseValidator.validate_phase(target_phase_str)
                
                # Convert back to Enum if needed for internal consistency
                try:
                    target_phase_enum = MissionPhase(target_phase_str)
                except ValueError:
                     raise ValidationError(f"Phase {target_phase_str} not found in MissionPhase enum")

                if self.current_phase == target_phase_enum:
                    health_monitor.mark_healthy("state_machine")
                    return {
                        "success": True,
                        "previous_phase": self.current_phase.value,
                        "new_phase": target_phase_enum.value,
                        "message": "Already in target phase",
                    }

                # Use central validator for transition
                MissionPhaseValidator.validate_transition(self.current_phase.value, target_phase_str)
            except ValidationError as e:
                # Map ValidationError to StateTransitionError for API compatibility
                raise StateTransitionError(
                    str(e),
                    component="state_machine",
                    context={
                        "current_phase": self.current_phase.value,
                        "target_phase": str(phase)
                    }
                ) from e
            
            # If we get here, transition is valid
            phase = target_phase_enum

            # Perform atomic state update within lock
            with self._transition_lock:
                self.current_phase = phase
                self.phase_start_time = datetime.now()
                self.phase_history.append((phase, datetime.now()))

            # Update Prometheus metrics
            try:
                # Reset all phases to 0 then set current to 1
                for p in MissionPhase:
                    MISSION_PHASE.labels(phase=p.value).set(0)
                MISSION_PHASE.labels(phase=phase.value).set(1)
            except Exception:
                pass  # Don't fail transition if metrics fail

            logger.info(
                f"Mission phase transitioned: {previous_phase.value} → {phase.value}"
            )
            health_monitor.mark_healthy(
                "state_machine",
                {
                    "current_phase": phase.value,
                    "previous_phase": previous_phase.value,
                },
            )

            return {
                "success": True,
                "previous_phase": previous_phase.value,
                "new_phase": phase.value,
                "message": f"Transitioned from {previous_phase.value} to {phase.value}",
            }
        except StateTransitionError as e:
            # Extract phase value safely
            phase_value = phase.value if isinstance(phase, MissionPhase) else str(phase)
            logger.error(
                f"State transition error: {e.message}",
                extra={
                    "component": "state_machine",
                    "error_type": "transition_invalid",
                    "previous_phase": previous_phase.value,
                    "requested_phase": phase_value,
                    "current_state": self.current_state.value,
                },
                exc_info=False,
            )
            health_monitor.mark_degraded(
                "state_machine",
                error_msg=e.message,
                metadata={"error_type": "transition_invalid"},
            )
            raise
        except Exception as e:
            # Extract phase value safely
            phase_value = phase.value if isinstance(phase, MissionPhase) else str(phase)
            logger.error(
                f"Unexpected error in set_phase: {e}",
                extra={
                    "component": "state_machine",
                    "error_type": type(e).__name__,
                    "previous_phase": previous_phase.value,
                    "requested_phase": phase_value,
                    "current_state": self.current_state.value,
                },
                exc_info=True,
            )
            health_monitor.mark_degraded(
                "state_machine", error_msg=str(e), metadata={"error_type": "unexpected"}
            )
            raise
        finally:
            # Always reset transition flag when exiting
            with self._transition_lock:
                self._is_transitioning = False

    def process_fault(
        self, fault_type: str, telemetry: Dict[str, Any]
    ) -> Dict[str, str]:
        """Process a detected fault and transition state."""
        # Validate telemetry data
        try:
            TelemetryData.validate(telemetry)
        except ValidationError as e:
            logger.warning(f"Telemetry validation failed in process_fault: {e}")
            # Continue processing but log the issue

        previous_state = self.current_state.value

        if fault_type == "normal":
            # If we were in anomaly/fault state but now normal, we might recover
            if self.current_state in [
                SystemState.ANOMALY_DETECTED,
                SystemState.FAULT_DETECTED,
            ]:
                # Auto-recover if transient
                self.current_state = SystemState.NORMAL
        else:
            # Escalation logic
            if self.current_state == SystemState.NORMAL:
                self.current_state = SystemState.ANOMALY_DETECTED
            elif self.current_state == SystemState.ANOMALY_DETECTED:
                self.current_state = SystemState.FAULT_DETECTED
            elif self.current_state == SystemState.FAULT_DETECTED:
                self.current_state = SystemState.RECOVERY_IN_PROGRESS
                self.recovery_steps = 0

        return {
            "previous_state": previous_state,
            "new_state": self.current_state.value,
            "action": "transition",
        }

    def check_recovery_complete(self) -> bool:
        """Check if recovery process is complete."""
        if self.current_state == SystemState.RECOVERY_IN_PROGRESS:
            self.recovery_steps += 1
            if self.recovery_steps >= self.recovery_duration:
                return True
        return False

    def resume_normal_operation(self) -> Dict[str, str]:
        """Force transition back to normal."""
        previous_state = self.current_state.value
        self.current_state = SystemState.NORMAL
        return {
            "previous_state": previous_state,
            "new_state": self.current_state.value,
            "action": "resume",
        }

    def get_phase_history(self) -> list:
        """Get the history of mission phase transitions."""
        return [(phase.value, timestamp) for phase, timestamp in self.phase_history]

    def force_safe_mode(self) -> Dict[str, Any]:
        """
        Forcibly transition to SAFE_MODE (emergency procedure).
        Always allowed regardless of current phase.
        """
        # Use lock to ensure atomic transition even for forced safe mode
        with self._transition_lock:
            # Force safe mode can interrupt ongoing transitions
            previous_phase = self.current_phase
            self.current_phase = MissionPhase.SAFE_MODE
            self.phase_start_time = datetime.now()
            self.phase_history.append((MissionPhase.SAFE_MODE, datetime.now()))
            # Reset transition flag if it was set
            self._is_transitioning = False

        # Update Prometheus metrics
        try:
            for p in MissionPhase:
                MISSION_PHASE.labels(phase=p.value).set(0)
            MISSION_PHASE.labels(phase=MissionPhase.SAFE_MODE.value).set(1)
        except Exception:
            pass

        logger.warning(f"Forced transition to SAFE_MODE from {previous_phase.value}")

        return {
            "success": True,
            "previous_phase": previous_phase.value,
            "new_phase": MissionPhase.SAFE_MODE.value,
            "message": "Emergency transition to SAFE_MODE executed",
            "forced": True,
        }

    def get_phase_description(self, phase: Optional[MissionPhase] = None) -> str:
        """Get human-readable description of a mission phase."""
        if phase is None:
            phase = self.current_phase

        descriptions = {
            MissionPhase.LAUNCH: "Rocket ascent and orbital insertion. Highly constrained, minimal automated actions.",
            MissionPhase.DEPLOYMENT: "Initial system startup and stabilization. Limited automated responses.",
            MissionPhase.NOMINAL_OPS: "Standard mission operations. Full automated response capabilities.",
            MissionPhase.PAYLOAD_OPS: "Specialized payload mission operations. Balanced constraints.",
            MissionPhase.SAFE_MODE: "Minimal power state for survival. Minimal automated actions.",
        }

        return descriptions.get(phase, "Unknown phase")

    def is_phase_transition_valid(self, target_phase: MissionPhase) -> bool:
        """Check if a phase transition is valid without performing it."""
        return target_phase in self.PHASE_TRANSITIONS.get(self.current_phase, [])
